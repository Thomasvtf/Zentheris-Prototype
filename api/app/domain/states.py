"""Motor de estados normal / elevado / crítico y referencias de consumo (RN-XI, DC-27, DC-28).

Puro: sin FastAPI, sin SQL, sin archivos y sin reloj. Los umbrales llegan ya leídos de
`config_files/umbrales-estado.v1.json` (`parse_thresholds`) y la hora entra por parámetro.

- 1a: port de `docs/datos/motor_estados_ref.py` (mismos resultados; prueba U-01). Los porcentajes
  se redondean a 6 decimales antes de comparar y los límites son inclusivos (RN-XI-07).
- 1b: referencias (promedio de la misma hora en los 30 días completos anteriores, mínimo 7 días
  con dato) y evaluación de las tres operaciones de consumo (RN-XI-01 a RN-XI-06, RN-XI-09).
- Comparación entre periodos, pico y proyección viven en `app.domain.history` (fase 7, una sola
  implementación); `history` importa de aquí, nunca al revés.

Convenciones:
- Una serie horaria es `{inicio de hora (datetime con zona, cualquiera): kWh de esa hora}`; la
  lectura con inicio h es la hora [h, h+1) y su kWh es el kW promedio de esa hora (RN-IV-03).
  Las fechas y horas del día se calculan en America/Bogota.
- `None` es «sin dato», nunca cero. Los números salen sin redondear ni formatear (DC-11).
"""

from __future__ import annotations

import calendar
import math
import statistics
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal, get_args
from uuid import UUID

from app.domain.simulator import TIMEZONE, hour_from_index, hour_index, recovery_end_hour

State = Literal["normal", "elevado", "critico", "sin_referencia", "sin_datos"]
ReferenceType = Literal["promedio", "meta"]
HourlySeries = Mapping[datetime, float]

STATES: tuple[str, ...] = get_args(State)
PCT_DECIMALS = 6  # redondeo antes de comparar (convención del archivo de umbrales)
HOURS_PER_DAY = 24
COMPARISON_VARIANTS = ("menor", "similar", "mayor", "muy_mayor")
# Bloques que el archivo de umbrales asigna al estado del pico (RN-XIII-03).
PEAK_DAY_BLOCK = "consumo_actual"
PEAK_WEEK_MONTH_BLOCK = "dia_completo"


# ------------------------------------------------------------------ umbrales
@dataclass(frozen=True)
class BandThresholds:
    elevated_from_pct: float
    critical_from_pct: float
    min_excess_kwh: float | None = None


@dataclass(frozen=True)
class PeriodComparisonThresholds:
    lower_if_below_pct: float
    similar_if_below_pct: float
    much_higher_from_pct: float
    states: Mapping[str, State]


@dataclass(frozen=True)
class StateThresholds:
    window_days: int
    min_days_with_data: int
    current: BandThresholds
    cumulative_average: BandThresholds
    cumulative_goal: BandThresholds
    zone_state: BandThresholds
    zone_share: BandThresholds
    full_day: BandThresholds
    peak_min_pct: float
    period_comparison: PeriodComparisonThresholds
    hour_variation_equal_abs_pct: float


def _get(raw: Mapping[str, Any], *path: str) -> Any:
    value: Any = raw
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            raise ValueError(f"falta la clave {'.'.join(path)} en los umbrales")
        value = value[key]
    return value


def _number(raw: Mapping[str, Any], *path: str) -> float:
    value = _get(raw, *path)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"{'.'.join(path)} debe ser numérico")
    return float(value)


def _positive_int(raw: Mapping[str, Any], *path: str) -> int:
    value = _get(raw, *path)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{'.'.join(path)} debe ser un entero positivo")
    return value


def _band(raw: Mapping[str, Any], block: str, suffix: str = "pct") -> BandThresholds:
    min_excess = None
    if isinstance(raw.get(block), Mapping) and "exceso_minimo_kwh" in raw[block]:
        min_excess = _number(raw, block, "exceso_minimo_kwh")
    return BandThresholds(
        _number(raw, block, f"elevado_desde_{suffix}"),
        _number(raw, block, f"critico_desde_{suffix}"),
        min_excess,
    )


def _period_comparison(raw: Mapping[str, Any]) -> PeriodComparisonThresholds:
    states: dict[str, State] = {}
    for variant in COMPARISON_VARIANTS:
        state = _get(raw, "comparacion_periodo", "estado", variant)
        if state not in STATES:
            raise ValueError(f"comparacion_periodo.estado.{variant} no es un estado válido")
        states[variant] = state
    return PeriodComparisonThresholds(
        _number(raw, "comparacion_periodo", "menor_si_menor_que_pct"),
        _number(raw, "comparacion_periodo", "similar_si_menor_que_pct"),
        _number(raw, "comparacion_periodo", "muy_mayor_desde_pct"),
        states,
    )


def parse_thresholds(raw: Mapping[str, Any]) -> StateThresholds:
    """Umbrales del JSON ya leído. ValueError si falta una clave o un valor no es numérico."""
    peak_blocks = (_get(raw, "pico", "estado_en_dia"), _get(raw, "pico", "estado_en_semana_y_mes"))
    if peak_blocks != (PEAK_DAY_BLOCK, PEAK_WEEK_MONTH_BLOCK):
        raise ValueError("pico.estado_en_* no coincide con los bloques que soporta el motor")
    return StateThresholds(
        window_days=_positive_int(raw, "referencia", "ventana_promedio_dias"),
        min_days_with_data=_positive_int(raw, "referencia", "minimo_dias_con_dato"),
        current=_band(raw, "consumo_actual"),
        cumulative_average=_band(raw, "acumulado_promedio"),
        cumulative_goal=_band(raw, "acumulado_meta", "pct_del_limite"),
        zone_state=_band(raw, "zona_estado"),
        zone_share=_band(raw, "zona_participacion"),
        full_day=_band(raw, "dia_completo"),
        peak_min_pct=_number(raw, "pico", "minimo_pct"),
        period_comparison=_period_comparison(raw),
        hour_variation_equal_abs_pct=_number(
            raw, "variacion_hora_anterior", "igual_si_abs_menor_que_pct"
        ),
    )


# ------------------------------------------------------------------ 1a · port de la referencia
def var_pct(value: float | None, reference: float | None) -> float | None:
    """(valor / referencia − 1) × 100 redondeado a 6 decimales; None sin valor o referencia <= 0."""
    if value is None or reference is None or reference <= 0:
        return None
    return round((value / reference - 1.0) * 100.0, PCT_DECIMALS)


def classify(pct: float, band: BandThresholds) -> State:
    """Banda de un % ya redondeado; límites inferiores inclusivos (RN-XI-07)."""
    if pct >= band.critical_from_pct:
        return "critico"
    if pct >= band.elevated_from_pct:
        return "elevado"
    return "normal"


def relative_state(
    value: float | None,
    reference: float | None,
    band: BandThresholds,
    *,
    min_days_with_data: int,
    days_with_data: int,
    excess_kwh: float | None = None,
) -> State:
    """Estado frente a una referencia (consumo actual, acumulado, zona, participación, día)."""
    if value is None:
        return "sin_datos"
    if days_with_data < min_days_with_data or reference is None or reference <= 0:
        return "sin_referencia"
    pct = var_pct(value, reference)
    if band.min_excess_kwh is not None:
        excess = value - reference if excess_kwh is None else excess_kwh
        if excess < band.min_excess_kwh:
            return "normal"
    return classify(pct, band)


def cumulative_goal_state(
    cumulative_kwh: float | None, monthly_goal_kwh: float, days_in_month: int, band: BandThresholds
) -> tuple[State, float | None]:
    """(estado, % del límite diario) del acumulado de hoy contra la meta (RN-XI-04)."""
    if cumulative_kwh is None:
        return "sin_datos", None
    limit = monthly_goal_kwh / days_in_month
    pct = round(cumulative_kwh / limit * 100.0, PCT_DECIMALS)
    return classify(pct, band), pct


def goal_hour_reference(
    monthly_goal_kwh: float, days_in_month: int, hourly_averages: Sequence[float], hour: int
) -> float | None:
    """Límite diario repartido según el peso habitual de la hora (RN-XI-03 con meta)."""
    total = sum(hourly_averages)
    if total <= 0:
        return None
    return monthly_goal_kwh / days_in_month * hourly_averages[hour] / total


def hour_variation(
    current: float | None, previous: float | None, equal_abs_pct: float
) -> Literal["mas", "menos", "igual", "sin_dato"]:
    """Comparación con la hora anterior para el texto corto del estado."""
    if current is None or previous is None or previous <= 0:
        return "sin_dato"
    pct = var_pct(current, previous)
    if abs(pct) < equal_abs_pct:
        return "igual"
    return "mas" if pct > 0 else "menos"


# ------------------------------------------------------------------ 1b · tiempo y series
def evaluated_hour(now: datetime) -> tuple[datetime, datetime]:
    """(inicio, fin) de la última hora completa en America/Bogota. ValueError si `now` es naive."""
    start = recovery_end_hour(now)
    return start, start + timedelta(hours=1)


def _local_date(moment: datetime) -> date:
    if moment.utcoffset() is None:
        raise ValueError("se exige una fecha con zona horaria")
    return moment.astimezone(TIMEZONE).date()


def reference_window_start(hour_start: datetime, window_days: int) -> datetime:
    """00:00 Bogotá de (fecha Bogotá de `hour_start` − `window_days` días)."""
    first = _local_date(hour_start) - timedelta(days=window_days)
    return datetime(first.year, first.month, first.day, tzinfo=TIMEZONE)


def by_index(series: HourlySeries) -> dict[int, float]:
    """Serie indexada por hora absoluta de Bogotá (ordinal × 24 + hora)."""
    return {hour_index(moment): value for moment, value in series.items()}


def totals_by_index(zones: Sequence[Mapping[int, float]]) -> dict[int, float]:
    """Suma por hora solo donde TODAS las zonas tienen lectura; sin zonas, vacío."""
    if not zones:
        return {}
    common = set(zones[0]).intersection(*zones[1:])
    return {index: math.fsum(zone[index] for zone in zones) for index in sorted(common)}


def _household_totals(readings_by_zone: Mapping[UUID, HourlySeries]) -> dict[int, float]:
    """Total del hogar por índice horario (única implementación)."""
    return totals_by_index([by_index(series) for series in readings_by_zone.values()])


def household_hourly_totals(readings_by_zone: Mapping[UUID, HourlySeries]) -> dict[datetime, float]:
    """Total del hogar por hora (claves en Bogotá): solo horas en que TODAS las zonas tienen
    lectura; si falta una, la hora no aparece (nunca un parcial). Mapa vacío -> {}."""
    totals = _household_totals(readings_by_zone)
    return {hour_from_index(index): value for index, value in totals.items()}


def same_hour_average_by_index(
    series: Mapping[int, float], day: int, hour: int, window_days: int
) -> tuple[float | None, int]:
    """`same_hour_average` sobre una serie ya indexada (`by_index`); `day` = ordinal Bogotá."""
    values = [
        series[ordinal * HOURS_PER_DAY + hour]
        for ordinal in range(day - window_days, day)
        if ordinal * HOURS_PER_DAY + hour in series
    ]
    return (statistics.mean(values) if values else None), len(values)


def cumulative_average_by_index(
    series: Mapping[int, float], day: int, hour: int, window_days: int
) -> tuple[float | None, int]:
    """`cumulative_average` sobre una serie ya indexada (`by_index`); `day` = ordinal Bogotá."""
    sums = []
    for ordinal in range(day - window_days, day):
        indexes = [ordinal * HOURS_PER_DAY + h for h in range(hour + 1)]
        if all(index in series for index in indexes):
            sums.append(math.fsum(series[index] for index in indexes))
    return (statistics.mean(sums) if sums else None), len(sums)


def same_hour_average(
    series: HourlySeries, hour_start: datetime, window_days: int
) -> tuple[float | None, int]:
    """(media, días con dato) de la misma hora del día en las `window_days` fechas anteriores a la
    fecha Bogotá de `hour_start`, ignorando días sin dato (DC-28). Media None si 0 días."""
    index = hour_index(hour_start)
    day, hour = divmod(index, HOURS_PER_DAY)
    return same_hour_average_by_index(by_index(series), day, hour, window_days)


def cumulative_average(
    series: HourlySeries, hour_start: datetime, window_days: int
) -> tuple[float | None, int]:
    """(media, días) de lo acumulado de 00:00 hasta la hora de `hour_start` (inclusive) en las
    `window_days` fechas anteriores, solo días con TODAS esas horas (RN-XI-04)."""
    index = hour_index(hour_start)
    day, hour = divmod(index, HOURS_PER_DAY)
    return cumulative_average_by_index(by_index(series), day, hour, window_days)


def valid(reference: float | None, days: int, thresholds: StateThresholds) -> float | None:
    """La referencia solo se publica con el mínimo de días con dato."""
    return reference if days >= thresholds.min_days_with_data else None


def cost(kwh: float | None, price: float | None) -> float | None:
    """kWh × precio por kWh (RN-V-01), sin cargo fijo (RN-V-02); None si falta cualquiera de los
    dos (RN-XI-08: sin tarifa vigente no hay costo; `None` es sin dato, nunca cero)."""
    if kwh is None or price is None:
        return None
    return kwh * price


def days_in_month(day: date) -> int:
    """Días del mes de `day`."""
    return calendar.monthrange(day.year, day.month)[1]


# ------------------------------------------------------------------ 1b · evaluación
@dataclass(frozen=True)
class GoalInput:
    monthly_kwh: float


@dataclass(frozen=True)
class CurrentEvaluation:
    power_kw: float | None
    variation_pct: float | None
    reference_type: ReferenceType
    reference_kw: float | None
    state: State
    message_code: str


@dataclass(frozen=True)
class TodayEvaluation:
    energy_kwh: float
    reference_type: ReferenceType
    reference_kwh: float | None
    shows_limit: bool
    state: State
    message_code: str


@dataclass(frozen=True)
class ZoneEvaluation:
    zona_id: UUID
    power_kw: float | None
    share_pct: float | None
    share_state: State
    average_kw: float | None
    variation_pct: float | None
    zone_state: State
    zone_message_code: str


@dataclass(frozen=True)
class ZonesEvaluation:
    total_kw: float | None
    zones: Mapping[UUID, ZoneEvaluation]


def _goal_hour_reference_for(
    totals: Mapping[int, float], day: int, hour: int, goal: GoalInput, thresholds: StateThresholds
) -> tuple[float | None, int]:
    """Referencia de la hora con meta; None si alguna de las 24 horas no tiene referencia válida."""
    averages: list[float] = []
    min_days = thresholds.window_days
    for h in range(HOURS_PER_DAY):
        average, days = same_hour_average_by_index(totals, day, h, thresholds.window_days)
        min_days = min(min_days, days)
        if average is None or days < thresholds.min_days_with_data:
            return None, min_days
        averages.append(average)
    month_days = days_in_month(date.fromordinal(day))
    return goal_hour_reference(goal.monthly_kwh, month_days, averages, hour), min_days


def evaluate_current(
    readings_by_zone: Mapping[UUID, HourlySeries],
    hour_start: datetime,
    goal: GoalInput | None,
    thresholds: StateThresholds,
) -> CurrentEvaluation:
    """Consumo actual del hogar (RN-XI-01, RN-XI-03). `readings_by_zone`: solo zonas que cuentan.

    `goal` no es None solo si se aplica la meta; su límite diario usa los días del mes de la hora
    evaluada. La variación es contra la hora anterior.
    """
    totals = _household_totals(readings_by_zone)
    index = hour_index(hour_start)
    day, hour = divmod(index, HOURS_PER_DAY)
    power = totals.get(index)
    if goal is None:
        reference_type: ReferenceType = "promedio"
        average, days = same_hour_average_by_index(totals, day, hour, thresholds.window_days)
        reference = valid(average, days, thresholds)
    else:
        reference_type = "meta"
        reference, days = _goal_hour_reference_for(totals, day, hour, goal, thresholds)
    state = relative_state(
        power,
        reference,
        thresholds.current,
        min_days_with_data=thresholds.min_days_with_data,
        days_with_data=days,
    )
    return CurrentEvaluation(
        power_kw=power,
        variation_pct=var_pct(power, totals.get(index - 1)),
        reference_type=reference_type,
        reference_kw=reference,
        state=state,
        message_code=f"consumo_actual.{state}",
    )


def evaluate_today(
    readings_by_zone: Mapping[UUID, HourlySeries],
    now: datetime,
    goal: GoalInput | None,
    thresholds: StateThresholds,
) -> TodayEvaluation:
    """Acumulado de hoy hasta la última hora completa (RN-XI-04).

    Entre 00:00 y 00:59 no hay horas completas de hoy: 0 kWh y `sin_datos`. Si falta alguna hora
    de hoy, suma las que están y el estado es `sin_datos`.
    """
    today = _local_date(now)
    last = hour_index(recovery_end_hour(now))
    day, hour = divmod(last, HOURS_PER_DAY)
    reference_type: ReferenceType = "meta" if goal is not None else "promedio"
    prefix = f"acumulado.{reference_type}"
    limit = goal.monthly_kwh / days_in_month(today) if goal is not None else None
    if day != today.toordinal():
        return TodayEvaluation(
            0.0, reference_type, limit, goal is not None, "sin_datos", f"{prefix}.sin_datos"
        )
    totals = _household_totals(readings_by_zone)
    indexes = [day * HOURS_PER_DAY + h for h in range(hour + 1)]
    energy = math.fsum(totals[index] for index in indexes if index in totals)
    complete = all(index in totals for index in indexes)
    if goal is not None:
        reference = limit
        state, _ = cumulative_goal_state(
            energy, goal.monthly_kwh, days_in_month(today), thresholds.cumulative_goal
        )
    else:
        average, days = cumulative_average_by_index(totals, day, hour, thresholds.window_days)
        reference = valid(average, days, thresholds)
        state = relative_state(
            energy,
            reference,
            thresholds.cumulative_average,
            min_days_with_data=thresholds.min_days_with_data,
            days_with_data=days,
        )
    if not complete:
        state = "sin_datos"
    return TodayEvaluation(
        energy_kwh=energy,
        reference_type=reference_type,
        reference_kwh=reference,
        shows_limit=goal is not None,
        state=state,
        message_code=f"{prefix}.{state}",
    )


def _share(
    power: float | None,
    total: float | None,
    zone_series: Mapping[int, float],
    totals: Mapping[int, float],
    day: int,
    hour: int,
    thresholds: StateThresholds,
) -> tuple[float | None, State]:
    """Participación de la zona y su estado frente a la habitual a la misma hora (RN-XI-05).

    RN-XI-05 no fija la fórmula de la participación habitual; se usa la más simple:
    habitual = promedio de la zona ÷ promedio del total, ambos sobre EL MISMO conjunto de días
    (los de la ventana en que, a esa hora, hay total del hogar y lectura de la zona);
    `days_with_data` = ese número de días. Estado = `relative_state(participación %,
    habitual × 100, zona_participacion)` con exceso = kW zona − habitual × total.
    Total None o zona sin lectura: (None, sin_datos); total <= 0: (None, sin_referencia).
    """
    if total is None or power is None:
        return None, "sin_datos"
    if total <= 0:
        return None, "sin_referencia"
    share = power / total * 100.0
    zone_values, total_values = [], []
    for ordinal in range(day - thresholds.window_days, day):
        index = ordinal * HOURS_PER_DAY + hour
        if index in totals and index in zone_series:
            zone_values.append(zone_series[index])
            total_values.append(totals[index])
    days = len(total_values)
    if not days:
        return share, "sin_referencia"
    total_average = statistics.mean(total_values)
    if total_average <= 0:
        return share, "sin_referencia"
    habitual = statistics.mean(zone_values) / total_average
    state = relative_state(
        share,
        habitual * 100.0,
        thresholds.zone_share,
        min_days_with_data=thresholds.min_days_with_data,
        days_with_data=days,
        excess_kwh=power - habitual * total,
    )
    return share, state


def _not_counting(zona_id: UUID) -> ZoneEvaluation:
    """Zona que no suma al total: sin dato en todo (decisión del 23/11/2026)."""
    return ZoneEvaluation(
        zona_id=zona_id,
        power_kw=None,
        share_pct=None,
        share_state="sin_datos",
        average_kw=None,
        variation_pct=None,
        zone_state="sin_datos",
        zone_message_code="zona_estado.sin_datos",
    )


def evaluate_zones(
    readings_by_zone: Mapping[UUID, HourlySeries],
    counting_zone_ids: Collection[UUID],
    hour_start: datetime,
    thresholds: StateThresholds,
) -> ZonesEvaluation:
    """Total del hogar, participación y estado de cada zona en la hora (RN-XI-05, RN-XI-06).

    El total suma solo `counting_zone_ids`; una zona que cuenta y no viene en `readings_by_zone`
    se trata como serie vacía y deja el total en None. Una zona de `readings_by_zone` que NO
    cuenta (zona inactiva o sensor pausado) no se evalúa: todo None y estados `sin_datos`, sin
    calcular nada con sus lecturas.
    """
    series = {zona_id: by_index(values) for zona_id, values in readings_by_zone.items()}
    counting = [series.get(zona_id, {}) for zona_id in counting_zone_ids]
    totals = totals_by_index(counting)
    index = hour_index(hour_start)
    day, hour = divmod(index, HOURS_PER_DAY)
    total = totals.get(index)
    zones: dict[UUID, ZoneEvaluation] = {}
    for zona_id, zone_series in series.items():
        if zona_id not in counting_zone_ids:
            zones[zona_id] = _not_counting(zona_id)
            continue
        power = zone_series.get(index)
        share, share_state = _share(power, total, zone_series, totals, day, hour, thresholds)
        average, days = same_hour_average_by_index(zone_series, day, hour, thresholds.window_days)
        reference = valid(average, days, thresholds)
        zone_state = relative_state(
            power,
            reference,
            thresholds.zone_state,
            min_days_with_data=thresholds.min_days_with_data,
            days_with_data=days,
        )
        zones[zona_id] = ZoneEvaluation(
            zona_id=zona_id,
            power_kw=power,
            share_pct=share,
            share_state=share_state,
            average_kw=reference,
            variation_pct=var_pct(power, reference),
            zone_state=zone_state,
            zone_message_code=f"zona_estado.{zone_state}",
        )
    return ZonesEvaluation(total_kw=total, zones=zones)
