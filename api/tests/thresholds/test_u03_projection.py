"""U-03 · Proyección: Fórmula de RN-XIII-05 con cargo fijo solo en Mes.

Esperado: Igual a la referencia **[ref]**. Regla: RN-XIII-05.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

`project_period` y `project_cost` frente a `proyeccion_cierre` y `proyeccion_cop` de
`docs/datos/motor_estados_ref.py` (DC-30), con los promedios reales de las 5 personalidades, y la
proyección completa de `evaluate_history` en Día, Semana y Mes.
"""

import importlib.util
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest

from app.domain import history as H
from tests.domain.history_support import (
    FIXED_CHARGE,
    NOW,
    PRICE,
    each_period,
    each_personality,
    evaluate,
    reference_readings,
    tariffs,
    zone_ids,
)
from tests.helpers.personalities import PersonalityAverages

REFERENCE_PATH = Path(__file__).resolve().parents[3] / "docs" / "datos" / "motor_estados_ref.py"
# Desde el jueves 26/11 14:20: horas 14..23 de hoy y días completos restantes por periodo.
REMAINING_HOURS = range(14, 24)
REMAINING_DAYS = {"dia": 0, "semana": 3, "mes": 4}


@cache
def reference_engine() -> ModuleType:
    spec = importlib.util.spec_from_file_location("motor_estados_ref", REFERENCE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@each_personality
def test_formula_equals_reference(personality: PersonalityAverages) -> None:
    ref = reference_engine()
    cumulative = sum(personality.household_kwh_for_hour(h) for h in range(14))
    remaining = [personality.household_kwh_for_hour(h) for h in REMAINING_HOURS]
    for days in (0, 3, 4, 30):
        expected = ref.proyeccion_cierre(cumulative, remaining, days, personality.kwh_per_day)
        got = H.project_period(cumulative, remaining, days, personality.kwh_per_day)
        assert got == expected
        for fixed in (None, 0, FIXED_CHARGE):
            for is_month in (True, False):
                assert H.project_cost(cumulative * PRICE, got, cumulative, PRICE, fixed,
                                      is_month) == ref.proyeccion_cop(
                    cumulative * PRICE, got, cumulative, PRICE, fixed, is_month)


def test_fixed_charge_only_in_month() -> None:
    assert H.project_cost(1000, 19, 10, 800, FIXED_CHARGE, is_month=True) == 1000 + 7200 + 12000
    assert H.project_cost(1000, 19, 10, 800, FIXED_CHARGE, is_month=False) == 1000 + 7200
    assert H.project_cost(1000, 19, 10, 800, None, is_month=True) == 1000 + 7200


def expected_projection(personality, period, total, zones=None, include_fixed=False):
    ref = reference_engine()
    remaining = [personality.household_kwh_for_hour(h, zones) for h in REMAINING_HOURS]
    daily = sum(personality.household_kwh_for_hour(h, zones) for h in range(24))
    kwh = ref.proyeccion_cierre(total, remaining, REMAINING_DAYS[period], daily)
    return ref.proyeccion_cop(total * PRICE, kwh, total, PRICE, FIXED_CHARGE, include_fixed)


@each_personality
@each_period
def test_history_projection_general(personality: PersonalityAverages, period: str) -> None:
    """General: proyección igual a la referencia; cargo fijo solo en Mes."""
    readings = reference_readings(personality, NOW)
    rng = H.period_range(period, NOW, 30)
    result = evaluate(readings, period, tariffs_by_date=tariffs(rng.start.date(), NOW.date()))
    assert result.has_tariff
    assert result.cost.cost_cop == pytest.approx(result.total_kwh * PRICE, rel=1e-12)
    assert result.cost.includes_fixed_charge is (period == "mes")
    expected = expected_projection(personality, period, result.total_kwh,
                                   include_fixed=period == "mes")
    assert result.cost.projection_cop == pytest.approx(expected, rel=1e-12)


@each_personality
def test_history_projection_zone_filter_has_no_fixed_charge(
    personality: PersonalityAverages,
) -> None:
    """Mes con filtro por zona: sin cargo fijo (solo General)."""
    zone, zona_id = next(iter(zone_ids(personality).items()))
    readings = {zona_id: reference_readings(personality, NOW)[zona_id]}
    rng = H.period_range("mes", NOW, 30)
    result = evaluate(readings, "mes", tariffs_by_date=tariffs(rng.start.date(), NOW.date()),
                      general=False)
    assert not result.cost.includes_fixed_charge
    expected = expected_projection(personality, "mes", result.total_kwh, zones=(zone,))
    assert result.cost.projection_cop == pytest.approx(expected, rel=1e-12)


@each_personality
def test_history_projection_tariff_without_fixed_charge(personality: PersonalityAverages) -> None:
    rng = H.period_range("mes", NOW, 30)
    result = evaluate(reference_readings(personality, NOW), "mes",
                      tariffs_by_date=tariffs(rng.start.date(), NOW.date(), fixed=None))
    assert not result.cost.includes_fixed_charge
    expected = expected_projection(personality, "mes", result.total_kwh)
    assert result.cost.projection_cop == pytest.approx(expected, rel=1e-12)
