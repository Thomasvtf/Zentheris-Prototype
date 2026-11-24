"""Consumo actual, por zonas y de una zona de punta a punta (fase 6).

El hogar se crea con el onboarding REAL por la API (`POST /api/v1/onboarding`) sobre el almacén
en memoria de `test_hour_recovery_e2e` (`RecoveryStore`), y después se piden por HTTP
`obtenerConsumoActual`, `obtenerConsumoZonas` y `obtenerConsumoZona`. Corren de verdad la
guardia (`app.security`), el router, el servicio, la recuperación de horas, el simulador, el
motor de estados y las funciones de `app.data`; solo se reemplaza lo más bajo, como en los e2e
del onboarding y de la recuperación. `ConsumptionStore` le enseña al almacén las sentencias de la
fase 6, imitando su resultado (no las ramas del SQL):

- `ACTIVE_MEMBERSHIP_SQL` (la guardia): membresía 'activo' del usuario en el hogar, con los 4
  permisos de `hogares`.
- `HOUSEHOLD_ZONES_SQL`: zonas del hogar LEFT JOIN su sensor, por nombre e id.
- `HOURLY_READINGS_SQL`: lecturas de las zonas pedidas del hogar en [start, end] inclusive, por
  zona y hora; el kWh como NUMERIC (Decimal) y la hora en UTC, como el controlador.
- `PREFERENCES_SQL`, `ACTIVE_GOAL_SQL` y `CURRENT_TARIFF_SQL` (vigencia [desde, hasta), DC-39).
  Metas y tarifas se siembran ya confirmadas: aún no hay operación que las cree (fase 7+).

Reloj: el onboarding corre en T (sábado 21/11/2026 22:10, Bogotá) y `datetime.now()` del
servicio de consumo se fija por prueba (`query_at`). Los umbrales salen de `make_test_settings()`
(no se lee `.env`).

Las alertas y los consejos siguen vigilados (DC-35, fase 8): si algo los llama, la prueba falla.

El SQL no se ejecuta: que PostgreSQL haga lo mismo queda pendiente (B-04 y R-01 sobre Postgres
real).

Reglas: RN-XI-01…09, RN-XII-03, RN-XII-05…07, RN-XVII-01, RN-IV-05, RN-V-01, RN-V-02.
Decisiones: DC-28, DC-34, DC-35; decisión de Nicolás del 23/11/2026 (si la recuperación falla,
la consulta responde con los datos guardados).
"""

import logging
import unicodedata
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta, tzinfo
from decimal import Decimal
from functools import cache
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.data import goals as goals_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import readings as readings_data
from app.data import tariffs as tariffs_data
from app.data import users as users_data
from app.domain import alert_rules
from app.domain.formats import zone_name
from app.domain.simulator import TIMEZONE, hour_from_index
from app.main import API_PREFIX
from app.services import consumption as consumption_service
from app.services import hour_recovery
from app.services import onboarding as onboarding_service
from app.services import thresholds as thresholds_service
from tests.contract.test_c01_responses_match_schema import assert_matches_contract
from tests.data.fake_session import FakeResult
from tests.e2e.test_hour_recovery_e2e import (
    END,
    HOURS_OFF,
    LATER,
    LOCK_STATEMENT,
    READ_STATEMENTS,
    RECOVERY_STATEMENTS,
    START,
    OnboardingClock,
    RecoveryStore,
    T,
    assert_contiguous,
    client_for,
    continuous,
    create_household,
    other_personality,
)
from tests.e2e.test_onboarding_e2e import (
    INTERNAL_DETAIL,
    READINGS_STATEMENT,
    REFERENCE_HOUSEHOLDS,
    Params,
    StoreSession,
    forbid_alerts_and_tips,
)
from tests.helpers.auth import auth_header, install_test_jwks, make_test_settings, make_token
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.simulator.support import stable_id

TAG = "e2e6"
MEMBERSHIP_STATEMENT = "ACTIVE_MEMBERSHIP_SQL"
ZONES_STATEMENT = "HOUSEHOLD_ZONES_SQL"
HOURLY_STATEMENT = "HOURLY_READINGS_SQL"
PREFERENCES_STATEMENT = "PREFERENCES_SQL"
GOAL_STATEMENT = "ACTIVE_GOAL_SQL"
TARIFF_STATEMENT = "CURRENT_TARIFF_SQL"
# Lo que lee cada consulta después de la recuperación (orden del servicio).
READS = {
    "actual": [ZONES_STATEMENT, HOURLY_STATEMENT, PREFERENCES_STATEMENT, TARIFF_STATEMENT],
    "zonas": [ZONES_STATEMENT, HOURLY_STATEMENT, TARIFF_STATEMENT],
    "zona": [ZONES_STATEMENT, HOURLY_STATEMENT, TARIFF_STATEMENT],
}
# En T (22:10) la última hora completa es la de las 21:00, ya en el backfill.
HOUR_AT_T = datetime(2026, 11, 21, 21, tzinfo=TIMEZONE)
# En LATER (domingo 03:10) es la de las 02:00, una de las 5 que faltan tras el apagado.
HOUR_AT_LATER = datetime(2026, 11, 22, 2, tzinfo=TIMEZONE)
PRICE_KWH = Decimal("812.5000")
GOAL_KWH = Decimal("300.00")
FORBIDDEN_BODY = {"codigo": "SIN_PERMISO_VER_CONSUMO"}
COUNTED_STATES = {"normal", "elevado", "critico"}

Key = tuple[UUID, datetime]

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)


# --- el almacén con las sentencias de la fase 6 ---------------------------------------------


class ConsumptionStore(RecoveryStore):
    """`RecoveryStore` más las lecturas de la guardia y de las consultas de consumo."""

    def __init__(self) -> None:
        super().__init__()
        self.goals: dict[UUID, dict[str, Any]] = {}  # metas_consumo 'activa' por hogar
        self.tariffs: dict[UUID, list[dict[str, Any]]] = {}  # tarifas_hogar por hogar
        self.hourly_requests: list[set[UUID]] = []  # zonas pedidas en cada HOURLY_READINGS_SQL
        for module, name, handler in (
            (memberships_data, MEMBERSHIP_STATEMENT, self._membership_with_permissions),
            (households_data, ZONES_STATEMENT, self._household_zones),
            (readings_data, HOURLY_STATEMENT, self._hourly_readings),
            (users_data, PREFERENCES_STATEMENT, self._preferences),
            (goals_data, GOAL_STATEMENT, self._active_goal),
            (tariffs_data, TARIFF_STATEMENT, self._current_tariff),
        ):
            self.handlers[id(getattr(module, name))] = (name, handler)

    def _membership_with_permissions(self, session: StoreSession, params: Params) -> FakeResult:
        """hogar_miembros 'activo' JOIN hogares: la fila con los 4 permisos del hogar."""
        households = self.view(session, "hogares")
        rows = []
        for row in self.view(session, "hogar_miembros").values():
            if (row["usuario_id"], row["hogar_id"]) != (params["usuario_id"], params["hogar_id"]):
                continue
            if row["estado"] != "activo" or row["hogar_id"] not in households:
                continue
            household = households[row["hogar_id"]]
            rows.append(
                {
                    "membresia_id": row["id"],
                    "hogar_id": row["hogar_id"],
                    "usuario_id": row["usuario_id"],
                    "rol": row["rol"],
                    **{
                        column: household[column]
                        for column in (
                            "permiso_ver_consumo_actual",
                            "permiso_ver_historial",
                            "permiso_recibir_alertas",
                            "permiso_modificar_metas",
                        )
                    },
                }
            )
        return FakeResult(rows)

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
            {"zona_id": zone_of_sensor[row["sensor_id"]], "fecha_hora": row["fecha_hora"],
             "consumo_kwh": row["consumo_kwh"]}
            for row in self.view(session, "lecturas").values()
            if row["sensor_id"] in zone_of_sensor and start <= row["fecha_hora"] <= end
        ]
        return FakeResult(sorted(rows, key=lambda row: (str(row["zona_id"]), row["fecha_hora"])))

    def _preferences(self, session: StoreSession, params: Params) -> FakeResult:
        row = self.view(session, "preferencias_usuario").get(params["usuario_id"])
        return FakeResult([] if row is None else [row])

    def _active_goal(self, _session: StoreSession, params: Params) -> FakeResult:
        goal = self.goals.get(params["hogar_id"])
        return FakeResult([] if goal is None else [goal])

    def _current_tariff(self, _session: StoreSession, params: Params) -> FakeResult:
        today = params["today"]
        return FakeResult(
            [
                row
                for row in self.tariffs.get(params["hogar_id"], [])
                if row["vigente_desde"] <= today
                and (row["vigente_hasta"] is None or row["vigente_hasta"] > today)
            ]
        )

    # --- preparación y lo que miran las pruebas ----------------------------------------

    def seed_member(self, hogar_id: UUID, usuario_id: UUID) -> None:
        """Otra persona con ficha y membresía 'miembro' activa en el hogar."""
        self.seed_user(usuario_id)
        membresia_id = stable_id("membresia", TAG, str(usuario_id))
        self.committed["hogar_miembros"][membresia_id] = {
            "id": membresia_id,
            "hogar_id": hogar_id,
            "usuario_id": usuario_id,
            "rol": "miembro",
            "estado": "activo",
            "fecha_ingreso": T,
            "fecha_salida": None,
        }

    def set_household_permission(self, hogar_id: UUID, column: str, value: bool) -> None:
        rows = self.committed["hogares"]
        rows[hogar_id] = {**rows[hogar_id], column: value}

    def set_comparison_base(self, usuario_id: UUID, base: str) -> None:
        rows = self.committed["preferencias_usuario"]
        rows[usuario_id] = {**rows[usuario_id], "base_comparacion": base}

    def zone_ids(self, hogar_id: UUID) -> dict[str, UUID]:
        return {row["tipo"]: row["id"] for row in self.rows("zonas") if row["hogar_id"] == hogar_id}

    def zone_kwh(self, hogar_id: UUID, hour: datetime) -> dict[str, float]:
        """kWh guardado de cada zona en la hora que empieza en `hour` (= su kW promedio)."""
        moment = hour.astimezone(UTC)
        return {
            zone: float(value)
            for (zone, stored), value in self.by_zone(hogar_id).items()
            if stored == moment
        }


# --- fixtures y pasos -----------------------------------------------------------------------


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[ConsumptionStore]:
    store = ConsumptionStore()
    guarded = forbid_alerts_and_tips(monkeypatch, store)  # DC-35: nadie llama alertas/consejos
    assert {"evaluate_alert_rules", "build_tips"} <= set(guarded)
    monkeypatch.setattr(onboarding_service, "datetime", OnboardingClock)
    monkeypatch.setattr(thresholds_service, "get_settings", make_test_settings)
    # Caché propia de la prueba (la de producción no queda con estos umbrales), en el nombre
    # que llama el servicio de consumo.
    fresh = cache(thresholds_service.get_thresholds.__wrapped__)
    monkeypatch.setattr(thresholds_service, "get_thresholds", fresh)
    monkeypatch.setattr(consumption_service, "get_thresholds", fresh)
    install_test_jwks(monkeypatch)
    yield store
    # Los servicios capturan cualquier excepción: lo inesperado se comprueba aquí.
    assert store.unexpected == []


@pytest.fixture
def client(db: ConsumptionStore) -> TestClient:
    return client_for(db)


def query_at(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    """`datetime.now()` del servicio de consumo congelado en `moment`."""

    class QueryClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return moment.astimezone(tz)

    monkeypatch.setattr(consumption_service, "datetime", QueryClock)


def user_of(name: str) -> UUID:
    """El administrador que crea `create_household(..., name, TAG)`."""
    return stable_id("usuario", TAG, name)


def new_household(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> UUID:
    return create_household(db, client, monkeypatch, name, TAG)


def get(
    client: TestClient, kind: str, user_id: UUID, hogar_id: UUID, zona_id: UUID | None = None
) -> httpx.Response:
    """GET de una de las 3 operaciones como `user_id`; un 200 se valida contra el contrato."""
    path = {
        "actual": ("obtenerConsumoActual", f"/hogares/{hogar_id}/consumo/actual"),
        "zonas": ("obtenerConsumoZonas", f"/hogares/{hogar_id}/consumo/zonas"),
        "zona": ("obtenerConsumoZona", f"/hogares/{hogar_id}/consumo/zonas/{zona_id}"),
    }
    operation_id, url = path[kind]
    response = client.get(API_PREFIX + url, headers=auth_header(make_token(user_id)))
    if response.status_code in (200, 403, 404):
        assert_matches_contract(operation_id, response)
    return response


def ok(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    return response.json()


def hour_of(body: dict[str, Any]) -> tuple[datetime, datetime]:
    return (
        datetime.fromisoformat(body["hora"]["inicio"]),
        datetime.fromisoformat(body["hora"]["fin"]),
    )


def alphabetical(names: list[str]) -> list[str]:
    """Orden alfabético por letra base, sin tildes ni mayúsculas (RN-XII-03)."""

    def key(text: str) -> str:
        base = unicodedata.normalize("NFD", text)
        return "".join(ch for ch in base if not unicodedata.combining(ch)).casefold()

    return sorted(names, key=key)


def every_cost(body: Any) -> list[Any]:
    """Todos los `costo_cop` de una respuesta, a cualquier profundidad."""
    if isinstance(body, dict):
        found = [body["costo_cop"]] if "costo_cop" in body else []
        return found + [cost for value in body.values() for cost in every_cost(value)]
    if isinstance(body, list):
        return [cost for item in body for cost in every_cost(item)]
    return []


def today_kwh(db: ConsumptionStore, hogar_id: UUID, last_hour: datetime) -> float:
    """Suma del hogar de 00:00 de hoy hasta `last_hour` inclusive, leída del almacén."""
    first = last_hour.replace(hour=0)
    total = 0.0
    moment = first
    while moment <= last_hour:
        total += sum(db.zone_kwh(hogar_id, moment).values())
        moment += timedelta(hours=1)
    return total


# --- 1. las 3 consultas por HTTP, para las 5 personalidades ---------------------------------


@each_personality
def test_the_three_queries_answer_the_last_complete_hour(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """200 válido contra el contrato; total = suma de zonas; orden alfabético; sin tarifa → null.

    RN-XI-01, RN-XI-04, RN-XI-05, RN-XI-08, RN-XII-03, RN-XII-05…07. Onboarding real en T
    (22:10): la hora evaluada es la de las 21:00, ya guardada por el backfill, así que la
    recuperación corre primero (después de la guardia) y no guarda nada.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    query_at(monkeypatch, T)
    stored = db.zone_kwh(hogar_id, HOUR_AT_T)
    assert set(stored) == set(zones)
    expected_total = sum(stored.values())
    before = db.readings_of(hogar_id)

    db.events.clear()
    actual = ok(get(client, "actual", user_id, hogar_id))
    assert db.events == [MEMBERSHIP_STATEMENT, *READ_STATEMENTS, "rollback", *READS["actual"]]

    db.events.clear()
    by_zone = ok(get(client, "zonas", user_id, hogar_id))
    assert db.events == [MEMBERSHIP_STATEMENT, *READ_STATEMENTS, "rollback", *READS["zonas"]]

    # Hora evaluada: la última completa, en Bogotá (la misma en las dos respuestas).
    hour = (HOUR_AT_T, HOUR_AT_T + timedelta(hours=1))
    assert hour_of(actual) == hour_of(by_zone) == hour
    assert actual["hora"]["inicio"].endswith("-05:00")

    # Sin tarifa: tarifa_vigente false y todo costo_cop null (RN-XI-08).
    assert actual["tarifa_vigente"] is by_zone["tarifa_vigente"] is False
    assert set(every_cost(actual)) == set(every_cost(by_zone)) == {None}

    # Total = suma de las zonas que cuentan (todas, recién creadas) = lo guardado.
    items = by_zone["zonas"]
    assert {item["tipo"] for item in items} == set(zones)
    assert all(item["nombre"] == zone_name(item["tipo"]) for item in items)  # RN-XII-03
    assert [item["nombre"] for item in items] == alphabetical([item["nombre"] for item in items])
    assert by_zone["total_kw"] == pytest.approx(sum(item["potencia_kw"] for item in items))
    assert by_zone["total_kw"] == pytest.approx(expected_total)
    assert actual["actual"]["potencia_kw"] == pytest.approx(expected_total)
    assert {item["tipo"]: item["potencia_kw"] for item in items} == pytest.approx(stored)
    assert sum(item["participacion_pct"] for item in items) == pytest.approx(100)

    # Con 29 días completos de backfill hay referencia promedio (≥ 7 días, DC-28).
    assert actual["actual"]["referencia_tipo"] == "promedio"
    assert actual["actual"]["referencia_kw"] > 0
    assert actual["actual"]["estado"] in COUNTED_STATES
    assert actual["actual"]["mensaje_codigo"] == f"consumo_actual.{actual['actual']['estado']}"
    today = actual["acumulado_hoy"]
    assert today["energia_kwh"] == pytest.approx(today_kwh(db, hogar_id, HOUR_AT_T))
    assert (today["referencia_tipo"], today["muestra_limite"]) == ("promedio", False)
    assert today["referencia_kwh"] > 0
    assert today["estado"] in COUNTED_STATES
    assert today["mensaje_codigo"] == f"acumulado.promedio.{today['estado']}"

    # Detalle de cada zona: los mismos kW y el mismo total del hogar.
    for item in items:
        db.events.clear()
        detail = ok(get(client, "zona", user_id, hogar_id, UUID(item["zona_id"])))
        assert db.events == [MEMBERSHIP_STATEMENT, *READ_STATEMENTS, "rollback", *READS["zona"]]
        assert hour_of(detail) == hour
        assert detail["zona"] == {
            "id": item["zona_id"],
            "tipo": item["tipo"],
            "nombre": item["nombre"],
            "estado": "activa",
        }
        assert detail["potencia_kw"] == pytest.approx(item["potencia_kw"])
        assert detail["participacion"]["participacion_pct"] == pytest.approx(
            item["participacion_pct"]
        )
        assert detail["participacion"]["total_hogar_kw"] == pytest.approx(by_zone["total_kw"])
        assert detail["participacion"]["estado"] == item["estado_participacion"]
        # Una zona que a esa hora no consume nunca (promedio 0, p. ej. el baño del hogar
        # compacto a las 21:00) no tiene referencia válida: `sin_referencia` (referencia ≤ 0).
        average = detail["estado_consumo"]["promedio_misma_hora_kw"]
        assert average >= 0
        expected = {"sin_referencia"} if average == 0 else COUNTED_STATES
        state = detail["estado_consumo"]["estado"]
        assert state in expected
        assert item["estado_participacion"] in expected
        assert detail["estado_consumo"]["mensaje_codigo"] == f"zona_estado.{state}"
        assert set(every_cost(detail)) == {None}

    assert db.readings_of(hogar_id) == before  # consultar no escribe
    assert "commit" not in db.events


@each_personality
def test_tariff_costs_and_goal_reference(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Con tarifa vigente: costo = kWh × precio, sin cargo fijo (RN-V-01, RN-V-02, RN-XI-08).

    Con `base_comparacion = meta` y una meta activa, el acumulado usa el límite diario = meta ÷
    días del mes (noviembre: 30) y muestra el límite (RN-XI-03, RN-XI-04).
    """
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    query_at(monkeypatch, T)
    db.tariffs[hogar_id] = [
        {  # vencida el 21/11: [desde, hasta) no la incluye
            "id": stable_id("tarifa", TAG, name, "vieja"),
            "precio_kwh": Decimal("999.0000"),
            "cargo_fijo_mensual": None,
            "vigente_desde": date(2026, 10, 1),
            "vigente_hasta": date(2026, 11, 21),
        },
        {
            "id": stable_id("tarifa", TAG, name),
            "precio_kwh": PRICE_KWH,
            "cargo_fijo_mensual": Decimal("15000.00"),
            "vigente_desde": date(2026, 11, 21),
            "vigente_hasta": None,
        },
    ]
    db.goals[hogar_id] = {
        "id": stable_id("meta", TAG, name),
        "tipo": "ahorro",
        "valor_kwh_mensual": GOAL_KWH,
        "fecha_inicio": date(2026, 11, 1),
    }
    db.set_comparison_base(user_id, "meta")
    price = float(PRICE_KWH)

    db.events.clear()
    actual = ok(get(client, "actual", user_id, hogar_id))
    assert db.events == [
        MEMBERSHIP_STATEMENT,
        *READ_STATEMENTS,
        "rollback",
        ZONES_STATEMENT,
        HOURLY_STATEMENT,
        PREFERENCES_STATEMENT,
        GOAL_STATEMENT,
        TARIFF_STATEMENT,
    ]
    by_zone = ok(get(client, "zonas", user_id, hogar_id))

    assert actual["tarifa_vigente"] is by_zone["tarifa_vigente"] is True
    now_kw = actual["actual"]["potencia_kw"]
    assert actual["actual"]["costo_cop"] == pytest.approx(now_kw * price)
    today = actual["acumulado_hoy"]
    assert today["costo_cop"] == pytest.approx(today["energia_kwh"] * price)
    for item in by_zone["zonas"]:
        assert item["costo_cop"] == pytest.approx(item["potencia_kw"] * price)
        detail = ok(get(client, "zona", user_id, hogar_id, UUID(item["zona_id"])))
        assert detail["tarifa_vigente"] is True
        assert detail["costo_cop"] == pytest.approx(item["potencia_kw"] * price)
        # El estado de una zona nunca se compara con la meta (RN-XI-06).
        assert detail["estado_consumo"]["mensaje_codigo"].startswith("zona_estado.")

    assert actual["actual"]["referencia_tipo"] == "meta"
    assert today["referencia_tipo"] == "meta"
    assert today["muestra_limite"] is True
    assert today["referencia_kwh"] == pytest.approx(float(GOAL_KWH) / 30)
    assert today["mensaje_codigo"] == f"acumulado.meta.{today['estado']}"


def test_reference_follows_the_personality_order(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """compacto < eficiente < intermedio < familiar < amplio, consultando por la API.

    Magnitud: `acumulado_hoy.referencia_kwh` en T (22:10, hora evaluada 21:00) con base
    promedio: media de lo acumulado de 00:00 a 21:59 en los días completos anteriores (DC-28),
    del hogar de referencia de cada personalidad. Además, lo acumulado hoy y el consumo de la
    hora siguen el mismo orden de la referencia en el total de 30 días de su backfill.
    """
    households = {name: new_household(db, client, monkeypatch, name) for name in PERSONALITY_ORDER}
    query_at(monkeypatch, T)

    references = {}
    backfill_totals = {}
    for name, hogar_id in households.items():
        body = ok(get(client, "actual", user_of(name), hogar_id))
        references[name] = body["acumulado_hoy"]["referencia_kwh"]
        backfill_totals[name] = sum(db.readings_of(hogar_id).values())

    values = [references[name] for name in PERSONALITY_ORDER]
    assert values == sorted(values), references
    assert len(set(values)) == len(values), references
    totals = [backfill_totals[name] for name in PERSONALITY_ORDER]
    assert totals == sorted(totals), backfill_totals


@each_personality
def test_zones_that_do_not_count_are_left_out(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Zona inactiva y zona con sensor pausado: no suman ni se listan; su detalle va en null.

    RN-XI-01, RN-XI-05 (`zone_rules.counts_for_total`): solo cuentan las zonas 'activa' con
    sensor 'activo'. El servicio no lee lecturas de las que no cuentan; su detalle responde 200
    con todo null y `sin_datos`, y el total del hogar es la suma de las que sí cuentan.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    ids = db.zone_ids(hogar_id)
    paused, inactive = sorted(zones)[:2]
    db.set_state("sensores_zona", db.sensors_of(hogar_id)[paused], "pausado")
    db.set_state("zonas", ids[inactive], "inactiva")
    counting = set(zones) - {paused, inactive}
    query_at(monkeypatch, T)
    stored = db.zone_kwh(hogar_id, HOUR_AT_T)

    db.hourly_requests.clear()
    by_zone = ok(get(client, "zonas", user_id, hogar_id))
    actual = ok(get(client, "actual", user_id, hogar_id))

    assert {item["tipo"] for item in by_zone["zonas"]} == counting
    expected_total = sum(stored[zone] for zone in counting)
    assert by_zone["total_kw"] == pytest.approx(expected_total)
    assert actual["actual"]["potencia_kw"] == pytest.approx(expected_total)

    for zone, estado in ((paused, "activa"), (inactive, "inactiva")):
        detail = ok(get(client, "zona", user_id, hogar_id, ids[zone]))
        assert detail["zona"] == {
            "id": str(ids[zone]),
            "tipo": zone,
            "nombre": zone_name(zone),
            "estado": estado,
        }
        assert detail["potencia_kw"] is None
        assert detail["costo_cop"] is None
        assert detail["estado_consumo"] == {
            "promedio_misma_hora_kw": None,
            "variacion_pct": None,
            "estado": "sin_datos",
            "mensaje_codigo": "zona_estado.sin_datos",
        }
        assert detail["participacion"]["participacion_pct"] is None
        assert detail["participacion"]["estado"] == "sin_datos"
        assert detail["participacion"]["total_hogar_kw"] == pytest.approx(expected_total)

    counting_ids = {ids[zone] for zone in counting}
    assert db.hourly_requests == [counting_ids] * 4  # zonas, actual y los 2 detalles


@each_personality
def test_tariff_of_the_evaluated_hour_and_cost_at_midnight(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """A las 00:10 la hora evaluada es la de las 23:00 de AYER: rige la tarifa de ayer.

    RN-V-01, RN-XI-08, DC-39: la tarifa es la vigente en la fecha (Bogotá) de la hora evaluada,
    aunque hoy empiece otra. Entre 00:00 y 00:59 no hay horas completas de hoy: el acumulado es
    0 kWh, `sin_datos` y `costo_cop` null (RN-XI-04).
    """
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    midnight = datetime(2026, 11, 22, 0, 10, tzinfo=TIMEZONE)
    evaluated = datetime(2026, 11, 21, 23, tzinfo=TIMEZONE)
    yesterday_price, today_price = Decimal("700.0000"), Decimal("900.0000")
    db.tariffs[hogar_id] = [
        {
            "id": stable_id("tarifa", TAG, name, "ayer"),
            "precio_kwh": yesterday_price,
            "cargo_fijo_mensual": None,
            "vigente_desde": date(2026, 11, 1),
            "vigente_hasta": date(2026, 11, 22),
        },
        {
            "id": stable_id("tarifa", TAG, name, "hoy"),
            "precio_kwh": today_price,
            "cargo_fijo_mensual": None,
            "vigente_desde": date(2026, 11, 22),
            "vigente_hasta": None,
        },
    ]
    query_at(monkeypatch, midnight)

    actual = ok(get(client, "actual", user_id, hogar_id))
    by_zone = ok(get(client, "zonas", user_id, hogar_id))

    assert hour_of(actual) == (evaluated, evaluated + timedelta(hours=1))
    stored = db.zone_kwh(hogar_id, evaluated)  # la recuperó la propia consulta
    assert actual["actual"]["potencia_kw"] == pytest.approx(sum(stored.values()))
    price = float(yesterday_price)
    assert actual["tarifa_vigente"] is by_zone["tarifa_vigente"] is True
    assert actual["actual"]["costo_cop"] == pytest.approx(actual["actual"]["potencia_kw"] * price)
    for item in by_zone["zonas"]:
        assert item["costo_cop"] == pytest.approx(item["potencia_kw"] * price)
        detail = ok(get(client, "zona", user_id, hogar_id, UUID(item["zona_id"])))
        assert detail["costo_cop"] == pytest.approx(item["potencia_kw"] * price)
    today = actual["acumulado_hoy"]
    assert (today["energia_kwh"], today["estado"], today["costo_cop"]) == (0, "sin_datos", None)


# --- 2. B-04 con la consulta real -----------------------------------------------------------


@each_personality
def test_b04_the_current_consumption_query_recovers_the_missing_hours(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Servidor apagado 5 h (cruza medianoche) y luego `GET /consumo/actual`.

    RN-IV-05, DC-34: la misma consulta, después de la guardia y antes de leer, guarda las 5
    horas de cada sensor (725 lecturas, sin huecos ni repetidas, iguales a la generación
    continua) y evalúa la hora nueva (02:00 del domingo). Repetirla no guarda nada más.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    backfill = db.readings_of(hogar_id)
    query_at(monkeypatch, LATER)

    db.events.clear()
    body = ok(get(client, "actual", user_id, hogar_id))

    assert db.events == [MEMBERSHIP_STATEMENT, *RECOVERY_STATEMENTS, "commit", *READS["actual"]]
    assert_contiguous(db, hogar_id, 720 + HOURS_OFF)
    stored = db.readings_of(hogar_id)
    assert len(stored) == (720 + HOURS_OFF) * len(zones)
    assert {key: stored[key] for key in backfill} == backfill
    assert stored == continuous(db, hogar_id, name, END + HOURS_OFF)
    assert {row["calidad"] for row in db.rows("lecturas")} == {"simulada"}

    assert hour_of(body) == (HOUR_AT_LATER, HOUR_AT_LATER + timedelta(hours=1))
    assert hour_from_index(END + HOURS_OFF - 1) == HOUR_AT_LATER
    new_hour = db.zone_kwh(hogar_id, HOUR_AT_LATER)
    assert set(new_hour) == set(zones)
    assert body["actual"]["potencia_kw"] == pytest.approx(sum(new_hour.values()))
    # Hoy (domingo) ya tiene sus 3 horas completas (00, 01 y 02), todas recuperadas.
    assert body["acumulado_hoy"]["energia_kwh"] == pytest.approx(
        today_kwh(db, hogar_id, HOUR_AT_LATER)
    )
    assert body["acumulado_hoy"]["estado"] != "sin_datos"

    db.events.clear()
    again = ok(get(client, "actual", user_id, hogar_id))
    assert db.events == [MEMBERSHIP_STATEMENT, *READ_STATEMENTS, "rollback", *READS["actual"]]
    assert READINGS_STATEMENT not in db.events
    assert db.readings_of(hogar_id) == stored
    assert again == body
    assert hour_from_index(START) == min(hour for _sensor, hour in stored).astimezone(TIMEZONE)


# --- 3. si la recuperación falla, se responde con lo guardado -------------------------------


FAILURES = {
    "candado": LOCK_STATEMENT,  # falla al tomar el candado del hogar
    "insercion": READINGS_STATEMENT,  # falla a mitad del lote de lecturas
}


@pytest.mark.parametrize("failure", sorted(FAILURES))
@each_personality
def test_failed_recovery_answers_200_with_the_stored_data(
    db: ConsumptionStore,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    name: str,
    failure: str,
) -> None:
    """Decisión de Nicolás (23/11/2026): recuperación fallida → 200 con los datos guardados.

    Apagado de 5 h y la recuperación falla en cada consulta (candado o inserción): nada se
    guarda (rollback), los 3 endpoints responden 200 y la hora evaluada (02:00, que falta) sale
    `potencia_kw` null y estado `sin_datos`. El log lleva el WARNING de recuperación omitida,
    sin el id del hogar ni el detalle interno de la base.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    backfill = db.readings_of(hogar_id)
    zona_id = db.zone_ids(hogar_id)[min(zones)]
    db.tariffs[hogar_id] = [
        {
            "id": stable_id("tarifa", TAG, name),
            "precio_kwh": PRICE_KWH,
            "cargo_fijo_mensual": None,
            "vigente_desde": date(2026, 11, 1),
            "vigente_hasta": None,
        }
    ]
    query_at(monkeypatch, LATER)
    caplog.set_level(logging.INFO)

    responses = {}
    for kind in ("actual", "zonas", "zona"):
        db.fail_once.add(FAILURES[failure])
        db.events.clear()
        responses[kind] = ok(get(client, kind, user_id, hogar_id, zona_id))
        assert FAILURES[failure] not in db.fail_once  # la falla sí ocurrió
        assert "rollback" in db.events and "commit" not in db.events
        assert db.events[-len(READS[kind]) :] == READS[kind]  # y luego leyó lo guardado

    assert db.readings_of(hogar_id) == backfill  # nada nuevo
    assert_contiguous(db, hogar_id, 720)

    actual, by_zone, detail = responses["actual"], responses["zonas"], responses["zona"]
    hour = (HOUR_AT_LATER, HOUR_AT_LATER + timedelta(hours=1))
    assert hour_of(actual) == hour_of(by_zone) == hour_of(detail) == hour
    assert actual["actual"]["potencia_kw"] is None
    assert actual["actual"]["estado"] == "sin_datos"
    assert actual["actual"]["mensaje_codigo"] == "consumo_actual.sin_datos"
    assert actual["acumulado_hoy"]["estado"] == "sin_datos"  # las horas de hoy faltan
    assert by_zone["total_kw"] is None
    assert {item["tipo"] for item in by_zone["zonas"]} == set(zones)
    assert {item["potencia_kw"] for item in by_zone["zonas"]} == {None}
    assert {item["estado_participacion"] for item in by_zone["zonas"]} == {"sin_datos"}
    assert detail["potencia_kw"] is None
    assert detail["estado_consumo"]["estado"] == "sin_datos"
    assert detail["participacion"]["total_hogar_kw"] is None
    # Con tarifa vigente, sin kWh (o con el acumulado en sin_datos) el costo es null (RN-XI-08).
    assert actual["tarifa_vigente"] is by_zone["tarifa_vigente"] is detail["tarifa_vigente"]
    assert actual["tarifa_vigente"] is True
    assert set(every_cost(actual)) == set(every_cost(by_zone)) == set(every_cost(detail))
    assert set(every_cost(actual)) == {None}

    skipped = [
        record
        for record in caplog.records
        if record.name == hour_recovery.__name__
        and record.levelno == logging.WARNING
        and record.getMessage() == hour_recovery.RECOVERY_SKIPPED_MESSAGE
    ]
    assert len(skipped) == 3
    for record in caplog.records:
        text = record.getMessage()
        assert str(hogar_id) not in text and INTERNAL_DETAIL not in text
        assert record.exc_info is None


# --- 4. seguridad antes que la recuperación -------------------------------------------------


@each_personality
def test_member_without_view_consumption_gets_403_and_nothing_is_recovered(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """P-02 de punta a punta: 403 `SIN_PERMISO_VER_CONSUMO` y la recuperación NO corre.

    RN-XVII-01, RN-IV-05: la guardia va antes. Control: con el permiso, el mismo miembro
    recibe 200 (y entonces sí se recupera); el administrador pasa aunque el permiso del hogar
    esté en false (P-06, RN-XVII-05).
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    member_id = stable_id("miembro", TAG, name)
    db.seed_member(hogar_id, member_id)
    db.set_household_permission(hogar_id, "permiso_ver_consumo_actual", False)
    zona_id = db.zone_ids(hogar_id)[min(zones)]
    backfill = db.readings_of(hogar_id)
    query_at(monkeypatch, LATER)

    for kind in ("actual", "zonas", "zona"):
        db.events.clear()
        response = get(client, kind, member_id, hogar_id, zona_id)
        assert response.status_code == 403, response.text
        assert response.json()["codigo"] == FORBIDDEN_BODY["codigo"]
        assert db.events == [MEMBERSHIP_STATEMENT]  # ni candado ni lecturas
    assert db.readings_of(hogar_id) == backfill

    db.events.clear()
    admin = ok(get(client, "actual", user_of(name), hogar_id))
    assert db.events[:2] == [MEMBERSHIP_STATEMENT, LOCK_STATEMENT]
    assert hour_of(admin)[0] == HOUR_AT_LATER

    db.set_household_permission(hogar_id, "permiso_ver_consumo_actual", True)
    assert ok(get(client, "zonas", member_id, hogar_id))["total_kw"] is not None


@each_personality
def test_another_household_gets_404_and_is_not_touched(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """P-01 y R-01: sin membresía en el hogar → 404 `NO_ENCONTRADO`, sin recuperar ni leer.

    Y una zona de otro hogar pedida por el hogar propio → 404 (el servicio la busca entre las
    zonas del hogar); el hogar ajeno no recibe lecturas.
    """
    hogar_id = new_household(db, client, monkeypatch, name)
    other = other_personality(name)
    neighbour = new_household(db, client, monkeypatch, other)
    neighbour_zone = next(iter(db.zone_ids(neighbour).values()))
    neighbour_before = db.readings_of(neighbour)
    query_at(monkeypatch, LATER)

    for kind in ("actual", "zonas", "zona"):
        db.events.clear()
        response = get(client, kind, user_of(name), neighbour, neighbour_zone)
        assert response.status_code == 404, response.text
        assert response.json()["codigo"] == "NO_ENCONTRADO"
        assert db.events == [MEMBERSHIP_STATEMENT]

    db.events.clear()
    response = get(client, "zona", user_of(name), hogar_id, neighbour_zone)
    assert response.status_code == 404, response.text
    assert response.json()["codigo"] == "NO_ENCONTRADO"
    assert HOURLY_STATEMENT not in db.events  # 404 antes de leer lecturas
    assert db.readings_of(neighbour) == neighbour_before
    assert_contiguous(db, neighbour, 720)


# --- 5. la vigilancia de alertas sigue activa (DC-35, fase 8) --------------------------------


def test_alert_and_tip_watch_is_still_active(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Las consultas de consumo no evalúan alertas ni consejos (DC-35): solo la fase 8.

    La vigilancia de `forbid_alerts_and_tips` anota cualquier llamada; aquí se comprueba que
    sigue instalada (llamar a una función vigilada falla y queda anotado) y que una consulta
    con recuperación no la dispara.
    """
    name = PERSONALITY_ORDER[0]
    hogar_id = new_household(db, client, monkeypatch, name)
    query_at(monkeypatch, LATER)

    ok(get(client, "actual", user_of(name), hogar_id))
    assert db.unexpected == []

    with pytest.raises(AssertionError):
        alert_rules.evaluate_alert_rules()
    assert db.unexpected == ["app.domain.alert_rules.evaluate_alert_rules (DC-35)"]
    db.unexpected.clear()  # anotado a propósito: la fixture no debe fallar por esto

