"""Apoyo de las pruebas del historial (U-02, U-03 y tests/domain/test_history.py).

Las series salen de los promedios reales de las 5 personalidades
(`tests/helpers/personalities.py`): cada zona consume en cada hora su referencia
`zone_kwh_for_hour(zona, hora)`, salvo donde la prueba la cambia. Así la referencia de una hora es
`household_kwh_for_hour(hora)` y la diaria `kwh_per_day`, sin números inventados.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime, timedelta
from functools import cache
from pathlib import Path
from uuid import UUID

import pytest

from app.domain import history as H
from app.domain import states as S
from app.domain.simulator import TIMEZONE, hour_from_index, hour_index
from app.domain.simulator.engine import simulate_household
from tests.helpers.personalities import PersonalityAverages, load_personalities
from tests.simulator.support import final_profiles, stable_id

THRESHOLDS_PATH = Path(__file__).resolve().parents[2] / "app" / "config_files" / (
    "umbrales-estado.v1.json"
)
PERIODS = ("dia", "semana", "mes")
# Jueves 26/11/2026 14:20 Bogotá: 14 horas completas hoy, lunes a miércoles completos en la
# semana y 25 días completos en el mes.
NOW = datetime(2026, 11, 26, 14, 20, tzinfo=TIMEZONE)
PRICE = 812.3  # COP/kWh de prueba (la tarifa la registra el hogar; no es constante de negocio)
FIXED_CHARGE = 12000.0

each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)
each_period = pytest.mark.parametrize("period", PERIODS)

# value(zone, hour_start, reference) -> kWh o None (None = sin lectura)
ValueFn = Callable[[str, datetime, float], float | None]


@cache
def thresholds() -> S.StateThresholds:
    return S.parse_thresholds(json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8")))


def at(day: date, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TIMEZONE)


def zone_ids(personality: PersonalityAverages) -> dict[str, UUID]:
    """Ids estables por zona, en el orden del consolidado (el orden de entrada y de salida)."""
    return {zone: stable_id("zona", "historial", personality.name, zone)
            for zone in personality.zone_kwh_per_day}


def reference_readings(
    personality: PersonalityAverages,
    now: datetime,
    value: ValueFn | None = None,
    first_day: date | None = None,
) -> dict[UUID, dict[datetime, float]]:
    """Lecturas de todas las zonas desde `first_day` (por defecto el read_start de Mes) hasta la
    última hora completa de `now`; cada hora vale su referencia salvo que `value` diga otra cosa."""
    if first_day is None:
        first_day = H.period_range("mes", now, thresholds().window_days).read_start.date()
    end = hour_index(now)
    readings = {}
    for zone, zona_id in zone_ids(personality).items():
        series = {}
        for index in range(hour_index(at(first_day)), end):
            moment = hour_from_index(index)
            reference = personality.zone_kwh_for_hour(zone, moment.hour)
            kwh = reference if value is None else value(zone, moment, reference)
            if kwh is not None:
                series[moment] = kwh
        readings[zona_id] = series
    return readings


def tariffs(
    start: date, end: date, price: float = PRICE, fixed: float | None = FIXED_CHARGE
) -> dict[date, H.DayTariff]:
    """Misma tarifa vigente en cada fecha de [start, end]."""
    return {start + timedelta(days=n): H.DayTariff(price, fixed)
            for n in range((end - start).days + 1)}


def evaluate(readings, period: str, now: datetime = NOW, tariffs_by_date=None,
             general: bool = True) -> H.HistoryEvaluation:
    return H.evaluate_history(readings, period, now, thresholds(), tariffs_by_date or {}, general)


@cache
def simulated_readings(name: str, now: datetime = NOW) -> dict[UUID, dict[datetime, float]]:
    """Lecturas del simulador del repo desde el read_start de Mes hasta la última hora completa."""
    personality = load_personalities()[name]
    ids = zone_ids(personality)
    first = H.period_range("mes", now, thresholds().window_days).read_start
    series = simulate_household(stable_id("hogar", "historial", name), final_profiles()[name],
                                ids, hour_index(first), hour_index(now))
    return {ids[zone]: {hour_from_index(r.index): r.total for r in series[zone]} for zone in ids}
