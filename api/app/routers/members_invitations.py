"""Router de la etiqueta «Miembros e invitaciones» del contrato.

Solo valida la entrada y llama al servicio (api/CLAUDE.md). Cada operación recibe la sesión de la
petición (`get_session`), la misma que usó la guardia de membresía; el servicio hace el commit y
vuelve a comprobar el rol de administrador bajo bloqueo (RN-X-08). Las operaciones de
`/invitaciones` solo exigen el token: pasan `user.correo` (claim `email`) para comprobar que la
invitación es para esa persona (403 `CORREO_NO_COINCIDE`, RN-X-05).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session

from app.config import Settings, get_settings
from app.data.database import get_session
from app.errors import error_responses
from app.schemas.households import Permisos, PermisosActualizar
from app.schemas.members_invitations import (
    InvitacionCrear,
    InvitacionesRecibidasLista,
    InvitacionPendiente,
    InvitacionRecibida,
    InvitacionToken,
    MiembrosHogar,
)
from app.schemas.users import MembresiaResumen
from app.security.dependencies import AdminMembership, CurrentMembership, CurrentUser
from app.services import members_invitations as service

router = APIRouter(tags=["Miembros e invitaciones"])

# La misma sesión que reciben las dependencias de la petición (la guardia de membresía).
DbSession = Annotated[Session, Depends(get_session)]


@router.get(
    "/hogares/{hogar_id}/miembros",
    operation_id="listarMiembros",
    summary="Miembros activos, invitaciones pendientes y permisos (RN-XVI-07)",
    response_model=MiembrosHogar,
    responses=error_responses(401, 404, 422),
)
def list_members(
    hogar_id: UUID, user: CurrentUser, member: CurrentMembership, session: DbSession
) -> MiembrosHogar:
    """Miembros activos, invitaciones pendientes y permisos (RN-XVI-07)."""
    return service.list_members(session, user.id, hogar_id)


@router.patch(
    "/hogares/{hogar_id}/permisos",
    operation_id="actualizarPermisos",
    summary="Cambiar los permisos generales del hogar (RN-II-03, RN-X-08)",
    response_model=Permisos,
    responses=error_responses(401, 403, 404, 422),
)
def update_permissions(
    hogar_id: UUID,
    user: CurrentUser,
    member: AdminMembership,
    payload: PermisosActualizar,
    session: DbSession,
) -> Permisos:
    """Cambiar los permisos generales del hogar (RN-II-03, RN-X-08)."""
    return service.update_permissions(session, user.id, hogar_id, payload)


@router.delete(
    "/hogares/{hogar_id}/miembros/{membresia_id}",
    operation_id="expulsarMiembro",
    summary="Expulsar a un miembro (RN-II-04, RN-X-07)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 403, 404, 409, 422),
)
def remove_member(
    hogar_id: UUID,
    membresia_id: UUID,
    user: CurrentUser,
    member: AdminMembership,
    session: DbSession,
) -> None:
    """Expulsar a un miembro (RN-II-04, RN-X-07)."""
    return service.remove_member(session, user.id, hogar_id, membresia_id)


@router.post(
    "/hogares/{hogar_id}/miembros/{membresia_id}/transferir-administracion",
    operation_id="transferirAdministracion",
    summary="Transferir el rol de administrador a otro miembro activo (RN-II-04, RN-X-07)",
    response_model=MiembrosHogar,
    responses=error_responses(401, 403, 404, 422),
)
def transfer_admin(
    hogar_id: UUID,
    membresia_id: UUID,
    user: CurrentUser,
    member: AdminMembership,
    session: DbSession,
) -> MiembrosHogar:
    """Transferir el rol de administrador a otro miembro activo (RN-II-04, RN-X-07)."""
    return service.transfer_admin(session, user.id, hogar_id, membresia_id)


@router.post(
    "/hogares/{hogar_id}/salir",
    operation_id="salirDelHogar",
    summary="Salir voluntariamente del hogar (RN-II-04, RN-X-07)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 404, 409, 422),
)
def leave_household(
    hogar_id: UUID, user: CurrentUser, member: CurrentMembership, session: DbSession
) -> None:
    """Salir voluntariamente del hogar (RN-II-04, RN-X-07)."""
    return service.leave_household(session, user.id, hogar_id)


@router.post(
    "/hogares/{hogar_id}/invitaciones",
    operation_id="crearInvitacion",
    summary="Invitar a una persona por correo (RN-X-05)",
    response_model=InvitacionPendiente,
    status_code=201,
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
def create_invitation(
    hogar_id: UUID,
    user: CurrentUser,
    member: AdminMembership,
    payload: InvitacionCrear,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> InvitacionPendiente:
    """Invitar a una persona por correo (RN-X-05)."""
    return service.create_invitation(session, settings, user.id, hogar_id, payload)


@router.delete(
    "/hogares/{hogar_id}/invitaciones/{invitacion_id}",
    operation_id="revocarInvitacion",
    summary="Cancelar una invitación pendiente (RN-X-06)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 403, 404, 409, 422),
)
def revoke_invitation(
    hogar_id: UUID,
    invitacion_id: UUID,
    user: CurrentUser,
    member: AdminMembership,
    session: DbSession,
) -> None:
    """Cancelar una invitación pendiente (RN-X-06)."""
    return service.revoke_invitation(session, user.id, hogar_id, invitacion_id)


@router.get(
    "/invitaciones/recibidas",
    operation_id="listarInvitacionesRecibidas",
    summary="Invitaciones pendientes para el correo del usuario (RN-X-01)",
    response_model=InvitacionesRecibidasLista,
    responses=error_responses(401),
)
def list_received_invitations(user: CurrentUser, session: DbSession) -> InvitacionesRecibidasLista:
    """Invitaciones pendientes para el correo del usuario (RN-X-01)."""
    return service.list_received_invitations(session, user.id, user.correo)


@router.post(
    "/invitaciones/resolver",
    operation_id="resolverTokenInvitacion",
    summary="Obtener la invitación a partir del token del enlace (RN-X-05)",
    response_model=InvitacionRecibida,
    responses=error_responses(401, 403, 404, 409, 422),
)
def resolve_invitation_token(
    user: CurrentUser, payload: InvitacionToken, session: DbSession
) -> InvitacionRecibida:
    """Obtener la invitación a partir del token del enlace (RN-X-05)."""
    return service.resolve_invitation_token(session, user.id, user.correo, payload)


@router.post(
    "/invitaciones/{invitacion_id}/aceptar",
    operation_id="aceptarInvitacion",
    summary="Aceptar una invitación (RN-X-05, RN-X-06)",
    response_model=MembresiaResumen,
    responses=error_responses(401, 403, 404, 409, 422),
)
def accept_invitation(
    invitacion_id: UUID, user: CurrentUser, session: DbSession
) -> MembresiaResumen:
    """Aceptar una invitación (RN-X-05, RN-X-06)."""
    return service.accept_invitation(session, user.id, user.correo, invitacion_id)


@router.post(
    "/invitaciones/{invitacion_id}/rechazar",
    operation_id="rechazarInvitacion",
    summary="Rechazar una invitación (RN-X-06)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 403, 404, 409, 422),
)
def reject_invitation(invitacion_id: UUID, user: CurrentUser, session: DbSession) -> None:
    """Rechazar una invitación (RN-X-06)."""
    return service.reject_invitation(session, user.id, user.correo, invitacion_id)
