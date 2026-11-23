"""B-02 · Backfill: Falla forzada a mitad de la transacción.

Esperado: 500 `BACKFILL_FALLIDO` y 0 filas del hogar. Regla: RN-X-03.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Con `app.data.*` falso en memoria: se comprueba que el servicio revierte en cada paso. Que
PostgreSQL deje 0 filas tras la reversión no se prueba aquí."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.data import readings as readings_data
from app.domain.simulator import HOURS_BACKFILL
from app.domain.zone_rules import BASIC_ZONES, FALLBACK_PERSONALITY, ZONE_TYPES
from app.errors import ApiError, CodigoError, register_error_handlers
from app.services import onboarding as service
from tests.helpers.onboarding import (
    HOUSEHOLD_NAME,
    NOW,
    REFERENCE_HOUSEHOLDS,
    STEPS,
    USER_ID,
    FakeDatabase,
    install_fake_database,
    make_payload,
    missing_profile_error,
    run,
    run_error,
)
from tests.helpers.personalities import PERSONALITY_ORDER

SECRET = f"detalle interno {USER_ID} {HOUSEHOLD_NAME}"


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeDatabase:
    return install_fake_database(monkeypatch)


def assert_backfill_failed(fake: FakeDatabase, error: ApiError) -> None:
    """500 con el código exacto, sin rastro de la causa y con la transacción revertida."""
    assert (error.status_code, error.codigo) == (500, CodigoError.BACKFILL_FALLIDO)
    assert error.detalles is None
    assert error.__cause__ is None and error.__suppress_context__
    assert SECRET not in error.mensaje and HOUSEHOLD_NAME not in error.mensaje
    assert fake.rollbacks == 1
    assert fake.events[-1] == "rollback"
    fake.assert_nothing_saved()


@pytest.mark.parametrize("step", STEPS)
def test_failure_in_any_step_reverts_everything(fake: FakeDatabase, step: str) -> None:
    fake.failures[step] = RuntimeError(SECRET)
    assert_backfill_failed(fake, run_error(fake))
    assert fake.events == [*STEPS[: STEPS.index(step) + 1], "rollback"]


@pytest.mark.parametrize("step", STEPS)
@pytest.mark.parametrize("failure", [ValueError, LookupError, ArithmeticError, TimeoutError])
def test_the_type_of_the_exception_does_not_matter(
    fake: FakeDatabase, step: str, failure: type[Exception]
) -> None:
    """Un ValueError posterior a las zonas no se confunde con una selección inválida (422)."""
    fake.failures[step] = failure(SECRET)
    assert_backfill_failed(fake, run_error(fake))


@pytest.mark.parametrize("name", PERSONALITY_ORDER)
def test_failure_after_generating_reverts_for_each_personality(
    fake: FakeDatabase, name: str
) -> None:
    fake.failures["insert_readings_batch"] = RuntimeError(SECRET)
    assert_backfill_failed(fake, run_error(fake, make_payload(*REFERENCE_HOUSEHOLDS[name])))


def test_failure_halfway_through_the_batch_reverts_the_rows_already_written(
    fake: FakeDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    def half_and_fail(_session: Any, lecturas: list[dict[str, Any]]) -> int:
        fake.pending["lecturas"].extend(lecturas[: len(lecturas) // 2])
        raise RuntimeError(SECRET)

    monkeypatch.setattr(readings_data, "insert_readings_batch", half_and_fail)
    assert_backfill_failed(fake, run_error(fake, make_payload("duplex", ZONE_TYPES)))


@pytest.mark.parametrize("step", ["insert_zones", "insert_zone_sensors", "insert_readings_batch"])
def test_a_different_row_count_reverts_everything(fake: FakeDatabase, step: str) -> None:
    """DC-38 y RN-IV-01: zonas, sensores y 720 lecturas por zona, ni una menos."""
    fake.short_counts[step] = 1
    assert_backfill_failed(fake, run_error(fake))
    assert "commit" not in fake.events


def test_more_readings_than_720_per_zone_reverts_everything(
    fake: FakeDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = service.generate_backfill
    monkeypatch.setattr(
        service,
        "generate_backfill",
        lambda hogar_id, profile, sensors, now: [
            *real(hogar_id, profile, sensors, now),
            {"sensor_id": next(iter(sensors.values())), "fecha_hora": now},
        ],
    )
    assert_backfill_failed(fake, run_error(fake))


def test_missing_profile_of_the_user_is_404_ficha_no_creada(fake: FakeDatabase) -> None:
    """Sin ficha (23503): 404 `FICHA_NO_CREADA` (contrato 0.2.8) y nada guardado."""
    fake.failures["insert_admin_membership"] = missing_profile_error()
    error = run_error(fake)
    assert (error.status_code, error.codigo) == (404, CodigoError.FICHA_NO_CREADA)
    assert error.detalles is None
    assert error.__cause__ is None and error.__suppress_context__
    assert SECRET not in error.mensaje and HOUSEHOLD_NAME not in error.mensaje
    assert fake.rollbacks == 1
    assert fake.events[-1] == "rollback"
    fake.assert_nothing_saved()


def test_without_any_active_personality_nothing_is_written(fake: FakeDatabase) -> None:
    fake.set_active(FALLBACK_PERSONALITY, False)
    assert_backfill_failed(fake, run_error(fake))
    assert "insert_household" not in fake.events


def test_without_profiles_in_the_table_nothing_is_written(fake: FakeDatabase) -> None:
    fake.profiles.clear()
    assert_backfill_failed(fake, run_error(fake))
    assert "insert_household" not in fake.events


def test_invalid_profile_parameters_write_nothing(fake: FakeDatabase) -> None:
    fake.profiles[FALLBACK_PERSONALITY].params["humor_min"] = -1.0
    assert_backfill_failed(fake, run_error(fake))
    assert "insert_household" not in fake.events


def test_naive_clock_reverts_everything(fake: FakeDatabase) -> None:
    """Sin zona horaria no se sabe cuál es la última hora completa."""
    with pytest.raises(ApiError) as caught:
        run(fake, now=NOW.replace(tzinfo=None))
    assert_backfill_failed(fake, caught.value)


@pytest.mark.parametrize("step", STEPS)
def test_a_failed_rollback_still_answers_backfill_failed(fake: FakeDatabase, step: str) -> None:
    fake.failures[step] = RuntimeError(SECRET)
    fake.rollback_failure = RuntimeError(SECRET)
    error = run_error(fake)
    assert (error.status_code, error.codigo) == (500, CodigoError.BACKFILL_FALLIDO)
    assert error.__cause__ is None and error.__suppress_context__
    assert SECRET not in error.mensaje
    assert fake.commits == 0
    assert all(not rows for rows in fake.saved.values())


def test_retry_after_the_failure_creates_the_household_once(fake: FakeDatabase) -> None:
    """Reintentar repite la misma llamada (sección 7.1)."""
    fake.failures["insert_readings_batch"] = RuntimeError(SECRET)
    run_error(fake)
    fake.failures.clear()
    run(fake)
    assert len(fake.saved["hogares"]) == len(fake.saved["hogar_miembros"]) == 1
    assert len(fake.saved["lecturas"]) == HOURS_BACKFILL * len(BASIC_ZONES)


def test_http_response_has_only_the_contract_error(fake: FakeDatabase) -> None:
    """La respuesta 500 lleva {codigo, mensaje, detalles} y nada de la excepción (S-01)."""
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/onboarding")
    def onboarding() -> Any:
        return run(fake)

    fake.failures["insert_readings_batch"] = RuntimeError(SECRET)
    response = TestClient(app).post("/onboarding")
    assert response.status_code == 500
    assert response.json() == {
        "codigo": "BACKFILL_FALLIDO",
        "mensaje": service.BACKFILL_FAILED_MESSAGE,
        "detalles": None,
    }
    fake.assert_nothing_saved()
