"""Router de la etiqueta «Metas y tarifa» del contrato.

Solo valida la entrada y llama al servicio (api/CLAUDE.md). Cada operación recibe la sesión de la
petición (`get_session`), la misma que usó la guardia de membresía; el servicio hace el commit y
el bloqueo del hogar. `puede_editar` lo decide el rol y el permiso de la guardia: meta,
administrador o `modificar_metas` (RN-XVII-04, RN-XVI-04); tarifa, solo administrador (RN-XVI-05).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.data.database import get_session
from app.errors import error_responses
from app.schemas.goals_tariff import Meta, MetaCrear, MetaVista, Tarifa, TarifaCrear, TarifaVista
from app.security.dependencies import (
    AdminMembership,
    CurrentMembership,
    CurrentUser,
    Membership,
    require_permission,
)
from app.services import goals_tariff as service

router = APIRouter(tags=["Metas y tarifa"])

# La misma sesión que reciben las dependencias de la petición (la guardia de membresía).
DbSession = Annotated[Session, Depends(get_session)]


@router.get(
    "/hogares/{hogar_id}/meta",
    operation_id="obtenerMeta",
    summary="Meta activa del hogar y promedio de referencia (RN-V-03, RN-XVI-04)",
    response_model=MetaVista,
    responses=error_responses(401, 404, 422),
)
def get_goal(
    hogar_id: UUID, user: CurrentUser, member: CurrentMembership, session: DbSession
) -> MetaVista:
    """Meta activa del hogar y promedio de referencia (RN-V-03, RN-XVI-04)."""
    can_edit = member.is_admin or member.permisos.modificar_metas
    return service.get_goal(session, user.id, hogar_id, can_edit)


@router.post(
    "/hogares/{hogar_id}/metas",
    operation_id="crearMeta",
    summary="Guardar una meta nueva (RN-V-03, RN-XVI-04, RN-XVII-04)",
    response_model=Meta,
    status_code=201,
    responses=error_responses(401, 403, 404, 422),
)
def create_goal(
    hogar_id: UUID,
    user: CurrentUser,
    member: Annotated[Membership, Depends(require_permission("modificar_metas"))],
    payload: MetaCrear,
    session: DbSession,
) -> Meta:
    """Guardar una meta nueva (RN-V-03, RN-XVI-04, RN-XVII-04)."""
    return service.create_goal(session, user.id, hogar_id, payload)


@router.get(
    "/hogares/{hogar_id}/tarifa",
    operation_id="obtenerTarifa",
    summary="Tarifa vigente del hogar (RN-XVI-05)",
    response_model=TarifaVista,
    responses=error_responses(401, 404, 422),
)
def get_tariff(
    hogar_id: UUID, user: CurrentUser, member: CurrentMembership, session: DbSession
) -> TarifaVista:
    """Tarifa vigente del hogar (RN-XVI-05)."""
    return service.get_tariff(session, user.id, hogar_id, member.is_admin)


@router.post(
    "/hogares/{hogar_id}/tarifas",
    operation_id="crearTarifa",
    summary="Guardar una tarifa nueva (RN-V-01, RN-V-02, RN-XVI-05)",
    response_model=Tarifa,
    status_code=201,
    responses=error_responses(401, 403, 404, 422),
)
def create_tariff(
    hogar_id: UUID,
    user: CurrentUser,
    member: AdminMembership,
    payload: TarifaCrear,
    session: DbSession,
) -> Tarifa:
    """Guardar una tarifa nueva (RN-V-01, RN-V-02, RN-XVI-05)."""
    return service.create_tariff(session, user.id, hogar_id, payload)
