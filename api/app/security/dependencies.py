"""Dependencias de FastAPI para autenticación, membresía y permisos.

Esqueleto: se implementan en la sesión 3. Reglas: 404 si no hay membresía activa
(RN-I-03); 403 con el `CodigoError` exacto si falta el permiso (RN-XVII).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.errors import NotImplementedOperation
from app.security.jwt import bearer_scheme


@dataclass(frozen=True)
class AuthenticatedUser:
    """Usuario autenticado según el token de Supabase."""

    id: UUID
    correo: str


@dataclass(frozen=True)
class Membership:
    """Membresía activa del usuario en un hogar, con sus permisos."""

    membresia_id: UUID
    hogar_id: UUID
    rol: str


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    """Valida el token con `validate_jwt` y devuelve el usuario.

    TODO(sesión 3). Mientras tanto, la operación responde 501 con su `operationId`.
    """
    route = request.scope.get("route")
    raise NotImplementedOperation(getattr(route, "operation_id", None) or "current_user")


CurrentUser = Annotated[AuthenticatedUser, Depends(current_user)]


def membership(hogar_id: UUID, user: CurrentUser) -> Membership:
    """Devuelve la membresía activa del usuario en el hogar; 404 si no existe."""
    raise NotImplementedError("TODO(sesión 3): membresía (RN-I-03)")


def require_permission(permission: str) -> Callable[..., Membership]:
    """Crea una dependencia que exige un permiso (`ver_consumo_actual`, `ver_historial`…)."""
    raise NotImplementedError("TODO(sesión 3): permisos (RN-XVII)")


def require_admin(member: Annotated[Membership, Depends(membership)]) -> Membership:
    """Exige el rol de administrador; 403 `NO_ES_ADMINISTRADOR` si no lo es."""
    raise NotImplementedError("TODO(sesión 3): administrador")
