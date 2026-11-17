"""Dependencias de FastAPI para autenticación, membresía y permisos.

Orden en cada llamada: 401 (token) → 404 (membresía activa, RN-I-03) → 403 (rol o permiso,
RN-XVII, RN-X-08 y RN-XVI-05). Excepción: un cuerpo que no es JSON válido da 422 antes,
porque FastAPI lo lee antes de resolver las dependencias. El 403 lleva el `CodigoError`
exacto; el administrador pasa todos los permisos aunque estén desactivados (RN-XVII-05).
Si no se puede validar ningún token (configuración faltante o JWKS caído), la
`AuthUnavailableError` no se captura aquí y responde 500, no 401 (DC-16).
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import Session

from app.config import Settings, get_settings
from app.data import memberships as memberships_data
from app.data.database import get_session
from app.errors import ERROR_DESCRIPTIONS, ApiError, CodigoError, PendingCodeError
from app.security.jwt import InvalidTokenError, bearer_scheme, validate_jwt


@dataclass(frozen=True)
class AuthenticatedUser:
    """Usuario autenticado según el token de Supabase."""

    id: UUID  # claim `sub`
    correo: str  # claim `email` (obligatorio)


@dataclass(frozen=True)
class HouseholdPermissions:
    """Los 4 permisos de los miembros del hogar (columnas `permiso_*` de `hogares`)."""

    ver_consumo_actual: bool
    ver_historial: bool
    recibir_alertas: bool
    modificar_metas: bool


@dataclass(frozen=True)
class Membership:
    """Membresía activa del usuario en un hogar, con los permisos del hogar."""

    membresia_id: UUID
    hogar_id: UUID
    usuario_id: UUID
    rol: Literal["administrador", "miembro"]
    permisos: HouseholdPermissions

    @property
    def is_admin(self) -> bool:
        """El administrador ve y hace todo, con o sin permisos activados (RN-XVII-05)."""
        return self.rol == "administrador"


Permission = Literal["ver_consumo_actual", "ver_historial", "recibir_alertas", "modificar_metas"]


def _unauthorized() -> PendingCodeError:
    # TODO(pendiente: código de error del 401, PENDIENTES #29; contrato 0.2.6)
    return PendingCodeError(401)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    """Valida el token con `validate_jwt` y devuelve el usuario; si no, 401.

    `AuthUnavailableError` (infraestructura) no se captura: el manejador genérico da 500.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    try:
        claims = validate_jwt(credentials.credentials, settings)
    except InvalidTokenError:
        raise _unauthorized() from None
    subject = claims.get("sub")
    email = claims.get("email")
    if not isinstance(subject, str) or not isinstance(email, str) or not email:
        raise _unauthorized()
    try:
        user_id = UUID(subject)
    except ValueError:
        raise _unauthorized() from None
    return AuthenticatedUser(id=user_id, correo=email)


CurrentUser = Annotated[AuthenticatedUser, Depends(current_user)]


# TODO(pendiente: sesión compartida guardia-servicio; decidir antes del primer servicio que escribe si el router pasa la misma Session al servicio o si el servicio revalida la membresía en su transacción)
def membership(
    hogar_id: UUID,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_session)],
) -> Membership:
    """Membresía activa del usuario en el hogar; 404 si no existe (RN-I-03), nunca 403."""
    row = memberships_data.get_active_membership(session, user.id, hogar_id)
    if row is None:
        # TODO(pendiente: código de error del 404, PENDIENTES #29; contrato 0.2.6)
        raise PendingCodeError(404)
    return Membership(
        membresia_id=row.membresia_id,
        hogar_id=row.hogar_id,
        usuario_id=row.usuario_id,
        rol=row.rol,
        permisos=HouseholdPermissions(
            ver_consumo_actual=row.permiso_ver_consumo_actual,
            ver_historial=row.permiso_ver_historial,
            recibir_alertas=row.permiso_recibir_alertas,
            modificar_metas=row.permiso_modificar_metas,
        ),
    )


CurrentMembership = Annotated[Membership, Depends(membership)]

PERMISSION_ERRORS: dict[Permission, CodigoError] = {
    "ver_consumo_actual": CodigoError.SIN_PERMISO_VER_CONSUMO,
    "ver_historial": CodigoError.SIN_PERMISO_VER_HISTORIAL,
    "recibir_alertas": CodigoError.SIN_PERMISO_RECIBIR_ALERTAS,
    "modificar_metas": CodigoError.SIN_PERMISO_MODIFICAR_METAS,
}


@cache
def require_permission(permission: Permission) -> Callable[..., Membership]:
    """Dependencia que exige un permiso del hogar (RN-XVII-01…04).

    Devuelve siempre la misma función para el mismo permiso, así FastAPI la resuelve una
    vez por petición y las pruebas pueden identificar el guardia de cada operación.
    """
    if permission not in PERMISSION_ERRORS:
        raise ValueError(f"Permiso desconocido: {permission}")
    error_code = PERMISSION_ERRORS[permission]

    def dependency(member: CurrentMembership) -> Membership:
        if member.is_admin or getattr(member.permisos, permission):
            return member
        raise ApiError(403, error_code, ERROR_DESCRIPTIONS[403])

    dependency.__name__ = dependency.__qualname__ = f"require_permission_{permission}"
    return dependency


def require_admin(member: CurrentMembership) -> Membership:
    """Exige el rol de administrador; 403 `NO_ES_ADMINISTRADOR` si no lo es.

    Reglas: RN-X-08 (invitar, expulsar, transferir, cancelar invitaciones y mover los
    permisos es exclusivo del administrador) y RN-XVI-05 (solo el administrador edita la
    tarifa).
    """
    if not member.is_admin:
        raise ApiError(403, CodigoError.NO_ES_ADMINISTRADOR, ERROR_DESCRIPTIONS[403])
    return member


AdminMembership = Annotated[Membership, Depends(require_admin)]
