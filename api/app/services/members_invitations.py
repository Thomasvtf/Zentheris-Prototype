"""Casos de uso de la etiqueta «Miembros e invitaciones».

Esqueleto: cada función responde 501 con su operationId hasta su sesión.
Manejan las transacciones y llaman a domain/ y data/ (api/CLAUDE.md).
"""

from uuid import UUID

from app.errors import NotImplementedOperation
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


def list_members(user_id: UUID, hogar_id: UUID) -> MiembrosHogar:
    """`listarMiembros`: Miembros activos, invitaciones pendientes y permisos (RN-XVI-07). TODO(listarMiembros)."""
    raise NotImplementedOperation("listarMiembros")


def update_permissions(user_id: UUID, hogar_id: UUID, payload: PermisosActualizar) -> Permisos:
    """`actualizarPermisos`: Cambiar los permisos generales del hogar (RN-II-03, RN-X-08). TODO(actualizarPermisos)."""
    raise NotImplementedOperation("actualizarPermisos")


def remove_member(user_id: UUID, hogar_id: UUID, membresia_id: UUID) -> None:
    """`expulsarMiembro`: Expulsar a un miembro (RN-II-04, RN-X-07). TODO(expulsarMiembro)."""
    raise NotImplementedOperation("expulsarMiembro")


def transfer_admin(user_id: UUID, hogar_id: UUID, membresia_id: UUID) -> MiembrosHogar:
    """`transferirAdministracion`: Transferir el rol de administrador a otro miembro activo (RN-II-04, RN-X-07). TODO(transferirAdministracion)."""
    raise NotImplementedOperation("transferirAdministracion")


def leave_household(user_id: UUID, hogar_id: UUID) -> None:
    """`salirDelHogar`: Salir voluntariamente del hogar (RN-II-04, RN-X-07). TODO(salirDelHogar)."""
    raise NotImplementedOperation("salirDelHogar")


def create_invitation(
    user_id: UUID, hogar_id: UUID, payload: InvitacionCrear
) -> InvitacionPendiente:
    """`crearInvitacion`: Invitar a una persona por correo (RN-X-05). TODO(crearInvitacion)."""
    raise NotImplementedOperation("crearInvitacion")


def revoke_invitation(user_id: UUID, hogar_id: UUID, invitacion_id: UUID) -> None:
    """`revocarInvitacion`: Cancelar una invitación pendiente (RN-X-06). TODO(revocarInvitacion)."""
    raise NotImplementedOperation("revocarInvitacion")


def list_received_invitations(user_id: UUID) -> InvitacionesRecibidasLista:
    """`listarInvitacionesRecibidas`: Invitaciones pendientes para el correo del usuario (RN-X-01). TODO(listarInvitacionesRecibidas)."""
    raise NotImplementedOperation("listarInvitacionesRecibidas")


def resolve_invitation_token(user_id: UUID, payload: InvitacionToken) -> InvitacionRecibida:
    """`resolverTokenInvitacion`: Obtener la invitación a partir del token del enlace (RN-X-05). TODO(resolverTokenInvitacion)."""
    raise NotImplementedOperation("resolverTokenInvitacion")


def accept_invitation(user_id: UUID, invitacion_id: UUID) -> MembresiaResumen:
    """`aceptarInvitacion`: Aceptar una invitación (RN-X-05, RN-X-06). TODO(aceptarInvitacion)."""
    raise NotImplementedOperation("aceptarInvitacion")


def reject_invitation(user_id: UUID, invitacion_id: UUID) -> None:
    """`rechazarInvitacion`: Rechazar una invitación (RN-X-06). TODO(rechazarInvitacion)."""
    raise NotImplementedOperation("rechazarInvitacion")
