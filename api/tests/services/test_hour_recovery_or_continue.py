"""`fill_missing_hours_or_continue`: la recuperación de las consultas (fases 6-10).

Decisión de Nicolás (23/11/2026): si la recuperación falla, la consulta sigue con los datos
guardados; WARNING sin ids ni mensajes de la base; nunca lanza `HourRecoveryError`. RN-IV-05,
DC-34. Dobles de `recovery_fakes.py` (sin base ni red).
"""

import logging

import pytest
from sqlalchemy.exc import OperationalError

from app.services import hour_recovery as service
from app.services.hour_recovery import RECOVERY_SKIPPED_MESSAGE
from tests.services.recovery_fakes import (
    HOURS_OFF,
    LATER,
    FakeHousehold,
    FakeRecoveryDatabase,
    install_fake_recovery_database,
)

STEPS = ("lock", "profile", "gaps", "insert", "commit")
SECRET = "DETAIL: Key (hogar_id)=(secreto) already exists"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeRecoveryDatabase:
    return install_fake_recovery_database(monkeypatch)


def test_returns_saved_count_when_recovery_works(
    db: FakeRecoveryDatabase, caplog: pytest.LogCaptureFixture
) -> None:
    household = db.add_household(FakeHousehold("Consumo familiar", tag="continue"))
    with caplog.at_level(logging.WARNING):
        saved = service.fill_missing_hours_or_continue(db.session(), household.id, LATER)
    assert saved == HOURS_OFF * len(household.sensors)
    assert RECOVERY_SKIPPED_MESSAGE not in caplog.text


def test_returns_zero_without_missing_hours(db: FakeRecoveryDatabase) -> None:
    household = db.add_household(FakeHousehold("Consumo compacto", tag="continue"))
    session = db.session()
    assert service.fill_missing_hours_or_continue(session, household.id, LATER) > 0
    assert service.fill_missing_hours_or_continue(db.session(), household.id, LATER) == 0


@pytest.mark.parametrize("step", STEPS)
def test_failure_returns_none_and_warns_without_ids(
    db: FakeRecoveryDatabase,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    step: str,
) -> None:
    household = db.add_household(FakeHousehold("Consumo amplio", tag="continue"))
    error = OperationalError("INSERT", {}, Exception(f"{SECRET} {household.id}"))
    session = db.session()
    if step == "commit":
        session.fail_commit = error
    else:
        db.failures[step] = error
    before = dict(db.saved)

    with caplog.at_level(logging.WARNING):
        result = service.fill_missing_hours_or_continue(session, household.id, LATER)

    assert result is None
    assert db.saved == before  # revertida: nada nuevo confirmado
    warnings = [r for r in caplog.records if r.getMessage() == RECOVERY_SKIPPED_MESSAGE]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    assert str(household.id) not in caplog.text
    assert "secreto" not in caplog.text and "DETAIL" not in caplog.text


def test_invalid_profile_also_continues(
    db: FakeRecoveryDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    household = db.add_household(FakeHousehold("Consumo eficiente", tag="continue"))

    def broken(params: object) -> object:
        raise ValueError("perfil inválido")

    monkeypatch.setattr(service, "validate_or_raise", broken)
    assert service.fill_missing_hours_or_continue(db.session(), household.id, LATER) is None


def test_naive_now_is_still_a_programming_error(db: FakeRecoveryDatabase) -> None:
    household = db.add_household(FakeHousehold("Consumo intermedio", tag="continue"))
    with pytest.raises(ValueError):
        service.fill_missing_hours_or_continue(
            db.session(), household.id, LATER.replace(tzinfo=None)
        )
    assert db.calls == []
