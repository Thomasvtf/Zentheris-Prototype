"""Router de la etiqueta «Consumo» del contrato.

Solo valida la entrada y llama al servicio (api/CLAUDE.md). Las consultas de consumo reciben la
sesión de la petición (`get_session`), la misma que usó la guardia; el servicio completa las horas
faltantes antes de leer (RN-IV-05, DC-34).
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.data.database import get_session
from app.errors import error_responses
from app.schemas.consumption import (
    ConsumoActualHogar,
    ConsumoZonaDetalle,
    ConsumoZonas,
    FuentesDatos,
    Historial,
)
from app.security.dependencies import (
    CurrentMembership,
    CurrentUser,
    Membership,
    require_permission,
)
from app.services import consumption as service

router = APIRouter(tags=["Consumo"])

# La misma sesión que reciben las dependencias de la petición (la guardia de membresía).
DbSession = Annotated[Session, Depends(get_session)]


@router.get(
    "/hogares/{hogar_id}/consumo/actual",
    operation_id="obtenerConsumoActual",
    summary="Cards del Panel principal (RN-XI-01, RN-XI-03, RN-XI-04, RN-XI-08)",
    response_model=ConsumoActualHogar,
    responses=error_responses(401, 403, 404),
)
def get_current_consumption(
    hogar_id: UUID,
    user: CurrentUser,
    member: Annotated[Membership, Depends(require_permission("ver_consumo_actual"))],
    session: DbSession,
) -> ConsumoActualHogar:
    """Cards del Panel principal (RN-XI-01, RN-XI-03, RN-XI-04, RN-XI-08)."""
    return service.get_current_consumption(session, user.id, hogar_id)


@router.get(
    "/hogares/{hogar_id}/consumo/zonas",
    operation_id="obtenerConsumoZonas",
    summary="Participación y estado de las zonas que cuentan en la última hora completa (RN-XI-05, RN-XII-05, RN-XII-06)",
    response_model=ConsumoZonas,
    responses=error_responses(401, 403, 404),
)
def get_zones_consumption(
    hogar_id: UUID,
    user: CurrentUser,
    member: Annotated[Membership, Depends(require_permission("ver_consumo_actual"))],
    session: DbSession,
) -> ConsumoZonas:
    """Participación y estado de cada zona en la última hora completa (RN-XI-05, RN-XII-05, RN-XII-06)."""
    return service.get_zones_consumption(session, user.id, hogar_id)


@router.get(
    "/hogares/{hogar_id}/consumo/zonas/{zona_id}",
    operation_id="obtenerConsumoZona",
    summary="Zona individual (RN-XI-05, RN-XI-06, RN-XII-07)",
    response_model=ConsumoZonaDetalle,
    responses=error_responses(401, 403, 404),
)
def get_zone_consumption(
    hogar_id: UUID,
    zona_id: UUID,
    user: CurrentUser,
    member: Annotated[Membership, Depends(require_permission("ver_consumo_actual"))],
    session: DbSession,
) -> ConsumoZonaDetalle:
    """Zona individual (RN-XI-05, RN-XI-06, RN-XII-07)."""
    return service.get_zone_consumption(session, user.id, hogar_id, zona_id)


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
    member: Annotated[Membership, Depends(require_permission("ver_historial"))],
    periodo: Annotated[Literal["dia", "semana", "mes"], Query()],
    session: DbSession,
    zona_id: Annotated[UUID | None, Query()] = None,
) -> Historial:
    """Historial por periodo (RN-XIII-01 a RN-XIII-06)."""
    return service.get_history(session, user.id, hogar_id, periodo, zona_id)


@router.get(
    "/hogares/{hogar_id}/fuentes-datos",
    operation_id="obtenerFuentesDatos",
    summary="Fuente principal y sensores, solo lectura (RN-III-03, RN-XVI-06)",
    response_model=FuentesDatos,
    responses=error_responses(401, 404, 422),
)
def get_data_sources(
    hogar_id: UUID, user: CurrentUser, member: CurrentMembership, session: DbSession
) -> FuentesDatos:
    """Fuente principal y sensores, solo lectura (RN-III-03, RN-XVI-06).

    Sin `ver_consumo_actual` no hay 403: el servicio oculta los valores (P-07, RN-XVII-01).
    """
    can_view_values = member.is_admin or member.permisos.ver_consumo_actual
    return service.get_data_sources(session, user.id, hogar_id, can_view_values)
