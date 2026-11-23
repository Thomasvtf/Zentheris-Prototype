"""Motor del simulador (sección 5 de las reglas, DC-53), fiel a la referencia del Avance 03.

L = T·Q + ΣE,  T = B·H·F,  n(t) = φ·n(t−1) + σ·ε,  w' = max(0, w·(1+n)),  Q = w'/Σw'
E = P·(D/60)·f/1000 repartida por minutos de solapamiento.

Convenciones adoptadas (Avance 01, A05–A15):
- franjas [desde, hasta); p efectiva = probabilidad × multiplicador (A05)
- P, D y f uniformes continuas; minuto uniforme discreto inclusivo (A06)
- n[−1] = 0 y la hora 0 ya recibe su innovación (A07)
- realización con Σw' <= 0 se rechaza, no se corrige (A08)
- la lectura de una hora se etiqueta por su inicio [h, h+1) (A12)
- frontera izquierda del historial: no se incorporan eventos iniciados antes (A10);
  la cola derecha del backfill no se exporta y la generación posterior la suma (A09)
- Q se calcula con el día completo aunque se exporte una parte (A11)

Representación del tiempo: índice horario absoluto = ordinal_de_fecha × 24 + hora, en hora local
de Bogotá (sin horario de verano), convertido a datetime de America/Bogota solo al exportar.

Puro: sin archivos, sin reloj, sin FastAPI ni SQL. Los perfiles y la hora entran por parámetro.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, NamedTuple
from uuid import UUID

from app.domain.simulator.constants import (
    BASE_COLUMNS,
    HOURS_BACKFILL,
    KWH_SCALE,
    READING_QUALITY,
    TIMEZONE,
    VERSION_MODELO,
)
from app.domain.simulator.seeds import uniforms
from app.domain.simulator.validation import effective_probabilities

_KWH_QUANTUM = Decimal(1).scaleb(-KWH_SCALE)  # 0.0001: NUMERIC(12,4)


class DegenerateRealizationError(ArithmeticError):
    """Σw' <= 0: el ruido anuló toda la curva (A08)."""


@dataclass(frozen=True)
class Event:
    """Evento de sobreconsumo sorteado."""

    zone: str
    start_min: int  # minutos absolutos enteros (ordinal × 1440 + minuto del día)
    duration_min: float
    power_w: float
    usage_fraction: float
    energy_kwh: float


@dataclass(frozen=True)
class RegularDay:
    """Componentes del consumo regular de una zona en un día."""

    base: float  # B
    humor: float  # H
    calendar_factor: float  # F
    target: float  # T = B·H·F
    weights: list[float]  # Q
    noise: list[float]  # n
    regular: list[float]  # T·Q por hora


class HourReading(NamedTuple):
    """Consumo de una zona en una hora; `total` = `regular` + `events`, sin redondear."""

    index: int
    regular: float
    events: float
    total: float


class ZoneDetail(NamedTuple):
    """Lecturas de una zona con los días y eventos de los que salen."""

    readings: list[HourReading]
    days: dict[int, RegularDay]
    events: list[Event]


# ------------------------------------------------------------ tiempo
def hour_index(moment: datetime) -> int:
    """Índice de la hora [h, h+1) que contiene el instante."""
    # Un datetime sin zona se interpretaría con la hora del servidor (UTC en Render).
    if moment.utcoffset() is None:
        raise ValueError("se exige una fecha con zona horaria")
    local = moment.astimezone(TIMEZONE)
    return local.date().toordinal() * 24 + local.hour


def hour_from_index(index: int) -> datetime:
    """Inicio de la hora, en America/Bogota."""
    day = date.fromordinal(index // 24)
    return datetime(day.year, day.month, day.day, index % 24, tzinfo=TIMEZONE)


def last_complete_hour(now: datetime) -> int:
    """Índice de la última hora completa [h, h+1) con h+1 <= now (RN-XI-01)."""
    return hour_index(now) - 1


# ------------------------------------------------------------ componentes puros
def daily_humor(
    hogar_id: UUID | str, day: date, profile: Mapping[str, Any], version: str = VERSION_MODELO
) -> float:
    """H: un sorteo por hogar y día, igual para todas sus zonas."""
    (u,) = uniforms(hogar_id, day, version, None, "humor", 1)
    return profile["humor_min"] + (profile["humor_max"] - profile["humor_min"]) * u


def calendar_factor(day: date, profile: Mapping[str, Any]) -> float:
    """F: `factor_fin_semana` en sábado y domingo; 1 los demás días."""
    return profile["factor_fin_semana"] if day.weekday() >= 5 else 1.0


def zone_curve(profile: Mapping[str, Any], zone: str) -> list[float]:
    """Curva propia de la zona o, si no tiene, la curva `base`."""
    curves = profile["curva_horaria"]
    return curves.get(zone, curves["base"])


def calculate_weights(
    curve: Sequence[float], epsilons: Sequence[float], memory: float, intensity: float
) -> tuple[list[float], list[float]]:
    """Devuelve (Q, n). Lanza `DegenerateRealizationError` si Σw' <= 0."""
    previous, noise, raw = 0.0, [], []
    for hour in range(24):
        current = memory * previous + intensity * epsilons[hour]
        noise.append(current)
        raw.append(max(0.0, curve[hour] * (1.0 + current)))
        previous = current
    total = math.fsum(raw)
    if not total > 0:
        raise DegenerateRealizationError("Σw' <= 0")
    return [value / total for value in raw], noise


def noise_epsilons(
    hogar_id: UUID | str, day: date, zone: str, version: str = VERSION_MODELO
) -> list[float]:
    """ε en [−1, 1) por hora del día."""
    return [2.0 * u - 1.0 for u in uniforms(hogar_id, day, version, zone, "ruido", 24)]


def regular_day(
    hogar_id: UUID | str,
    day: date,
    zone: str,
    profile: Mapping[str, Any],
    version: str = VERSION_MODELO,
) -> RegularDay:
    """Consumo regular de la zona en el día completo (A11)."""
    base = profile[BASE_COLUMNS[zone]]
    humor = daily_humor(hogar_id, day, profile, version)
    factor = calendar_factor(day, profile)
    target = base * humor * factor
    noise_config = profile["ruido_config"]
    weights, noise = calculate_weights(
        zone_curve(profile, zone),
        noise_epsilons(hogar_id, day, zone, version),
        noise_config["memoria"],
        noise_config["intensidad"],
    )
    return RegularDay(
        base, humor, factor, target, weights, noise, [target * weight for weight in weights]
    )


def _uniform(low: float, high: float, u: float) -> float:
    return low + (high - low) * u


def _minute(low: int, high: int, u: float) -> int:
    low, high = int(low), int(high)
    return min(high, low + math.floor(u * (high - low + 1)))


def day_events(
    hogar_id: UUID | str,
    day: date,
    zone: str,
    profile: Mapping[str, Any],
    version: str = VERSION_MODELO,
) -> list[Event]:
    """Eventos que empiezan ese día en la zona."""
    config = profile["picos_config"].get(zone)
    if config is None:
        return []
    draws = uniforms(hogar_id, day, version, zone, "eventos", 24 * 5)
    probabilities = effective_probabilities(config)
    day_start_min = day.toordinal() * 1440
    events = []
    for hour in range(24):
        u_occurs, u_power, u_duration, u_minute, u_fraction = draws[5 * hour : 5 * hour + 5]
        if u_occurs < probabilities[hour]:
            power = _uniform(*config["potencia_w"], u_power)
            duration = _uniform(*config["duracion_min"], u_duration)
            minute = _minute(*config["minuto_inicio"], u_minute)
            fraction = _uniform(*config["fraccion_uso"], u_fraction)
            energy = power * (duration / 60.0) * fraction / 1000.0
            start_min = day_start_min + 60 * hour + minute
            events.append(Event(zone, start_min, duration, power, fraction, energy))
    return events


def spread_event(event: Event) -> dict[int, float]:
    """Energía del evento por índice horario, proporcional a los minutos de solapamiento."""
    if event.duration_min <= 0 or event.energy_kwh == 0:
        return {}
    # Desplazamientos relativos a la hora de inicio: con minutos absolutos (~1e9) la suma
    # inicio + D pierde precisión (registro_cambios de la referencia, F01).
    first_hour = int(event.start_min) // 60
    offset = event.start_min - 60 * first_hour  # minuto entero dentro de la hora
    end = offset + event.duration_min
    shares: dict[int, float] = {}
    step = 0
    while 60 * step < end:
        overlap = min(end, 60.0 * (step + 1)) - max(offset, 60.0 * step)
        if overlap > 0:
            shares[first_hour + step] = event.energy_kwh * overlap / event.duration_min
        step += 1
    return shares


def lookback_days(profile: Mapping[str, Any]) -> int:
    """Días previos cuyos eventos pueden alcanzar el día actual."""
    longest = max(
        (config["duracion_min"][1] for config in profile["picos_config"].values()), default=0
    )
    return math.ceil((59 + longest) / 1440.0) if longest > 0 else 0


# ------------------------------------------------------------ generación
def simulate_zone_detail(
    hogar_id: UUID | str,
    profile: Mapping[str, Any],
    zone: str,
    start: int,
    end: int,
    frontier: int,
    version: str = VERSION_MODELO,
) -> ZoneDetail:
    """Lecturas de una zona para los índices horarios [start, end), con días y eventos.

    `frontier`: índice de la primera hora del historial del sensor; no se incorporan eventos
    iniciados antes de ella (A10). La lectura de cada hora es una función pura de (hogar, perfil,
    zona, hora, frontera, versión): backfill, generación incremental y recuperación producen el
    mismo valor (RN-IV-05).
    """
    if not frontier <= start <= end:
        raise ValueError("se exige frontier <= start <= end")
    regular: dict[int, float] = {}
    event_kwh = {index: 0.0 for index in range(start, end)}
    days: dict[int, RegularDay] = {}
    events: list[Event] = []
    first_day, last_day = start // 24, (end - 1) // 24
    for ordinal in range(first_day, last_day + 1):
        day = regular_day(hogar_id, date.fromordinal(ordinal), zone, profile, version)
        days[ordinal] = day
        for hour in range(24):
            index = ordinal * 24 + hour
            if start <= index < end:
                regular[index] = day.regular[hour]
    first_event_day = max(frontier // 24, first_day - lookback_days(profile))
    for ordinal in range(first_event_day, last_day + 1):
        for event in day_events(hogar_id, date.fromordinal(ordinal), zone, profile, version):
            if event.start_min < frontier * 60 or event.start_min >= end * 60:
                continue
            for index, kwh in spread_event(event).items():
                if start <= index < end:
                    event_kwh[index] += kwh
            events.append(event)
    readings = [
        HourReading(index, regular[index], event_kwh[index], regular[index] + event_kwh[index])
        for index in range(start, end)
    ]
    return ZoneDetail(readings, days, events)


def simulate_zone(
    hogar_id: UUID | str,
    profile: Mapping[str, Any],
    zone: str,
    start: int,
    end: int,
    frontier: int,
    version: str = VERSION_MODELO,
) -> list[HourReading]:
    """Como `simulate_zone_detail`, pero solo las lecturas."""
    return simulate_zone_detail(hogar_id, profile, zone, start, end, frontier, version).readings


def simulate_household(
    hogar_id: UUID | str,
    profile: Mapping[str, Any],
    zones: Iterable[str],
    start: int,
    end: int,
    frontier: int | None = None,
    version: str = VERSION_MODELO,
) -> dict[str, list[HourReading]]:
    """Solo las zonas elegidas por el hogar (RN-IV-07).

    Las zonas ausentes no generan filas y su base no se reparte entre las demás.
    """
    frontier = start if frontier is None else frontier
    return {
        zone: simulate_zone(hogar_id, profile, zone, start, end, frontier, version)
        for zone in sorted(zones)
    }


def simulate_backfill(
    hogar_id: UUID | str,
    profile: Mapping[str, Any],
    zones: Iterable[str],
    now: datetime,
    hours: int = HOURS_BACKFILL,
    version: str = VERSION_MODELO,
) -> dict[str, list[HourReading]]:
    """RN-IV-01: `hours` horas que terminan en la última hora completa, sin redondear."""
    end = last_complete_hour(now) + 1
    start = end - hours
    return simulate_household(hogar_id, profile, zones, start, end, start, version)


def household_total(series: Mapping[str, Sequence[HourReading]]) -> dict[int, float]:
    """El total del hogar se deriva de las zonas; no es una lectura almacenada."""
    totals: dict[int, float] = {}
    for readings in series.values():
        for reading in readings:
            totals[reading.index] = totals.get(reading.index, 0.0) + reading.total
    return totals


# ------------------------------------------------------------ filas de `lecturas`
def round_kwh(value: float) -> Decimal:
    """Valor tal como lo guarda NUMERIC(12,4) (mitad hacia arriba, value >= 0)."""
    return Decimal(repr(value)).quantize(_KWH_QUANTUM, rounding=ROUND_HALF_UP)


def reading_row(sensor_id: UUID, index: int, total: float) -> dict[str, Any]:
    """Fila para `lecturas` (sin id)."""
    return {
        "sensor_id": sensor_id,
        "fecha_hora": hour_from_index(index),
        "consumo_kwh": round_kwh(total),
        "calidad": READING_QUALITY,
    }


def to_reading_rows(
    sensors_by_zone: Mapping[str, UUID], series: Mapping[str, Sequence[HourReading]]
) -> list[dict[str, Any]]:
    """Filas para `lecturas` a partir de las series por zona."""
    return [
        reading_row(sensors_by_zone[zone], reading.index, reading.total)
        for zone, readings in series.items()
        for reading in readings
    ]


def generate_backfill(
    hogar_id: UUID,
    profile: Mapping[str, Any],
    sensors_by_zone: Mapping[str, UUID],
    now: datetime,
    hours: int = HOURS_BACKFILL,
) -> list[dict[str, Any]]:
    """Llenado inicial (RN-IV-01): `hours` lecturas por zona hasta la última hora completa.

    Solo las zonas de `sensors_by_zone` (RN-IV-07). Filas con `sensor_id` (UUID), `fecha_hora`
    (datetime de Bogotá), `consumo_kwh` (Decimal de 4 decimales) y `calidad` («simulada»).
    """
    series = simulate_backfill(hogar_id, profile, sensors_by_zone, now, hours)
    return to_reading_rows(sensors_by_zone, series)
