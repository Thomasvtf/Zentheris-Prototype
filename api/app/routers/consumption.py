"""Router de la etiqueta «Consumo» del contrato 0.2.5.

Solo valida la entrada y llama al servicio (api/CLAUDE.md).
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.errors import error_responses
from app.schemas.consumption import (
    ConsumoActualHogar,
    ConsumoZonaDetalle,
    ConsumoZonas,
    FuentesDatos,
    Historial,
)
from app.security.dependencies import CurrentUser
from app.services import consumption as service

router = APIRouter(tags=["Consumo"])


@router.get(
    "/hogares/{hogar_id}/consumo/actual",
    operation_id="obtenerConsumoActual",
    summary="Cards del Panel principal (RN-XI-01, RN-XI-03, RN-XI-04, RN-XI-08)",
    response_model=ConsumoActualHogar,
    responses=error_responses(401, 403, 404),
)
def get_current_consumption(hogar_id: UUID, user: CurrentUser) -> ConsumoActualHogar:
    """Cards del Panel principal (RN-XI-01, RN-XI-03, RN-XI-04, RN-XI-08)."""
    return service.get_current_consumption(user.id, hogar_id)


@router.get(
    "/hogares/{hogar_id}/consumo/zonas",
    operation_id="obtenerConsumoZonas",
    summary="Participación y estado de cada zona en la última hora completa (RN-XI-05, RN-XII-05, RN-XII-06)",
    response_model=ConsumoZonas,
    responses=error_responses(401, 403, 404),
)
def get_zones_consumption(hogar_id: UUID, user: CurrentUser) -> ConsumoZonas:
    """Participación y estado de cada zona en la última hora completa (RN-XI-05, RN-XII-05, RN-XII-06)."""
    return service.get_zones_consumption(user.id, hogar_id)


@router.get(
    "/hogares/{hogar_id}/consumo/zonas/{zona_id}",
    operation_id="obtenerConsumoZona",
    summary="Zona individual (RN-XI-05, RN-XI-06, RN-XII-07)",
    response_model=ConsumoZonaDetalle,
    responses=error_responses(401, 403, 404),
)
def get_zone_consumption(hogar_id: UUID, zona_id: UUID, user: CurrentUser) -> ConsumoZonaDetalle:
    """Zona individual (RN-XI-05, RN-XI-06, RN-XII-07)."""
    return service.get_zone_consumption(user.id, hogar_id, zona_id)


@router.get(
    "/hogares/{hogar_id}/historial",
    operation_id="obtenerHistorial",
    summary="Historial por periodo (RN-XIII-01 a RN-XIII-06)",
    response_model=Historial,
    responses=error_responses(401, 403, 404, 422),
)
def get_history(
    hogar_id: UUID,
    user: CurrentUser,
    periodo: Annotated[Literal["dia", "semana", "mes"], Query()],
    zona_id: Annotated[UUID | None, Query()] = None,
) -> Historial:
    """Historial por periodo (RN-XIII-01 a RN-XIII-06)."""
    return service.get_history(user.id, hogar_id, periodo, zona_id)


@router.get(
    "/hogares/{hogar_id}/fuentes-datos",
    operation_id="obtenerFuentesDatos",
    summary="Fuente principal y sensores, solo lectura (RN-III-03, RN-XVI-06)",
    response_model=FuentesDatos,
    responses=error_responses(401, 404),
)
def get_data_sources(hogar_id: UUID, user: CurrentUser) -> FuentesDatos:
    """Fuente principal y sensores, solo lectura (RN-III-03, RN-XVI-06)."""
    return service.get_data_sources(user.id, hogar_id)
