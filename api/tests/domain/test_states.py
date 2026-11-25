"""Referencias y evaluación de las 3 operaciones de consumo (RN-XI-01 a RN-XI-06, DC-28).

`app.domain.states` (evaluación de la fase 6). Las referencias salen de
los promedios reales de las 5 personalidades (`tests/helpers/personalities.py`): referencia de
una zona a una hora = `zone_kwh_for_hour(zona, hora)`; «normal» = referencia; «elevado» = +45 %;
«crítico» = +0,8 kWh. Las series generadas con el simulador del repo comprueban el caso real.
"""

import json
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path
from uuid import UUID

import pytest

from app.domain import states as S
from app.domain.simulator import TIMEZONE, hour_from_index
from app.domain.simulator.engine import simulate_household
from tests.helpers.personalities import PERSONALITY_ORDER, PersonalityAverages, load_personalities
from tests.simulator.support import final_profiles, stable_id

THRESHOLDS_PATH = Path(__file__).resolve().parents[2] / "app" / "config_files" / (
    "umbrales-estado.v1.json"
)
DAY = date(2026, 11, 3)  # martes
ZONE_A = UUID(int=1)
ZONE_B = UUID(int=2)
ZONE_C = UUID(int=3)

each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


@cache
def thresholds() -> S.StateThresholds:
    return S.parse_thresholds(json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8")))


def at(day: date, hour: int, tz=TIMEZONE) -> datetime:
    """Inicio de hora en Bogotá (o la misma hora expresada en otra zona)."""
    return datetime(day.year, day.month, day.day, hour, tzinfo=TIMEZONE).astimezone(tz)


def history(values_by_hour, day: date = DAY, days: int = 30, include_day: bool = True,
            skip: frozenset[tuple[int, int]] = frozenset()) -> dict[datetime, float]:
    """Serie con `days` días anteriores a `day` (y `day` completo si include_day).

    `values_by_hour(offset, hour)` da el kWh; offset 0 = `day`, −1 = el día anterior, etc.
    `skip` = (offset, hora) sin lectura.
    """
    series = {}
    first = -days
    last = 0 if include_day else -1
    for offset in range(first, last + 1):
        current = day + timedelta(days=offset)
        for hour in range(24):
            if (offset, hour) not in skip:
                series[at(current, hour)] = values_by_hour(offset, hour)
    return series


def constant(value: float):
    return lambda offset, hour: value


# ------------------------------------------------------------------ tiempo
def test_evaluated_hour_is_last_complete_hour_in_bogota() -> None:
    start, end = S.evaluated_hour(datetime(2026, 11, 3, 15, 23, tzinfo=UTC))  # 10:23 Bogotá
    assert start == at(DAY, 9) and end == at(DAY, 10)
    assert start.tzinfo == TIMEZONE


def test_evaluated_hour_after_midnight_is_previous_day() -> None:
    start, end = S.evaluated_hour(at(DAY, 0) + timedelta(minutes=30))
    assert start == at(DAY - timedelta(days=1), 23) and end == at(DAY, 0)


def test_evaluated_hour_rejects_naive() -> None:
    with pytest.raises(ValueError):
        S.evaluated_hour(at(DAY, 10).replace(tzinfo=None))


def test_reference_window_start_crosses_month() -> None:
    start = S.reference_window_start(at(date(2026, 3, 5), 14), 30)
    assert start == datetime(2026, 2, 3, tzinfo=TIMEZONE)


def test_reference_window_start_uses_bogota_date() -> None:
    # 03:00 UTC del 4 de nov. = 22:00 Bogotá del 3: la fecha es la de Bogotá.
    start = S.reference_window_start(datetime(2026, 11, 4, 3, tzinfo=UTC), 30)
    assert start == datetime(2026, 10, 4, tzinfo=TIMEZONE)


# ------------------------------------------------------------------ totales y promedios
def test_household_totals_only_hours_with_every_zone() -> None:
    a = {at(DAY, 8): 0.2, at(DAY, 9): 0.3}
    b = {at(DAY, 8): 0.5}
    totals = S.household_hourly_totals({ZONE_A: a, ZONE_B: b})
    assert totals == {at(DAY, 8): pytest.approx(0.7)}  # la hora 9 no es un parcial de 0,3


def test_household_totals_empty() -> None:
    assert S.household_hourly_totals({}) == {}


def test_household_totals_utc_and_bogota_keys_are_the_same_hour() -> None:
    a = {at(DAY, 8, UTC): 0.2}
    b = {at(DAY, 8): 0.5}
    assert S.household_hourly_totals({ZONE_A: a, ZONE_B: b}) == {at(DAY, 8): pytest.approx(0.7)}


def test_same_hour_average_previous_days_only() -> None:
    series = history(lambda offset, hour: 1.0 + offset / 100 + hour)
    average, days = S.same_hour_average(series, at(DAY, 5), 30)
    assert days == 30
    # offsets −30..−1 a las 05:00: 6 + media(−0,30..−0,01) = 6 − 0,155
    assert average == pytest.approx(6 - 0.155)


def test_same_hour_average_ignores_days_without_data() -> None:
    skip = frozenset({(-1, 5), (-2, 5), (-3, 5)})
    average, days = S.same_hour_average(history(constant(0.4), skip=skip), at(DAY, 5), 30)
    assert (average, days) == (pytest.approx(0.4), 27)


def test_same_hour_average_without_data() -> None:
    assert S.same_hour_average({}, at(DAY, 5), 30) == (None, 0)


def test_same_hour_average_utc_key_equivalent() -> None:
    series = history(lambda offset, hour: 0.1 * hour + 0.01 * offset)
    in_utc = {moment.astimezone(UTC): value for moment, value in series.items()}
    assert S.same_hour_average(in_utc, at(DAY, 7, UTC), 30) == S.same_hour_average(
        series, at(DAY, 7), 30
    )


def test_same_hour_average_window_crosses_month() -> None:
    day = date(2026, 3, 5)
    series = {at(day - timedelta(days=d), 10): float(d) for d in range(1, 40)}
    average, days = S.same_hour_average(series, at(day, 10), 30)
    assert days == 30
    assert average == pytest.approx(15.5)  # días 1..30 hacia atrás, del 4 de mar. al 3 de feb.


def test_cumulative_average_needs_every_hour_of_the_day() -> None:
    series = history(constant(0.5), skip=frozenset({(-4, 2)}))
    average, days = S.cumulative_average(series, at(DAY, 3), 30)
    assert days == 29  # el día −4 no tiene la hora 2
    assert average == pytest.approx(2.0)  # 4 horas × 0,5


def test_cumulative_average_hour_after_the_missing_one_is_ignored() -> None:
    series = history(constant(0.5), skip=frozenset({(-4, 10)}))
    assert S.cumulative_average(series, at(DAY, 3), 30)[1] == 30


# ------------------------------------------------------------------ consumo actual
def test_goal_hour_reference_by_hourly_weight() -> None:
    weights = [0.0] * 6 + [2.0] * 18  # suma 36
    assert S.goal_hour_reference(310.0, 31, weights, 3) == 0.0
    assert S.goal_hour_reference(310.0, 31, weights, 10) == pytest.approx(10 * 2 / 36)
    assert S.goal_hour_reference(310.0, 31, [0.0] * 24, 10) is None


@each_personality
def test_goal_hour_reference_with_personality_profile(personality: PersonalityAverages) -> None:
    """Con el perfil habitual de la personalidad, las 24 referencias suman el límite diario."""
    averages = [personality.household_kwh_for_hour(hour) for hour in range(24)]
    limit = personality.kwh_per_month / 30
    references = [S.goal_hour_reference(personality.kwh_per_month, 30, averages, h)
                  for h in range(24)]
    assert sum(references) == pytest.approx(limit)


def test_current_missing_hour_is_sin_datos_not_zero() -> None:
    a = history(constant(0.3), skip=frozenset({(0, 9)}))
    b = history(constant(0.2))
    result = S.evaluate_current({ZONE_A: a, ZONE_B: b}, at(DAY, 9), None, thresholds())
    assert result.power_kw is None
    assert result.state == "sin_datos"
    assert result.message_code == "consumo_actual.sin_datos"
    assert result.variation_pct is None
    assert result.reference_kw == pytest.approx(0.5)


def test_current_without_counting_zones_is_sin_datos() -> None:
    result = S.evaluate_current({}, at(DAY, 9), None, thresholds())
    assert (result.power_kw, result.state, result.reference_kw) == (None, "sin_datos", None)


@pytest.mark.parametrize(("days", "expected"), [(6, "sin_referencia"), (7, "normal")])
def test_current_needs_seven_days(days: int, expected: str) -> None:
    series = history(constant(0.5), days=days)
    result = S.evaluate_current({ZONE_A: series}, at(DAY, 9), None, thresholds())
    assert result.state == expected
    assert result.message_code == f"consumo_actual.{expected}"
    assert result.reference_kw == (None if days < 7 else pytest.approx(0.5))


def test_current_variation_against_previous_hour() -> None:
    series = history(lambda offset, hour: 1.2 if (offset, hour) == (0, 9) else 1.0)
    result = S.evaluate_current({ZONE_A: series}, at(DAY, 9), None, thresholds())
    assert result.variation_pct == 20.0
    assert result.reference_type == "promedio"
    assert result.state == "elevado"  # 1,2 / 1,0: límite inclusivo


def test_current_variation_null_without_previous_hour() -> None:
    series = history(constant(1.0), skip=frozenset({(0, 8)}))
    result = S.evaluate_current({ZONE_A: series}, at(DAY, 9), None, thresholds())
    assert result.variation_pct is None
    assert result.state == "normal"


def test_current_with_goal_uses_daily_limit_by_hourly_weight() -> None:
    weights = [1.0] * 12 + [3.0] * 12  # suma 48
    series = history(lambda offset, hour: weights[hour])
    goal = S.GoalInput(monthly_kwh=300.0)  # noviembre: 10 kWh/día
    result = S.evaluate_current({ZONE_A: series}, at(DAY, 15), goal, thresholds())
    assert result.reference_type == "meta"
    assert result.reference_kw == pytest.approx(10 * 3 / 48)
    assert result.state == "critico"  # 3 kWh contra 0,625
    assert result.message_code == "consumo_actual.critico"


def test_current_with_goal_without_reference_in_some_hour() -> None:
    series = history(constant(0.5), skip=frozenset((-d, 4) for d in range(1, 31)))
    goal = S.GoalInput(monthly_kwh=300.0)
    result = S.evaluate_current({ZONE_A: series}, at(DAY, 15), goal, thresholds())
    assert (result.reference_kw, result.state) == (None, "sin_referencia")


def test_current_with_goal_and_zero_profile() -> None:
    result = S.evaluate_current(
        {ZONE_A: history(constant(0.0))}, at(DAY, 15), S.GoalInput(300.0), thresholds()
    )
    assert (result.reference_kw, result.state) == (None, "sin_referencia")


def test_current_utc_and_bogota_inputs_are_equivalent() -> None:
    series = history(lambda offset, hour: 0.2 + 0.01 * hour + 0.001 * offset)
    in_utc = {moment.astimezone(UTC): value for moment, value in series.items()}
    bogota = S.evaluate_current({ZONE_A: series}, at(DAY, 9), None, thresholds())
    utc = S.evaluate_current({ZONE_A: in_utc}, at(DAY, 9, UTC), None, thresholds())
    assert bogota == utc


# ------------------------------------------------------------------ acumulado de hoy
def test_today_before_first_complete_hour() -> None:
    now = at(DAY, 0) + timedelta(minutes=40)
    result = S.evaluate_today({ZONE_A: history(constant(0.5))}, now, None, thresholds())
    assert result.energy_kwh == 0
    assert result.state == "sin_datos"
    assert result.message_code == "acumulado.promedio.sin_datos"
    assert (result.reference_type, result.shows_limit, result.reference_kwh) == (
        "promedio", False, None
    )


def test_today_before_first_complete_hour_with_goal() -> None:
    now = at(DAY, 0) + timedelta(minutes=5)
    result = S.evaluate_today({ZONE_A: history(constant(0.5))}, now, S.GoalInput(300.0),
                              thresholds())
    assert (result.energy_kwh, result.state, result.message_code) == (
        0, "sin_datos", "acumulado.meta.sin_datos"
    )
    assert result.shows_limit is True
    assert result.reference_kwh == pytest.approx(10.0)


def test_today_sums_until_last_complete_hour() -> None:
    now = at(DAY, 6) + timedelta(minutes=10)  # horas 00..05
    result = S.evaluate_today({ZONE_A: history(constant(0.5))}, now, None, thresholds())
    assert result.energy_kwh == pytest.approx(3.0)
    assert result.reference_kwh == pytest.approx(3.0)
    assert (result.state, result.message_code) == ("normal", "acumulado.promedio.normal")


def test_today_missing_hour_is_sin_datos_with_partial_sum() -> None:
    now = at(DAY, 6) + timedelta(minutes=10)
    series = history(constant(0.5), skip=frozenset({(0, 2)}))
    result = S.evaluate_today({ZONE_A: series}, now, None, thresholds())
    assert result.energy_kwh == pytest.approx(2.5)
    assert result.state == "sin_datos"
    assert result.message_code == "acumulado.promedio.sin_datos"


def test_today_with_goal_shows_limit() -> None:
    now = at(DAY, 20) + timedelta(minutes=1)  # 20 horas de 0,4 = 8 kWh = 80 % de 10
    result = S.evaluate_today({ZONE_A: history(constant(0.4))}, now, S.GoalInput(300.0),
                              thresholds())
    assert result.reference_type == "meta"
    assert result.shows_limit is True
    assert result.reference_kwh == pytest.approx(10.0)
    assert result.energy_kwh == pytest.approx(8.0)
    assert (result.state, result.message_code) == ("elevado", "acumulado.meta.elevado")


def test_today_with_goal_uses_days_of_current_month() -> None:
    day = date(2026, 2, 10)
    now = at(day, 3) + timedelta(minutes=1)
    series = history(constant(0.1), day=day)
    result = S.evaluate_today({ZONE_A: series}, now, S.GoalInput(280.0), thresholds())
    assert result.reference_kwh == pytest.approx(10.0)  # febrero de 2026: 28 días


def test_today_average_needs_seven_complete_days() -> None:
    now = at(DAY, 6) + timedelta(minutes=10)
    result = S.evaluate_today({ZONE_A: history(constant(0.5), days=6)}, now, None, thresholds())
    assert (result.reference_kwh, result.state) == (None, "sin_referencia")


def test_today_average_states() -> None:
    now = at(DAY, 4) + timedelta(minutes=10)  # horas 00..03
    def values(offset, hour):
        return 1.3 if offset == 0 else 1.0
    result = S.evaluate_today({ZONE_A: history(values)}, now, None, thresholds())
    assert result.state == "critico"  # +30 %: límite inclusivo de acumulado_promedio


# ------------------------------------------------------------------ zonas
def test_zone_without_reading_makes_total_null() -> None:
    a = history(constant(0.3), skip=frozenset({(0, 9)}))
    b = history(constant(0.2))
    result = S.evaluate_zones({ZONE_A: a, ZONE_B: b}, {ZONE_A, ZONE_B}, at(DAY, 9), thresholds())
    assert result.total_kw is None
    assert result.zones[ZONE_A].power_kw is None
    assert result.zones[ZONE_A].zone_state == "sin_datos"
    assert result.zones[ZONE_B].power_kw == pytest.approx(0.2)
    assert result.zones[ZONE_B].share_pct is None
    assert result.zones[ZONE_B].share_state == "sin_datos"
    assert result.zones[ZONE_B].zone_state == "normal"


def test_zone_outside_counting_zones() -> None:
    a = history(constant(0.3))
    c = history(constant(0.9))
    result = S.evaluate_zones({ZONE_A: a, ZONE_C: c}, {ZONE_A}, at(DAY, 9), thresholds())
    assert result.total_kw == pytest.approx(0.3)
    assert set(result.zones) == {ZONE_A, ZONE_C}
    # La zona que no cuenta (inactiva o con sensor pausado) no se evalúa aunque traiga lecturas.
    assert result.zones[ZONE_C] == S.ZoneEvaluation(
        zona_id=ZONE_C,
        power_kw=None,
        share_pct=None,
        share_state="sin_datos",
        average_kw=None,
        variation_pct=None,
        zone_state="sin_datos",
        zone_message_code="zona_estado.sin_datos",
    )
    assert result.zones[ZONE_A].share_pct == pytest.approx(100.0)
    assert result.zones[ZONE_A].zone_state == "normal"


def test_zone_outside_counting_zones_with_critical_readings_is_not_evaluated() -> None:
    def c_values(offset, hour):
        return 5.0 if (offset, hour) == (0, 9) else 0.2

    result = S.evaluate_zones(
        {ZONE_A: history(constant(0.3)), ZONE_C: history(c_values)}, [ZONE_A], at(DAY, 9),
        thresholds(),
    )
    assert result.zones[ZONE_C].zone_state == "sin_datos"
    assert result.zones[ZONE_C].power_kw is None
    assert result.total_kw == pytest.approx(0.3)


def test_habitual_share_uses_the_same_days_for_zone_and_total() -> None:
    """Días -30..-21 sin lectura de B (sin total): la zona A ahí valía 0,9 y no debe contar.

    Con los mismos días (-20..-1): habitual = 0,2 / (0,2 + 0,8) = 20 %; hoy 0,2 / 1,0 = 20 %
    -> normal. Si se mezclaran los días de A sin total (promedio de A 0,43), la habitual
    subiría a más de 30 % y hoy saldría por debajo. `days_with_data` = 20 (>= 7).
    """
    def a_values(offset, hour):
        return 0.9 if offset < -20 else 0.2

    skip_b = frozenset((offset, 9) for offset in range(-30, -20))
    b = history(constant(0.8), skip=skip_b)
    result = S.evaluate_zones({ZONE_A: history(a_values), ZONE_B: b}, {ZONE_A, ZONE_B},
                              at(DAY, 9), thresholds())
    zone = result.zones[ZONE_A]
    assert zone.share_pct == pytest.approx(20.0)
    assert zone.share_state == "normal"
    # El estado de la zona sí usa todos sus días (promedio de la zona, RN-XI-06).
    assert zone.average_kw == pytest.approx((10 * 0.9 + 20 * 0.2) / 30)


def test_habitual_share_same_days_detects_critical_share() -> None:
    """Mismos días: habitual 20 %; hoy A = 0,8 con B = 0,8 -> 50 % (+150 %), exceso 0,48."""
    def a_values(offset, hour):
        if (offset, hour) == (0, 9):
            return 0.8
        return 5.0 if offset < -20 else 0.2

    skip_b = frozenset((offset, 9) for offset in range(-30, -20))
    b = history(constant(0.8), skip=skip_b)
    result = S.evaluate_zones({ZONE_A: history(a_values), ZONE_B: b}, {ZONE_A, ZONE_B},
                              at(DAY, 9), thresholds())
    # Con los días de A sin total, la habitual sería (10*5 + 20*0,2)/30 / 1,0 = 180 % (absurda).
    assert result.zones[ZONE_A].share_state == "critico"


def test_habitual_share_needs_seven_shared_days() -> None:
    skip_b = frozenset((offset, 9) for offset in range(-30, -6))  # B solo 6 días a las 09:00
    b = history(constant(0.8), skip=skip_b)
    result = S.evaluate_zones({ZONE_A: history(constant(0.2)), ZONE_B: b}, {ZONE_A, ZONE_B},
                              at(DAY, 9), thresholds())
    assert result.zones[ZONE_A].share_state == "sin_referencia"
    assert result.zones[ZONE_A].zone_state == "normal"  # la zona A sí tiene 30 días


def test_counting_zone_without_series_makes_total_null() -> None:
    result = S.evaluate_zones({ZONE_A: history(constant(0.3))}, {ZONE_A, ZONE_B}, at(DAY, 9),
                              thresholds())
    assert result.total_kw is None


def test_zone_total_zero_share_is_sin_referencia() -> None:
    result = S.evaluate_zones({ZONE_A: history(constant(0.0))}, {ZONE_A}, at(DAY, 9),
                              thresholds())
    zone = result.zones[ZONE_A]
    assert result.total_kw == 0.0
    assert (zone.share_pct, zone.share_state) == (None, "sin_referencia")
    # Promedio 0 con 30 días (decisión de Nicolás del 23/11/2026: con 7 o más días con dato,
    # un promedio 0 es referencia válida): exceso 0 < 0,05 kWh -> normal.
    assert zone.zone_state == "normal"


# ------------------------------------------------------------------ promedio 0 (23/11/2026)
ZERO_REFERENCE_BANDS = ("zone_state", "zone_share")
NO_EXCESS_BANDS = ("current", "cumulative_average", "full_day")


def zero_state(value, band_name: str, *, days: int = 30, excess=None, reference=0.0) -> str:
    t = thresholds()
    return S.relative_state(value, reference, getattr(t, band_name),
                            min_days_with_data=t.min_days_with_data, days_with_data=days,
                            excess_kwh=excess)


@pytest.mark.parametrize("band_name", ZERO_REFERENCE_BANDS)
@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "normal"), (0.049999, "normal"), (0.05, "critico"), (0.8, "critico")],
)
def test_zero_reference_with_minimum_excess(band_name: str, value: float, expected: str) -> None:
    """Decisión del 23/11/2026 (promedio 0): referencia exactamente 0 con >= 7 días;
    exceso >= 0,05 kWh -> crítico; si no, normal.

    Se aparta de motor_estados_ref.py (referencia <= 0 -> sin_referencia).
    """
    assert zero_state(value, band_name) == expected


@pytest.mark.parametrize("band_name", ZERO_REFERENCE_BANDS)
def test_zero_reference_uses_given_excess(band_name: str) -> None:
    assert zero_state(10.0, band_name, excess=0.01) == "normal"
    assert zero_state(0.0, band_name, excess=0.05) == "critico"


@pytest.mark.parametrize("band_name", ZERO_REFERENCE_BANDS)
def test_zero_reference_needs_seven_days(band_name: str) -> None:
    assert zero_state(0.8, band_name, days=6) == "sin_referencia"
    assert zero_state(0.8, band_name, days=7) == "critico"


@pytest.mark.parametrize("band_name", ZERO_REFERENCE_BANDS + NO_EXCESS_BANDS)
def test_negative_or_missing_reference_is_sin_referencia(band_name: str) -> None:
    assert zero_state(0.8, band_name, reference=-0.1) == "sin_referencia"
    assert zero_state(0.8, band_name, reference=None) == "sin_referencia"
    assert zero_state(None, band_name) == "sin_datos"


@pytest.mark.parametrize("band_name", NO_EXCESS_BANDS)
def test_zero_reference_without_minimum_excess_is_sin_referencia(band_name: str) -> None:
    assert zero_state(0.8, band_name) == "sin_referencia"
    assert zero_state(0.0, band_name) == "sin_referencia"


def test_zone_with_zero_average_and_consumption_is_critical() -> None:
    """Zona que nunca consume a esa hora (promedio 0) y hoy consume 0,3 kWh -> crítico
    (decisión del 23/11/2026, promedio 0)."""
    a = history(lambda offset, hour: 0.3 if (offset, hour) == (0, 9) else 0.0)
    b = history(constant(1.0))
    result = S.evaluate_zones({ZONE_A: a, ZONE_B: b}, {ZONE_A, ZONE_B}, at(DAY, 9), thresholds())
    zone = result.zones[ZONE_A]
    assert zone.average_kw == 0.0
    assert zone.variation_pct is None  # sin % contra 0
    assert zone.zone_state == "critico"
    assert zone.zone_message_code == "zona_estado.critico"
    assert zone.share_state == "critico"  # habitual 0 %; exceso = 0,3 kWh


def test_zone_with_zero_average_and_small_consumption_is_normal() -> None:
    a = history(lambda offset, hour: 0.04 if (offset, hour) == (0, 9) else 0.0)
    b = history(constant(1.0))
    result = S.evaluate_zones({ZONE_A: a, ZONE_B: b}, {ZONE_A, ZONE_B}, at(DAY, 9), thresholds())
    assert (result.zones[ZONE_A].zone_state, result.zones[ZONE_A].share_state) == (
        "normal", "normal")


def test_zone_needs_seven_days() -> None:
    result = S.evaluate_zones({ZONE_A: history(constant(0.3), days=6)}, {ZONE_A}, at(DAY, 9),
                              thresholds())
    zone = result.zones[ZONE_A]
    assert (zone.average_kw, zone.variation_pct, zone.zone_state) == (None, None,
                                                                     "sin_referencia")
    assert zone.share_state == "sin_referencia"
    assert zone.zone_message_code == "zona_estado.sin_referencia"


def test_share_needs_minimum_excess() -> None:
    """Participación +100 % sobre la habitual, pero exceso < 0,05 kWh -> normal."""
    def a_values(offset, hour):
        return 0.04 if (offset, hour) == (0, 9) else 0.02
    b = history(constant(1.0))
    result = S.evaluate_zones({ZONE_A: history(a_values), ZONE_B: b}, {ZONE_A, ZONE_B},
                              at(DAY, 9), thresholds())
    zone = result.zones[ZONE_A]
    assert zone.share_pct == pytest.approx(0.04 / 1.04 * 100)
    assert zone.share_state == "normal"
    assert zone.zone_state == "normal"  # exceso 0,02 < 0,05 aunque sea +100 %


def test_share_with_excess_is_critical() -> None:
    def a_values(offset, hour):
        return 0.8 if (offset, hour) == (0, 9) else 0.2
    b = history(constant(0.8))
    result = S.evaluate_zones({ZONE_A: history(a_values), ZONE_B: b}, {ZONE_A, ZONE_B},
                              at(DAY, 9), thresholds())
    zone = result.zones[ZONE_A]
    # habitual 20 %; ahora 50 % (+150 %); exceso 0,8 − 0,2 × 1,6 = 0,48 kWh
    assert zone.share_pct == pytest.approx(50.0)
    assert zone.share_state == "critico"
    assert zone.zone_state == "critico"
    assert zone.variation_pct == 300.0
    assert zone.average_kw == pytest.approx(0.2)
    assert zone.zone_message_code == "zona_estado.critico"


# ------------------------------------------------------------------ personalidades (promedios)
def personality_series(personality: PersonalityAverages, hour: int, today_value) -> dict:
    """30 días con la referencia de cada zona (`zone_kwh_for_hour`) y hoy con `today_value`."""
    series = {}
    for zone in personality.zone_kwh_per_day:
        def values(offset, h, zone=zone):
            reference = personality.zone_kwh_for_hour(zone, h)
            if offset == 0 and h == hour:
                return today_value(zone, reference)
            return reference
        series[stable_id("zona", personality.name, zone)] = history(values)
    return series


def peak_zone_hour(personality: PersonalityAverages) -> tuple[str, int]:
    """Zona y hora con la mayor referencia (la hora habitual de más consumo)."""
    return max(
        ((zone, hour) for zone in personality.zone_kwh_per_day for hour in range(24)),
        key=lambda item: personality.zone_kwh_for_hour(*item),
    )


@each_personality
def test_personality_reference_is_normal(personality: PersonalityAverages) -> None:
    _, hour = peak_zone_hour(personality)
    series = personality_series(personality, hour, lambda z, ref: ref)
    current = S.evaluate_current(series, at(DAY, hour), None, thresholds())
    assert current.state == "normal"
    assert current.reference_kw == pytest.approx(personality.household_kwh_for_hour(hour))
    zones = S.evaluate_zones(series, set(series), at(DAY, hour), thresholds())
    for zone_type in personality.zone_kwh_per_day:
        result = zones.zones[stable_id("zona", personality.name, zone_type)]
        # Referencia 0 kWh (curva habitual en 0 a esa hora) y hoy 0: normal (decisión del
        # 23/11/2026, promedio 0; motor_estados_ref daba sin_referencia con referencia <= 0).
        assert (result.zone_state, result.share_state) == ("normal", "normal"), zone_type
    assert sum(z.share_pct for z in zones.zones.values()) == pytest.approx(100.0)


@each_personality
@pytest.mark.parametrize(
    ("change", "expected"),
    [(lambda ref: ref * 1.45, "elevado"), (lambda ref: ref + 0.8, "critico")],
    ids=["+45%", "+0.8kWh"],
)
def test_personality_zone_elevated_and_critical(
    personality: PersonalityAverages, change, expected: str
) -> None:
    zone, hour = peak_zone_hour(personality)
    reference = personality.zone_kwh_for_hour(zone, hour)
    assert 0.8 / reference >= 0.6
    if change(reference) - reference < thresholds().zone_state.min_excess_kwh:
        # Consumo compacto: su mayor referencia (cocina 19:00, ~0,088 kWh) no llega a que +45 %
        # supere el exceso mínimo de 0,05 kWh; el piso manda.
        expected = "normal"
    series = personality_series(
        personality, hour, lambda z, ref: change(ref) if z == zone else ref
    )
    zones = S.evaluate_zones(series, set(series), at(DAY, hour), thresholds())
    target = zones.zones[stable_id("zona", personality.name, zone)]
    assert target.zone_state == expected
    assert target.average_kw == pytest.approx(reference)


@each_personality
def test_personality_small_zone_floor_keeps_normal(personality: PersonalityAverages) -> None:
    """Zona y hora con referencia baja: +45 % con exceso < 0,05 kWh sigue normal."""
    zone, hour = min(
        ((z, h) for z in personality.zone_kwh_per_day for h in range(24)
         if personality.zone_kwh_for_hour(z, h) > 0),
        key=lambda item: personality.zone_kwh_for_hour(*item),
    )
    reference = personality.zone_kwh_for_hour(zone, hour)
    assert reference * 0.45 < 0.05
    series = personality_series(
        personality, hour, lambda z, ref: ref * 1.45 if z == zone else ref
    )
    zones = S.evaluate_zones(series, set(series), at(DAY, hour), thresholds())
    assert zones.zones[stable_id("zona", personality.name, zone)].zone_state == "normal"


@each_personality
def test_personality_household_bands(personality: PersonalityAverages) -> None:
    """Hogar entero: entre los límites de consumo_actual es elevado; sobre el crítico, crítico."""
    band = thresholds().current
    hour = 19
    middle = 1 + (band.elevated_from_pct + band.critical_from_pct) / 200
    for factor, expected in ((1.0, "normal"), (middle, "elevado"),
                             (1 + band.critical_from_pct / 100, "critico")):
        series = personality_series(personality, hour, lambda z, ref, f=factor: ref * f)
        assert S.evaluate_current(series, at(DAY, hour), None, thresholds()).state == expected


# ------------------------------------------------------------------ personalidades (simulador)
def personality_household(personality: PersonalityAverages):
    hogar_id = stable_id("hogar", "estados", personality.name)
    return hogar_id, {zone: stable_id("zona", "estados", personality.name, zone)
                      for zone in personality.zone_kwh_per_day}


@cache
def simulated_readings(name: str) -> dict[UUID, dict[datetime, float]]:
    """30 días previos + el día evaluado, con todas las zonas de la personalidad."""
    personality = load_personalities()[name]
    hogar_id, zone_ids = personality_household(personality)
    day = DAY.toordinal()
    series = simulate_household(hogar_id, final_profiles()[name], zone_ids, (day - 30) * 24,
                                (day + 1) * 24)
    return {
        zone_ids[zone]: {hour_from_index(r.index): r.total for r in readings}
        for zone, readings in series.items()
    }


@each_personality
def test_simulated_usual_hours_are_mostly_normal(personality: PersonalityAverages) -> None:
    """A la hora habitual (sin alterar), la mayoría de estados de hogar y de zona son normales.

    Las horas en que la zona suele consumir 0 kWh (curva en 0) siguen la decisión del
    23/11/2026 (promedio 0):
    crítico si hoy consume 0,05 kWh o más; si no, normal. Se excluyen del conteo.
    """
    readings = simulated_readings(personality.name)
    household, zone_states = [], []
    for hour in range(24):
        household.append(S.evaluate_current(readings, at(DAY, hour), None, thresholds()).state)
        zones = S.evaluate_zones(readings, set(readings), at(DAY, hour), thresholds())
        for zone in zones.zones.values():
            if zone.average_kw == 0:
                expected = "critico" if zone.power_kw >= 0.05 else "normal"
                assert zone.zone_state == expected
                continue
            zone_states += [zone.zone_state, zone.share_state]
    assert household.count("normal") > len(household) / 2
    assert zone_states.count("normal") > len(zone_states) / 2
    assert not {"sin_datos", "sin_referencia"} & set(household + zone_states)


def test_simulated_daily_reference_follows_personality_order() -> None:
    """compacto < eficiente < intermedio < familiar < amplio en la referencia diaria."""
    daily = []
    for name in PERSONALITY_ORDER:
        totals = S.household_hourly_totals(simulated_readings(name))
        hourly = [S.same_hour_average(totals, at(DAY, hour), 30) for hour in range(24)]
        assert all(days == 30 for _, days in hourly)
        cumulative, days = S.cumulative_average(totals, at(DAY, 23), 30)
        assert days == 30
        assert cumulative == pytest.approx(sum(avg for avg, _ in hourly), rel=1e-12)
        daily.append(cumulative)
    assert daily == sorted(daily) and len(set(daily)) == len(daily)


@each_personality
@pytest.mark.parametrize(
    ("change", "expected"),
    [(lambda ref: ref * 1.45, "elevado"), (lambda ref: ref + 0.8, "critico")],
    ids=["+45%", "+0.8kWh"],
)
def test_simulated_zone_elevated_and_critical(
    personality: PersonalityAverages, change, expected: str
) -> None:
    readings = simulated_readings(personality.name)
    _, zone_ids = personality_household(personality)
    # Zona y hora con el mayor promedio, para acercarse al exceso mínimo de 0,05 kWh.
    averages = {(zid, hour): S.same_hour_average(readings[zid], at(DAY, hour), 30)[0]
                for zid in zone_ids.values() for hour in range(24)}
    zone_id, hour = max(averages, key=averages.get)
    reference = averages[zone_id, hour]
    assert 0.8 / reference >= 0.6
    if change(reference) - reference < thresholds().zone_state.min_excess_kwh:
        expected = "normal"  # Consumo compacto: el piso de 0,05 kWh manda
    changed = {zid: dict(series) for zid, series in readings.items()}
    changed[zone_id][at(DAY, hour)] = change(reference)
    zones = S.evaluate_zones(changed, set(changed), at(DAY, hour), thresholds())
    assert zones.zones[zone_id].zone_state == expected


# ------------------------------------------------------------------ estado de zona por hora (fase 8)
def test_evaluate_zone_hours_matches_evaluate_zones() -> None:
    """Misma lógica que `evaluate_zones(...).zone_state` (RN-XI-06) para cada (zona, hora)."""
    def a_values(offset, hour):
        return {(0, 9): 0.8, (0, 10): 0.27}.get((offset, hour), 0.2)
    series = {ZONE_A: history(a_values), ZONE_B: history(constant(0.5))}
    hours = [at(DAY, 9), at(DAY, 10), at(DAY, 11)]
    result = S.evaluate_zone_hours(series, {ZONE_A: hours, ZONE_B: hours}, thresholds())
    for item in result:
        expected = S.evaluate_zones(series, set(series), item.hour_start, thresholds())
        zone = expected.zones[item.zona_id]
        assert (item.state, item.power_kw) == (zone.zone_state, zone.power_kw)
    states = {(item.zona_id, item.hour_start): item.state for item in result}
    assert states[ZONE_A, at(DAY, 9)] == "critico"
    assert states[ZONE_A, at(DAY, 10)] == "elevado"  # +35 %, exceso 0,07
    assert states[ZONE_A, at(DAY, 11)] == "normal"


def test_evaluate_zone_hours_order_by_hour_then_zone() -> None:
    series = {ZONE_B: history(constant(0.5)), ZONE_A: history(constant(0.2))}
    result = S.evaluate_zone_hours(
        series, {ZONE_B: [at(DAY, 10), at(DAY, 9)], ZONE_A: [at(DAY, 10, UTC), at(DAY, 9)]},
        thresholds())
    assert [(r.hour_start, r.zona_id) for r in result] == [
        (at(DAY, 9), ZONE_A), (at(DAY, 9), ZONE_B), (at(DAY, 10), ZONE_A), (at(DAY, 10), ZONE_B)]


def test_evaluate_zone_hours_zone_without_series_is_sin_datos() -> None:
    result = S.evaluate_zone_hours({}, {ZONE_C: [at(DAY, 9)]}, thresholds())
    assert result == [S.ZoneHourState(ZONE_C, at(DAY, 9), None, "sin_datos")]


def test_evaluate_zone_hours_missing_hour_and_few_days() -> None:
    series = {ZONE_A: history(constant(0.3), skip=frozenset({(0, 9)})),
              ZONE_B: history(constant(0.3), days=6)}
    result = S.evaluate_zone_hours(series, {ZONE_A: [at(DAY, 9)], ZONE_B: [at(DAY, 9)]},
                                   thresholds())
    assert [(r.zona_id, r.power_kw, r.state) for r in result] == [
        (ZONE_A, None, "sin_datos"), (ZONE_B, 0.3, "sin_referencia")]


def test_evaluate_zone_hours_zero_average_follows_d1() -> None:
    series = {ZONE_A: history(lambda offset, hour: 0.3 if (offset, hour) == (0, 3) else 0.0)}
    result = S.evaluate_zone_hours(series, {ZONE_A: [at(DAY, 3), at(DAY, 4)]}, thresholds())
    assert [r.state for r in result] == ["critico", "normal"]


def test_evaluate_zone_hours_empty() -> None:
    assert S.evaluate_zone_hours({ZONE_A: history(constant(0.3))}, {}, thresholds()) == []


@each_personality
@pytest.mark.parametrize(("factor", "expected"), [(1.0, "normal"), (1.3, "elevado"),
                                                  (1.6, "critico")])
def test_evaluate_zone_hours_personality_curve(
    personality: PersonalityAverages, factor: float, expected: str
) -> None:
    """Referencia = curva real de la zona; la hora +30 % es elevado y +60 % crítico (límites
    inclusivos), salvo que el exceso no llegue a 0,05 kWh (piso)."""
    zone, hour = peak_zone_hour(personality)
    reference = personality.zone_kwh_for_hour(zone, hour)
    if reference * (factor - 1) < thresholds().zone_state.min_excess_kwh:
        expected = "normal"
    series = personality_series(
        personality, hour, lambda z, ref: ref * factor if z == zone else ref)
    zona_id = stable_id("zona", personality.name, zone)
    hours = {zid: [at(DAY, hour)] for zid in series}
    result = {r.zona_id: r for r in S.evaluate_zone_hours(series, hours, thresholds())}
    assert result[zona_id].state == expected
    assert result[zona_id].power_kw == pytest.approx(reference * factor)
    others = {r.state for zid, r in result.items() if zid != zona_id}
    assert others <= {"normal"}
