"""Router de la etiqueta «Miembros e invitaciones» del contrato 0.2.5.

Solo valida la entrada y llama al servicio (api/CLAUDE.md).
"""

from uuid import UUID

from fastapi import APIRouter, Response

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
from app.security.dependencies import CurrentUser
from app.services import members_invitations as service

router = APIRouter(tags=["Miembros e invitaciones"])


@router.get(
    "/hogares/{hogar_id}/miembros",
    operation_id="listarMiembros",
    summary="Miembros activos, invitaciones pendientes y permisos (RN-XVI-07)",
    response_model=MiembrosHogar,
    responses=error_responses(401, 404),
)
def list_members(hogar_id: UUID, user: CurrentUser) -> MiembrosHogar:
    """Miembros activos, invitaciones pendientes y permisos (RN-XVI-07)."""
    return service.list_members(user.id, hogar_id)


@router.patch(
    "/hogares/{hogar_id}/permisos",
    operation_id="actualizarPermisos",
    summary="Cambiar los permisos generales del hogar (RN-II-03, RN-X-08)",
    response_model=Permisos,
    responses=error_responses(401, 403, 404, 422),
)
def update_permissions(hogar_id: UUID, user: CurrentUser, payload: PermisosActualizar) -> Permisos:
    """Cambiar los permisos generales del hogar (RN-II-03, RN-X-08)."""
    return service.update_permissions(user.id, hogar_id, payload)


@router.delete(
    "/hogares/{hogar_id}/miembros/{membresia_id}",
    operation_id="expulsarMiembro",
    summary="Expulsar a un miembro (RN-II-04, RN-X-07)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 403, 404, 409),
)
def remove_member(hogar_id: UUID, membresia_id: UUID, user: CurrentUser) -> None:
    """Expulsar a un miembro (RN-II-04, RN-X-07)."""
    return service.remove_member(user.id, hogar_id, membresia_id)


@router.post(
    "/hogares/{hogar_id}/miembros/{membresia_id}/transferir-administracion",
    operation_id="transferirAdministracion",
    summary="Transferir el rol de administrador a otro miembro activo (RN-II-04, RN-X-07)",
    response_model=MiembrosHogar,
    responses=error_responses(401, 403, 404, 409),
)
def transfer_admin(hogar_id: UUID, membresia_id: UUID, user: CurrentUser) -> MiembrosHogar:
    """Transferir el rol de administrador a otro miembro activo (RN-II-04, RN-X-07)."""
    return service.transfer_admin(user.id, hogar_id, membresia_id)


@router.post(
    "/hogares/{hogar_id}/salir",
    operation_id="salirDelHogar",
    summary="Salir voluntariamente del hogar (RN-II-04, RN-X-07)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 404, 409),
)
def leave_household(hogar_id: UUID, user: CurrentUser) -> None:
    """Salir voluntariamente del hogar (RN-II-04, RN-X-07)."""
    return service.leave_household(user.id, hogar_id)


@router.post(
    "/hogares/{hogar_id}/invitaciones",
    operation_id="crearInvitacion",
    summary="Invitar a una persona por correo (RN-X-05)",
    response_model=InvitacionPendiente,
    status_code=201,
    responses=error_responses(401, 403, 404, 409, 422),
)
def create_invitation(
    hogar_id: UUID, user: CurrentUser, payload: InvitacionCrear
) -> InvitacionPendiente:
    """Invitar a una persona por correo (RN-X-05)."""
    return service.create_invitation(user.id, hogar_id, payload)


@router.delete(
    "/hogares/{hogar_id}/invitaciones/{invitacion_id}",
    operation_id="revocarInvitacion",
    summary="Cancelar una invitación pendiente (RN-X-06)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 403, 404, 409),
)
def revoke_invitation(hogar_id: UUID, invitacion_id: UUID, user: CurrentUser) -> None:
    """Cancelar una invitación pendiente (RN-X-06)."""
    return service.revoke_invitation(user.id, hogar_id, invitacion_id)


@router.get(
    "/invitaciones/recibidas",
    operation_id="listarInvitacionesRecibidas",
    summary="Invitaciones pendientes para el correo del usuario (RN-X-01)",
    response_model=InvitacionesRecibidasLista,
    responses=error_responses(401),
)
def list_received_invitations(user: CurrentUser) -> InvitacionesRecibidasLista:
    """Invitaciones pendientes para el correo del usuario (RN-X-01)."""
    return service.list_received_invitations(user.id)


@router.post(
    "/invitaciones/resolver",
    operation_id="resolverTokenInvitacion",
    summary="Obtener la invitación a partir del token del enlace (RN-X-05)",
    response_model=InvitacionRecibida,
    responses=error_responses(401, 403, 404, 409),
)
def resolve_invitation_token(user: CurrentUser, payload: InvitacionToken) -> InvitacionRecibida:
    """Obtener la invitación a partir del token del enlace (RN-X-05)."""
    return service.resolve_invitation_token(user.id, payload)


@router.post(
    "/invitaciones/{invitacion_id}/aceptar",
    operation_id="aceptarInvitacion",
    summary="Aceptar una invitación (RN-X-05, RN-X-06)",
    response_model=MembresiaResumen,
    responses=error_responses(401, 403, 404, 409),
)
def accept_invitation(invitacion_id: UUID, user: CurrentUser) -> MembresiaResumen:
    """Aceptar una invitación (RN-X-05, RN-X-06)."""
    return service.accept_invitation(user.id, invitacion_id)


@router.post(
    "/invitaciones/{invitacion_id}/rechazar",
    operation_id="rechazarInvitacion",
    summary="Rechazar una invitación (RN-X-06)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 403, 404, 409),
)
def reject_invitation(invitacion_id: UUID, user: CurrentUser) -> None:
    """Rechazar una invitación (RN-X-06)."""
    return service.reject_invitation(user.id, invitacion_id)
