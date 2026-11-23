"""Recuperación de horas faltantes (RN-IV-05, DC-34). Pura: recibe lo que ya existe."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.simulator.engine import (
    hour_index,
    last_complete_hour,
    reading_row,
    simulate_zone,
)


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
    """
    end = last_complete_hour(now) + 1
    rows: list[dict[str, Any]] = []
    for zone in sorted(sensors_by_zone):
        stored = {hour_index(moment) for moment in existing_hours.get(zone, ())}
        if not stored:
            continue
        frontier = min(stored)
        missing = [index for index in range(frontier, end) if index not in stored]
        if not missing:
            continue
        readings = simulate_zone(hogar_id, profile, zone, missing[0], end, frontier)
        totals = {reading.index: reading.total for reading in readings}
        rows += [reading_row(sensors_by_zone[zone], index, totals[index]) for index in missing]
    return rows
