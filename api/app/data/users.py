"""Consultas de usuarios y preferencias_usuario.

Perfil (nombre y teléfono): RN-IX-07. Avatar: RN-I-02, DC-43. Preferencias: RN-VII-01,
RN-VI-04, RN-XVI-02, RN-XVI-03. Valores por defecto al crear la ficha: RN-IX-01, RN-VII-01.

Todas las sentencias son constantes `sqlalchemy.text` con parámetros con nombre: ningún dato
del cliente se interpola en el SQL. Las actualizaciones parciales no arman el SET con texto:
cada columna de la lista blanca tiene un indicador `set_<columna>` y la sentencia es fija.
Ninguna función hace commit: la transacción es del servicio.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.data._convert import as_uuid

# SQLSTATE de Postgres para violación de clave foránea (usuarios.id → auth.users.id).
_FOREIGN_KEY_VIOLATION = "23503"

# Columnas que el cliente puede cambiar (lista blanca fija, nunca viene del cliente).
USER_PROFILE_FIELDS = frozenset({"nombre_completo", "telefono"})
PREFERENCE_FIELDS = frozenset({"notif_consumo", "notif_consejos", "base_comparacion"})

# Columnas NOT NULL de la lista blanca: un None ahí es un error de programación (no "borrar").
_NOT_NULL_FIELDS = frozenset(
    {"nombre_completo", "notif_consumo", "notif_consejos", "base_comparacion"}
)

# RN-IX-07, RN-VII-01: ficha del usuario (perfil) con sus preferencias (1:1).
_USER_PROFILE_BASE = """
    select u.id,
           u.nombre_completo,
           u.telefono,
           u.avatar_url,
           p.notif_consumo,
           p.notif_consejos,
           p.base_comparacion
      from usuarios u
      join preferencias_usuario p on p.usuario_id = u.id
     where u.id = :usuario_id
    """
USER_PROFILE_SQL = text(_USER_PROFILE_BASE)
# RN-IX-09, RN-X-06, DC-36: igual, bloqueando SOLO la fila de usuarios (`for update of u`), último
# nivel del orden de bloqueo hogar → membresía → usuario. Cierra la carrera entre eliminar la
# cuenta y aceptar una invitación.
LOCK_USER_PROFILE_SQL = text(_USER_PROFILE_BASE + " for update of u")

# RN-IX-09, DC-36: borra la ficha. En cascada: preferencias_usuario, alertas_usuario y
# consejos_usuario; a nulo: hogar_miembros.usuario_id e invitaciones_hogar.invitado_por.
DELETE_USER_PROFILE_SQL = text(
    """
    delete from usuarios
     where id = :usuario_id
    returning id
    """
)

# RN-IX-01, RN-IX-07: crea la ficha solo si no existe (idempotente frente a carreras).
INSERT_USER_SQL = text(
    """
    insert into usuarios (id, nombre_completo, telefono)
    values (:usuario_id, :nombre_completo, :telefono)
    on conflict (id) do nothing
    returning id
    """
)

# RN-IX-01, RN-VII-01: preferencias con los valores por defecto de la tabla
# (true, true, 'promedio').
INSERT_DEFAULT_PREFERENCES_SQL = text(
    """
    insert into preferencias_usuario (usuario_id)
    values (:usuario_id)
    """
)

# RN-IX-07: actualización parcial del perfil; `telefono = null` borra el teléfono.
UPDATE_USER_PROFILE_SQL = text(
    """
    update usuarios
       set nombre_completo = case when :set_nombre_completo then :nombre_completo
                                  else nombre_completo end,
           telefono = case when :set_telefono then :telefono else telefono end
     where id = :usuario_id
    returning id
    """
)

# RN-I-02, DC-43: ruta del avatar en el bucket privado (o null para quitarlo).
SET_AVATAR_URL_SQL = text(
    """
    update usuarios
       set avatar_url = :avatar_url
     where id = :usuario_id
    returning id
    """
)

# RN-VII-01, RN-VI-04, RN-XVI-02, RN-XVI-03: preferencias individuales del usuario.
PREFERENCES_SQL = text(
    """
    select notif_consumo,
           notif_consejos,
           base_comparacion
      from preferencias_usuario
     where usuario_id = :usuario_id
    """
)

# RN-VII-01, RN-VI-04, RN-XVI-02, RN-XVI-03: actualización parcial de preferencias.
UPDATE_PREFERENCES_SQL = text(
    """
    update preferencias_usuario
       set notif_consumo = case when :set_notif_consumo then :notif_consumo
                                else notif_consumo end,
           notif_consejos = case when :set_notif_consejos then :notif_consejos
                                 else notif_consejos end,
           base_comparacion = case when :set_base_comparacion then :base_comparacion
                                   else base_comparacion end
     where usuario_id = :usuario_id
    returning notif_consumo, notif_consejos, base_comparacion
    """
)


class AuthUserMissingError(Exception):
    """La fila de auth.users ya no existe al crear la ficha (FK 23503).

    Caso: token todavía válido de una cuenta ya borrada. El servicio la traduce a 401.
    """


@dataclass(frozen=True)
class PreferencesRow:
    """Fila de preferencias_usuario (RN-VII-01, RN-VI-04, RN-XVI-02, RN-XVI-03)."""

    notif_consumo: bool
    notif_consejos: bool
    base_comparacion: Literal["promedio", "meta"]


@dataclass(frozen=True)
class UserProfileRow:
    """Ficha de usuarios (perfil, RN-IX-07) unida a sus preferencias (RN-VII-01)."""

    id: UUID
    nombre_completo: str
    telefono: str | None
    avatar_url: str | None
    preferencias: PreferencesRow


def get_user_profile(session: Session, usuario_id: UUID) -> UserProfileRow | None:
    """Ficha del usuario con sus preferencias (RN-IX-07, RN-VII-01); None si no tiene ficha.

    Filtra por el id del usuario autenticado: nunca devuelve la ficha de otra persona.
    """
    result = session.exec(USER_PROFILE_SQL, params={"usuario_id": usuario_id})
    row = result.mappings().first()
    return None if row is None else _to_user_profile_row(row)


def lock_user_profile(session: Session, usuario_id: UUID) -> UserProfileRow | None:
    """Como `get_user_profile`, pero `FOR UPDATE OF u` sobre la fila de usuarios (RN-IX-09, DC-36).

    Último nivel del orden de bloqueo único (hogar → membresía → usuario): se pide después de
    `lock_household` y de las membresías. None si la persona no tiene ficha o si otra transacción
    la borró mientras se esperaba el bloqueo (cuenta eliminándose). Sin commit.
    """
    result = session.exec(LOCK_USER_PROFILE_SQL, params={"usuario_id": usuario_id})
    row = result.mappings().first()
    return None if row is None else _to_user_profile_row(row)


def delete_user_profile(session: Session, usuario_id: UUID) -> bool:
    """Borra la ficha del usuario dentro de la transacción (RN-IX-09, DC-36, I-03).

    Cascada a preferencias_usuario, alertas_usuario y consejos_usuario; `SET NULL` en
    hogar_miembros.usuario_id e invitaciones_hogar.invitado_por. Su membresía activa debe estar
    cerrada antes (la verificación miembros_activo_con_usuario no admite una activa sin usuario).
    True si borró la fila. Sin commit.
    """
    result = session.exec(DELETE_USER_PROFILE_SQL, params={"usuario_id": usuario_id})
    return result.mappings().first() is not None


def _to_user_profile_row(row: Mapping[str, Any]) -> UserProfileRow:
    """Convierte la fila de USER_PROFILE_SQL (o su variante con bloqueo) en UserProfileRow."""
    return UserProfileRow(
        id=as_uuid(row["id"]),
        nombre_completo=row["nombre_completo"],
        telefono=row["telefono"],
        avatar_url=row["avatar_url"],
        preferencias=_to_preferences_row(row),
    )


def insert_user_with_default_preferences(
    session: Session, usuario_id: UUID, nombre_completo: str, telefono: str | None
) -> bool:
    """Crea la ficha y sus preferencias por defecto (RN-IX-01, RN-IX-07, RN-VII-01).

    `INSERT ... ON CONFLICT (id) DO NOTHING RETURNING id`: si la ficha ya existía no toca
    nada y devuelve False. Si la creó, inserta preferencias_usuario con los valores por
    defecto de la tabla (true, true, 'promedio') y devuelve True. Sin commit.

    AuthUserMissingError si el INSERT viola la clave foránea hacia auth.users (SQLSTATE
    23503): token todavía válido de una cuenta ya borrada. Cualquier otra IntegrityError sube
    tal cual. La transacción queda abortada: el servicio no debe hacer commit.
    """
    try:
        result = session.exec(
            INSERT_USER_SQL,
            params={
                "usuario_id": usuario_id,
                "nombre_completo": nombre_completo,
                "telefono": telefono,
            },
        )
    except IntegrityError as exc:
        if getattr(exc.orig, "pgcode", None) == _FOREIGN_KEY_VIOLATION:
            raise AuthUserMissingError("La cuenta de Auth ya no existe.") from None
        raise
    if result.mappings().first() is None:
        return False
    session.exec(INSERT_DEFAULT_PREFERENCES_SQL, params={"usuario_id": usuario_id})
    return True


def update_user_profile(
    session: Session, usuario_id: UUID, changes: Mapping[str, str | None]
) -> bool:
    """Actualiza solo las columnas de USER_PROFILE_FIELDS presentes en `changes` (RN-IX-07).

    ValueError si `changes` está vacío, trae una clave fuera de la lista blanca o un None en
    `nombre_completo` (NOT NULL). `telefono: None` borra el teléfono. Devuelve False si no
    existe la fila. Sin commit.
    """
    params = _partial_update_params(changes, USER_PROFILE_FIELDS)
    params["usuario_id"] = usuario_id
    result = session.exec(UPDATE_USER_PROFILE_SQL, params=params)
    return result.mappings().first() is not None


def set_avatar_url(session: Session, usuario_id: UUID, avatar_url: str | None) -> bool:
    """Guarda (o quita con None) la ruta del avatar del usuario (RN-I-02, DC-43).

    La validación del formato `{usuario_id}/avatar.(jpg|png|webp)` es del servicio.
    Devuelve False si no existe la fila. Sin commit.
    """
    result = session.exec(
        SET_AVATAR_URL_SQL,
        params={"usuario_id": usuario_id, "avatar_url": avatar_url},
    )
    return result.mappings().first() is not None


def get_preferences(session: Session, usuario_id: UUID) -> PreferencesRow | None:
    """Preferencias del usuario (RN-VII-01, RN-VI-04, RN-XVI-02, RN-XVI-03); None si no hay fila."""
    result = session.exec(PREFERENCES_SQL, params={"usuario_id": usuario_id})
    row = result.mappings().first()
    if row is None:
        return None
    return _to_preferences_row(row)


def update_preferences(
    session: Session, usuario_id: UUID, changes: Mapping[str, bool | str]
) -> PreferencesRow | None:
    """Actualiza solo las columnas de PREFERENCE_FIELDS presentes en `changes` (RN-VII-01).

    Devuelve las 3 columnas tras el cambio (RETURNING). ValueError si `changes` está vacío,
    trae una clave fuera de la lista blanca o un None (columnas NOT NULL). None si no existe
    la fila. Sin commit.
    """
    params = _partial_update_params(changes, PREFERENCE_FIELDS)
    params["usuario_id"] = usuario_id
    result = session.exec(UPDATE_PREFERENCES_SQL, params=params)
    row = result.mappings().first()
    if row is None:
        return None
    return _to_preferences_row(row)


def _partial_update_params(changes: Mapping[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    """Parámetros `set_<col>` y `<col>` para una sentencia de actualización parcial fija."""
    if not changes:
        raise ValueError("No hay cambios que aplicar.")
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"Columnas no permitidas: {sorted(unknown)}")
    nulls = {field for field, value in changes.items() if value is None} & _NOT_NULL_FIELDS
    if nulls:
        raise ValueError(f"Columnas que no admiten nulo: {sorted(nulls)}")
    params: dict[str, Any] = {}
    for field in sorted(allowed):
        params[f"set_{field}"] = field in changes
        params[field] = changes.get(field)
    return params


def _to_preferences_row(row: Mapping[str, Any]) -> PreferencesRow:
    """Convierte las 3 columnas de preferencias_usuario en PreferencesRow."""
    return PreferencesRow(
        notif_consumo=bool(row["notif_consumo"]),
        notif_consejos=bool(row["notif_consejos"]),
        base_comparacion=row["base_comparacion"],
    )
