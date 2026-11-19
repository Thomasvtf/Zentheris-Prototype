"""Casos de uso de la etiqueta «Consumo».

Esqueleto: cada función responde 501 con su operationId hasta su sesión.
Manejan las transacciones y llaman a domain/ y data/ (api/CLAUDE.md).
"""

from typing import Literal
from uuid import UUID

from app.errors import NotImplementedOperation
from app.schemas.consumption import (
    ConsumoActualHogar,
    ConsumoZonaDetalle,
    ConsumoZonas,
    FuentesDatos,
    Historial,
)


def get_current_consumption(user_id: UUID, hogar_id: UUID) -> ConsumoActualHogar:
    """`obtenerConsumoActual`: Cards del Panel principal (RN-XI-01, RN-XI-03, RN-XI-04, RN-XI-08). TODO(obtenerConsumoActual)."""
    raise NotImplementedOperation("obtenerConsumoActual")


def get_zones_consumption(user_id: UUID, hogar_id: UUID) -> ConsumoZonas:
    """`obtenerConsumoZonas`: Participación y estado de cada zona en la última hora completa (RN-XI-05, RN-XII-05, RN-XII-06). TODO(obtenerConsumoZonas)."""
    raise NotImplementedOperation("obtenerConsumoZonas")


def get_zone_consumption(user_id: UUID, hogar_id: UUID, zona_id: UUID) -> ConsumoZonaDetalle:
    """`obtenerConsumoZona`: Zona individual (RN-XI-05, RN-XI-06, RN-XII-07). TODO(obtenerConsumoZona)."""
    raise NotImplementedOperation("obtenerConsumoZona")


def get_history(
    user_id: UUID, hogar_id: UUID, periodo: Literal["dia", "semana", "mes"], zona_id: UUID | None
) -> Historial:
    """`obtenerHistorial`: Historial por periodo (RN-XIII-01 a RN-XIII-06). TODO(obtenerHistorial)."""
    raise NotImplementedOperation("obtenerHistorial")


def get_data_sources(user_id: UUID, hogar_id: UUID) -> FuentesDatos:
    """`obtenerFuentesDatos`: Fuente principal y sensores, solo lectura (RN-III-03, RN-XVI-06). TODO(obtenerFuentesDatos)."""
    raise NotImplementedOperation("obtenerFuentesDatos")
