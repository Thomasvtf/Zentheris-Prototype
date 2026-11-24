"""U-02 · Umbrales: Pico: 9,9 % no es pico, 10 % sí.

Esperado: Según DC-31 **[ref]**. Regla: RN-XIII-03.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

`is_peak` frente a `es_pico` de `docs/datos/motor_estados_ref.py` con las referencias reales de
las 5 personalidades, y el mismo borde a través de `evaluate_history` en Día, Semana y Mes.
"""

import importlib.util
from datetime import date
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest

from app.domain import history as H
from tests.domain.history_support import (
    NOW,
    each_personality,
    evaluate,
    reference_readings,
    thresholds,
)
from tests.helpers.personalities import PersonalityAverages

REFERENCE_PATH = Path(__file__).resolve().parents[3] / "docs" / "datos" / "motor_estados_ref.py"
BELOW = 1.099  # +9,9 %
AT = 1.10  # +10 %


@cache
def reference_engine() -> ModuleType:
    spec = importlib.util.spec_from_file_location("motor_estados_ref", REFERENCE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_boundary_on_round_numbers() -> None:
    minimum = thresholds().peak_min_pct
    assert minimum == 10
    assert not H.is_peak(1.099, 1.0, minimum)
    assert not H.is_peak(1.0999, 1.0, minimum)
    assert H.is_peak(1.10, 1.0, minimum)  # 1,10/1,00 − 1 = 0,10000000000000009
    assert H.is_peak(0.77, 0.7, minimum)  # 0,77/0,70 − 1 = 0,09999999999999987 -> 10 %
    assert not H.is_peak(None, 1.0, minimum)
    assert not H.is_peak(1.0, None, minimum)
    assert not H.is_peak(1.0, 0.0, minimum)


@each_personality
def test_boundary_on_every_personality_reference(personality: PersonalityAverages) -> None:
    """Cada zona y hora con referencia > 0: ×1,099 no es pico, ×1,10 sí; igual que la referencia."""
    ref, minimum = reference_engine(), thresholds().peak_min_pct
    checked = 0
    for zone in personality.zone_kwh_per_day:
        for hour in range(24):
            average = personality.zone_kwh_for_hour(zone, hour)
            if average <= 0:
                continue
            for factor, expected in ((BELOW, False), (AT, True)):
                value = average * factor
                assert H.is_peak(value, average, minimum) is expected, (zone, hour)
                assert ref.es_pico(value, average) is expected
                checked += 1
    assert checked > 0


@each_personality
@pytest.mark.parametrize(("factor", "is_peak"), [(BELOW, False), (AT, True)], ids=["9.9%", "10%"])
def test_day_view_hour_boundary(personality: PersonalityAverages, factor, is_peak) -> None:
    """Día: la hora 9 de hoy en todas las zonas × factor frente a su promedio de 30 días."""
    def value(zone, moment, reference):
        hit = (moment.date(), moment.hour) == (NOW.date(), 9)
        return reference * factor if hit else reference

    result = evaluate(reference_readings(personality, NOW, value), "dia", now=NOW)
    peaks = [p for p in result.series if p.is_max_peak]
    if not is_peak:
        assert result.last_peak is None and peaks == []
        return
    assert result.last_peak.start.hour == 9
    assert result.last_peak.excess_pct == 10.0
    assert result.last_peak.average_kwh == pytest.approx(personality.household_kwh_for_hour(9))
    assert result.last_peak.state == "normal"  # +10 % < 20 % de consumo actual
    assert [p.start.hour for p in peaks] == [9]


@each_personality
@pytest.mark.parametrize("period", ["semana", "mes"])
@pytest.mark.parametrize(("factor", "is_peak"), [(BELOW, False), (AT, True)], ids=["9.9%", "10%"])
def test_week_and_month_day_boundary(
    personality: PersonalityAverages, period: str, factor, is_peak
) -> None:
    """Semana y Mes: el martes 24/11 completo × factor frente al promedio diario de 30 días."""
    def value(zone, moment, reference):
        return reference * factor if moment.date() == date(2026, 11, 24) else reference

    result = evaluate(reference_readings(personality, NOW, value), period, now=NOW)
    peaks = [p for p in result.series if p.is_max_peak]
    if not is_peak:
        assert result.last_peak is None and peaks == []
        return
    assert result.last_peak.start.date() == date(2026, 11, 24)
    assert result.last_peak.excess_pct == 10.0
    assert result.last_peak.average_kwh == pytest.approx(personality.kwh_per_day)
    assert result.last_peak.state == "normal"  # +10 % < 15 % de día completo
    assert [p.start.date() for p in peaks] == [date(2026, 11, 24)]

