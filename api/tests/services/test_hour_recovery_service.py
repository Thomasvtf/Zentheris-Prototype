"""Pruebas de app.services.hour_recovery con `app.data.*` falso en memoria (sin base ni red).

B-04 de servicio · Servidor apagado 5 h y luego una consulta: 5 h × zonas nuevas, idénticas a
las de una generación continua. RN-IV-05, DC-34, RN-IV-07; DC-35 (no genera alertas).
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md. Los dobles están en `recovery_fakes.py`.
"""

import logging
from datetime import UTC, timedelta

import pytest
from sqlalchemy.exc import OperationalError

from app.data import alerts as alerts_data
from app.data import readings as readings_data
from app.domain.simulator import hour_from_index
from app.services import hour_recovery as service
from app.services.hour_recovery import HOUR_RECOVERY_FAILED_MESSAGE, HourRecoveryError
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.services.recovery_fakes import (
    END,
    HOURS_OFF,
    LATER,
    NOW,
    FakeHousehold,
    FakeRecoveryDatabase,
    by_key,
    install_fake_recovery_database,
)

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)
STEPS = ("lock", "profile", "validate", "gaps", "insert", "commit")
FIRST_OFF_HOUR = hour_from_index(END)  # 22:00 del sábado: la primera hora apagada
SECRET = "DETAIL: Key (hogar_id)=(secreto) already exists"


class PgError(Exception):
    """Error del controlador con SQLSTATE, como psycopg."""

    pgcode = "40001"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeRecoveryDatabase:
    return install_fake_recovery_database(monkeypatch)


@pytest.fixture
def no_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    """DC-35: la recuperación no toca alertas (fase 8)."""

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("la recuperación no debe generar alertas")

    for name in dir(alerts_data):
        if name.startswith(("insert", "create")):
            monkeypatch.setattr(alerts_data, name, forbidden)


# ------------------------------------------------------------------ B-04 por personalidad


@each_personality
def test_five_hours_off_store_exactly_the_continuous_rows(
    db: FakeRecoveryDatabase, no_alerts: None, name: str
) -> None:
    household = db.add_household(FakeHousehold(name))
    session = db.session()
    expected = household.off_rows()

    saved = service.fill_missing_hours(session, household.id, LATER)

    assert saved == HOURS_OFF * len(household.sensors)
    new = {key: row for key, row in db.rows_of(household).items() if key[1] >= FIRST_OFF_HOUR}
    assert new == by_key(expected)
    # Las 5 h cruzan la medianoche y solo hay sensores de las zonas del hogar (RN-IV-07).
    assert len({moment.date() for _, moment in new}) == 2
    assert {sensor for sensor, _ in new} == set(household.sensors.values())
    # Backfill + recuperación = generación continua completa, sin huecos ni duplicados.
    assert db.rows_of(household) == by_key(household.continuous(END + HOURS_OFF))
    assert session.commits == 1
    assert session.rollbacks == 0
    # El candado va primero, con el mismo hogar, y el commit lo suelta.
    assert db.calls == ["lock", "profile", "gaps", "insert", "commit"]
    assert db.locked == [household.id]
    assert not session.locks


@each_personality
def test_the_second_call_saves_nothing_and_does_not_commit(
    db: FakeRecoveryDatabase, name: str
) -> None:
    household = db.add_household(FakeHousehold(name))
    session = db.session()
    service.fill_missing_hours(session, household.id, LATER)
    before = dict(db.saved)
    db.calls.clear()

    assert service.fill_missing_hours(session, household.id, LATER) == 0

    assert db.saved == before
    # Sin filas no hay commit, pero sí rollback: suelta el candado.
    assert db.calls == ["lock", "profile", "gaps", "rollback"]
    assert session.commits == 1
    assert session.rollbacks == 1
    assert not session.locks


@each_personality
def test_hour_by_hour_equals_the_continuous_generation(db: FakeRecoveryDatabase, name: str) -> None:
    household = db.add_household(FakeHousehold(name))
    session = db.session()
    for hour in range(1, HOURS_OFF + 1):
        saved = service.fill_missing_hours(session, household.id, NOW + timedelta(hours=hour))
        assert saved == len(household.sensors)
        assert session.commits == hour  # un commit por llamada con datos
    assert db.rows_of(household) == by_key(household.continuous(END + HOURS_OFF))


def test_before_the_next_complete_hour_there_is_nothing_to_save(db: FakeRecoveryDatabase) -> None:
    household = db.add_household(FakeHousehold("Consumo familiar"))
    session = db.session()
    assert service.fill_missing_hours(session, household.id, NOW + timedelta(minutes=49)) == 0
    assert "insert" not in db.calls
    assert session.commits == 0
    assert session.rollbacks == 1
    assert not session.locks


def test_hours_in_utc_give_the_same_rows(db: FakeRecoveryDatabase) -> None:
    household = db.add_household(FakeHousehold("Consumo intermedio"))
    session = db.session()
    assert service.fill_missing_hours(session, household.id, LATER.astimezone(UTC)) == (
        HOURS_OFF * len(household.sensors)
    )
    new = {key: row for key, row in db.rows_of(household).items() if key[1] >= FIRST_OFF_HOUR}
    assert new == by_key(household.off_rows())


def test_internal_gaps_are_filled_with_the_original_rows(db: FakeRecoveryDatabase) -> None:
    """A13: también completa huecos internos, sin repetir lo que existe."""
    household = db.add_household(FakeHousehold("Consumo amplio"))
    original = dict(db.saved)
    first = min(moment for _, moment in original)
    holes = {first + timedelta(hours=offset) for offset in (1, 100, 719)}
    removed = [key for key in original if key[1] in holes]
    for key in removed:
        del db.saved[key]
    session = db.session()

    saved = service.fill_missing_hours(session, household.id, NOW)

    assert saved == len(removed) == 3 * len(household.sensors)
    assert db.saved == original


def test_only_new_readings_are_counted_and_a_write_outside_the_lock_warns(
    db: FakeRecoveryDatabase, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Si alguien guardó una hora sin el candado, no se cuenta dos veces y queda un WARNING."""
    household = db.add_household(FakeHousehold("Consumo eficiente"))
    rival = household.off_rows()[0]
    real_gaps = db.get_sensor_gaps

    def gaps_then_race(session, hogar_id, until):
        gaps = real_gaps(session, hogar_id, until)
        db.store([rival])  # otra escritura, sin candado, confirma esta fila
        return gaps

    monkeypatch.setattr(readings_data, "get_sensor_gaps", gaps_then_race)
    expected = HOURS_OFF * len(household.sensors)
    saved = service.fill_missing_hours(db.session(), household.id, LATER)
    assert saved == expected - 1
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert f"guardadas={expected - 1} generadas={expected}" in message
    assert str(household.id) not in message and str(rival["sensor_id"]) not in message


# ------------------------------------------------------------------ casos sin datos


def test_unknown_household_returns_zero_and_releases_the_lock(db: FakeRecoveryDatabase) -> None:
    session = db.session()
    unknown = FakeHousehold("Consumo familiar", tag="no-existe")
    assert service.fill_missing_hours(session, unknown.id, LATER) == 0
    assert db.calls == ["lock", "profile", "rollback"]
    assert db.locked == [unknown.id]
    assert session.commits == 0
    assert session.rollbacks == 1
    assert not session.locks


def test_now_without_timezone_is_rejected_before_any_sql(db: FakeRecoveryDatabase) -> None:
    household = db.add_household(FakeHousehold("Consumo compacto"))
    session = db.session()
    with pytest.raises(ValueError):
        service.fill_missing_hours(session, household.id, LATER.replace(tzinfo=None))
    assert db.calls == []
    assert session.commits == session.rollbacks == 0


def test_now_defaults_to_the_current_time(
    db: FakeRecoveryDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin `now` usa el reloj (con zona horaria): aquí, una hora completa después del backfill."""
    household = db.add_household(FakeHousehold("Consumo familiar"))

    class Clock(service.datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) + timedelta(hours=1)

    monkeypatch.setattr(service, "datetime", Clock)
    assert service.fill_missing_hours(db.session(), household.id) == len(household.sensors)


# ------------------------------------------------------------------ fallos


def _break(db: FakeRecoveryDatabase, session, household: FakeHousehold, step: str) -> None:
    error = OperationalError("SELECT 1", {}, PgError(f"{SECRET} {household.id}"))
    if step == "commit":
        session.fail_commit = error
    elif step == "validate":
        household.profile_row.params.clear()  # perfil inválido: sin parámetros
    else:
        db.failures[step] = error


@pytest.mark.parametrize("step", STEPS)
def test_any_failure_rolls_back_and_raises_without_data(
    db: FakeRecoveryDatabase, caplog: pytest.LogCaptureFixture, step: str
) -> None:
    household = db.add_household(FakeHousehold("Consumo familiar"))
    before = dict(db.saved)
    session = db.session()
    _break(db, session, household, step)
    caplog.set_level(logging.INFO, logger="app.services.hour_recovery")

    with pytest.raises(HourRecoveryError) as raised:
        service.fill_missing_hours(session, household.id, LATER)

    assert str(raised.value) == HOUR_RECOVERY_FAILED_MESSAGE
    assert raised.value.__cause__ is None and raised.value.__suppress_context__
    assert session.rollbacks == 1
    assert session.commits == 0
    assert db.saved == before
    assert not session.pending
    assert not session.locks
    log = caplog.text
    assert "Recuperación de horas fallida" in log
    assert "origen=app." in log
    assert SECRET not in log and "secreto" not in log
    assert str(household.id) not in log
    assert "Horas recuperadas" not in log
    if step != "validate":
        assert "tipo=OperationalError sqlstate=40001" in log
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_a_deleted_household_foreign_key_error_is_a_warning(
    db: FakeRecoveryDatabase, caplog: pytest.LogCaptureFixture
) -> None:
    """Hogar borrado entre el listado y la inserción: 23503, WARNING y no ERROR."""

    class ForeignKeyError(Exception):
        pgcode = "23503"

    household = db.add_household(FakeHousehold("Consumo compacto"))
    db.failures["insert"] = OperationalError("INSERT", {}, ForeignKeyError(SECRET))
    session = db.session()

    with pytest.raises(HourRecoveryError):
        service.fill_missing_hours(session, household.id, LATER)

    levels = {r.levelno for r in caplog.records if r.name == "app.services.hour_recovery"}
    assert levels == {logging.WARNING}
    assert "sqlstate=23503" in caplog.text
    assert SECRET not in caplog.text and str(household.id) not in caplog.text
    assert session.rollbacks == 1 and not session.locks


def test_a_failed_rollback_still_raises_the_recovery_error(
    db: FakeRecoveryDatabase, caplog: pytest.LogCaptureFixture
) -> None:
    household = db.add_household(FakeHousehold("Consumo familiar"))
    session = db.session()
    session.fail_commit = RuntimeError(f"conexión perdida {household.id}")
    session.fail_rollback = OperationalError("ROLLBACK", {}, PgError(SECRET))

    with pytest.raises(HourRecoveryError):
        service.fill_missing_hours(session, household.id, LATER)

    assert session.rollbacks == 1
    assert "Reversión de la recuperación de horas fallida" in caplog.text
    assert SECRET not in caplog.text and str(household.id) not in caplog.text


def test_success_logs_count_and_time_without_ids(
    db: FakeRecoveryDatabase, caplog: pytest.LogCaptureFixture
) -> None:
    household = db.add_household(FakeHousehold("Consumo amplio"))
    caplog.set_level(logging.INFO, logger="app.services.hour_recovery")
    service.fill_missing_hours(db.session(), household.id, LATER)
    records = [r for r in caplog.records if r.name == "app.services.hour_recovery"]
    assert len(records) == 1 and records[0].levelno == logging.INFO
    message = records[0].getMessage()
    assert f"lecturas={HOURS_OFF * len(household.sensors)}" in message
    assert "total_ms=" in message
    assert str(household.id) not in message
    assert not any(str(sensor) in message for sensor in household.sensors.values())
