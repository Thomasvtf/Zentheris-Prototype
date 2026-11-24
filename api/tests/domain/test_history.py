"""Historial (`app.domain.history`) para la operación obtenerHistorial.

RN-XIII-01 a RN-XIII-06, DC-29 (tramo anterior), DC-30 (proyección), DC-31 (pico). Las series
salen de los promedios reales de las 5 personalidades (`tests/domain/history_support.py`) y del
simulador del repo; los bordes de umbral usan los bloques de `umbrales-estado.v1.json`.
"""

from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from uuid import UUID

import pytest

from app.domain import history as H
from app.domain import states as S
from app.domain.simulator import TIMEZONE
from tests.domain.history_support import (
    NOW,
    PERIODS,
    PRICE,
    at,
    each_period,
    each_personality,
    evaluate,
    reference_readings,
    simulated_readings,
    tariffs,
    thresholds,
    zone_ids,
)
from tests.helpers.personalities import PERSONALITY_ORDER, PersonalityAverages, load_personalities

TODAY = NOW.date()  # jueves 26/11/2026
MONDAY = date(2026, 11, 23)
TUESDAY = date(2026, 11, 24)
FIRST_PERSONALITY = load_personalities()[PERSONALITY_ORDER[0]]


# ------------------------------------------------------------------ periodos y tramos (DC-29)
def test_day_range() -> None:
    rng = H.period_range("dia", NOW, 30)
    assert (rng.period, rng.granularity, rng.today) == ("dia", "hora", TODAY)
    assert (rng.start, rng.end) == (at(TODAY), at(TODAY, 14))
    assert (rng.previous_start, rng.previous_end) == (at(date(2026, 11, 25)),
                                                      at(date(2026, 11, 25), 14))
    assert rng.read_start == at(date(2026, 10, 27))
    assert rng.end.utcoffset() == timedelta(hours=-5)


def test_week_range() -> None:
    rng = H.period_range("semana", NOW, 30)
    assert (rng.granularity, rng.start, rng.end) == ("dia", at(MONDAY), at(TODAY, 14))
    assert (rng.previous_start, rng.previous_end) == (at(date(2026, 11, 16)),
                                                      at(date(2026, 11, 19), 14))
    assert rng.read_start == at(date(2026, 10, 24))


def test_month_range() -> None:
    rng = H.period_range("mes", NOW, 30)
    assert (rng.granularity, rng.start, rng.end) == ("dia", at(date(2026, 11, 1)), at(TODAY, 14))
    assert (rng.previous_start, rng.previous_end) == (at(date(2026, 10, 1)),
                                                      at(date(2026, 10, 26), 14))
    assert rng.read_start == at(date(2026, 10, 1))  # min(1/10, 1/11 − 30 d = 2/10)


@pytest.mark.parametrize(
    ("now", "previous_end", "read_start"),
    [
        (datetime(2026, 3, 31, 15, 20, tzinfo=TIMEZONE), at(date(2026, 3, 1)), at(date(2026, 1, 30))),
        (datetime(2026, 3, 29, 9, 5, tzinfo=TIMEZONE), at(date(2026, 3, 1)), at(date(2026, 1, 30))),
        (datetime(2026, 3, 28, 10, 5, tzinfo=TIMEZONE), at(date(2026, 2, 28), 10),
         at(date(2026, 1, 30))),
        (datetime(2028, 3, 29, 10, 5, tzinfo=TIMEZONE), at(date(2028, 2, 29), 10),
         at(date(2028, 1, 31))),
        (datetime(2028, 3, 30, 10, 5, tzinfo=TIMEZONE), at(date(2028, 3, 1)), at(date(2028, 1, 31))),
        (datetime(2027, 1, 15, 8, 0, tzinfo=TIMEZONE), at(date(2026, 12, 15), 8),
         at(date(2026, 12, 1))),
    ],
    ids=["31-mar", "29-mar", "28-mar", "29-mar-bisiesto", "30-mar-bisiesto", "enero"],
)
def test_month_previous_stretch_short_month(now, previous_end, read_start) -> None:
    """Si el día no existe en el mes anterior, el tramo llega hasta el final de ese mes."""
    rng = H.period_range("mes", now, 30)
    first_of_previous = (rng.start.date() - timedelta(days=1)).replace(day=1)
    assert rng.previous_start == at(first_of_previous)
    assert rng.previous_end == previous_end
    assert rng.read_start == read_start


@pytest.mark.parametrize(
    ("period", "now"),
    [("dia", datetime(2026, 11, 26, 0, 10, tzinfo=TIMEZONE)),
     ("semana", datetime(2026, 11, 23, 0, 10, tzinfo=TIMEZONE)),  # lunes 00:10
     ("mes", datetime(2026, 11, 1, 0, 10, tzinfo=TIMEZONE))],  # día 1 00:10
)
def test_first_hour_gives_empty_range(period: str, now: datetime) -> None:
    rng = H.period_range(period, now, 30)
    assert rng.start == rng.end == at(now.date())
    assert rng.previous_start == rng.previous_end


def test_monday_after_first_hour_week_is_monday_only() -> None:
    rng = H.period_range("semana", datetime(2026, 11, 24, 0, 10, tzinfo=TIMEZONE), 30)
    assert (rng.start, rng.end) == (at(MONDAY), at(TUESDAY))


def test_now_in_another_zone_uses_bogota_date() -> None:
    utc = datetime(2026, 11, 27, 3, 30, tzinfo=UTC)  # 26/11 22:30 en Bogotá
    rng = H.period_range("dia", utc, 30)
    assert (rng.today, rng.end) == (TODAY, at(TODAY, 22))


def test_naive_now_is_rejected() -> None:
    naive = NOW.replace(tzinfo=None)
    with pytest.raises(ValueError):
        H.period_range("dia", naive, 30)
    with pytest.raises(ValueError):
        H.evaluate_history({}, "dia", naive, thresholds(), {}, True)


# ------------------------------------------------------------------ serie, total y participación
POINTS = {"dia": 14, "semana": 4, "mes": 26}


@each_personality
@each_period
def test_series_points_and_totals(personality: PersonalityAverages, period: str) -> None:
    rng = H.period_range(period, NOW, 30)
    result = evaluate(reference_readings(personality, NOW), period,
                      tariffs_by_date=tariffs(rng.start.date(), TODAY))
    series = result.series
    assert len(series) == POINTS[period]
    assert series[0].start == rng.start and series[-1].end == rng.end
    assert all(a.end == b.start for a, b in pairwise(series))
    ids = list(zone_ids(personality).values())
    for point in series:
        assert point.energy_kwh is not None
        assert [z.zona_id for z in point.zones] == ids
        assert sum(z.energy_kwh for z in point.zones) == pytest.approx(point.energy_kwh)
        assert point.cost_cop == pytest.approx(point.energy_kwh * PRICE)
    if period != "dia":
        assert series[-1].energy_kwh == pytest.approx(
            sum(personality.household_kwh_for_hour(h) for h in range(14)))
        assert all(p.energy_kwh == pytest.approx(personality.kwh_per_day) for p in series[:-1])
    full_days = POINTS[period] - 1 if period != "dia" else 0
    expected_total = full_days * personality.kwh_per_day + sum(
        personality.household_kwh_for_hour(h) for h in range(14))
    assert result.total_kwh == pytest.approx(expected_total)
    assert sum(p.energy_kwh for p in series) == pytest.approx(result.total_kwh)
    assert [s.zona_id for s in result.zone_shares] == ids
    assert sum(s.share_pct for s in result.zone_shares) == pytest.approx(100.0)
    assert sum(s.energy_kwh for s in result.zone_shares) == pytest.approx(result.total_kwh)
    assert result.last_peak is None and not any(p.is_max_peak for p in series)
    assert result.comparison.state == "normal"
    assert result.comparison.message_code == "historial_comparacion.similar"
    assert result.comparison.variation_pct == 0.0


@each_personality
@pytest.mark.parametrize("period", ["semana", "mes"])
def test_missing_reading_is_none_never_zero(personality: PersonalityAverages, period: str) -> None:
    """Falta la cocina el martes 10:00: el martes y su cocina son None; nada suma un parcial."""
    zone = next(iter(personality.zone_kwh_per_day))
    missing = at(TUESDAY, 10)

    def value(z, moment, reference):
        return None if (z, moment) == (zone, missing) else reference

    rng = H.period_range(period, NOW, 30)
    result = evaluate(reference_readings(personality, NOW, value), period,
                      tariffs_by_date=tariffs(rng.start.date(), TODAY))
    tuesday = next(p for p in result.series if p.start == at(TUESDAY))
    assert tuesday.energy_kwh is None and tuesday.cost_cop is None
    by_zone = {z.zona_id: z.energy_kwh for z in tuesday.zones}
    assert by_zone.pop(zone_ids(personality)[zone]) is None
    assert all(v is not None for v in by_zone.values())
    others = [p for p in result.series if p.start != at(TUESDAY)]
    assert all(p.energy_kwh is not None for p in others)
    expected_total = sum(p.energy_kwh for p in others) + (
        personality.kwh_per_day - personality.household_kwh_for_hour(10))
    assert result.total_kwh == pytest.approx(expected_total)
    assert sum(s.energy_kwh for s in result.zone_shares) == pytest.approx(result.total_kwh)
    assert sum(s.share_pct for s in result.zone_shares) == pytest.approx(100.0)
    comparison = result.comparison
    assert (comparison.state, comparison.message_code, comparison.variation_pct) == (
        "sin_datos", None, None)
    assert comparison.previous_kwh is not None
    assert (result.cost.cost_cop, result.cost.projection_cop) == (None, None)
    assert (result.cost.state, result.cost.message_code) == ("sin_datos", None)


@each_personality
def test_day_missing_hour_point_is_none(personality: PersonalityAverages) -> None:
    zone = list(personality.zone_kwh_per_day)[-1]

    def value(z, moment, reference):
        return None if (z, moment) == (zone, at(TODAY, 3)) else reference

    result = evaluate(reference_readings(personality, NOW, value), "dia")
    assert result.series[3].energy_kwh is None
    assert sum(z.energy_kwh is None for z in result.series[3].zones) == 1
    assert result.comparison.state == "sin_datos"


@each_personality
@each_period
def test_zone_filter(personality: PersonalityAverages, period: str) -> None:
    zone, zona_id = list(zone_ids(personality).items())[1]
    readings = {zona_id: reference_readings(personality, NOW)[zona_id]}
    result = evaluate(readings, period, general=False)
    assert result.zone_shares is None
    assert all(p.zones is None for p in result.series)
    full_days = POINTS[period] - 1 if period != "dia" else 0
    expected = full_days * personality.zone_kwh_per_day[zone] + sum(
        personality.zone_kwh_for_hour(zone, h) for h in range(14))
    assert result.total_kwh == pytest.approx(expected)
    assert result.comparison.message_code == "historial_comparacion.similar"


@each_period
def test_zone_that_does_not_count_is_all_without_data(period: str) -> None:
    result = evaluate({UUID(int=7): {}}, period, general=False)
    assert result.total_kwh == 0
    assert all(p.energy_kwh is None and p.cost_cop is None for p in result.series)
    assert result.last_peak is None
    assert (result.comparison.state, result.comparison.previous_kwh) == ("sin_datos", None)


@each_personality
@pytest.mark.parametrize(
    ("period", "now"),
    [("dia", datetime(2026, 11, 26, 0, 10, tzinfo=TIMEZONE)),
     ("semana", datetime(2026, 11, 23, 0, 10, tzinfo=TIMEZONE)),
     ("mes", datetime(2026, 11, 1, 0, 10, tzinfo=TIMEZONE))],
)
def test_empty_range(personality: PersonalityAverages, period: str, now: datetime) -> None:
    readings = reference_readings(personality, now, first_day=date(2026, 9, 1))
    result = evaluate(readings, period, now=now, tariffs_by_date=tariffs(now.date(), now.date()))
    assert result.series == () and result.total_kwh == 0
    assert [s.share_pct for s in result.zone_shares] == [0.0] * len(readings)
    assert [s.zona_id for s in result.zone_shares] == list(readings)
    assert result.last_peak is None
    assert result.comparison == H.Comparison(0, None, None, "sin_datos", None)
    assert result.has_tariff
    assert (result.cost.cost_cop, result.cost.projection_cop) == (None, None)


# ------------------------------------------------------------------ pico (RN-XIII-03, DC-31)
@each_personality
def test_day_last_peak_and_max_peak(personality: PersonalityAverages) -> None:
    """+50 % a las 8 (máximo) y +20 % a las 12 (último). Estado con los umbrales de la hora."""
    factors = {8: 1.5, 12: 1.2}

    def value(z, moment, reference):
        return reference * factors.get(moment.hour, 1) if moment.date() == TODAY else reference

    result = evaluate(reference_readings(personality, NOW, value), "dia")
    peak = result.last_peak
    assert peak.start == at(TODAY, 12) and peak.end == at(TODAY, 13)
    assert peak.excess_pct == 20.0 and peak.state == "elevado"  # 20 % de consumo actual
    assert peak.energy_kwh == pytest.approx(personality.household_kwh_for_hour(12) * 1.2)
    assert peak.average_kwh == pytest.approx(personality.household_kwh_for_hour(12))
    expected_max = max(factors, key=lambda h: personality.household_kwh_for_hour(h) * factors[h])
    assert [p.start.hour for p in result.series if p.is_max_peak] == [expected_max]


@each_personality
@pytest.mark.parametrize("period", ["semana", "mes"])
def test_week_tie_max_peak_is_most_recent(personality: PersonalityAverages, period: str) -> None:
    """Lunes y martes con la misma energía (×1,3): el máximo y el último son el martes.

    El lunes supera su promedio en 30 % (crítico en día completo); el promedio del martes ya
    incluye el lunes (29 días normales + 1 × 1,3 → ×1,01), así que lo supera en 28,712871 %.
    """
    def value(z, moment, reference):
        return reference * 1.3 if moment.date() in (MONDAY, TUESDAY) else reference

    result = evaluate(reference_readings(personality, NOW, value), period)
    monday, tuesday = (next(p for p in result.series if p.start == at(d))
                       for d in (MONDAY, TUESDAY))
    assert monday.energy_kwh == tuesday.energy_kwh
    assert result.last_peak.start == at(TUESDAY)
    assert result.last_peak.average_kwh == pytest.approx(personality.kwh_per_day * 1.01)
    assert result.last_peak.excess_pct == pytest.approx(28.712871, abs=1e-6)
    assert result.last_peak.state == "elevado"  # 15 % <= 28,7 % < 30 % de día completo
    assert [p.start for p in result.series if p.is_max_peak] == [at(TUESDAY)]


@each_personality
def test_today_partial_point_uses_cumulative_reference(personality: PersonalityAverages) -> None:
    """El punto de hoy (00:00 a 14:00) se compara con el acumulado habitual hasta las 13:00."""
    def value(z, moment, reference):
        return reference * 1.16 if moment.date() == TODAY else reference

    result = evaluate(reference_readings(personality, NOW, value), "semana")
    peak = result.last_peak
    assert (peak.start, peak.end) == (at(TODAY), at(TODAY, 14))
    assert peak.average_kwh == pytest.approx(
        sum(personality.household_kwh_for_hour(h) for h in range(14)))
    assert peak.excess_pct == 16.0 and peak.state == "elevado"


@each_personality
def test_peak_needs_minimum_days(personality: PersonalityAverages) -> None:
    """Con 6 días de historia no hay referencia: ni un +100 % es pico."""
    def value(z, moment, reference):
        return reference * 2 if moment.date() == TODAY else reference

    readings = reference_readings(personality, NOW, value, first_day=TODAY - timedelta(days=6))
    result = evaluate(readings, "dia")
    assert result.last_peak is None and not any(p.is_max_peak for p in result.series)


# ------------------------------------------------------------------ comparación (RN-XIII-01)
@each_personality
@pytest.mark.parametrize(
    ("factor", "variant", "state"),
    [(0.94, "menor", "normal"), (0.95, "similar", "normal"), (1.1, "mayor", "elevado"),
     (1.25, "muy_mayor", "critico")],
)
def test_day_comparison_bands(personality: PersonalityAverages, factor, variant, state) -> None:
    def value(z, moment, reference):
        return reference * factor if moment.date() == TODAY else reference

    result = evaluate(reference_readings(personality, NOW, value), "dia")
    comparison = result.comparison
    assert (comparison.state, comparison.message_code) == (state,
                                                           f"historial_comparacion.{variant}")
    assert comparison.variation_pct == pytest.approx((factor - 1) * 100, abs=1e-6)
    assert comparison.previous_kwh == pytest.approx(
        sum(personality.household_kwh_for_hour(h) for h in range(14)))
    assert (result.cost.state, result.cost.message_code) == (state, comparison.message_code)


@each_personality
@each_period
def test_previous_missing_hour_is_sin_anterior(personality: PersonalityAverages, period) -> None:
    rng = H.period_range(period, NOW, 30)
    zone = next(iter(personality.zone_kwh_per_day))

    def value(z, moment, reference):
        return None if (z, moment) == (zone, rng.previous_start) else reference

    result = evaluate(reference_readings(personality, NOW, value), period)
    assert result.comparison == H.Comparison(
        result.total_kwh, None, None, "sin_referencia", "historial_comparacion.sin_anterior")


def test_month_previous_is_whole_february_on_march_31() -> None:
    now = datetime(2026, 3, 31, 15, 20, tzinfo=TIMEZONE)
    personality = FIRST_PERSONALITY
    result = evaluate(reference_readings(personality, now), "mes", now=now)
    february = 28 * personality.kwh_per_day
    assert result.comparison.previous_kwh == pytest.approx(february)
    # 30 días y 15 h frente a los 28 días de febrero: +9,4 % (similar, normal)
    assert result.comparison.variation_pct == pytest.approx(
        (result.total_kwh / february - 1) * 100, abs=1e-6)
    assert result.comparison.message_code == "historial_comparacion.similar"


# ------------------------------------------------------------------ costo y proyección
@each_personality
def test_cost_uses_tariff_of_each_date(personality: PersonalityAverages) -> None:
    by_date = {**tariffs(MONDAY, TUESDAY, price=800.0), **tariffs(TUESDAY + timedelta(days=1),
                                                                  TODAY, price=900.0)}
    result = evaluate(reference_readings(personality, NOW), "semana", tariffs_by_date=by_date)
    prices = [800.0, 800.0, 900.0, 900.0]
    assert [p.cost_cop for p in result.series] == pytest.approx(
        [p.energy_kwh * price for p, price in zip(result.series, prices, strict=True)])
    assert result.cost.cost_cop == pytest.approx(sum(p.cost_cop for p in result.series))
    assert not result.cost.includes_fixed_charge  # Semana


@each_personality
def test_cost_none_if_a_date_has_no_tariff(personality: PersonalityAverages) -> None:
    result = evaluate(reference_readings(personality, NOW), "semana",
                      tariffs_by_date=tariffs(TUESDAY, TODAY))
    assert result.has_tariff
    assert result.series[0].cost_cop is None and result.series[1].cost_cop is not None
    assert (result.cost.cost_cop, result.cost.projection_cop) == (None, None)


@each_personality
@each_period
def test_without_tariff_today(personality: PersonalityAverages, period: str) -> None:
    result = evaluate(reference_readings(personality, NOW), period,
                      tariffs_by_date=tariffs(MONDAY, TODAY - timedelta(days=1)))
    assert not result.has_tariff
    assert (result.cost.cost_cop, result.cost.projection_cop) == (None, None)
    assert not result.cost.includes_fixed_charge
    assert result.cost.state == result.comparison.state == "normal"


@each_personality
def test_projection_none_without_hour_reference(personality: PersonalityAverages) -> None:
    readings = reference_readings(personality, NOW, first_day=TODAY - timedelta(days=6))
    result = evaluate(readings, "dia", tariffs_by_date=tariffs(TODAY, TODAY))
    assert result.cost.cost_cop is not None
    assert result.cost.projection_cop is None


@each_personality
def test_fixed_charge_flag_only_when_it_enters_the_projection(
    personality: PersonalityAverages,
) -> None:
    """Mes General con cargo fijo: sin proyección (falta referencia o falta una hora del
    periodo), `includes_fixed_charge` es False; con proyección, True (decisión de la fase 7)."""
    rng = H.period_range("mes", NOW, 30)
    by_date = tariffs(rng.start.date(), TODAY)
    complete = evaluate(reference_readings(personality, NOW), "mes", tariffs_by_date=by_date)
    assert complete.cost.projection_cop is not None
    assert complete.cost.includes_fixed_charge

    # Viernes 6/11 14:20 con lecturas solo desde el día 1: mes completo pero 5 días de historia.
    early = datetime(2026, 11, 6, 14, 20, tzinfo=TIMEZONE)
    short = reference_readings(personality, early, first_day=date(2026, 11, 1))
    without_reference = evaluate(short, "mes", now=early,
                                 tariffs_by_date=tariffs(date(2026, 11, 1), early.date()))
    assert without_reference.cost.cost_cop is not None
    assert without_reference.cost.projection_cop is None
    assert not without_reference.cost.includes_fixed_charge

    zone = next(iter(personality.zone_kwh_per_day))

    def value(z, moment, reference):
        return None if (z, moment) == (zone, at(TUESDAY, 10)) else reference

    incomplete = evaluate(reference_readings(personality, NOW, value), "mes",
                          tariffs_by_date=by_date)
    assert incomplete.cost.projection_cop is None
    assert not incomplete.cost.includes_fixed_charge


def test_cost_is_kwh_times_price() -> None:
    """Una sola implementación de kWh × precio (RN-V-01); None si falta cualquiera (RN-XI-08)."""
    assert S.cost(2.5, 800.0) == 2000.0
    assert S.cost(0.0, 800.0) == 0.0
    assert S.cost(None, 800.0) is None
    assert S.cost(2.5, None) is None
    assert S.cost(None, None) is None


# ------------------------------------------------------------------ tarifas por fecha (DC-39)
def period(price, valid_from, valid_until, fixed=None) -> H.TariffPeriod:
    return H.TariffPeriod(price, fixed, valid_from, valid_until)


def test_tariffs_by_date_bounds_are_inclusive_exclusive() -> None:
    by_date = H.tariffs_by_date([period(800.0, date(2026, 11, 10), date(2026, 11, 12), 9000.0)],
                                date(2026, 11, 9), date(2026, 11, 13))
    assert by_date == {date(2026, 11, 10): H.DayTariff(800.0, 9000.0),
                       date(2026, 11, 11): H.DayTariff(800.0, 9000.0)}


def test_tariffs_by_date_open_validity() -> None:
    by_date = H.tariffs_by_date([period(800.0, date(2026, 11, 20), None)],
                                date(2026, 11, 18), date(2026, 11, 26))
    assert sorted(by_date) == [date(2026, 11, d) for d in range(20, 27)]
    assert date(2026, 11, 19) not in by_date


def test_tariffs_by_date_two_contiguous_tariffs() -> None:
    old = period(800.0, date(2026, 10, 1), date(2026, 11, 24))
    new = period(900.0, date(2026, 11, 24), None, 12000.0)
    by_date = H.tariffs_by_date([old, new], MONDAY, TODAY)
    assert by_date == {MONDAY: H.DayTariff(800.0, None), TUESDAY: H.DayTariff(900.0, 12000.0),
                       date(2026, 11, 25): H.DayTariff(900.0, 12000.0),
                       TODAY: H.DayTariff(900.0, 12000.0)}


def test_tariffs_by_date_gap_and_empty() -> None:
    tariffs_list = [period(800.0, date(2026, 11, 1), date(2026, 11, 24)),
                    period(900.0, date(2026, 11, 25), None)]
    by_date = H.tariffs_by_date(tariffs_list, MONDAY, TODAY)
    assert TUESDAY not in by_date
    assert [by_date[d].price_per_kwh for d in sorted(by_date)] == [800.0, 900.0, 900.0]
    assert H.tariffs_by_date([], MONDAY, TODAY) == {}
    assert H.tariffs_by_date(tariffs_list, TODAY, MONDAY) == {}
    assert H.tariffs_by_date(tariffs_list, TODAY, TODAY) == {TODAY: H.DayTariff(900.0, None)}


# ------------------------------------------------------------------ simulador (5 personalidades)
@each_personality
@each_period
def test_simulated_history_is_consistent(personality: PersonalityAverages, period: str) -> None:
    readings = simulated_readings(personality.name)
    rng = H.period_range(period, NOW, 30)
    result = evaluate(readings, period, tariffs_by_date=tariffs(rng.start.date(), TODAY))
    assert len(result.series) == POINTS[period]
    assert all(p.energy_kwh is not None and p.energy_kwh > 0 for p in result.series)
    assert sum(p.energy_kwh for p in result.series) == pytest.approx(result.total_kwh)
    assert sum(s.share_pct for s in result.zone_shares) == pytest.approx(100.0)
    assert result.comparison.state in {"normal", "elevado", "critico"}
    assert result.comparison.previous_kwh is not None
    assert result.cost.projection_cop is not None
    assert result.cost.projection_cop > result.cost.cost_cop
    assert sum(p.is_max_peak for p in result.series) == (result.last_peak is not None)
    if result.last_peak is not None:
        assert result.last_peak.excess_pct >= thresholds().peak_min_pct


@pytest.mark.parametrize("period", ["semana", "mes"])
def test_simulated_totals_follow_personality_order(period: str) -> None:
    """compacto < eficiente < intermedio < familiar < amplio en el total del periodo."""
    totals = [evaluate(simulated_readings(name), period).total_kwh for name in PERSONALITY_ORDER]
    assert totals == sorted(totals) and len(set(totals)) == len(totals)


def test_periods_constant_matches_contract() -> None:
    assert PERIODS == ("dia", "semana", "mes")
