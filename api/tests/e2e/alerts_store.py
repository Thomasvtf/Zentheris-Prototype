"""Alertas, consejos y SAVEPOINT en el almacén en memoria de los e2e (fase 8).

La recuperación de horas (`services.hour_recovery._fill`) evalúa las alertas de las horas en vivo
dentro de `session.begin_nested()` (`services.live_alerts.evaluate_live_hours`; DC-35:
alertas solo sobre horas en vivo; se evalúan en un SAVEPOINT para que un fallo no impida guardar
las lecturas). Este módulo le enseña eso al almacén de
`test_onboarding_e2e` (`Store`), a través de `LiveAlertsMixin`, que usan `RecoveryStore` y sus
descendientes (consumo, historial y alertas):

- **SAVEPOINT** (`Savepoint`, devuelto por `RecoverySession.begin_nested()`): guarda lo pendiente
  de la transacción y, si el bloque lanza, lo restaura (ROLLBACK TO SAVEPOINT: también limpia el
  estado abortado, 25P02) y vuelve a lanzar. Las sentencias de dentro NO van a `events`: van a
  `live_evaluations` (una entrada por SAVEPOINT con su resultado); en `events` queda una sola
  marca, `SAVEPOINT_RELEASED` o `SAVEPOINT_REVERTED`. Así las secuencias de las fases 5–7 siguen
  siendo legibles.
- **Sentencias nuevas** de `app.data` (se imita su resultado, no las ramas del SQL):
  `HOUSEHOLD_ZONES_SQL` y `HOURLY_READINGS_SQL` (antes en el almacén del consumo; ahora también
  las usa la evaluación), `HOUSEHOLD_CREATED_AT_SQL`, `ALERT_MEMBERS_SQL`, `ALERT_PERMISSION_SQL`,
  `GOAL_ACTIVE_ON_SQL`, las 7 de `data/alerts.py` y las 6 de `data/tips.py`. Restricciones de
  `supabase/migrations/…0002`: checks de categoría, severidad, prioridad y estado, único de
  `alertas.clave_evento` (ON CONFLICT DO NOTHING), claves primarias de `alertas_usuario` y
  `consejos_usuario_unico`, `consejos_categoria_coherente`, `consejos_usuario_estado_coherente`
  y las claves foráneas a `hogares`, `zonas` y `usuarios`.
- **Vigilancia que reemplaza a la de DC-35** en la recuperación: las sentencias que solo usa la
  evaluación (`EVALUATION_ONLY`) fuera de un SAVEPOINT son un uso no previsto (anotado en
  `unexpected`), y `assert_live_alert_rules()` comprueba al final de cada prueba A-01 (una alerta
  por regla, zona y día) y A-02 (toda alerta y todo consejo nacen de una hora EN VIVO; nunca del
  backfill del onboarding).

El SQL no se ejecuta: que PostgreSQL haga lo mismo queda pendiente (A-01…A-05 y R-01 sobre
Postgres real).

Reglas: RN-VI-02…05, RN-XIV-03…08, RN-XV-03…06, DC-24, DC-25, DC-32, DC-35. created_at = momento
del evento (fin de la hora; cierre: 00:00 del día 1). Entrega: RN-VI-02, RN-XIV-06; consejos:
RN-VI-03, RN-XV-06; solo para miembros con `fecha_ingreso <= created_at` del evento.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from functools import cache
from types import TracebackType
from typing import Any, Self
from uuid import UUID, uuid4

import pytest

from app.data import alerts as alerts_data
from app.data import goals as goals_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import readings as readings_data
from app.data import tips as tips_data
from app.domain.simulator import TIMEZONE
from app.services import backend_texts as backend_texts_service
from app.services import consumption as consumption_service
from app.services import live_alerts
from app.services import thresholds as thresholds_service
from tests.data.fake_session import FakeResult
from tests.e2e.test_onboarding_e2e import Params, PgError, StoreSession
from tests.helpers.auth import make_test_settings

SAVEPOINT_RELEASED = "savepoint"
SAVEPOINT_REVERTED = "savepoint-revertido"
ZONES_STATEMENT = "HOUSEHOLD_ZONES_SQL"
HOURLY_STATEMENT = "HOURLY_READINGS_SQL"
# Solo las usa la evaluación en vivo: fuera de un SAVEPOINT son un uso no previsto (DC-35).
EVALUATION_ONLY = frozenset(
    {
        "HOUSEHOLD_CREATED_AT_SQL",
        "ALERT_MEMBERS_SQL",
        "ALERT_PERMISSION_SQL",
        "GOAL_ACTIVE_ON_SQL",
        "EXISTING_EVENT_KEYS_SQL",
        "INSERT_ALERT_SQL",
        "INSERT_ALERT_DELIVERIES_SQL",
        "LATEST_TIPS_SQL",
        "INSERT_TIP_SQL",
        "INSERT_TIP_ASSIGNMENTS_SQL",
    }
)
CONSUMPTION_RULES = ("consumo_elevado", "consumo_critico")
MONTH_CLOSE_RULES = ("cierre_mes_dentro", "cierre_mes_encima")
NOTICE_RULES = ("nuevo_consejo_zona", "nuevo_consejo_general")
# Regla del consejo → regla de la alerta que lo dispara (DC-35: consejo y aviso con la alerta).
TIP_TRIGGER_RULE = {
    "zona_elevada": "consumo_elevado",
    "zona_critica": "consumo_critico",
    "cierre_mes_encima": "cierre_mes_encima",
}
PRIORITY_ORDER = {"alta": 0, "media": 1, "baja": 2}
ONE_HOUR = timedelta(hours=1)


def use_test_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Umbrales y textos del backend de `make_test_settings()`, con cachés propias de la prueba.

    Se reemplazan los nombres que llaman los servicios de consumo y de alertas (la caché de
    producción no queda con estos archivos). No se lee `.env`.
    """
    monkeypatch.setattr(thresholds_service, "get_settings", make_test_settings)
    monkeypatch.setattr(backend_texts_service, "get_settings", make_test_settings)
    thresholds = cache(thresholds_service.get_thresholds.__wrapped__)
    texts = cache(backend_texts_service.get_backend_texts.__wrapped__)
    monkeypatch.setattr(thresholds_service, "get_thresholds", thresholds)
    monkeypatch.setattr(consumption_service, "get_thresholds", thresholds)
    monkeypatch.setattr(live_alerts, "get_thresholds", thresholds)
    monkeypatch.setattr(backend_texts_service, "get_backend_texts", texts)
    monkeypatch.setattr(live_alerts, "get_backend_texts", texts)


class Savepoint:
    """`session.begin_nested()`: SAVEPOINT con reversión real de lo hecho dentro del bloque."""

    def __init__(self, session: Any) -> None:
        self.session = session
        self.saved: tuple[dict[str, dict[Any, Any]], set[tuple[Any, ...]]] | None = None

    def __enter__(self) -> Self:
        session, db = self.session, self.session.db
        if session.nested is not None:
            raise db.unexpected_use("SAVEPOINT anidado")
        if session.aborted:  # como PostgreSQL: SAVEPOINT en una transacción abortada
            exc = PgError("current transaction is aborted", "25P02")
            raise db._sqlalchemy_error("SAVEPOINT", {}, exc) from exc
        with db.lock:
            # Copia por tabla: las filas nunca se modifican, se reemplazan.
            changes = {table: dict(rows) for table, rows in session.changes.items()}
            self.saved = (changes, set(session.unique_keys))
            session.nested = []
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> bool:
        session, db = self.session, self.session.db
        assert self.saved is not None
        with db.lock:
            statements, session.nested = session.nested, None
            if exc_type is None:
                outcome = SAVEPOINT_RELEASED
            else:  # ROLLBACK TO SAVEPOINT: deshace lo de dentro y limpia el estado abortado
                session.changes, session.unique_keys = self.saved
                session.aborted = False
                outcome = SAVEPOINT_REVERTED
            db.events.append(outcome)
            db.live_evaluations.append((outcome, statements))
            db.lock.notify_all()
        return False  # la excepción sigue su camino (la captura hour_recovery)


class LiveAlertsMixin:
    """Sentencias de alertas, consejos, miembros, metas y zonas para un `Store` (ver el módulo).

    Se mezcla delante de `Store` (`class RecoveryStore(LiveAlertsMixin, Store)`).
    """

    committed: dict[str, dict[Any, dict[str, Any]]]
    events: list[str]
    handlers: dict[int, tuple[str, Any]]

    def register_live_alerts(self) -> None:
        self.live_evaluations: list[tuple[str, list[str]]] = []
        self.backfill_keys: set[tuple[UUID, datetime]] = set()  # lecturas del onboarding
        self.hourly_requests: list[set[UUID]] = []  # zonas pedidas en cada HOURLY_READINGS_SQL
        for module, name, handler in (
            (households_data, ZONES_STATEMENT, self._household_zones),
            (readings_data, HOURLY_STATEMENT, self._hourly_readings),
            (households_data, "HOUSEHOLD_CREATED_AT_SQL", self._household_created_at),
            (memberships_data, "ALERT_MEMBERS_SQL", self._alert_members),
            (memberships_data, "ALERT_PERMISSION_SQL", self._alert_permission),
            (goals_data, "GOAL_ACTIVE_ON_SQL", self._goal_active_on),
            (alerts_data, "EXISTING_EVENT_KEYS_SQL", self._existing_event_keys),
            (alerts_data, "INSERT_ALERT_SQL", self._insert_alert),
            (alerts_data, "INSERT_ALERT_DELIVERIES_SQL", self._insert_alert_deliveries),
            (alerts_data, "USER_ALERTS_SQL", self._user_alerts),
            (alerts_data, "USER_ALERTS_BY_CATEGORY_SQL", self._user_alerts),
            (alerts_data, "COUNT_UNREAD_ALERTS_SQL", self._count_unread_alerts),
            (alerts_data, "MARK_ALERTS_READ_SQL", self._mark_alerts_read),
            (tips_data, "LATEST_TIPS_SQL", self._latest_tips),
            (tips_data, "INSERT_TIP_SQL", self._insert_tip),
            (tips_data, "INSERT_TIP_ASSIGNMENTS_SQL", self._insert_tip_assignments),
            (tips_data, "USER_TIPS_SQL", self._user_tips),
            (tips_data, "USER_TIP_SQL", self._user_tip),
            (tips_data, "UPDATE_USER_TIP_STATUS_SQL", self._update_user_tip_status),
        ):
            self.handlers[id(getattr(module, name))] = (name, handler)

    # --- registro y transacción ---------------------------------------------------------

    def record(self, session: StoreSession, name: str) -> None:
        """Dentro de un SAVEPOINT la sentencia va a su evaluación; fuera, a `events`."""
        nested = vars(session).get("nested")  # una StoreSession simple no tiene SAVEPOINT
        if nested is None:
            if name in EVALUATION_ONLY:
                raise self.unexpected_use(f"{name} fuera del SAVEPOINT de la recuperación")
            self.events.append(name)
        else:
            nested.append(name)

    def commit(self, session: StoreSession) -> None:
        """Además anota qué lecturas publicó el onboarding (el backfill), para A-02."""
        onboarding = any(row is not None for row in session.changes["hogares"].values())
        pending = [k for k, r in session.changes["lecturas"].items() if r is not None]
        super().commit(session)  # type: ignore[misc]
        if onboarding:
            self.backfill_keys.update(k for k in pending if k in self.committed["lecturas"])

    # --- zonas y lecturas (las usan el consumo, el historial y la evaluación) -------------

    def _household_zones(self, session: StoreSession, params: Params) -> FakeResult:
        """zonas LEFT JOIN sensores_zona del hogar, ORDER BY nombre, id."""
        sensor_state = {
            row["zona_id"]: row["estado"] for row in self.view(session, "sensores_zona").values()
        }
        rows = [
            {
                "id": zone["id"],
                "tipo": zone["tipo"],
                "nombre": zone["nombre"],
                "estado": zone["estado"],
                "sensor_estado": sensor_state.get(zone["id"]),
            }
            for zone in self.view(session, "zonas").values()
            if zone["hogar_id"] == params["hogar_id"]
        ]
        return FakeResult(sorted(rows, key=lambda row: (row["nombre"], str(row["id"]))))

    def _hourly_readings(self, session: StoreSession, params: Params) -> FakeResult:
        """lecturas JOIN sensores_zona JOIN zonas; zona del hogar y pedida; hora en [start, end]."""
        wanted = {UUID(zona_id) for zona_id in params["zona_ids"]}
        self.hourly_requests.append(wanted)
        zones = {
            key: row
            for key, row in self.view(session, "zonas").items()
            if row["hogar_id"] == params["hogar_id"] and key in wanted
        }
        zone_of_sensor = {
            row["id"]: row["zona_id"]
            for row in self.view(session, "sensores_zona").values()
            if row["zona_id"] in zones
        }
        start, end = params["start"], params["end"]
        rows = [
            {
                "zona_id": zone_of_sensor[row["sensor_id"]],
                "fecha_hora": row["fecha_hora"],
                "consumo_kwh": row["consumo_kwh"],
            }
            for row in self.view(session, "lecturas").values()
            if row["sensor_id"] in zone_of_sensor and start <= row["fecha_hora"] <= end
        ]
        return FakeResult(sorted(rows, key=lambda row: (str(row["zona_id"]), row["fecha_hora"])))

    # --- hogar, miembros y metas ---------------------------------------------------------

    def _household_created_at(self, session: StoreSession, params: Params) -> FakeResult:
        household = self.view(session, "hogares").get(params["hogar_id"])
        return FakeResult([] if household is None else [{"created_at": household["created_at"]}])

    def _alert_members(self, session: StoreSession, params: Params) -> FakeResult:
        """Miembros 'activo' (usuario no nulo) LEFT JOIN preferencias (coalesce true), por id.

        Devuelve `fecha_ingreso` sin filtrar: excluir a quien ingresó después del evento lo decide
        el servicio (RN-VI-02, RN-XV-06), no el SQL.
        """
        preferences = self.view(session, "preferencias_usuario")
        rows = []
        for row in self.view(session, "hogar_miembros").values():
            if row["hogar_id"] != params["hogar_id"] or row["estado"] != "activo":
                continue
            if row["usuario_id"] is None:
                continue
            prefs = preferences.get(row["usuario_id"], {})
            rows.append(
                {
                    "usuario_id": row["usuario_id"],
                    "rol": row["rol"],
                    "notif_consumo": prefs.get("notif_consumo", True),
                    "notif_consejos": prefs.get("notif_consejos", True),
                    "fecha_ingreso": row["fecha_ingreso"],
                }
            )
        return FakeResult(sorted(rows, key=lambda row: str(row["usuario_id"])))

    def _alert_permission(self, session: StoreSession, params: Params) -> FakeResult:
        household = self.view(session, "hogares").get(params["hogar_id"])
        if household is None:
            return FakeResult()
        return FakeResult([{"permiso_recibir_alertas": household["permiso_recibir_alertas"]}])

    def _goal_active_on(self, session: StoreSession, params: Params) -> FakeResult:
        """Vigente el día: fecha_inicio <= día < fecha_fin (o sin fin), sin mirar el estado."""
        day = params["day"]
        found = [
            row
            for row in self.view(session, "metas_consumo").values()
            if row["hogar_id"] == params["hogar_id"]
            and row["fecha_inicio"] <= day
            and (row["fecha_fin"] is None or row["fecha_fin"] > day)
        ]
        found.sort(key=lambda r: (r["fecha_inicio"], r["created_at"], str(r["id"])), reverse=True)
        return FakeResult(found[:1])

    # --- alertas -------------------------------------------------------------------------

    def _existing_event_keys(self, session: StoreSession, params: Params) -> FakeResult:
        wanted = set(params["claves"])
        return FakeResult(
            [
                {"clave_evento": row["clave_evento"]}
                for row in self.view(session, "alertas").values()
                if row["hogar_id"] == params["hogar_id"] and row["clave_evento"] in wanted
            ]
        )

    def _zone_of_household(self, session: StoreSession, zona_id: Any, hogar_id: UUID) -> bool:
        if zona_id is None:
            return True
        zone = self.view(session, "zonas").get(UUID(str(zona_id)))
        return zone is not None and zone["hogar_id"] == hogar_id

    def _insert_alert(self, session: StoreSession, params: Params) -> FakeResult:
        """INSERT … SELECT … WHERE zona del hogar ON CONFLICT (clave_evento) DO NOTHING."""
        hogar_id = params["hogar_id"]
        self._require(hogar_id in self.view(session, "hogares"), "23503", "alertas_hogar_id_fkey")
        self._require(
            params["categoria"] in ("consumo", "consejo", "informacion"),
            "23514",
            "alertas_categoria_check",
        )
        self._require(
            params["severidad"] in ("informativa", "advertencia", "critica"),
            "23514",
            "alertas_severidad_check",
        )
        for column in ("titulo", "mensaje", "regla_origen", "clave_evento", "created_at"):
            self._require(params[column] is not None, "23502", f"alertas_{column}")
        if not self._zone_of_household(session, params["zona_id"], hogar_id):
            return FakeResult(rowcount=0)
        keys = {row["clave_evento"] for row in self.view(session, "alertas").values()}
        if params["clave_evento"] in keys:
            return FakeResult(rowcount=0)
        alerta_id = uuid4()
        created_at = params["created_at"].astimezone(UTC)
        row = {
            "id": alerta_id,
            "hogar_id": hogar_id,
            "categoria": params["categoria"],
            "severidad": params["severidad"],
            "titulo": params["titulo"],
            "mensaje": params["mensaje"],
            "zona_id": None if params["zona_id"] is None else UUID(str(params["zona_id"])),
            "regla_origen": params["regla_origen"],
            "clave_evento": params["clave_evento"],
            "created_at": created_at,
            "updated_at": created_at,
        }
        self.put(session, "alertas", alerta_id, row)
        return FakeResult([{"id": alerta_id}], rowcount=1)

    def _active_member_ids(self, session: StoreSession, hogar_id: UUID) -> set[UUID]:
        return {
            row["usuario_id"]
            for row in self.view(session, "hogar_miembros").values()
            if row["hogar_id"] == hogar_id and row["estado"] == "activo"
        }

    def _insert_alert_deliveries(self, session: StoreSession, params: Params) -> FakeResult:
        """Una entrega sin leer por miembro activo del hogar de la alerta; repetida → nada."""
        alerta_id = UUID(str(params["alerta_id"]))
        alert = self.view(session, "alertas").get(alerta_id)
        if alert is None:
            return FakeResult(rowcount=0)
        active = self._active_member_ids(session, alert["hogar_id"])
        existing = set(self.view(session, "alertas_usuario"))
        inserted = 0
        for text in params["usuario_ids"]:
            usuario_id = UUID(text)
            key = (alerta_id, usuario_id)
            if usuario_id not in active or key in existing:
                continue
            existing.add(key)
            row = {"alerta_id": alerta_id, "usuario_id": usuario_id, "leida_en": None}
            self.put(session, "alertas_usuario", key, row)
            inserted += 1
        return FakeResult(rowcount=inserted)

    def _user_alerts(self, session: StoreSession, params: Params) -> FakeResult:
        """Entregas de la persona en el hogar, salvo las leídas en read_after o antes (`>`)."""
        alerts = self.view(session, "alertas")
        zones = self.view(session, "zonas")
        rows = []
        for (alerta_id, usuario_id), delivery in self.view(session, "alertas_usuario").items():
            alert = alerts[alerta_id]
            if usuario_id != params["usuario_id"] or alert["hogar_id"] != params["hogar_id"]:
                continue
            leida_en = delivery["leida_en"]
            if leida_en is not None and leida_en <= params["read_after"]:
                continue
            if "categoria" in params and alert["categoria"] != params["categoria"]:
                continue
            zone = zones.get(alert["zona_id"]) if alert["zona_id"] is not None else None
            rows.append(
                {
                    **{
                        column: alert[column]
                        for column in (
                            "id",
                            "categoria",
                            "severidad",
                            "titulo",
                            "mensaje",
                            "zona_id",
                            "created_at",
                        )
                    },
                    "zona_tipo": None if zone is None else zone["tipo"],
                    "leida_en": leida_en,
                }
            )
        rows.sort(key=lambda row: (row["created_at"], str(row["id"])), reverse=True)
        return FakeResult(rows[: params["limite"]])

    def _count_unread_alerts(self, session: StoreSession, params: Params) -> FakeResult:
        alerts = self.view(session, "alertas")
        total = sum(
            usuario_id == params["usuario_id"]
            and delivery["leida_en"] is None
            and alerts[alerta_id]["hogar_id"] == params["hogar_id"]
            for (alerta_id, usuario_id), delivery in self.view(session, "alertas_usuario").items()
        )
        return FakeResult([{"total": total}])

    def _mark_alerts_read(self, session: StoreSession, params: Params) -> FakeResult:
        """Solo filas de la persona, de alertas del hogar y aún sin leer."""
        wanted = {UUID(text) for text in params["alerta_ids"]}
        alerts = self.view(session, "alertas")
        changed = 0
        for key, delivery in self.view(session, "alertas_usuario").items():
            alerta_id, usuario_id = key
            if alerta_id not in wanted or usuario_id != params["usuario_id"]:
                continue
            if alerts[alerta_id]["hogar_id"] != params["hogar_id"]:
                continue
            if delivery["leida_en"] is not None:
                continue
            self.put(session, "alertas_usuario", key, {**delivery, "leida_en": params["read_at"]})
            changed += 1
        return FakeResult(rowcount=changed)

    # --- consejos ------------------------------------------------------------------------

    def _latest_tips(self, session: StoreSession, params: Params) -> FakeResult:
        """DISTINCT ON (regla_origen, zona_id), el último por created_at desc, id desc."""
        latest: dict[tuple[str, Any], dict[str, Any]] = {}
        for row in self.view(session, "consejos").values():
            if row["hogar_id"] != params["hogar_id"]:
                continue
            key = (row["regla_origen"], row["zona_id"])
            current = latest.get(key)
            if current is None or (row["created_at"], str(row["id"])) > (
                current["created_at"],
                str(current["id"]),
            ):
                latest[key] = row
        return FakeResult(
            [
                {column: row[column] for column in ("regla_origen", "zona_id", "titulo", "created_at")}
                for row in latest.values()
            ]
        )

    def _insert_tip(self, session: StoreSession, params: Params) -> FakeResult:
        hogar_id = params["hogar_id"]
        self._require(hogar_id in self.view(session, "hogares"), "23503", "consejos_hogar_id_fkey")
        self._require(params["categoria"] in ("zona", "general"), "23514", "consejos_categoria")
        self._require(
            params["prioridad"] in ("baja", "media", "alta"), "23514", "consejos_prioridad_check"
        )
        self._require(
            (params["categoria"] == "zona") == (params["zona_id"] is not None),
            "23514",
            "consejos_categoria_coherente",
        )
        if not self._zone_of_household(session, params["zona_id"], hogar_id):
            return FakeResult(rowcount=0)
        consejo_id = uuid4()
        created_at = params["created_at"].astimezone(UTC)
        row = {
            "id": consejo_id,
            "hogar_id": hogar_id,
            "categoria": params["categoria"],
            "prioridad": params["prioridad"],
            "zona_id": None if params["zona_id"] is None else UUID(str(params["zona_id"])),
            "titulo": params["titulo"],
            "descripcion": params["descripcion"],
            "regla_origen": params["regla_origen"],
            "created_at": created_at,
            "updated_at": created_at,
        }
        self.put(session, "consejos", consejo_id, row)
        return FakeResult([{"id": consejo_id}], rowcount=1)

    def _insert_tip_assignments(self, session: StoreSession, params: Params) -> FakeResult:
        """Una fila 'pendiente' por miembro activo del hogar del consejo; repetida → nada."""
        consejo_id = UUID(str(params["consejo_id"]))
        tip = self.view(session, "consejos").get(consejo_id)
        if tip is None:
            return FakeResult(rowcount=0)
        active = self._active_member_ids(session, tip["hogar_id"])
        existing = set(self.view(session, "consejos_usuario"))
        inserted = 0
        for text in params["usuario_ids"]:
            usuario_id = UUID(text)
            key = (consejo_id, usuario_id)
            if usuario_id not in active or key in existing:
                continue
            existing.add(key)
            row = {
                "id": uuid4(),
                "consejo_id": consejo_id,
                "usuario_id": usuario_id,
                "estado": "pendiente",
                "completada_en": None,
            }
            self.put(session, "consejos_usuario", key, row)
            inserted += 1
        return FakeResult(rowcount=inserted)

    def _tip_rows(self, session: StoreSession, params: Params) -> list[dict[str, Any]]:
        """consejos_usuario de la persona JOIN consejos del hogar LEFT JOIN zonas."""
        tips = self.view(session, "consejos")
        zones = self.view(session, "zonas")
        rows = []
        for (consejo_id, usuario_id), state in self.view(session, "consejos_usuario").items():
            tip = tips[consejo_id]
            if usuario_id != params["usuario_id"] or tip["hogar_id"] != params["hogar_id"]:
                continue
            zone = zones.get(tip["zona_id"]) if tip["zona_id"] is not None else None
            rows.append(
                {
                    **{
                        column: tip[column]
                        for column in (
                            "id",
                            "categoria",
                            "prioridad",
                            "titulo",
                            "descripcion",
                            "zona_id",
                            "created_at",
                        )
                    },
                    "zona_tipo": None if zone is None else zone["tipo"],
                    "estado": state["estado"],
                    "completada_en": state["completada_en"],
                }
            )
        return rows

    def _user_tips(self, session: StoreSession, params: Params) -> FakeResult:
        """Pendientes vigentes (alta, media, baja; created_at desc, id desc) y luego completadas
        recientes (completada_en desc, id desc)."""
        rows = self._tip_rows(session, params)
        pending = [
            r
            for r in rows
            if r["estado"] == "pendiente" and r["created_at"] > params["pending_created_after"]
        ]
        completed = [
            r
            for r in rows
            if r["estado"] == "completada" and r["completada_en"] > params["completed_after"]
        ]
        pending.sort(key=lambda r: (r["created_at"], str(r["id"])), reverse=True)
        pending.sort(key=lambda r: PRIORITY_ORDER[r["prioridad"]])
        completed.sort(key=lambda r: (r["completada_en"], str(r["id"])), reverse=True)
        return FakeResult(pending + completed)

    def _user_tip(self, session: StoreSession, params: Params) -> FakeResult:
        wanted = UUID(str(params["consejo_id"]))
        return FakeResult([r for r in self._tip_rows(session, params) if r["id"] == wanted])

    def _update_user_tip_status(self, session: StoreSession, params: Params) -> FakeResult:
        estado, completada_en = params["estado"], params["completada_en"]
        self._require(
            estado in ("pendiente", "completada"), "23514", "consejos_usuario_estado_check"
        )
        self._require(
            (estado == "completada") == (completada_en is not None),
            "23514",
            "consejos_usuario_estado_coherente",
        )
        key = (UUID(str(params["consejo_id"])), params["usuario_id"])
        state = self.view(session, "consejos_usuario").get(key)
        tip = self.view(session, "consejos").get(key[0])
        if state is None or tip is None or tip["hogar_id"] != params["hogar_id"]:
            return FakeResult(rowcount=0)
        row = {**state, "estado": estado, "completada_en": completada_en}
        self.put(session, "consejos_usuario", key, row)
        return FakeResult(rowcount=1)

    # --- A-01 y A-02 sobre lo confirmado --------------------------------------------------

    def _sensor_of_zone(self) -> dict[UUID, UUID]:
        return {row["zona_id"]: row["id"] for row in self.committed["sensores_zona"].values()}

    def _is_live(self, sensor_id: UUID, hour: datetime) -> bool:
        key = (sensor_id, hour.astimezone(UTC))
        return key in self.committed["lecturas"] and key not in self.backfill_keys

    def assert_live_alert_rules(self) -> None:
        """A-01 y A-02 sobre todo lo confirmado (se llama al final de cada prueba).

        A-02: una alerta de consumo nace del fin de una hora en vivo de su zona (created_at =
        momento del evento: fin de la hora) y su clave es `<regla>:<zona_id>:<fecha Bogotá>`
        (DC-25); un cierre de mes, de las 23:00 en vivo del último día, en un mes que terminó
        después del alta del hogar (DC-32 y RN-XIV-07; created_at: 00:00 del día 1); un aviso
        «Nuevo consejo», de un consejo del hogar con su mismo created_at; un consejo, de una alerta
        de su regla, zona y momento (DC-35: consejo y aviso con la alerta). Ninguna nace del
        backfill.
        A-01: a lo sumo una alerta por (regla, zona, día) y `clave_evento` sin repetir.
        """
        sensor_of = self._sensor_of_zone()
        alerts = list(self.committed["alertas"].values())
        tips = {row["id"]: row for row in self.committed["consejos"].values()}
        per_day: Counter[tuple[str, UUID, date]] = Counter()
        assert len({a["clave_evento"] for a in alerts}) == len(alerts), "clave_evento repetida"
        for alert in alerts:
            rule, hour = alert["regla_origen"], alert["created_at"] - ONE_HOUR
            if rule in CONSUMPTION_RULES:
                day = hour.astimezone(TIMEZONE).date()
                assert alert["zona_id"] in sensor_of, alert
                assert self._is_live(sensor_of[alert["zona_id"]], hour), ("A-02", alert)
                assert alert["clave_evento"] == f"{rule}:{alert['zona_id']}:{day}", alert
                per_day[rule, alert["zona_id"], day] += 1
            elif rule in MONTH_CLOSE_RULES:
                household = self.committed["hogares"][alert["hogar_id"]]
                local = hour.astimezone(TIMEZONE)
                assert (local.hour, (local + ONE_HOUR).day) == (23, 1), alert
                assert alert["created_at"] > household["created_at"], ("DC-32", alert)
                zones = [
                    z["id"] for z in self.committed["zonas"].values()
                    if z["hogar_id"] == alert["hogar_id"]
                ]
                assert any(
                    z in sensor_of and self._is_live(sensor_of[z], hour) for z in zones
                ), ("A-02", alert)
            elif rule in NOTICE_RULES:
                rule_name, consejo_id = alert["clave_evento"].split(":")
                tip = tips[UUID(consejo_id)]
                assert rule_name == "nuevo_consejo", alert
                assert (tip["hogar_id"], tip["created_at"]) == (
                    alert["hogar_id"],
                    alert["created_at"],
                ), alert
            else:
                raise AssertionError(f"alerta de una regla inesperada: {alert}")
        assert all(count == 1 for count in per_day.values()), ("A-01", per_day)
        for tip in tips.values():
            trigger = TIP_TRIGGER_RULE[tip["regla_origen"]]
            assert any(
                a["regla_origen"] == trigger
                and a["hogar_id"] == tip["hogar_id"]
                and a["zona_id"] == tip["zona_id"]
                and a["created_at"] == tip["created_at"]
                for a in alerts
            ), ("DC-35", tip)
