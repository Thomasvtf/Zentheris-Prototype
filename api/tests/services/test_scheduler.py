"""Pruebas de app.services.scheduler sin base, sin red y sin hilos reales.

RN-IV-05 (generación al arrancar y cada hora mientras la API está activa), DC-34. La tarea usa
la recuperación real (`fill_missing_hours`) sobre los dobles en memoria de `recovery_fakes.py`.
El planificador se crea, pero nunca se arranca en estas pruebas.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.data import readings as readings_data
from app.domain.simulator import TIMEZONE
from app.services import hour_recovery
from app.services import scheduler as service
from app.services.scheduler import HOURLY_JOB_ID, GenerationSummary
from tests.services.recovery_fakes import (
    HOURS_OFF,
    LATER,
    NOW,
    FakeHousehold,
    FakeRecoveryDatabase,
    by_key,
    install_fake_recovery_database,
)
from tests.simulator.support import bogota

THREE = ("Consumo compacto", "Consumo familiar", "Consumo amplio")


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeRecoveryDatabase:
    return install_fake_recovery_database(monkeypatch)


@pytest.fixture
def fill_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, Any, datetime]]:
    """Espía de `fill_missing_hours` que delega en la real."""
    calls: list[tuple[Any, Any, datetime]] = []
    real = hour_recovery.fill_missing_hours

    def spy(session: Any, hogar_id: Any, now: datetime | None = None) -> int:
        calls.append((session, hogar_id, now))
        return real(session, hogar_id, now)

    monkeypatch.setattr(hour_recovery, "fill_missing_hours", spy)
    return calls


# ------------------------------------------------------------------ run_hourly_generation


def test_one_failing_household_does_not_stop_the_others(
    db: FakeRecoveryDatabase, fill_calls: list, caplog: pytest.LogCaptureFixture
) -> None:
    households = [db.add_household(FakeHousehold(name)) for name in THREE]
    broken = households[1]
    db.failing_households[broken.id] = RuntimeError(f"caída {broken.id}")
    caplog.set_level(logging.INFO, logger="app.services")

    summary = service.run_hourly_generation(LATER, session_factory=db.session)

    healthy = [households[0], households[2]]
    expected = sum(HOURS_OFF * len(h.sensors) for h in healthy)
    assert summary == GenerationSummary(3, expected, 1)
    for household in healthy:
        rows = db.rows_of(household)
        assert by_key(household.off_rows()).items() <= rows.items()
    assert all(moment <= NOW for sensor, moment in db.rows_of(broken))
    # Una sesión para listar y una por hogar, todas cerradas; el mismo `now` para todos.
    assert len(db.sessions) == 1 + 3
    assert all(session.closed for session in db.sessions)
    assert [call[0] for call in fill_calls] == db.sessions[1:]
    assert sorted(call[1] for call in fill_calls) == sorted(h.id for h in households)
    assert {call[2] for call in fill_calls} == {LATER}
    assert "Generación horaria: hogares=3" in caplog.text
    assert "fallos=1" in caplog.text
    assert not any(str(h.id) in caplog.text for h in households)


def test_a_second_run_saves_nothing(db: FakeRecoveryDatabase) -> None:
    for name in THREE:
        db.add_household(FakeHousehold(name))
    first = service.run_hourly_generation(LATER, session_factory=db.session)
    assert first.readings > 0
    assert service.run_hourly_generation(LATER, session_factory=db.session) == (3, 0, 0)


def test_an_unexpected_error_of_a_household_is_counted(
    db: FakeRecoveryDatabase, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    households = [db.add_household(FakeHousehold(name)) for name in THREE]
    target = households[0].id

    def flaky(session: Any, hogar_id: Any, now: datetime | None = None) -> int:
        if hogar_id == target:
            raise ValueError(f"inesperado {hogar_id}")
        return 2

    monkeypatch.setattr(hour_recovery, "fill_missing_hours", flaky)
    assert service.run_hourly_generation(LATER, session_factory=db.session) == (3, 4, 1)
    assert all(session.closed for session in db.sessions)
    assert "tipo=ValueError" in caplog.text
    assert str(target) not in caplog.text and "inesperado" not in caplog.text


def test_a_failing_session_factory_is_counted(db: FakeRecoveryDatabase) -> None:
    for name in THREE:
        db.add_household(FakeHousehold(name))
    made = iter(range(10))

    def factory():
        if next(made) == 2:  # la segunda sesión de hogar no se puede abrir
            raise ConnectionError("sin conexión")
        return db.session()

    summary = service.run_hourly_generation(LATER, session_factory=factory)
    assert summary.households == 3 and summary.failures == 1


def test_a_failing_list_returns_one_failure_without_raising(
    db: FakeRecoveryDatabase, fill_calls: list, caplog: pytest.LogCaptureFixture
) -> None:
    db.add_household(FakeHousehold("Consumo familiar"))
    db.list_failure = RuntimeError("DETAIL: secreto")

    assert service.run_hourly_generation(LATER, session_factory=db.session) == (0, 0, 1)

    assert fill_calls == []
    assert len(db.sessions) == 1 and db.sessions[0].closed
    assert "tipo=RuntimeError" in caplog.text
    assert "secreto" not in caplog.text


def test_without_households_nothing_happens(db: FakeRecoveryDatabase) -> None:
    assert service.run_hourly_generation(LATER, session_factory=db.session) == (0, 0, 0)


def test_now_defaults_to_one_aware_moment_for_the_whole_run(
    db: FakeRecoveryDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in THREE:
        household = FakeHousehold(name)
        db.households[household.id] = household
    nows: list[datetime] = []

    def record(session: Any, hogar_id: Any, now: datetime | None = None) -> int:
        nows.append(now)
        return 0

    monkeypatch.setattr(hour_recovery, "fill_missing_hours", record)
    service.run_hourly_generation(session_factory=db.session)
    assert len(nows) == 3 and len(set(nows)) == 1
    assert nows[0].utcoffset() is not None


def test_the_default_session_factory_uses_the_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    made: list[Any] = []

    class FakeSessionClass:
        def __init__(self, engine: Any) -> None:
            made.append(engine)

    monkeypatch.setattr(service, "get_engine", lambda: sentinel)
    monkeypatch.setattr(service, "Session", FakeSessionClass)
    service._default_session()
    assert made == [sentinel]


# ------------------------------------------------------------------ planificador


def test_create_scheduler_has_the_hourly_job_without_starting() -> None:
    scheduler = service.create_scheduler()
    try:
        assert isinstance(scheduler, BackgroundScheduler)
        assert not scheduler.running
        jobs = scheduler.get_jobs()
        assert [job.id for job in jobs] == [HOURLY_JOB_ID]
        job = scheduler.get_job(HOURLY_JOB_ID)
        assert job.func is service.run_hourly_generation
        assert isinstance(job.trigger, CronTrigger)
        fields = {field.name: str(field) for field in job.trigger.fields}
        assert fields["minute"] == "0"
        assert fields["hour"] == "*"
        assert job.trigger.timezone == TIMEZONE
        assert job.next_run_time is not None  # también corre al arrancar (RN-IV-05)
        assert abs(job.next_run_time - datetime.now(UTC)) < timedelta(minutes=1)
        assert job.coalesce is True
        assert job.max_instances == 1
        assert job.misfire_grace_time and job.misfire_grace_time > 0
        # Minuto 0 de cada hora, hora de Bogotá, aunque se pregunte en UTC.
        after = job.trigger.get_next_fire_time(None, bogota(2026, 11, 21, 22, 10))
        assert after == bogota(2026, 11, 21, 23)
        midnight = job.trigger.get_next_fire_time(None, datetime(2026, 11, 22, 4, 30, tzinfo=UTC))
        assert midnight == bogota(2026, 11, 22, 0)
    finally:
        assert not scheduler.running


class SchedulerDouble:
    def __init__(self) -> None:
        self.started = 0
        self.shutdowns: list[dict[str, Any]] = []

    def start(self) -> None:
        self.started += 1

    def shutdown(self, **kwargs: Any) -> None:
        self.shutdowns.append(kwargs)


def test_start_without_database_url_returns_none_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def forbidden() -> None:
        raise AssertionError("sin base no se crea el planificador")

    monkeypatch.setattr(service, "create_scheduler", forbidden)
    caplog.set_level(logging.WARNING, logger="app.services.scheduler")

    assert service.start_scheduler(Settings(_env_file=None)) is None

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "DATABASE_URL" in warnings[0].getMessage()


def test_start_with_database_url_starts_the_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    double = SchedulerDouble()
    monkeypatch.setattr(service, "create_scheduler", lambda: double)
    settings = Settings(_env_file=None, DATABASE_URL="postgresql://ejemplo.invalid/falsa")

    assert service.start_scheduler(settings) is double
    assert double.started == 1
    assert double.shutdowns == []


def test_stop_none_does_nothing() -> None:
    service.stop_scheduler(None)


def test_stop_shuts_down_without_waiting() -> None:
    double = SchedulerDouble()
    service.stop_scheduler(double)  # type: ignore[arg-type]
    assert double.shutdowns == [{"wait": False}]


def test_a_household_deleted_after_the_list_is_a_warning_and_a_failure(
    db: FakeRecoveryDatabase, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """23503 de llave foránea: cuenta como fallo, pero se registra como WARNING y no ERROR."""

    class ForeignKeyError(Exception):
        pgcode = "23503"

    households = [db.add_household(FakeHousehold(name)) for name in THREE]
    deleted = households[0]
    real_insert = db.insert_readings_batch

    def insert(session: Any, lecturas: Any) -> int:
        if any(row["sensor_id"] in deleted.sensors.values() for row in lecturas):
            raise IntegrityError("INSERT", {}, ForeignKeyError("DETAIL: secreto"))
        return real_insert(session, lecturas)

    monkeypatch.setattr(readings_data, "insert_readings_batch", insert)
    caplog.set_level(logging.INFO, logger="app.services")

    summary = service.run_hourly_generation(LATER, session_factory=db.session)

    assert summary.households == 3 and summary.failures == 1
    assert summary.readings == sum(HOURS_OFF * len(h.sensors) for h in households[1:])
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert "sqlstate=23503" in caplog.text and "secreto" not in caplog.text
    assert all(session.closed and not session.locks for session in db.sessions)
