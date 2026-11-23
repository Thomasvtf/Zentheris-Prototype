"""Recuperación de horas faltantes (RN-IV-05, DC-34). Pura: recibe lo que ya existe."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime
from typing import Any, NamedTuple
from uuid import UUID

from app.domain.simulator.engine import (
    hour_from_index,
    hour_index,
    last_complete_hour,
    reading_row,
    simulate_zone,
)


class SensorGaps(NamedTuple):
    """Lo que falta de un sensor, tal como lo entrega la base."""

    sensor_id: UUID
    first_hour: datetime | None  # primera lectura guardada (frontera). None: sin lecturas
    missing_hours: Collection[datetime]  # horas sin lectura en [first_hour, end_hour], con zona


def recovery_end_hour(now: datetime) -> datetime:
    """Inicio (America/Bogota) de la última hora completa de `now`: la última que debe existir.

    ValueError si `now` no tiene zona horaria.
    """
    return hour_from_index(last_complete_hour(now))


def generate_readings_for_gaps(
    hogar_id: UUID,
    profile: Mapping[str, Any],
    gaps_by_zone: Mapping[str, SensorGaps],
    now: datetime,
) -> list[dict[str, Any]]:
    """Filas de `lecturas` para las horas faltantes, idénticas a una generación continua.

    La frontera de cada zona es `first_hour` (primera lectura del sensor). Se ignoran las horas
    anteriores a la frontera y las posteriores a `recovery_end_hour(now)`; una hora repetida en
    `missing_hours` sale una sola vez. Zona sin lecturas o sin horas faltantes: nada. Orden: por
    zona (sorted) y luego por hora.
    """
    end = last_complete_hour(now) + 1
    rows: list[dict[str, Any]] = []
    for zone in sorted(gaps_by_zone):
        gaps = gaps_by_zone[zone]
        if gaps.first_hour is None:
            continue
        frontier = hour_index(gaps.first_hour)
        missing = sorted(
            {index for index in map(hour_index, gaps.missing_hours) if frontier <= index < end}
        )
        if not missing:
            continue
        readings = simulate_zone(hogar_id, profile, zone, missing[0], end, frontier)
        totals = {reading.index: reading.total for reading in readings}
        rows += [reading_row(gaps.sensor_id, index, totals[index]) for index in missing]
    return rows


def generate_missing_readings(
    hogar_id: UUID,
    profile: Mapping[str, Any],
    sensors_by_zone: Mapping[str, UUID],
    existing_hours: Mapping[str, Collection[datetime]],
    now: datetime,
) -> list[dict[str, Any]]:
    """Filas que faltan por zona hasta la última hora completa, idénticas a las continuas.

    `existing_hours` trae, por zona, las `fecha_hora` guardadas de su sensor. Completa huecos
    internos y horas posteriores sin repetir lo existente (A13). La frontera es la primera
    lectura del sensor, así que la colección debe incluirla. Una zona sin lecturas no genera nada.
    Construye los huecos de cada sensor y delega en `generate_readings_for_gaps`.
    """
    end = last_complete_hour(now) + 1
    gaps_by_zone: dict[str, SensorGaps] = {}
    for zone, sensor_id in sensors_by_zone.items():
        stored = {hour_index(moment) for moment in existing_hours.get(zone, ())}
        if not stored:
            gaps_by_zone[zone] = SensorGaps(sensor_id, None, ())
            continue
        frontier = min(stored)
        gaps_by_zone[zone] = SensorGaps(
            sensor_id,
            hour_from_index(frontier),
            [hour_from_index(index) for index in range(frontier, end) if index not in stored],
        )
    return generate_readings_for_gaps(hogar_id, profile, gaps_by_zone, now)
