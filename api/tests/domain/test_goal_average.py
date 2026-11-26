"""Límite diario de la meta y promedio diario de 30 días (RN-XVI-04, RN-XI-03, DC-28, DC-30/31).

`app.domain.states.daily_goal_limit` y `daily_average` (fase 10, pantalla Meta). Las series salen
de los promedios reales de las 5 personalidades (`tests/helpers/personalities.py`): kWh de una
zona en una hora = `zone_kwh_for_hour(zona, hora)`, con su factor de fin de semana. El promedio
diario debe ser el mismo número que usa el historial (`history._point_reference` con hora 23).
"""

import json
import math
from datetime import date, datetime, timedelta
from functools import cache
from pathlib import Path
from uuid import UUID

import pytest

from app.domain import history as H
from app.domain import states as S
from app.domain.simulator import TIMEZONE
from tests.helpers.personalities import (
    PERSONALITY_ORDER,
    PersonalityAverages,
    load_personalities,
)

THRESHOLDS_PATH = Path(__file__).resolve().parents[2] / "app" / "config_files" / (
    "umbrales-estado.v1.json"
)
TODAY = date(2026, 11, 26)  # jueves; noviembre tiene 30 días
WEEKEND = (5, 6)

each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


@cache
def thresholds() -> S.StateThresholds:
    return S.parse_thresholds(json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8")))


def zone_ids(personality: PersonalityAverages) -> dict[str, UUID]:
    return {zone: UUID(int=i + 1) for i, zone in enumerate(personality.zone_kwh_per_day)}


def readings(
    personality: PersonalityAverages,
    *,
    days: int = 30,
    weekend: bool = True,
    include_today: bool = True,
    skip: frozenset[tuple[int, str, int]] = frozenset(),
    scale_by_offset: dict[int, float] | None = None,
) -> dict[UUID, dict[datetime, float]]:
    """Serie por zona de los `days` días anteriores a TODAY (y TODAY si `include_today`).

    `skip` = (offset de día, zona, hora) sin lectura; `scale_by_offset` multiplica un día entero.
    """
    ids = zone_ids(personality)
    scale_by_offset = scale_by_offset or {}
    series: dict[UUID, dict[datetime, float]] = {zid: {} for zid in ids.values()}
    last = 0 if include_today else -1
    for offset in range(-days, last + 1):
        day = TODAY + timedelta(days=offset)
        factor = personality.weekend_factor if weekend and day.weekday() in WEEKEND else 1.0
        factor *= scale_by_offset.get(offset, 1.0)
        for zone, zid in ids.items():
            for hour in range(24):
                if (offset, zone, hour) in skip:
                    continue
                moment = datetime(day.year, day.month, day.day, hour, tzinfo=TIMEZONE)
                series[zid][moment] = personality.zone_kwh_for_hour(zone, hour) * factor
    return series


def expected_average(personality: PersonalityAverages, days: int = 30) -> float:
    """Media de los totales diarios esperados (fin de semana con su factor)."""
    totals = []
    for offset in range(-days, 0):
        day = TODAY + timedelta(days=offset)
        factor = personality.weekend_factor if day.weekday() in WEEKEND else 1.0
        totals.append(personality.kwh_per_day * factor)
    return sum(totals) / len(totals)


# ------------------------------------------------------------------ daily_goal_limit
@pytest.mark.parametrize(
    ("monthly", "today", "expected"),
    [
        (300.0, date(2026, 11, 26), 10.0),  # 30 días
        (310.0, date(2026, 12, 1), 10.0),  # 31 días
        (280.0, date(2026, 2, 28), 10.0),  # 28 días
        (290.0, date(2028, 2, 29), 10.0),  # bisiesto: 29 días
    ],
)
def test_daily_goal_limit_divides_by_days_of_the_month(
    monthly: float, today: date, expected: float
) -> None:
    assert S.daily_goal_limit(monthly, today) == pytest.approx(expected)


def test_daily_goal_limit_without_goal_is_none() -> None:
    assert S.daily_goal_limit(None, TODAY) is None


@each_personality
def test_daily_goal_limit_with_personality_month(personality: PersonalityAverages) -> None:
    """Una meta igual al consumo mensual de referencia (30 días) da su kWh/día en noviembre."""
    limit = S.daily_goal_limit(personality.kwh_per_month, TODAY)
    assert limit == pytest.approx(personality.kwh_per_day)


@each_personality
def test_daily_goal_limit_matches_cumulative_goal_reference(
    personality: PersonalityAverages,
) -> None:
    """Mismo límite que usa el acumulado de hoy con meta (RN-XI-04)."""
    monthly = personality.kwh_per_month
    _, pct = S.cumulative_goal_state(
        S.daily_goal_limit(monthly, TODAY), monthly, S.days_in_month(TODAY),
        thresholds().cumulative_goal,
    )
    assert pct == pytest.approx(100.0)


# ------------------------------------------------------------------ daily_average
@each_personality
def test_daily_average_without_weekend_is_the_daily_kwh(personality: PersonalityAverages) -> None:
    value = S.daily_average(readings(personality, weekend=False), TODAY, thresholds())
    assert value == pytest.approx(personality.kwh_per_day)


@each_personality
def test_daily_average_with_weekend_factor(personality: PersonalityAverages) -> None:
    value = S.daily_average(readings(personality), TODAY, thresholds())
    assert value == pytest.approx(expected_average(personality))


def test_daily_average_order_of_personalities() -> None:
    values = [
        S.daily_average(readings(load_personalities()[name]), TODAY, thresholds())
        for name in PERSONALITY_ORDER
    ]
    assert all(v is not None for v in values)
    assert values == sorted(values)
    assert len(set(values)) == len(values)


@each_personality
def test_daily_average_is_the_history_daily_average(personality: PersonalityAverages) -> None:
    """Mismo número que el promedio diario del historial (semana/mes, hora 23; DC-31)."""
    series = readings(personality, skip=frozenset({(-3, "cocina", 7), (-12, "bano", 23)}))
    totals = S._household_totals(series)
    day = TODAY.toordinal()
    hours = range(day * 24, day * 24 + 24)
    expected = H._point_reference(totals, "semana", hours, thresholds())
    assert S.daily_average(series, TODAY, thresholds()) == expected


@each_personality
def test_daily_average_ignores_today_and_older_days(personality: PersonalityAverages) -> None:
    """Solo los 30 días completos anteriores a hoy: hoy y el día 31 no cuentan."""
    base = S.daily_average(readings(personality, weekend=False), TODAY, thresholds())
    noisy = readings(personality, days=31, weekend=False, scale_by_offset={0: 5.0, -31: 5.0})
    assert S.daily_average(noisy, TODAY, thresholds()) == pytest.approx(base)


@each_personality
@pytest.mark.parametrize(("days", "has_value"), [(6, False), (7, True)])
def test_daily_average_needs_minimum_days(
    personality: PersonalityAverages, days: int, has_value: bool
) -> None:
    assert thresholds().min_days_with_data == 7
    value = S.daily_average(
        readings(personality, days=days, weekend=False, include_today=False), TODAY, thresholds()
    )
    if has_value:
        assert value == pytest.approx(personality.kwh_per_day)
    else:
        assert value is None


@each_personality
def test_daily_average_skips_day_missing_one_hour_of_one_zone(
    personality: PersonalityAverages,
) -> None:
    """Un día al que le falta una hora de una zona no cuenta (nunca un total parcial)."""
    zone = next(iter(personality.zone_kwh_per_day))
    series = readings(
        personality,
        weekend=False,
        skip=frozenset({(-4, zone, 13)}),
        scale_by_offset={-4: 3.0},
    )
    value = S.daily_average(series, TODAY, thresholds())
    assert value == pytest.approx(personality.kwh_per_day)


@each_personality
def test_daily_average_incomplete_day_drops_below_minimum(
    personality: PersonalityAverages,
) -> None:
    """7 días en la ventana pero uno incompleto: quedan 6 con dato -> None."""
    zone = next(iter(personality.zone_kwh_per_day))
    series = readings(
        personality, days=7, weekend=False, include_today=False,
        skip=frozenset({(-2, zone, 0)}),
    )
    assert S.daily_average(series, TODAY, thresholds()) is None


def test_daily_average_without_zones_is_none() -> None:
    assert S.daily_average({}, TODAY, thresholds()) is None


@each_personality
def test_daily_average_zero_readings_are_data_not_missing(
    personality: PersonalityAverages,
) -> None:
    """Una lectura 0 es dato (no «sin dato»): el promedio es 0, no None."""
    series = readings(personality, weekend=False, scale_by_offset={o: 0.0 for o in range(-30, 1)})
    value = S.daily_average(series, TODAY, thresholds())
    assert value is not None
    assert math.isclose(value, 0.0, abs_tol=1e-12)
