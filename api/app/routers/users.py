"""Router de la etiqueta «Usuario» del contrato 0.2.5.

Solo valida la entrada y llama al servicio (api/CLAUDE.md).
"""

from fastapi import APIRouter, Response

from app.errors import error_responses
from app.schemas.users import (
    AvatarGuardar,
    ContrasenaCambiar,
    ContrasenaVerificar,
    Preferencias,
    PreferenciasActualizar,
    UsuarioActual,
    UsuarioActualizar,
    UsuarioCrear,
)
from app.security.dependencies import CurrentUser
from app.services import users as service

router = APIRouter(tags=["Usuario"])


@router.get(
    "/usuarios/me",
    operation_id="obtenerUsuarioActual",
    summary="Ficha, preferencias y membresía del usuario autenticado",
    response_model=UsuarioActual,
    responses=error_responses(401, 404),
)
def get_current_user(user: CurrentUser) -> UsuarioActual:
    """Ficha, preferencias y membresía del usuario autenticado."""
    return service.get_current_user(user.id)


@router.post(
    "/usuarios/me",
    operation_id="crearFichaUsuario",
    summary="Crear la ficha y las preferencias por defecto (RN-IX-01)",
    response_model=UsuarioActual,
    status_code=201,
    responses=error_responses(401, 409, 422),
)
def create_user_profile(user: CurrentUser, payload: UsuarioCrear) -> UsuarioActual:
    """Crear la ficha y las preferencias por defecto (RN-IX-01)."""
    return service.create_user_profile(user.id, payload)


@router.patch(
    "/usuarios/me",
    operation_id="actualizarPerfil",
    summary="Editar nombre completo y teléfono (RN-IX-07)",
    response_model=UsuarioActual,
    responses=error_responses(401, 422),
)
def update_profile(user: CurrentUser, payload: UsuarioActualizar) -> UsuarioActual:
    """Editar nombre completo y teléfono (RN-IX-07)."""
    return service.update_profile(user.id, payload)


@router.delete(
    "/usuarios/me",
    operation_id="eliminarCuenta",
    summary="Eliminar la cuenta de forma irreversible (RN-IX-09)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 409),
)
def delete_account(user: CurrentUser) -> None:
    """Eliminar la cuenta de forma irreversible (RN-IX-09)."""
    return service.delete_account(user.id)


@router.put(
    "/usuarios/me/avatar",
    operation_id="guardarAvatar",
    summary="Registrar la foto de perfil (RN-I-02)",
    response_model=UsuarioActual,
    responses=error_responses(401, 422),
)
def save_avatar(user: CurrentUser, payload: AvatarGuardar) -> UsuarioActual:
    """Registrar la foto de perfil (RN-I-02)."""
    return service.save_avatar(user.id, payload)


@router.delete(
    "/usuarios/me/avatar",
    operation_id="eliminarAvatar",
    summary="Eliminar la foto de perfil (RN-I-02)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401),
)
def delete_avatar(user: CurrentUser) -> None:
    """Eliminar la foto de perfil (RN-I-02)."""
    return service.delete_avatar(user.id)


@router.get(
    "/usuarios/me/preferencias",
    operation_id="obtenerPreferencias",
    summary="Interruptores de notificación y base de comparación",
    response_model=Preferencias,
    responses=error_responses(401),
)
def get_preferences(user: CurrentUser) -> Preferencias:
    """Interruptores de notificación y base de comparación."""
    return service.get_preferences(user.id)


@router.patch(
    "/usuarios/me/preferencias",
    operation_id="actualizarPreferencias",
    summary="Cambiar interruptores y base de comparación (RN-VI-04, RN-VII-01, RN-XVI-02, RN-XVI-03)",
    response_model=Preferencias,
    responses=error_responses(401, 422),
)
def update_preferences(user: CurrentUser, payload: PreferenciasActualizar) -> Preferencias:
    """Cambiar interruptores y base de comparación (RN-VI-04, RN-VII-01, RN-XVI-02, RN-XVI-03)."""
    return service.update_preferences(user.id, payload)


@router.post(
    "/usuarios/me/contrasena/verificar",
    operation_id="verificarContrasenaActual",
    summary="Verificar la contraseña actual (RN-IX-05)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 422),
)
def verify_current_password(user: CurrentUser, payload: ContrasenaVerificar) -> None:
    """Verificar la contraseña actual (RN-IX-05)."""
    return service.verify_current_password(user.id, payload)


@router.post(
    "/usuarios/me/contrasena",
    operation_id="cambiarContrasena",
    summary="Cambiar la contraseña (RN-IX-02, RN-IX-05)",
    response_model=None,
    response_class=Response,
    status_code=204,
    responses=error_responses(401, 422),
)
def change_password(user: CurrentUser, payload: ContrasenaCambiar) -> None:
    """Cambiar la contraseña (RN-IX-02, RN-IX-05)."""
    return service.change_password(user.id, payload)
