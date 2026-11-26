"""Fuentes de datos: sensores por zona y fuente principal (RN-XVI-06, RN-III-03, RN-XVII-01).

Puro: recibe los sensores del hogar con el kWh de la última hora completa (kWh en 1 h = kW medio,
RN-IV-03) y devuelve la vista. `None` es «sin dato», nunca cero.

- Estado del sensor: `pausado` si el sensor está pausado (gana a `sin_datos`); si no,
  `sin_datos` si no llegó la lectura de esa hora; si no, `activo`. No es una columna guardada.
- Fuente principal: suma de los sensores que cuentan (`zone_rules.counts_for_total`: zona activa
  y sensor activo). None si a alguno de ellos le falta la lectura o si no cuenta ninguno (nunca
  un total parcial).
- Sin permiso de ver consumo actual (ni administrador): `valores_ocultos=True` y todos los kW
  None; nombres y estados se siguen mostrando.
- Orden: nombre visible de la zona (RN-XII-03) y luego id de zona.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.domain.formats import sensor_name, zone_name
from app.domain.zone_rules import counts_for_total

SensorState = Literal["activo", "pausado", "sin_datos"]
SensorStatus = Literal["activo", "pausado"]

_PAUSED = "pausado"
_ACTIVE = "activo"


@dataclass(frozen=True)
class SensorInput:
    sensor_id: UUID
    zona_id: UUID
    zona_tipo: str
    zona_estado: str
    sensor_estado: SensorStatus
    kwh: float | None  # kWh de la última hora completa o None


@dataclass(frozen=True)
class SensorView:
    sensor_id: UUID
    zona_id: UUID
    nombre: str
    zona_nombre: str
    potencia_kw: float | None
    estado: SensorState


@dataclass(frozen=True)
class DataSourcesView:
    valores_ocultos: bool
    fuente_potencia_kw: float | None
    sensores: tuple[SensorView, ...]


def sensor_state(sensor_estado: SensorStatus, kwh: float | None) -> SensorState:
    """Estado visible del sensor; `pausado` gana a `sin_datos`.

    Raises:
        ValueError: `sensor_estado` no es `activo` ni `pausado`.
    """
    if sensor_estado == _PAUSED:
        return "pausado"
    if sensor_estado != _ACTIVE:
        raise ValueError("estado de sensor fuera del catálogo")
    return "sin_datos" if kwh is None else "activo"


def _source_kw(sensors: Sequence[SensorInput]) -> float | None:
    """Suma de los sensores que cuentan; None si falta una lectura o no cuenta ninguno."""
    counting = [s for s in sensors if counts_for_total(s.zona_estado, s.sensor_estado)]
    if not counting or any(s.kwh is None for s in counting):
        return None
    return math.fsum(s.kwh for s in counting if s.kwh is not None)


def evaluate_data_sources(
    sensors: Sequence[SensorInput], can_view_values: bool
) -> DataSourcesView:
    """Vista de Fuentes de datos (D5 de la fase 10).

    Raises:
        KeyError: un `zona_tipo` no está en el catálogo de 9 zonas.
        ValueError: un `sensor_estado` no es `activo` ni `pausado`.
    """
    views = [
        SensorView(
            sensor_id=s.sensor_id,
            zona_id=s.zona_id,
            nombre=sensor_name(s.zona_tipo),
            zona_nombre=zone_name(s.zona_tipo),
            potencia_kw=s.kwh if can_view_values else None,
            estado=sensor_state(s.sensor_estado, s.kwh),
        )
        for s in sensors
    ]
    views.sort(key=lambda view: (view.zona_nombre, view.zona_id))
    return DataSourcesView(
        valores_ocultos=not can_view_values,
        fuente_potencia_kw=_source_kw(sensors) if can_view_values else None,
        sensores=tuple(views),
    )
