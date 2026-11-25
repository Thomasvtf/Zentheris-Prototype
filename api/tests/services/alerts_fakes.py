"""Dobles en memoria de `app.data` para las alertas y los consejos (fase 8), sin base ni red.

`FakeAlertsDatabase` amplía `FakeRecoveryDatabase` (recuperación real con el simulador real) con
lo que leen y escriben `app.services.live_alerts` y `app.services.alerts_tips`: zonas, lecturas
por zona, miembros con sus interruptores y su fecha de ingreso, permiso del hogar, fecha de creación, metas, `alertas`, `alertas_usuario`,
`consejos` y `consejos_usuario`. Cada función imita su sentencia: filtra por `hogar_id` (R-01),
`ON CONFLICT (clave_evento) DO NOTHING` en las alertas, entregas y filas de consejo solo para
miembros activos, órdenes y ventanas de las consultas de la persona (alerta leída visible si
`leida_en > read_after`, como el SQL).

Transacciones: las tablas confirmadas viven en `db.tables`; la sesión trabaja sobre una copia
(`work`) que el commit confirma y el rollback descarta; `begin_nested()` guarda una copia de la
copia y la restaura si el bloque lanza (SAVEPOINT, DC-35). Las lecturas pendientes siguen el
mecanismo de `FakeRecoveryDatabase`. No demuestra compatibilidad con PostgreSQL.
"""

from __future__ import annotations

import copy
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.data import alerts as alerts_data
from app.data import goals as goals_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import readings as readings_data
from app.data import tips as tips_data
from app.data.alerts import UserAlertRow
from app.data.goals import ActiveGoalRow
from app.data.households import ZoneRow
from app.data.memberships import AlertMemberRow
from app.data.readings import HourlyReadingRow
from app.data.tips import TipHistoryRow, UserTipRow
from app.domain.formats import zone_name
from app.domain.simulator import TIMEZONE, generate_backfill
from app.services import hour_recovery, live_alerts
from tests.services.recovery_fakes import (
    FakeHousehold,
    FakeRecoveryDatabase,
    FakeSession,
    install_fake_recovery_database,
)
from tests.simulator.support import bogota, stable_id

PRIORITY_ORDER = {"alta": 0, "media": 1, "baja": 2}
ADMIN = stable_id("usuario", "admin")
# Onboarding (backfill) el domingo 22/11/2026 a las 18:10: la última hora del backfill es la de
# las 17:00; las recuperaciones de la noche generan 18:00, 19:00… en vivo (horas de consumo alto).
BACKFILL_AT = bogota(2026, 11, 22, 18, 10)
DAY = "2026-11-22"
# Fecha de ingreso por defecto de los miembros de prueba: anterior a todas las horas en vivo.
JOINED = bogota(2026, 1, 1)


@dataclass
class Member:
    usuario_id: UUID
    rol: str = "miembro"
    estado: str = "activo"
    notif_consumo: bool = True
    notif_consejos: bool = True
    fecha_ingreso: datetime = JOINED


def empty_tables() -> dict[str, dict[Any, Any]]:
    return {"alertas": {}, "alertas_usuario": {}, "consejos": {}, "consejos_usuario": {}}


class FakeAlertsSession(FakeSession):
    """Sesión con copia de trabajo de las tablas de alertas y consejos."""

    db: FakeAlertsDatabase

    def __init__(self, db: FakeAlertsDatabase) -> None:
        super().__init__(db)
        self.work: dict[str, dict[Any, Any]] | None = None

    def tables(self) -> dict[str, dict[Any, Any]]:
        """Lo que ve la transacción (confirmado + pendiente), copiado al primer uso."""
        if self.work is None:
            self.work = copy.deepcopy(self.db.tables)
        return self.work

    def commit(self) -> None:
        work = self.work
        super().commit()  # lecturas; con fail_commit lanza antes de confirmar nada
        if work is not None:
            self.db.tables = work

    def end_transaction(self) -> None:
        self.work = None
        super().end_transaction()

    def snapshot(self) -> Any:
        return super().snapshot(), copy.deepcopy(self.work)

    def restore(self, state: Any) -> None:
        base, work = state
        super().restore(base)
        self.work = work


class FakeAlertsDatabase(FakeRecoveryDatabase):
    """Almacén en memoria de la recuperación más alertas, consejos, miembros y metas."""

    def __init__(self) -> None:
        super().__init__()
        self.tables = empty_tables()
        self.zones: dict[UUID, list[ZoneRow]] = {}
        self.zone_of_sensor: dict[UUID, UUID] = {}
        self.zone_household: dict[UUID, UUID] = {}
        self.members: dict[UUID, list[Member]] = {}
        self.permission: dict[UUID, bool] = {}
        self.created_at: dict[UUID, datetime] = {}
        self.goals: dict[UUID, list[tuple[date, date | None, float]]] = {}
        self.ids = 0

    # --- preparación ---------------------------------------------------------------
    def session(self) -> FakeAlertsSession:  # type: ignore[override]
        session = FakeAlertsSession(self)
        self.sessions.append(session)
        return session

    def register(
        self,
        household: FakeHousehold,
        created_at: datetime,
        members: Sequence[Member] = (),
        permission: bool = True,
    ) -> FakeHousehold:
        """Hogar con una zona activa (sensor activo) por cada sensor, sin lecturas aún."""
        self.households[household.id] = household
        self.zones[household.id] = []
        for zone, sensor in household.sensors.items():
            zona_id = zone_id(household, zone)
            self.zones[household.id].append(
                ZoneRow(id=zona_id, tipo=zone, nombre=zone_name(zone), estado="activa",
                        sensor_estado="activo")
            )
            self.zone_of_sensor[sensor] = zona_id
            self.zone_household[zona_id] = household.id
        self.members[household.id] = list(members) or [Member(ADMIN, rol="administrador")]
        self.permission[household.id] = permission
        self.created_at[household.id] = created_at
        return household

    def add_backfill(self, household: FakeHousehold, now: datetime, hours: int = 720) -> None:
        self.store(generate_backfill(household.id, household.profile, household.sensors, now,
                                     hours))

    def set_goal(self, hogar_id: UUID, start: date, end: date | None, kwh: float) -> None:
        self.goals.setdefault(hogar_id, []).append((start, end, kwh))

    def new_id(self, kind: str) -> UUID:
        self.ids += 1
        return stable_id(kind, str(self.ids))

    def alerts(self, hogar_id: UUID | None = None) -> list[dict[str, Any]]:
        rows = self.tables["alertas"].values()
        return [row for row in rows if hogar_id is None or row["hogar_id"] == hogar_id]

    def tips(self, hogar_id: UUID | None = None) -> list[dict[str, Any]]:
        rows = self.tables["consejos"].values()
        return [row for row in rows if hogar_id is None or row["hogar_id"] == hogar_id]

    def deliveries(self, alerta_id: UUID) -> set[UUID]:
        return {user for (alert, user) in self.tables["alertas_usuario"] if alert == alerta_id}

    def assignments(self, consejo_id: UUID) -> dict[UUID, dict[str, Any]]:
        return {
            user: row
            for (tip, user), row in self.tables["consejos_usuario"].items()
            if tip == consejo_id
        }

    def same_hour_average(self, household: FakeHousehold, zone: str, hour_start: datetime,
                          days: int = 30) -> float:
        """Promedio de la misma hora en los `days` días anteriores (lecturas confirmadas)."""
        sensor = household.sensors[zone]
        values = []
        for back in range(1, days + 1):
            key = (sensor, hour_start - timedelta(days=back))
            if key in self.saved:
                values.append(float(self.saved[key]["consumo_kwh"]))
        return statistics.mean(values)

    def seed_alert(self, hogar_id: UUID, **fields: Any) -> UUID:
        alerta_id = fields.pop("id", None) or self.new_id("alerta")
        row = {"id": alerta_id, "hogar_id": hogar_id, "categoria": "consumo",
               "severidad": "critica", "titulo": "t", "mensaje": "m", "zona_id": None,
               "regla_origen": "consumo_critico", "clave_evento": f"seed:{alerta_id}",
               "created_at": datetime(2026, 11, 20, tzinfo=TIMEZONE)}
        row.update(fields)
        self.tables["alertas"][alerta_id] = row
        return alerta_id

    def seed_delivery(self, alerta_id: UUID, usuario_id: UUID,
                      leida_en: datetime | None = None) -> None:
        self.tables["alertas_usuario"][(alerta_id, usuario_id)] = leida_en

    def seed_tip(self, hogar_id: UUID, **fields: Any) -> UUID:
        consejo_id = fields.pop("id", None) or self.new_id("consejo")
        row = {"id": consejo_id, "hogar_id": hogar_id, "categoria": "general",
               "prioridad": "baja", "zona_id": None, "titulo": "t", "descripcion": "d",
               "regla_origen": "cierre_mes_encima",
               "created_at": datetime(2026, 11, 20, tzinfo=TIMEZONE)}
        row.update(fields)
        self.tables["consejos"][consejo_id] = row
        return consejo_id

    def seed_assignment(self, consejo_id: UUID, usuario_id: UUID, estado: str = "pendiente",
                        completada_en: datetime | None = None) -> None:
        self.tables["consejos_usuario"][(consejo_id, usuario_id)] = {
            "estado": estado, "completada_en": completada_en
        }

    # --- auxiliares ----------------------------------------------------------------
    def _active(self, hogar_id: UUID) -> list[Member]:
        return [m for m in self.members.get(hogar_id, []) if m.estado == "activo"]

    def _zone_of_household(self, zona_id: UUID | None, hogar_id: UUID) -> bool:
        return zona_id is None or self.zone_household.get(zona_id) == hogar_id

    def _zone_type(self, zona_id: UUID | None) -> str | None:
        if zona_id is None:
            return None
        for zones in self.zones.values():
            for zone in zones:
                if zone.id == zona_id:
                    return zone.tipo
        return None

    # --- households, readings, memberships, goals ----------------------------------
    def list_household_zones(self, session: Any, hogar_id: UUID) -> list[ZoneRow]:
        self.calls.append("zones")
        return list(self.zones.get(hogar_id, []))

    def get_household_created_at(self, session: Any, hogar_id: UUID) -> datetime | None:
        return self.created_at.get(hogar_id)

    def get_hourly_readings(
        self, session: Any, hogar_id: UUID, zona_ids: Sequence[UUID], start: datetime,
        end: datetime,
    ) -> list[HourlyReadingRow]:
        self.calls.append("readings")
        if start.utcoffset() is None or end.utcoffset() is None:
            raise ValueError("start y end deben llevar zona horaria")
        wanted = set(zona_ids)
        visible = {**self.saved, **getattr(session, "pending", {})}
        rows = []
        for (sensor, moment), row in visible.items():
            zona_id = self.zone_of_sensor.get(sensor)
            if zona_id not in wanted or self.zone_household.get(zona_id) != hogar_id:
                continue
            if start <= moment <= end:
                rows.append(HourlyReadingRow(zona_id, moment, float(row["consumo_kwh"])))
        return sorted(rows, key=lambda r: (str(r.zona_id), r.fecha_hora))

    def list_alert_members(self, session: Any, hogar_id: UUID) -> list[AlertMemberRow]:
        return [
            AlertMemberRow(m.usuario_id, m.rol, m.notif_consumo, m.notif_consejos,  # type: ignore[arg-type]
                           m.fecha_ingreso)
            for m in sorted(self._active(hogar_id), key=lambda m: str(m.usuario_id))
        ]

    def get_alert_permission(self, session: Any, hogar_id: UUID) -> bool | None:
        return self.permission.get(hogar_id)

    def get_goal_active_on(self, session: Any, hogar_id: UUID, day: date) -> ActiveGoalRow | None:
        found = [g for g in self.goals.get(hogar_id, []) if g[0] <= day and (g[1] is None
                                                                            or g[1] > day)]
        if not found:
            return None
        start, _end, kwh = max(found, key=lambda g: g[0])
        return ActiveGoalRow(id=stable_id("meta", str(hogar_id), start.isoformat()),
                             tipo="ahorro", valor_kwh_mensual=kwh, fecha_inicio=start)

    # --- alerts --------------------------------------------------------------------
    def list_existing_event_keys(self, session: FakeAlertsSession, hogar_id: UUID,
                                 keys: Sequence[str]) -> set[str]:
        self.calls.append("existing_keys")
        alerts = session.tables()["alertas"].values()
        return {a["clave_evento"] for a in alerts
                if a["hogar_id"] == hogar_id and a["clave_evento"] in set(keys)}

    def insert_alert(self, session: FakeAlertsSession, **fields: Any) -> UUID | None:
        self.calls.append("insert_alert")
        if fields["created_at"].utcoffset() is None:
            raise ValueError("created_at sin zona horaria")
        alerts = session.tables()["alertas"]
        if any(a["clave_evento"] == fields["clave_evento"] for a in alerts.values()):
            return None
        if not self._zone_of_household(fields["zona_id"], fields["hogar_id"]):
            return None
        alerta_id = self.new_id("alerta")
        alerts[alerta_id] = {"id": alerta_id, **fields}
        return alerta_id

    def insert_alert_deliveries(self, session: FakeAlertsSession, alerta_id: UUID,
                                usuario_ids: Sequence[UUID]) -> int:
        tables = session.tables()
        alert = tables["alertas"].get(alerta_id)
        if alert is None:
            return 0
        active = {m.usuario_id for m in self._active(alert["hogar_id"])}
        count = 0
        for usuario_id in usuario_ids:
            key = (alerta_id, usuario_id)
            if usuario_id in active and key not in tables["alertas_usuario"]:
                tables["alertas_usuario"][key] = None
                count += 1
        return count

    def list_user_alerts(self, session: FakeAlertsSession, usuario_id: UUID, hogar_id: UUID,
                         categoria: str | None, limite: int,
                         read_after: datetime) -> list[UserAlertRow]:
        self.calls.append("list_user_alerts")
        tables = session.tables()
        rows = []
        for (alerta_id, user), leida_en in tables["alertas_usuario"].items():
            alert = tables["alertas"][alerta_id]
            if user != usuario_id or alert["hogar_id"] != hogar_id:
                continue
            if leida_en is not None and leida_en <= read_after:
                continue
            if categoria is not None and alert["categoria"] != categoria:
                continue
            rows.append(UserAlertRow(
                id=alerta_id, categoria=alert["categoria"], severidad=alert["severidad"],
                titulo=alert["titulo"], mensaje=alert["mensaje"], zona_id=alert["zona_id"],
                zona_tipo=self._zone_type(alert["zona_id"]), created_at=alert["created_at"],
                leida_en=leida_en,
            ))
        rows.sort(key=lambda r: (r.created_at, str(r.id)), reverse=True)
        return rows[:limite]

    def count_unread_alerts(self, session: FakeAlertsSession, usuario_id: UUID,
                            hogar_id: UUID) -> int:
        self.calls.append("count_unread_alerts")
        tables = session.tables()
        return sum(
            1
            for (alerta_id, user), leida_en in tables["alertas_usuario"].items()
            if user == usuario_id and leida_en is None
            and tables["alertas"][alerta_id]["hogar_id"] == hogar_id
        )

    def mark_alerts_read(self, session: FakeAlertsSession, usuario_id: UUID, hogar_id: UUID,
                         alerta_ids: Sequence[UUID], read_at: datetime) -> int:
        self.calls.append("mark_alerts_read")
        tables = session.tables()
        count = 0
        for alerta_id in set(alerta_ids):
            key = (alerta_id, usuario_id)
            alert = tables["alertas"].get(alerta_id)
            if (alert is not None and alert["hogar_id"] == hogar_id
                    and key in tables["alertas_usuario"] and tables["alertas_usuario"][key] is None):
                tables["alertas_usuario"][key] = read_at
                count += 1
        return count

    # --- tips ----------------------------------------------------------------------
    def list_latest_tips(self, session: FakeAlertsSession, hogar_id: UUID) -> list[TipHistoryRow]:
        latest: dict[tuple[str, UUID | None], dict[str, Any]] = {}
        for tip in session.tables()["consejos"].values():
            if tip["hogar_id"] != hogar_id:
                continue
            key = (tip["regla_origen"], tip["zona_id"])
            if key not in latest or (tip["created_at"], str(tip["id"])) > (
                latest[key]["created_at"], str(latest[key]["id"])
            ):
                latest[key] = tip
        return [TipHistoryRow(t["regla_origen"], t["zona_id"], t["titulo"], t["created_at"])
                for t in latest.values()]

    def insert_tip(self, session: FakeAlertsSession, **fields: Any) -> UUID:
        self.calls.append("insert_tip")
        if not self._zone_of_household(fields["zona_id"], fields["hogar_id"]):
            raise ValueError("La zona del consejo no es del hogar.")
        consejo_id = self.new_id("consejo")
        session.tables()["consejos"][consejo_id] = {"id": consejo_id, **fields}
        return consejo_id

    def insert_tip_assignments(self, session: FakeAlertsSession, consejo_id: UUID,
                               usuario_ids: Sequence[UUID]) -> int:
        tables = session.tables()
        tip = tables["consejos"].get(consejo_id)
        if tip is None:
            return 0
        active = {m.usuario_id for m in self._active(tip["hogar_id"])}
        count = 0
        for usuario_id in usuario_ids:
            key = (consejo_id, usuario_id)
            if usuario_id in active and key not in tables["consejos_usuario"]:
                tables["consejos_usuario"][key] = {"estado": "pendiente", "completada_en": None}
                count += 1
        return count

    def _user_tip(self, tables: Mapping[str, Any], consejo_id: UUID,
                  state: Mapping[str, Any]) -> UserTipRow:
        tip = tables["consejos"][consejo_id]
        return UserTipRow(
            id=consejo_id, categoria=tip["categoria"], prioridad=tip["prioridad"],
            titulo=tip["titulo"], descripcion=tip["descripcion"], zona_id=tip["zona_id"],
            zona_tipo=self._zone_type(tip["zona_id"]), estado=state["estado"],
            completada_en=state["completada_en"], created_at=tip["created_at"],
        )

    def list_user_tips(self, session: FakeAlertsSession, usuario_id: UUID, hogar_id: UUID,
                       pending_created_after: datetime,
                       completed_after: datetime) -> list[UserTipRow]:
        self.calls.append("list_user_tips")
        tables = session.tables()
        pending, completed = [], []
        for (consejo_id, user), state in tables["consejos_usuario"].items():
            tip = tables["consejos"][consejo_id]
            if user != usuario_id or tip["hogar_id"] != hogar_id:
                continue
            row = self._user_tip(tables, consejo_id, state)
            if row.estado == "pendiente" and row.created_at > pending_created_after:
                pending.append(row)
            elif row.estado == "completada" and row.completada_en > completed_after:
                completed.append(row)
        pending.sort(key=lambda r: str(r.id), reverse=True)
        pending.sort(key=lambda r: r.created_at, reverse=True)
        pending.sort(key=lambda r: PRIORITY_ORDER[r.prioridad])
        completed.sort(key=lambda r: (r.completada_en, str(r.id)), reverse=True)
        return pending + completed

    def get_user_tip(self, session: FakeAlertsSession, usuario_id: UUID, hogar_id: UUID,
                     consejo_id: UUID) -> UserTipRow | None:
        self.calls.append("get_user_tip")
        tables = session.tables()
        state = tables["consejos_usuario"].get((consejo_id, usuario_id))
        tip = tables["consejos"].get(consejo_id)
        if state is None or tip is None or tip["hogar_id"] != hogar_id:
            return None
        return self._user_tip(tables, consejo_id, state)

    def update_user_tip_status(self, session: FakeAlertsSession, usuario_id: UUID,
                               hogar_id: UUID, consejo_id: UUID, estado: str,
                               completada_en: datetime | None) -> bool:
        self.calls.append("update_user_tip_status")
        if (estado == "completada") != (completada_en is not None):
            raise ValueError("estado incoherente con completada_en")
        tables = session.tables()
        tip = tables["consejos"].get(consejo_id)
        key = (consejo_id, usuario_id)
        if tip is None or tip["hogar_id"] != hogar_id or key not in tables["consejos_usuario"]:
            return False
        tables["consejos_usuario"][key] = {"estado": estado, "completada_en": completada_en}
        return True


def zone_id(household: FakeHousehold, zone: str) -> UUID:
    return stable_id("zona", str(household.id), zone)


def install_fake_alerts_database(monkeypatch: pytest.MonkeyPatch) -> FakeAlertsDatabase:
    """Recuperación real + evaluación real de alertas sobre el almacén en memoria."""
    db = FakeAlertsDatabase()
    install_fake_recovery_database(monkeypatch, db, real_alerts=True)
    for module, names in (
        (households_data, ("list_household_zones", "get_household_created_at")),
        (readings_data, ("get_hourly_readings",)),
        (memberships_data, ("list_alert_members", "get_alert_permission")),
        (goals_data, ("get_goal_active_on",)),
        (alerts_data, ("list_existing_event_keys", "insert_alert", "insert_alert_deliveries",
                       "list_user_alerts", "count_unread_alerts", "mark_alerts_read")),
        (tips_data, ("list_latest_tips", "insert_tip", "insert_tip_assignments",
                     "list_user_tips", "get_user_tip", "update_user_tip_status")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, getattr(db, name))
    return db


Spikes = dict[tuple[UUID, datetime], float]


def install_spikes(monkeypatch: pytest.MonkeyPatch, spikes: Spikes) -> None:
    """Cambia el kWh de las lecturas EN VIVO indicadas (sensor, hora) por el valor pedido."""
    real = hour_recovery.generate_readings_for_gaps

    def generate(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        rows = real(*args, **kwargs)
        return [
            {**row, "consumo_kwh": Decimal(str(round(spikes[key], 4)))}
            if (key := (row["sensor_id"], row["fecha_hora"])) in spikes else row
            for row in rows
        ]

    monkeypatch.setattr(hour_recovery, "generate_readings_for_gaps", generate)


def critical_value(average: float) -> float:
    """kWh que deja la zona en crítico frente a su promedio: +100 % o +0,06 kWh, lo que sea más
    (zona_estado: crítico desde +60 % con exceso >= 0,05 kWh)."""
    return average + max(average, 0.06)


def spy_live_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, list[datetime]]]:
    """Envuelve la evaluación real y anota las horas que recibe cada llamada."""
    real: Callable[..., Any] = live_alerts.evaluate_live_hours
    seen: list[dict[str, list[datetime]]] = []

    def spy(session: Any, hogar_id: UUID, hours: Mapping[str, Sequence[datetime]]) -> Any:
        seen.append({zone: list(moments) for zone, moments in hours.items()})
        return real(session, hogar_id, hours)

    monkeypatch.setattr(live_alerts, "evaluate_live_hours", spy)
    return seen
