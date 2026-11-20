"""Casos de uso de la etiqueta «Usuario» (ficha, preferencias, avatar y baja de la cuenta).

Manejan las transacciones y llaman a data/ (api/CLAUDE.md). La sesión llega del router y es
la misma de las dependencias de seguridad: cada operación que escribe hace `session.commit()`
al final; si algo lanza antes, la sesión se cierra sin commit (rollback).
La autorización (usuario autenticado) ya viene resuelta por `app.security`; aquí no se importa.
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.config import Settings
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import supabase_admin
from app.data import users as users_data
from app.errors import ApiError, CodigoError, NotImplementedOperation
from app.schemas.users import (
    AvatarGuardar,
    ContrasenaCambiar,
    ContrasenaVerificar,
    MembresiaResumen,
    Preferencias,
    PreferenciasActualizar,
    UsuarioActual,
    UsuarioActualizar,
    UsuarioCrear,
)

logger = logging.getLogger(__name__)

# Mensajes técnicos y cortos: la app decide el texto por `codigo`.
FICHA_NO_CREADA_MESSAGE = "El usuario aún no tiene ficha."
FICHA_EXISTENTE_MESSAGE = "El usuario ya tiene ficha."
ADMIN_DEBE_TRANSFERIR_MESSAGE = (
    "El administrador debe transferir la administración antes de eliminar la cuenta."
)
VALIDACION_MESSAGE = "Los datos enviados no cumplen las reglas."
AVATAR_PATH_MESSAGE = "La ruta debe ser <usuario_id>/avatar.(jpg|png|webp)."
EMPTY_PATCH_MESSAGE = "Envía al menos un campo."
NOT_NULL_MESSAGE = "El campo no admite null."
AUTH_USER_MISSING_MESSAGE = "La cuenta del token ya no existe."
MEMBERSHIP_MOVED_MESSAGE = "La membresía activa cambió de hogar mientras se bloqueaba."

# Lectura sin bloqueo → bloqueo del hogar → relectura FOR UPDATE; se repite como máximo una vez
# más si la membresía cambió de hogar entre la lectura y el bloqueo.
LOCK_ATTEMPTS = 2


def get_current_user(session: Session, user_id: UUID, correo: str) -> UsuarioActual:
    """`obtenerUsuarioActual`: ficha, preferencias y membresía activa (RN-IX-01).

    404 `FICHA_NO_CREADA` si el usuario aún no tiene ficha: la app lo lleva a crearla.
    """
    return _read_current_user(session, user_id, correo)


def create_user_profile(
    session: Session, user_id: UUID, correo: str, payload: UsuarioCrear
) -> UsuarioActual:
    """`crearFichaUsuario`: ficha y preferencias por defecto en el primer acceso (RN-IX-01).

    409 `FICHA_EXISTENTE` si ya existía (sin tocar nada). Las preferencias toman los valores
    por defecto de la tabla (true, true, 'promedio'). Si el token sigue vigente pero la cuenta
    ya no existe en Supabase Auth (falla la FK hacia auth.users), 401 `NO_AUTENTICADO` sin
    commit.
    """
    try:
        created = users_data.insert_user_with_default_preferences(
            session, user_id, payload.nombre_completo, payload.telefono
        )
    except users_data.AuthUserMissingError:
        raise ApiError(
            401,
            CodigoError.NO_AUTENTICADO,
            AUTH_USER_MISSING_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    if not created:
        raise ApiError(409, CodigoError.FICHA_EXISTENTE, FICHA_EXISTENTE_MESSAGE)
    current = _read_current_user(session, user_id, correo)
    session.commit()
    return current


def update_profile(
    session: Session, user_id: UUID, correo: str, payload: UsuarioActualizar
) -> UsuarioActual:
    """`actualizarPerfil`: editar nombre completo y teléfono (RN-IX-07).

    Solo cambian los campos enviados; `telefono: null` borra el teléfono.
    404 `FICHA_NO_CREADA` si no hay ficha.
    """
    changes = _sent_changes(payload, not_null=frozenset({"nombre_completo"}))
    if not users_data.update_user_profile(session, user_id, changes):
        raise _ficha_no_creada()
    current = _read_current_user(session, user_id, correo)
    session.commit()
    return current


def delete_account(
    session: Session, user_id: UUID, settings: Settings, now: datetime | None = None
) -> None:
    """`eliminarCuenta`: eliminar la cuenta de forma irreversible (RN-IX-09, DC-36).

    Orden de bloqueo único en todo el proyecto: HOGAR primero, membresía después (con el
    orden inverso, dos transacciones cruzadas acabarían en interbloqueo). Ver
    `_lock_active_membership`.

    1) Con membresía activa (su hogar y su fila bloqueados, en ese orden): un administrador
       con otros miembros activos recibe 409 `ADMIN_DEBE_TRANSFERIR` sin cambios. Si no, se
       cierra la membresía y, si era el único miembro activo, se borra el hogar (cascada).
    2) Commit.
    3) Se borra el usuario en Supabase Auth (cascada a usuarios, preferencias, alertas y
       consejos del usuario). Si falla, la excepción sube (500 `ERROR_INTERNO`); reintentar es
       seguro porque ya no hay membresía activa.
    4) Se borran sus fotos en Storage con mejor esfuerzo: si falla, solo queda en el log.
    """
    closed_at = now if now is not None else datetime.now(UTC)
    membership = _lock_active_membership(session, user_id)
    if membership is not None:
        others = memberships_data.count_other_active_members(session, membership.hogar_id, user_id)
        if membership.rol == "administrador" and others > 0:
            raise ApiError(409, CodigoError.ADMIN_DEBE_TRANSFERIR, ADMIN_DEBE_TRANSFERIR_MESSAGE)
        memberships_data.close_membership(session, membership.membresia_id, closed_at)
        if others == 0:
            households_data.delete_household(session, membership.hogar_id)
    session.commit()

    supabase_admin.delete_auth_user(settings, user_id)
    try:
        supabase_admin.delete_avatar_files(settings, user_id)
    except supabase_admin.SupabaseAdminError as exc:
        # Sin ids ni datos personales: solo el tipo de error. La cuenta ya no existe.
        logger.warning(
            "No se pudieron borrar los avatares tras eliminar una cuenta (%s).",
            type(exc).__name__,
        )


def save_avatar(
    session: Session, user_id: UUID, correo: str, payload: AvatarGuardar
) -> UsuarioActual:
    """`guardarAvatar`: registrar la ruta de la foto de perfil (RN-I-02; DC-43).

    La ruta debe ser `{user_id}/avatar.(jpg|png|webp)`, igual que la política de Storage de
    la migración 0005; si no, 422 `VALIDACION`. 404 `FICHA_NO_CREADA` si no hay ficha.
    """
    if not _is_own_avatar_path(user_id, payload.avatar_url):
        raise _validation_error(["body", "avatar_url"], AVATAR_PATH_MESSAGE)
    if not users_data.set_avatar_url(session, user_id, payload.avatar_url):
        raise _ficha_no_creada()
    current = _read_current_user(session, user_id, correo)
    session.commit()
    return current


def delete_avatar(session: Session, user_id: UUID) -> None:
    """`eliminarAvatar`: deja `avatar_url` en null (RN-I-02); la app muestra las iniciales.

    404 `FICHA_NO_CREADA` si no hay ficha.
    """
    if not users_data.set_avatar_url(session, user_id, None):
        raise _ficha_no_creada()
    session.commit()


def get_preferences(session: Session, user_id: UUID) -> Preferencias:
    """`obtenerPreferencias`: interruptores y base de comparación (RN-VII-01, RN-XVI-02).

    404 `FICHA_NO_CREADA` si no hay fila de preferencias.
    """
    row = users_data.get_preferences(session, user_id)
    if row is None:
        raise _ficha_no_creada()
    return _to_preferences(row)


def update_preferences(
    session: Session, user_id: UUID, payload: PreferenciasActualizar
) -> Preferencias:
    """`actualizarPreferencias`: cambia solo los campos enviados.

    `base_comparacion` es individual y no cambia la meta del hogar (RN-VII-01, RN-XVI-03).
    Los interruptores son personales (RN-VI-04, RN-XVI-02) y solo afectan alertas futuras,
    sin efecto retroactivo (RN-VI-02).
    404 `FICHA_NO_CREADA` si no hay fila.
    """
    changes = _sent_changes(payload, not_null=users_data.PREFERENCE_FIELDS)
    row = users_data.update_preferences(session, user_id, changes)
    if row is None:
        raise _ficha_no_creada()
    preferences = _to_preferences(row)
    session.commit()
    return preferences


def verify_current_password(user_id: UUID, payload: ContrasenaVerificar) -> None:
    """`verificarContrasenaActual`: Verificar la contraseña actual (RN-IX-05). TODO(verificarContrasenaActual)."""
    raise NotImplementedOperation("verificarContrasenaActual")


def change_password(user_id: UUID, payload: ContrasenaCambiar) -> None:
    """`cambiarContrasena`: Cambiar la contraseña (RN-IX-02, RN-IX-05). TODO(cambiarContrasena)."""
    raise NotImplementedOperation("cambiarContrasena")


# --- auxiliares ---------------------------------------------------------------------------


def _read_current_user(session: Session, user_id: UUID, correo: str) -> UsuarioActual:
    """Ficha + membresía activa como `UsuarioActual`; 404 `FICHA_NO_CREADA` si no hay ficha."""
    profile = users_data.get_user_profile(session, user_id)
    if profile is None:
        raise _ficha_no_creada()
    membership = memberships_data.get_active_membership_of_user(session, user_id)
    return UsuarioActual(
        id=profile.id,
        correo=correo,
        nombre_completo=profile.nombre_completo,
        telefono=profile.telefono,
        avatar_url=profile.avatar_url,
        preferencias=_to_preferences(profile.preferencias),
        membresia=(
            None
            if membership is None
            else MembresiaResumen(
                membresia_id=membership.membresia_id,
                hogar_id=membership.hogar_id,
                rol=membership.rol,
            )
        ),
    )


def _lock_active_membership(
    session: Session, user_id: UUID
) -> memberships_data.MembershipSummaryRow | None:
    """Membresía activa bloqueada con el orden único del proyecto: hogar → membresía.

    1) Lectura SIN bloqueo para conocer el hogar. 2) `lock_household(hogar_id)`.
    3) Relectura con `FOR UPDATE`. Si la relectura es None, no hay membresía (la cerró otra
    transacción). Si cambió de hogar entre 1 y 3, se repite la secuencia una sola vez más; si
    vuelve a cambiar, RuntimeError (500 `ERROR_INTERNO`).
    """
    for _attempt in range(LOCK_ATTEMPTS):
        candidate = memberships_data.get_active_membership_of_user(session, user_id)
        if candidate is None:
            return None
        households_data.lock_household(session, candidate.hogar_id)
        locked = memberships_data.get_active_membership_of_user(session, user_id, for_update=True)
        if locked is None or locked.hogar_id == candidate.hogar_id:
            return locked
    raise RuntimeError(MEMBERSHIP_MOVED_MESSAGE)


def _to_preferences(row: users_data.PreferencesRow) -> Preferencias:
    return Preferencias(
        notif_consumo=row.notif_consumo,
        notif_consejos=row.notif_consejos,
        base_comparacion=row.base_comparacion,
    )


def _sent_changes(
    payload: UsuarioActualizar | PreferenciasActualizar, *, not_null: frozenset[str]
) -> dict[str, Any]:
    """Solo los campos que el cliente envió (PATCH parcial).

    Defensa en profundidad frente al esquema: `{}` o un null en una columna NOT NULL dan
    422 `VALIDACION` en vez de llegar a la capa de datos.
    """
    changes = {field: _plain(getattr(payload, field)) for field in sorted(payload.model_fields_set)}
    if not changes:
        raise _validation_error(["body"], EMPTY_PATCH_MESSAGE)
    for field, value in changes.items():
        if value is None and field in not_null:
            raise _validation_error(["body", field], NOT_NULL_MESSAGE)
    return changes


def _plain(value: Any) -> Any:
    """Enums del esquema (p. ej. `ReferenciaTipo`) como su valor de texto para el SQL."""
    return getattr(value, "value", value)


def _is_own_avatar_path(user_id: UUID, avatar_url: str) -> bool:
    """`{user_id}/avatar.(jpg|png|webp)` exacto: sin prefijo de bucket, sin `..`, sin otro id."""
    extensions = "|".join(supabase_admin.AVATAR_EXTENSIONS)
    pattern = rf"{re.escape(str(user_id))}/avatar\.(?:{extensions})"
    return re.fullmatch(pattern, avatar_url) is not None


def _ficha_no_creada() -> ApiError:
    return ApiError(404, CodigoError.FICHA_NO_CREADA, FICHA_NO_CREADA_MESSAGE)


def _validation_error(location: list[str], message: str) -> ApiError:
    return ApiError(
        422,
        CodigoError.VALIDACION,
        VALIDACION_MESSAGE,
        {"campos": [{"ubicacion": location, "mensaje": message}]},
    )
