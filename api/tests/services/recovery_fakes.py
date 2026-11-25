"""Dobles en memoria de `app.data` para la recuperación de horas y la tarea programada.

Sin base ni red: `get_household_profile`, `get_sensor_gaps`, `insert_readings_batch` y
`list_household_ids_with_active_sensors` (y el candado `lock_household_recovery`) se reemplazan con monkeypatch por funciones que leen y
escriben en `FakeRecoveryDatabase`. Los huecos se calculan como la consulta real: por sensor, de
hora en hora desde su primera lectura hasta `until` inclusive. El candado se anota en la sesión
y se suelta con su commit, rollback o cierre, como pg_advisory_xact_lock. El simulador es el real, con los
perfiles oficiales de `docs/datos/perfiles/`. No demuestra compatibilidad con PostgreSQL.

Fase 8 (DC-35: alertas solo sobre horas en vivo, evaluadas en un SAVEPOINT para que un fallo no
impida guardar las lecturas). `FakeSession.begin_nested()` lo imita (guarda lo pendiente y lo
restaura si el bloque lanza) y, salvo `real_alerts=True`, `live_alerts.evaluate_live_hours` se
reemplaza por un espía que anota
cada llamada en `evaluations`, deja una «alerta» pendiente en la sesión (`pending_alerts`, que el
commit pasa a `saved_alerts`) y lanza `evaluation_failure` si está puesto. Las pruebas de las
alertas reales usan `tests/services/alerts_fakes.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from types import TracebackType
from typing import Any, Self
from uuid import UUID

import pytest

from app.data import households as households_data
from app.data import readings as readings_data
from app.data import simulation_profiles as profiles_data
from app.data.readings import SensorGapRow
from app.data.simulation_profiles import SimulationProfileRow
from app.domain.simulator import generate_backfill, hour_from_index
from app.domain.simulator.engine import simulate_household, to_reading_rows
from app.services import live_alerts
from app.services.live_alerts import LiveEvaluationSummary
from tests.helpers.personalities import load_personalities
from tests.simulator.support import bogota, final_profiles, idx, stable_id

HOURS_OFF = 5
NOW = bogota(2026, 11, 21, 22, 10)  # el apagado cruza la medianoche de sábado a domingo
LATER = NOW + timedelta(hours=HOURS_OFF)
END = idx(2026, 11, 21, 22)  # primera hora sin lectura después del backfill en NOW
START = END - 720

Key = tuple[UUID, datetime]


class FakeHousehold:
    """Hogar con un sensor por zona de su personalidad y su perfil oficial."""

    def __init__(self, personality_name: str, tag: str = "svc") -> None:
        personality = load_personalities()[personality_name]
        self.name = personality_name
        self.id = stable_id("hogar", tag, personality_name)
        self.sensors = {
            zone: stable_id("sensor", tag, personality_name, zone)
            for zone in personality.zone_kwh_per_day
        }
        self.profile = final_profiles()[personality_name]
        self.profile_row = SimulationProfileRow(
            id=stable_id("perfil", personality_name),
            nombre=personality_name,
            activo=True,
            params=self.profile,
        )

    def backfill(self, now: datetime = NOW) -> list[dict[str, Any]]:
        return generate_backfill(self.id, self.profile, self.sensors, now)

    def continuous(self, end: int) -> list[dict[str, Any]]:
        """Lo que habría generado sin apagarse, con la misma frontera (primera lectura)."""
        series = simulate_household(self.id, self.profile, self.sensors, START, end, START)
        return to_reading_rows(self.sensors, series)

    def off_rows(self, hours: int = HOURS_OFF) -> list[dict[str, Any]]:
        """Filas continuas de las `hours` horas siguientes al backfill."""
        off_hours = {hour_from_index(index) for index in range(END, END + hours)}
        return [row for row in self.continuous(END + hours) if row["fecha_hora"] in off_hours]


class FakeSession:
    """Sesión falsa: guarda lo insertado como pendiente hasta el commit."""

    def __init__(self, db: FakeRecoveryDatabase) -> None:
        self.db = db
        self.pending: dict[Key, dict[str, Any]] = {}
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.fail_commit: Exception | None = None
        self.fail_rollback: Exception | None = None
        self.locks: set[UUID] = set()  # candados de recuperación tomados en la transacción
        self.pending_alerts: list[UUID] = []  # lo que deja el espía de alertas
        self.savepoints = 0
        self.savepoint_rollbacks = 0

    def commit(self) -> None:
        self.db.calls.append("commit")
        if self.fail_commit is not None:
            raise self.fail_commit
        self.db.saved.update(self.pending)
        self.db.saved_alerts.extend(self.pending_alerts)
        self.end_transaction()
        self.commits += 1

    def rollback(self) -> None:
        self.db.calls.append("rollback")
        self.rollbacks += 1
        if self.fail_rollback is not None:
            raise self.fail_rollback
        self.end_transaction()

    def close(self) -> None:
        self.end_transaction()
        self.closed = True

    def begin_nested(self) -> FakeSavepoint:
        """SAVEPOINT: si el bloque lanza, se restaura lo pendiente de antes (y sigue lanzando)."""
        self.db.calls.append("savepoint")
        self.savepoints += 1
        return FakeSavepoint(self)

    # --- lo que guarda y restaura un SAVEPOINT (las subclases añaden su estado) -------
    def snapshot(self) -> Any:
        return dict(self.pending), list(self.pending_alerts)

    def restore(self, state: Any) -> None:
        pending, alerts = state
        self.pending = dict(pending)
        self.pending_alerts = list(alerts)

    def end_transaction(self) -> None:
        self.pending.clear()
        self.pending_alerts.clear()
        self.locks.clear()


class FakeSavepoint:
    """Contexto de `begin_nested()`: revierte solo lo hecho dentro del bloque si lanza."""

    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.state: Any = None

    def __enter__(self) -> Self:
        self.state = self.session.snapshot()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        db = self.session.db
        if exc_type is None:
            db.calls.append("release")
            return False
        db.calls.append("savepoint_rollback")
        self.session.savepoint_rollbacks += 1
        if db.savepoint_rollback_failure is not None:
            raise db.savepoint_rollback_failure
        self.session.restore(self.state)
        return False  # la excepción sigue: la captura hour_recovery


class FakeRecoveryDatabase:
    """Almacén en memoria: hogares, perfiles y lecturas confirmadas."""

    def __init__(self) -> None:
        self.households: dict[UUID, FakeHousehold] = {}
        self.saved: dict[Key, dict[str, Any]] = {}
        self.calls: list[str] = []
        self.locked: list[UUID] = []  # hogar de cada candado pedido, en orden
        self.failures: dict[str, Exception] = {}  # paso → excepción que lanza
        self.failing_households: dict[UUID, Exception] = {}  # perfil que falla por hogar
        self.sessions: list[FakeSession] = []
        self.list_failure: Exception | None = None
        # Espía de `live_alerts.evaluate_live_hours` (fase 8): (hogar, horas por zona).
        self.evaluations: list[tuple[UUID, dict[str, list[datetime]]]] = []
        self.evaluation_failure: Exception | None = None
        self.savepoint_rollback_failure: Exception | None = None
        self.saved_alerts: list[UUID] = []

    # --- preparación ---------------------------------------------------------------
    def add_household(self, household: FakeHousehold, now: datetime = NOW) -> FakeHousehold:
        self.households[household.id] = household
        self.store(household.backfill(now))
        return household

    def store(self, rows: Sequence[dict[str, Any]]) -> None:
        self.saved.update({_key(row): row for row in rows})

    def session(self) -> FakeSession:
        session = FakeSession(self)
        self.sessions.append(session)
        return session

    def rows_of(self, household: FakeHousehold) -> dict[Key, dict[str, Any]]:
        sensors = set(household.sensors.values())
        return {key: row for key, row in self.saved.items() if key[0] in sensors}

    def _fail(self, step: str) -> None:
        if step in self.failures:
            raise self.failures[step]

    # --- dobles de app.data --------------------------------------------------------
    def lock_household_recovery(self, session: FakeSession, hogar_id: UUID) -> None:
        self.calls.append("lock")
        self._fail("lock")
        self.locked.append(hogar_id)
        session.locks.add(hogar_id)

    def get_household_profile(
        self, session: FakeSession, hogar_id: UUID
    ) -> SimulationProfileRow | None:
        self.calls.append("profile")
        self._fail("profile")
        if hogar_id in self.failing_households:
            raise self.failing_households[hogar_id]
        household = self.households.get(hogar_id)
        return None if household is None else household.profile_row

    def get_sensor_gaps(
        self, session: FakeSession, hogar_id: UUID, until: datetime
    ) -> list[SensorGapRow]:
        self.calls.append("gaps")
        if until.utcoffset() is None:
            raise ValueError("`until` debe llevar zona horaria.")
        if hogar_id not in session.locks:
            raise AssertionError("huecos leídos sin el candado del hogar en esta transacción")
        self._fail("gaps")
        visible = {**self.saved, **session.pending}
        gaps = []
        for zone, sensor in sorted(self.households[hogar_id].sensors.items()):
            stored = {moment for sensor_id, moment in visible if sensor_id == sensor}
            if not stored:
                gaps.append(SensorGapRow(sensor, zone, None, []))
                continue
            first = min(stored)
            missing, moment = [], first
            while moment <= until:
                if moment not in stored:
                    missing.append(moment)
                moment += timedelta(hours=1)
            gaps.append(SensorGapRow(sensor, zone, first, missing))
        return gaps

    def insert_readings_batch(
        self, session: FakeSession, lecturas: Sequence[dict[str, Any]]
    ) -> int:
        """ON CONFLICT DO NOTHING: solo cuenta las filas nuevas."""
        self.calls.append("insert")
        if not session.locks:
            raise AssertionError("lecturas insertadas sin el candado de recuperación")
        self._fail("insert")
        inserted = 0
        for row in lecturas:
            key = _key(row)
            if key in self.saved or key in session.pending:
                continue
            session.pending[key] = row
            inserted += 1
        return inserted

    def evaluate_live_hours(
        self,
        session: FakeSession,
        hogar_id: UUID,
        live_hours_by_zone_type: Any,
    ) -> LiveEvaluationSummary:
        """Espía: anota la llamada, deja una «alerta» pendiente y falla si se pidió."""
        self.calls.append("alerts")
        hours = {zone: list(moments) for zone, moments in live_hours_by_zone_type.items()}
        self.evaluations.append((hogar_id, hours))
        session.pending_alerts.append(hogar_id)
        if self.evaluation_failure is not None:
            raise self.evaluation_failure
        return LiveEvaluationSummary(alerts=1, tips=0)

    def list_household_ids_with_active_sensors(self, session: FakeSession) -> list[UUID]:
        self.calls.append("list")
        if self.list_failure is not None:
            raise self.list_failure
        return sorted(self.households)


def _key(row: dict[str, Any]) -> Key:
    return row["sensor_id"], row["fecha_hora"]


def by_key(rows: Sequence[dict[str, Any]]) -> dict[Key, dict[str, Any]]:
    return {_key(row): row for row in rows}


def install_fake_recovery_database(
    monkeypatch: pytest.MonkeyPatch,
    db: FakeRecoveryDatabase | None = None,
    real_alerts: bool = False,
) -> FakeRecoveryDatabase:
    """Instala los dobles de la recuperación. Con `real_alerts=False`, espía de las alertas."""
    db = FakeRecoveryDatabase() if db is None else db
    if not real_alerts:
        monkeypatch.setattr(live_alerts, "evaluate_live_hours", db.evaluate_live_hours)
    monkeypatch.setattr(profiles_data, "get_household_profile", db.get_household_profile)
    monkeypatch.setattr(readings_data, "lock_household_recovery", db.lock_household_recovery)
    monkeypatch.setattr(readings_data, "get_sensor_gaps", db.get_sensor_gaps)
    monkeypatch.setattr(readings_data, "insert_readings_batch", db.insert_readings_batch)
    monkeypatch.setattr(
        households_data,
        "list_household_ids_with_active_sensors",
        db.list_household_ids_with_active_sensors,
    )
    return db
