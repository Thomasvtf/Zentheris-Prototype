"""B-01 · Backfill: Onboarding de un dúplex con 9 zonas.

Esperado: 6.480 lecturas, sin duplicados, `calidad=simulada` **[ref local]**. Regla: RN-IV-01.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Parte de dominio: lo que genera el simulador. La inserción en PostgreSQL no se prueba aquí."""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.domain.simulator import HOURS_BACKFILL, generate_backfill, hour_from_index
from app.domain.zone_rules import PERSONALITIES, ZONE_TYPES
from tests.simulator.support import bogota, create_household, final_profiles, idx

NOW = bogota(2026, 11, 22, 15, 23)
HOUSEHOLD = create_household("b01", "duplex", ZONE_TYPES)


@pytest.fixture(scope="module")
def rows():
    assert HOUSEHOLD.personality == "Consumo amplio"
    profile = final_profiles()[HOUSEHOLD.personality]
    return generate_backfill(HOUSEHOLD.id, profile, HOUSEHOLD.sensors, NOW)


def test_duplex_with_nine_zones_generates_6480_readings(rows):
    assert HOURS_BACKFILL == 720
    assert len(rows) == 6480


def test_there_are_no_duplicates_per_sensor_and_hour(rows):
    assert len({(row["sensor_id"], row["fecha_hora"]) for row in rows}) == 6480


def test_every_row_is_simulated_and_storable(rows):
    for row in rows:
        assert set(row) == {"sensor_id", "fecha_hora", "consumo_kwh", "calidad"}
        assert row["calidad"] == "simulada"
        assert isinstance(row["consumo_kwh"], Decimal)
        assert row["consumo_kwh"] >= 0
        assert row["consumo_kwh"].as_tuple().exponent == -4  # NUMERIC(12,4)


def test_every_sensor_has_the_720_hours_up_to_the_last_complete_hour(rows):
    last = idx(2026, 11, 22, 14)
    expected = {hour_from_index(index) for index in range(last - 719, last + 1)}
    for sensor_id in HOUSEHOLD.sensors.values():
        assert {row["fecha_hora"] for row in rows if row["sensor_id"] == sensor_id} == expected
    assert {row["fecha_hora"].utcoffset() for row in rows} == {timedelta(hours=-5)}


@pytest.mark.parametrize("name", PERSONALITIES)
def test_nine_zones_with_any_profile_keep_the_row_count(name):
    """El respaldo de RN-X-04 y zonas de base 0 no cambian cuántas lecturas se guardan."""
    rows = generate_backfill(HOUSEHOLD.id, final_profiles()[name], HOUSEHOLD.sensors, NOW)
    assert len({(row["sensor_id"], row["fecha_hora"]) for row in rows}) == len(rows) == 6480
