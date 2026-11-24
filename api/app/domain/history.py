"""Historial de consumo: periodos, serie, pico, comparación, costo y proyección.

Reglas RN-XIII-01 a RN-XIII-06 y decisiones DC-29 (tramo anterior), DC-30 (proyección) y DC-31
(pico). Puro: sin FastAPI, sin SQL, sin archivos y sin reloj; la hora actual, los umbrales y las
tarifas entran por parámetro. Única implementación de `period_comparison`, `is_peak`,
`peak_state`, `project_period` y `project_cost` (antes en `states`; cierra el TODO de la fase 7).

Convenciones (las de `app.domain.states`):
- Todo en America/Bogota (`TIMEZONE`, -05:00 fijo). La lectura con inicio h cubre [h, h+1).
- `None` = sin dato, nunca cero. Números sin redondear, salvo los % que redondea `var_pct`.
- Donde las reglas no fijan un detalle, el docstring lo marca como «decisión de la fase 7».
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from uuid import UUID

from app.domain.simulator import TIMEZONE, hour_from_index, hour_index
from app.domain.states import (
    HOURS_PER_DAY,
    HourlySeries,
    PeriodComparisonThresholds,
    State,
    StateThresholds,
    by_index,
    classify,
    cost,
    cumulative_average_by_index,
    days_in_month,
    evaluated_hour,
    reference_window_start,
    same_hour_average_by_index,
    totals_by_index,
    valid,
    var_pct,
)

Period = Literal["dia", "semana", "mes"]
Granularity = Literal["hora", "dia"]

LAST_HOUR = HOURS_PER_DAY - 1
DAYS_PER_WEEK = 7
COMPARISON_MESSAGE_PREFIX = "historial_comparacion"


# ------------------------------------------------------------------ reglas sueltas (port de la ref)
def period_comparison(
    current_kwh: float, previous_kwh: float | None, thresholds: PeriodComparisonThresholds
) -> tuple[str, State]:
    """(variante del mensaje, estado) frente al tramo anterior (RN-XIII-01, DC-29).

    Sin periodo anterior: ("sin_anterior", "sin_referencia"); anterior <= 0: ("sin_referencia",
    "sin_referencia"). Límites: menor < −5 % <= similar < +10 % <= mayor < +25 % <= muy_mayor.
    """
    if previous_kwh is None:
        return "sin_anterior", "sin_referencia"
    if previous_kwh <= 0:
        return "sin_referencia", "sin_referencia"
    pct = var_pct(current_kwh, previous_kwh)
    if pct < thresholds.lower_if_below_pct:
        variant = "menor"
    elif pct < thresholds.similar_if_below_pct:
        variant = "similar"
    elif pct < thresholds.much_higher_from_pct:
        variant = "mayor"
    else:
        variant = "muy_mayor"
    return variant, thresholds.states[variant]


def is_peak(value: float | None, average: float | None, min_pct: float) -> bool:
    """Pico: supera su promedio en al menos `min_pct` % (RN-XIII-03, DC-31; 9,9 % no, 10 % sí)."""
    pct = var_pct(value, average)
    return pct is not None and pct >= min_pct


def peak_state(
    value: float,
    average: float,
    period: Period,
    thresholds: StateThresholds,
) -> State:
    """Estado del pico: bloque de consumo actual en Día; de día completo en Semana y Mes (DC-31)."""
    pct = var_pct(value, average)
    if pct is None:
        raise ValueError("el pico exige un valor y un promedio mayor que cero")
    band = thresholds.current if period == "dia" else thresholds.full_day
    return classify(pct, band)


def project_period(
    cumulative_kwh: float,
    remaining_hour_averages_today: Sequence[float],
    remaining_full_days: int,
    daily_average_30d: float,
) -> float:
    """RN-XIII-05, DC-30: lo que llevas + lo que sueles consumir en lo que falta del periodo."""
    return (
        cumulative_kwh
        + sum(remaining_hour_averages_today)
        + remaining_full_days * daily_average_30d
    )


def project_cost(
    cumulative_cost_cop: float,
    projected_kwh: float,
    cumulative_kwh: float,
    price_per_kwh: float,
    fixed_charge: float | None = None,
    is_month: bool = False,
) -> float:
    """Proyección en COP: lo que falta al precio vigente hoy; el cargo fijo solo en Mes (DC-30)."""
    extra = (projected_kwh - cumulative_kwh) * price_per_kwh
    return cumulative_cost_cop + extra + ((fixed_charge or 0) if is_month else 0)


# ------------------------------------------------------------------ tipos
@dataclass(frozen=True)
class PeriodRange:
    period: Period
    granularity: Granularity  # "hora" en dia; "dia" en semana y mes
    today: date  # fecha Bogotá de `now`
    start: datetime  # 00:00 de hoy / del lunes / del día 1 (Bogotá)
    end: datetime  # EXCLUSIVO = inicio de la hora en curso
    previous_start: datetime  # tramo anterior (DC-29)
    previous_end: datetime  # EXCLUSIVO
    read_start: datetime  # primera hora que hay que leer (referencias + tramo anterior)


@dataclass(frozen=True)
class DayTariff:
    price_per_kwh: float
    fixed_charge_monthly: float | None


@dataclass(frozen=True)
class TariffPeriod:
    """Tarifa del hogar con su vigencia [valid_from, valid_until); None = abierta (DC-39)."""

    price_per_kwh: float
    fixed_charge_monthly: float | None
    valid_from: date
    valid_until: date | None


@dataclass(frozen=True)
class ZonePointEnergy:
    zona_id: UUID
    energy_kwh: float | None


@dataclass(frozen=True)
class SeriesPoint:
    start: datetime
    end: datetime
    energy_kwh: float | None
    cost_cop: float | None
    is_max_peak: bool
    zones: tuple[ZonePointEnergy, ...] | None  # None con filtro por zona


@dataclass(frozen=True)
class ZoneShare:
    zona_id: UUID
    energy_kwh: float
    share_pct: float


@dataclass(frozen=True)
class Peak:
    start: datetime
    end: datetime
    energy_kwh: float
    average_kwh: float
    excess_pct: float
    state: State


@dataclass(frozen=True)
class Comparison:
    current_kwh: float
    previous_kwh: float | None
    variation_pct: float | None
    state: State
    message_code: str | None


@dataclass(frozen=True)
class CostSummary:
    cost_cop: float | None
    projection_cop: float | None
    includes_fixed_charge: bool
    state: State
    message_code: str | None


@dataclass(frozen=True)
class HistoryEvaluation:
    bounds: PeriodRange
    has_tariff: bool
    total_kwh: float
    series: tuple[SeriesPoint, ...]
    zone_shares: tuple[ZoneShare, ...] | None  # None con filtro por zona
    last_peak: Peak | None
    comparison: Comparison
    cost: CostSummary


# ------------------------------------------------------------------ tarifas
def tariffs_by_date(
    tariffs: Sequence[TariffPeriod], first_day: date, last_day: date
) -> dict[date, DayTariff]:
    """`{fecha: DayTariff}` para cada fecha de [first_day, last_day] con una tarifa vigente.

    Vigencia [valid_from, valid_until), `valid_until` None = abierta (RN-V-01, DC-39: las tarifas
    del hogar no se solapan). La fecha sin tarifa queda ausente: su costo es None (RN-XIII-05,
    RN-XI-08). Si first_day > last_day, mapa vacío.
    """
    by_date: dict[date, DayTariff] = {}
    for offset in range((last_day - first_day).days + 1):
        day = first_day + timedelta(days=offset)
        for tariff in tariffs:
            if tariff.valid_from <= day and (tariff.valid_until is None or day < tariff.valid_until):
                by_date[day] = DayTariff(tariff.price_per_kwh, tariff.fixed_charge_monthly)
                break
    return by_date


# ------------------------------------------------------------------ periodos
def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=TIMEZONE)


def _previous_month_end(end: datetime, month_start: datetime) -> datetime:
    """Mismo día y hora de `end` en el mes anterior; si ese día no existe, el fin de ese mes
    (= `month_start`, 00:00 del día 1 del mes actual) (DC-29)."""
    year, month = (end.year, end.month - 1) if end.month > 1 else (end.year - 1, 12)
    if end.day > days_in_month(date(year, month, 1)):
        return month_start
    return end.replace(year=year, month=month)


def period_range(period: Period, now: datetime, window_days: int) -> PeriodRange:
    """Rango actual, tramo anterior y primera hora a leer (RN-XIII-01, DC-29).

    - start: 00:00 de hoy (dia), del lunes de esta semana (semana) o del día 1 (mes).
    - end (exclusivo): fin de la última hora completa. Entre 00:00 y 00:59 de hoy (dia), del lunes
      (semana) o del día 1 (mes) el rango queda vacío (start == end).
    - Tramo anterior: dia −1 día; semana −7 días; mes del día 1 del mes anterior hasta el mismo
      día y hora de `end` en ese mes (si no existe, hasta el final del mes anterior).
    - read_start = min(previous_start, 00:00 de (fecha de start − window_days)).
    ValueError si `now` no tiene zona horaria.
    """
    end = evaluated_hour(now)[1]
    today = now.astimezone(TIMEZONE).date()
    if period == "dia":
        start = _midnight(today)
        previous_start, previous_end = start - timedelta(days=1), end - timedelta(days=1)
    elif period == "semana":
        start = _midnight(today - timedelta(days=today.weekday()))
        week = timedelta(days=DAYS_PER_WEEK)
        previous_start, previous_end = start - week, end - week
    elif period == "mes":
        start = _midnight(today.replace(day=1))
        previous_start = _midnight((today.replace(day=1) - timedelta(days=1)).replace(day=1))
        previous_end = _previous_month_end(end, start)
    else:
        raise ValueError(f"periodo no soportado: {period!r}")
    window_start = reference_window_start(start, window_days)
    return PeriodRange(
        period=period,
        granularity="hora" if period == "dia" else "dia",
        today=today,
        start=start,
        end=end,
        previous_start=previous_start,
        previous_end=previous_end,
        read_start=min(previous_start, window_start),
    )


# ------------------------------------------------------------------ evaluación
def _sum_if_complete(series: Mapping[int, float], indexes: Sequence[int]) -> float | None:
    """Suma de las horas si TODAS tienen dato; si falta una, None (nunca un parcial)."""
    if not indexes or any(index not in series for index in indexes):
        return None
    return math.fsum(series[index] for index in indexes)


def _point_hours(period: Period, start: int, end: int) -> list[range]:
    """Horas de cada punto (RN-XIII-03: una hora en Día, un día en Semana y Mes). El punto de
    hoy es parcial y termina en `end` (decisión de la fase 7)."""
    if period == "dia":
        return [range(index, index + 1) for index in range(start, end)]
    days = range(start // HOURS_PER_DAY, (end - 1) // HOURS_PER_DAY + 1) if end > start else ()
    return [
        range(max(start, day * HOURS_PER_DAY), min(end, (day + 1) * HOURS_PER_DAY))
        for day in days
    ]


def _date_of(index: int) -> date:
    return date.fromordinal(index // HOURS_PER_DAY)


def _point_reference(
    totals: Mapping[int, float], period: Period, hours: range, thresholds: StateThresholds
) -> float | None:
    """Promedio histórico del punto (RN-XIII-03, DC-31), solo con el mínimo de días con dato.

    dia: misma hora en los `window_days` días anteriores. semana/mes: acumulado 00:00..última hora
    del punto en los `window_days` días anteriores a su fecha (con 23 = promedio diario; el punto
    parcial de hoy usa el acumulado hasta su última hora: decisión de la fase 7).
    """
    day, hour = divmod(hours[-1], HOURS_PER_DAY)
    if period == "dia":
        average, days = same_hour_average_by_index(totals, day, hour, thresholds.window_days)
    else:
        average, days = cumulative_average_by_index(totals, day, hour, thresholds.window_days)
    return valid(average, days, thresholds)


def _peaks(
    points: Sequence[tuple[range, float | None]],
    totals: Mapping[int, float],
    period: Period,
    thresholds: StateThresholds,
) -> list[tuple[int, float, float]]:
    """(posición, energía, promedio) de cada punto que es pico (RN-XIII-03, DC-31)."""
    found = []
    for position, (hours, energy) in enumerate(points):
        if energy is None:
            continue
        reference = _point_reference(totals, period, hours, thresholds)
        if is_peak(energy, reference, thresholds.peak_min_pct):
            found.append((position, energy, reference))
    return found


def _max_peak_position(peaks: Sequence[tuple[int, float, float]]) -> int | None:
    """Pico del gráfico = el de mayor energía (DC-31); en empate, el más reciente (decisión de la
    fase 7)."""
    best: tuple[int, float, float] | None = None
    for peak in peaks:
        if best is None or peak[1] >= best[1]:
            best = peak
    return None if best is None else best[0]


def _comparison(
    total: float, previous: float | None, complete: bool, thresholds: StateThresholds
) -> Comparison:
    """Comparación con el tramo anterior (RN-XIII-01, DC-29). Si al periodo actual le falta
    alguna hora (o está vacío), `sin_datos` sin mensaje (decisión de la fase 7)."""
    if not complete:
        return Comparison(total, previous, None, "sin_datos", None)
    variant, state = period_comparison(total, previous, thresholds.period_comparison)
    return Comparison(
        current_kwh=total,
        previous_kwh=previous,
        variation_pct=var_pct(total, previous),
        state=state,
        message_code=f"{COMPARISON_MESSAGE_PREFIX}.{variant}",
    )


def _period_cost(
    totals: Mapping[int, float],
    hours: Sequence[int],
    tariffs_by_date: Mapping[date, DayTariff],
) -> float | None:
    """Σ kWh de cada hora × precio de su fecha (RN-XIII-05, RN-V-01); None si una fecha no
    tiene tarifa. Sin cargo fijo."""
    if any(_date_of(index) not in tariffs_by_date for index in hours):
        return None
    return math.fsum(
        cost(totals[index], tariffs_by_date[_date_of(index)].price_per_kwh)
        for index in hours
        if index in totals
    )


def _remaining_full_days(period: Period, today: date) -> int:
    if period == "dia":
        return 0
    if period == "semana":
        return DAYS_PER_WEEK - 1 - today.weekday()
    return days_in_month(today) - today.day


def _projected_kwh(
    totals: Mapping[int, float],
    rng: PeriodRange,
    total: float,
    thresholds: StateThresholds,
) -> float | None:
    """Proyección en kWh (RN-XIII-05, DC-30): horas que faltan hoy (desde la de `end`) con su
    promedio de la misma hora y días completos restantes con el promedio diario. None si falta
    alguna referencia con el mínimo de días con dato."""
    today = rng.today.toordinal()
    averages = []
    for hour in range(hour_index(rng.end) - today * HOURS_PER_DAY, HOURS_PER_DAY):
        average, days = same_hour_average_by_index(totals, today, hour, thresholds.window_days)
        average = valid(average, days, thresholds)
        if average is None:
            return None
        averages.append(average)
    remaining_days = _remaining_full_days(rng.period, rng.today)
    daily = 0.0
    if remaining_days:
        average, days = cumulative_average_by_index(
            totals, today, LAST_HOUR, thresholds.window_days
        )
        daily = valid(average, days, thresholds)
        if daily is None:
            return None
    return project_period(total, averages, remaining_days, daily)


def _cost_summary(
    totals: Mapping[int, float],
    rng: PeriodRange,
    hours: Sequence[int],
    total: float,
    complete: bool,
    comparison: Comparison,
    tariffs_by_date: Mapping[date, DayTariff],
    thresholds: StateThresholds,
    general: bool,
) -> CostSummary:
    """Costo y proyección (RN-XIII-05, RN-V-01, RN-V-02, RN-XI-08, DC-30).

    Costo: solo con tarifa hoy y el periodo completo; None si una fecha no tiene tarifa. El cargo
    fijo entra solo en Mes, solo con General y solo si la tarifa de hoy lo tiene;
    `includes_fixed_charge` es True solo si de verdad entró en una proyección calculada (decisión
    de la fase 7). Estado y mensaje = los de la comparación (DC-29, opción A).
    """
    today_tariff = tariffs_by_date.get(rng.today)
    fixed_applies = (
        rng.period == "mes"
        and general
        and today_tariff is not None
        and today_tariff.fixed_charge_monthly is not None
    )
    period_cost = None
    projection = None
    if today_tariff is not None and complete:
        period_cost = _period_cost(totals, hours, tariffs_by_date)
    if period_cost is not None:
        projected = _projected_kwh(totals, rng, total, thresholds)
        if projected is not None:
            projection = project_cost(
                period_cost,
                projected,
                total,
                today_tariff.price_per_kwh,
                today_tariff.fixed_charge_monthly,
                is_month=fixed_applies,
            )
    return CostSummary(
        cost_cop=period_cost,
        projection_cop=projection,
        includes_fixed_charge=fixed_applies and projection is not None,
        state=comparison.state,
        message_code=comparison.message_code,
    )


def _series_point(
    hours: range,
    energy: float | None,
    zone_series: Sequence[tuple[UUID, Mapping[int, float]]],
    tariffs_by_date: Mapping[date, DayTariff],
    is_max_peak: bool,
    general: bool,
) -> SeriesPoint:
    tariff = tariffs_by_date.get(_date_of(hours[0]))
    zones = None
    if general:
        zones = tuple(
            ZonePointEnergy(zona_id, _sum_if_complete(series, hours))
            for zona_id, series in zone_series
        )
    return SeriesPoint(
        start=hour_from_index(hours[0]),
        end=hour_from_index(hours[-1] + 1),
        energy_kwh=energy,
        cost_cop=cost(energy, None if tariff is None else tariff.price_per_kwh),
        is_max_peak=is_max_peak,
        zones=zones,
    )


def evaluate_history(
    readings_by_zone: Mapping[UUID, HourlySeries],
    period: Period,
    now: datetime,
    thresholds: StateThresholds,
    tariffs_by_date: Mapping[date, DayTariff],
    general: bool,
) -> HistoryEvaluation:
    """Historial del periodo para `obtenerHistorial` (RN-XIII-01 a RN-XIII-06, DC-29 a DC-31).

    `readings_by_zone`: el orden de iteración es el de salida. General: las zonas que cuentan.
    Filtro por zona (`general=False`): un solo elemento (serie vacía si la zona no cuenta).
    `tariffs_by_date`: solo fechas con tarifa vigente. Total por hora solo donde TODAS las zonas
    tienen lectura (nunca una suma parcial). ValueError si `now` no tiene zona horaria.
    """
    rng = period_range(period, now, thresholds.window_days)
    zone_series = [(zona_id, by_index(series)) for zona_id, series in readings_by_zone.items()]
    totals = totals_by_index([series for _, series in zone_series])
    start, end = hour_index(rng.start), hour_index(rng.end)
    hours = range(start, end)
    total = math.fsum(totals[index] for index in hours if index in totals)
    complete = bool(hours) and all(index in totals for index in hours)

    points = [(h, _sum_if_complete(totals, h)) for h in _point_hours(period, start, end)]
    peaks = _peaks(points, totals, period, thresholds)
    max_position = _max_peak_position(peaks)
    series = tuple(
        _series_point(h, energy, zone_series, tariffs_by_date, position == max_position, general)
        for position, (h, energy) in enumerate(points)
    )
    last_peak = None
    if peaks:
        position, energy, reference = peaks[-1]
        last_peak = Peak(
            start=series[position].start,
            end=series[position].end,
            energy_kwh=energy,
            average_kwh=reference,
            excess_pct=var_pct(energy, reference),
            state=peak_state(energy, reference, period, thresholds),
        )

    zone_shares = None
    if general:
        zone_energy = [
            (zona_id, math.fsum(series[index] for index in hours if index in totals))
            for zona_id, series in zone_series
        ]
        zone_shares = tuple(
            ZoneShare(zona_id, energy, energy / total * 100.0 if total > 0 else 0.0)
            for zona_id, energy in zone_energy
        )

    previous = _sum_if_complete(
        totals, range(hour_index(rng.previous_start), hour_index(rng.previous_end))
    )
    comparison = _comparison(total, previous, complete, thresholds)
    cost = _cost_summary(
        totals, rng, hours, total, complete, comparison, tariffs_by_date, thresholds, general
    )
    return HistoryEvaluation(
        bounds=rng,
        has_tariff=rng.today in tariffs_by_date,
        total_kwh=total,
        series=series,
        zone_shares=zone_shares,
        last_peak=last_peak,
        comparison=comparison,
        cost=cost,
    )
