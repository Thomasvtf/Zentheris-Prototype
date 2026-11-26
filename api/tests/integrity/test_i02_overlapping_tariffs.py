"""I-02 · Integridad: Tarifas solapadas del mismo hogar.

Esperado: Rechazado. Regla: DC-39 (y DC-41: una sola tarifa abierta por hogar; RN-XVI-05).
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Sin base real: el rechazo lo hace Postgres con la restricción de exclusión
`tarifas_sin_solapamiento` (migración 0002). Aquí se comprueba (1) que la migración sigue
declarando esa exclusión sobre `daterange(vigente_desde, vigente_hasta, '[)')` por hogar y el
único parcial de la tarifa abierta (0003), (2) que `insert_tariff` traduce esa violación a
`TariffOverlapError` (el servicio responde 422 VIGENCIA_NO_POSTERIOR) y (3) que cualquier otra
IntegrityError sube tal cual.
TODO(I-02): requiere Postgres local para insertar dos vigencias solapadas y ver el 23P01 real
(`supabase start` o una rama de base, a decisión del equipo).
"""

import re
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.data import tariffs
from app.data.tariffs import TariffOverlapError, insert_tariff
from tests.data.fake_session import FakeDiag, FakeDriverError, FakeSession, integrity_error

MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
EXCLUSION_MESSAGE = (
    'conflicting key value violates exclusion constraint "tarifas_sin_solapamiento"\n'
    "DETAIL: Key (hogar_id, daterange(vigente_desde, vigente_hasta, '[)'::text))=(x, [2026-12-01,)) "
    "conflicts with existing key (hogar_id, daterange(vigente_desde, vigente_hasta, '[)'::text))"
    "=(x, [2026-09-01,))."
)


def _tarifas_hogar_sql() -> str:
    (migration,) = MIGRATIONS.glob("*_0002_*.sql")
    text = migration.read_text(encoding="utf-8")
    match = re.search(r"create table public\.tarifas_hogar \((.*?)\n\);", text, re.DOTALL)
    assert match is not None, "la migración 0002 ya no crea tarifas_hogar"
    return re.sub(r"\s+", " ", match.group(1))


def _insert(session: FakeSession) -> None:
    insert_tariff(
        session,  # type: ignore[arg-type]
        hogar_id=uuid4(),
        operador=None,
        precio_kwh=892.0,
        cargo_fijo_mensual=None,
        vigente_desde=date(2026, 12, 1),
    )


def test_migration_declares_the_half_open_exclusion_per_household() -> None:
    """DC-39: vigencias [desde, hasta) del mismo hogar no pueden solaparse (&&)."""
    sql = _tarifas_hogar_sql()

    assert (
        "constraint tarifas_sin_solapamiento exclude using gist ( hogar_id with =, "
        "daterange(vigente_desde, vigente_hasta, '[)') with && )"
    ) in sql
    assert "constraint tarifas_rango_valido check " in sql
    assert "(vigente_hasta is null or vigente_hasta > vigente_desde)" in sql


def test_migration_declares_a_single_open_tariff_per_household() -> None:
    """DC-41: a lo sumo una tarifa con vigente_hasta nula por hogar."""
    (migration,) = MIGRATIONS.glob("*_0003_*.sql")

    assert (
        "create unique index uq_tarifa_abierta_por_hogar\n"
        "  on public.tarifas_hogar (hogar_id) where vigente_hasta is null;"
    ) in migration.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "orig",
    [
        FakeDriverError("23P01", diag=FakeDiag(tariffs.OVERLAP_CONSTRAINT)),
        FakeDriverError("23P01", message=EXCLUSION_MESSAGE),
    ],
    ids=["diag", "mensaje"],
)
def test_overlapping_tariff_is_rejected_as_tariff_overlap_error(orig: Exception) -> None:
    """Rechazado: la violación de tarifas_sin_solapamiento llega como TariffOverlapError."""
    session = FakeSession(integrity_error(orig, "insert into tarifas_hogar ..."))

    with pytest.raises(TariffOverlapError) as exc_info:
        _insert(session)

    assert exc_info.value.constraint == "tarifas_sin_solapamiento"
    assert session.commits == 0


@pytest.mark.parametrize(
    "orig",
    [
        FakeDriverError("23503", diag=FakeDiag("tarifas_hogar_hogar_id_fkey")),
        FakeDriverError("23514", diag=FakeDiag("tarifas_hogar_precio_kwh_check")),
        FakeDriverError("23P01", diag=FakeDiag("otra_exclusion")),
    ],
    ids=["FK del hogar", "check del precio", "otra exclusión"],
)
def test_other_integrity_errors_are_not_masked(orig: Exception) -> None:
    error = integrity_error(orig, "insert into tarifas_hogar ...")
    session = FakeSession(error)

    with pytest.raises(IntegrityError) as exc_info:
        _insert(session)

    assert exc_info.value is error
