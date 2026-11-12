"""Casos de uso de la etiqueta «Usuario».

Esqueleto: cada función responde 501 con su operationId hasta su sesión.
Manejan las transacciones y llaman a domain/ y data/ (api/CLAUDE.md).
"""

from uuid import UUID

from app.errors import NotImplementedOperation
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


def get_current_user(user_id: UUID) -> UsuarioActual:
    """`obtenerUsuarioActual`: Ficha, preferencias y membresía del usuario autenticado. TODO(obtenerUsuarioActual)."""
    raise NotImplementedOperation("obtenerUsuarioActual")


def create_user_profile(user_id: UUID, payload: UsuarioCrear) -> UsuarioActual:
    """`crearFichaUsuario`: Crear la ficha y las preferencias por defecto (RN-IX-01). TODO(crearFichaUsuario)."""
    raise NotImplementedOperation("crearFichaUsuario")


def update_profile(user_id: UUID, payload: UsuarioActualizar) -> UsuarioActual:
    """`actualizarPerfil`: Editar nombre completo y teléfono (RN-IX-07). TODO(actualizarPerfil)."""
    raise NotImplementedOperation("actualizarPerfil")


def delete_account(user_id: UUID) -> None:
    """`eliminarCuenta`: Eliminar la cuenta de forma irreversible (RN-IX-09). TODO(eliminarCuenta)."""
    raise NotImplementedOperation("eliminarCuenta")


def save_avatar(user_id: UUID, payload: AvatarGuardar) -> UsuarioActual:
    """`guardarAvatar`: Registrar la foto de perfil (RN-I-02). TODO(guardarAvatar)."""
    raise NotImplementedOperation("guardarAvatar")


def delete_avatar(user_id: UUID) -> None:
    """`eliminarAvatar`: Eliminar la foto de perfil (RN-I-02). TODO(eliminarAvatar)."""
    raise NotImplementedOperation("eliminarAvatar")


def get_preferences(user_id: UUID) -> Preferencias:
    """`obtenerPreferencias`: Interruptores de notificación y base de comparación. TODO(obtenerPreferencias)."""
    raise NotImplementedOperation("obtenerPreferencias")


def update_preferences(user_id: UUID, payload: PreferenciasActualizar) -> Preferencias:
    """`actualizarPreferencias`: Cambiar interruptores y base de comparación (RN-VI-04, RN-VII-01, RN-XVI-02, RN-XVI-03). TODO(actualizarPreferencias)."""
    raise NotImplementedOperation("actualizarPreferencias")


def verify_current_password(user_id: UUID, payload: ContrasenaVerificar) -> None:
    """`verificarContrasenaActual`: Verificar la contraseña actual (RN-IX-05). TODO(verificarContrasenaActual)."""
    raise NotImplementedOperation("verificarContrasenaActual")


def change_password(user_id: UUID, payload: ContrasenaCambiar) -> None:
    """`cambiarContrasena`: Cambiar la contraseña (RN-IX-02, RN-IX-05). TODO(cambiarContrasena)."""
    raise NotImplementedOperation("cambiarContrasena")
