"""Consultas de hogar_miembros y permisos.

Membresía activa, alta, cierre, destinatarios de alertas y gestión de miembros (fase 9). Las
demás funciones se escriben en la sesión de cada endpoint (ver docs/MAPA-DE-INTEGRACION.md).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.data._convert import as_uuid

# RN-I-03 y RN-XVII: membresía activa del usuario en el hogar con los 4 permisos generales.
# Constante sin datos del usuario: los valores viajan como parámetros con nombre.
ACTIVE_MEMBERSHIP_SQL = text(
    """
    select m.id as membresia_id,
           m.hogar_id,
           m.usuario_id,
           m.rol,
           h.permiso_ver_consumo_actual,
           h.permiso_ver_historial,
           h.permiso_recibir_alertas,
           h.permiso_modificar_metas
      from hogar_miembros m
      join hogares h on h.id = m.hogar_id
     where m.usuario_id = :usuario_id
       and m.hogar_id = :hogar_id
       and m.estado = 'activo'
    """
)


@dataclass(frozen=True)
class ActiveMembershipRow:
    """Fila activa de hogar_miembros unida a los 4 permisos de hogares (RN-I-03, RN-XVII)."""

    membresia_id: UUID
    hogar_id: UUID
    usuario_id: UUID
    rol: Literal["administrador", "miembro"]
    permiso_ver_consumo_actual: bool
    permiso_ver_historial: bool
    permiso_recibir_alertas: bool
    permiso_modificar_metas: bool


def get_active_membership(
    session: Session, usuario_id: UUID, hogar_id: UUID
) -> ActiveMembershipRow | None:
    """Membresía con estado 'activo' del usuario en ese hogar (RN-I-03); None si no existe.

    Una sola consulta parametrizada que une hogar_miembros con los 4 permisos de hogares
    (RN-XVII). Filtra por hogar y usuario (R-01, P-01) y descarta membresías inactivas.
    No abre ni cierra la transacción: eso es del servicio o de la dependencia.
    """
    result = session.exec(
        ACTIVE_MEMBERSHIP_SQL,
        params={"usuario_id": usuario_id, "hogar_id": hogar_id},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return _to_active_membership_row(row)


def _to_active_membership_row(row: Mapping[str, Any]) -> ActiveMembershipRow:
    """Convierte la fila de ACTIVE_MEMBERSHIP_SQL en ActiveMembershipRow."""
    return ActiveMembershipRow(
        membresia_id=as_uuid(row["membresia_id"]),
        hogar_id=as_uuid(row["hogar_id"]),
        usuario_id=as_uuid(row["usuario_id"]),
        rol=row["rol"],
        permiso_ver_consumo_actual=bool(row["permiso_ver_consumo_actual"]),
        permiso_ver_historial=bool(row["permiso_ver_historial"]),
        permiso_recibir_alertas=bool(row["permiso_recibir_alertas"]),
        permiso_modificar_metas=bool(row["permiso_modificar_metas"]),
    )


# RN-IX-09, DC-36: la membresía activa del usuario (como máximo una por el índice único
# parcial uq_miembros_usuario_activo). Se filtra por el usuario autenticado.
_ACTIVE_MEMBERSHIP_OF_USER_BASE = """
    select id as membresia_id,
           hogar_id,
           rol
      from hogar_miembros
     where usuario_id = :usuario_id
       and estado = 'activo'
    """
ACTIVE_MEMBERSHIP_OF_USER_SQL = text(_ACTIVE_MEMBERSHIP_OF_USER_BASE)
# Igual, bloqueando la fila hasta el fin de la transacción (eliminar cuenta, RN-IX-09).
ACTIVE_MEMBERSHIP_OF_USER_FOR_UPDATE_SQL = text(_ACTIVE_MEMBERSHIP_OF_USER_BASE + " for update")

# RN-IX-09, DC-36: cuántos miembros activos quedan en el hogar además del usuario.
COUNT_OTHER_ACTIVE_MEMBERS_SQL = text(
    """
    select count(*) as total
      from hogar_miembros
     where hogar_id = :hogar_id
       and estado = 'activo'
       and usuario_id <> :usuario_id
    """
)

# RN-X-07, DC-36: cierra la membresía (los datos del hogar quedan intactos).
CLOSE_MEMBERSHIP_SQL = text(
    """
    update hogar_miembros
       set estado = 'inactivo',
           fecha_salida = :closed_at
     where id = :membresia_id
       and estado = 'activo'
    """
)


@dataclass(frozen=True)
class MembershipSummaryRow:
    """Membresía activa del usuario sin permisos: id, hogar y rol (RN-IX-09, DC-36)."""

    membresia_id: UUID
    hogar_id: UUID
    rol: Literal["administrador", "miembro"]


def get_active_membership_of_user(
    session: Session, usuario_id: UUID, *, for_update: bool = False
) -> MembershipSummaryRow | None:
    """Membresía con estado 'activo' del usuario en cualquier hogar; None si no tiene.

    RN-I-03 y uq_miembros_usuario_activo: como máximo una. Filtra por el usuario
    autenticado, así que no expone membresías ajenas (R-01). Con `for_update=True` bloquea
    la fila (`FOR UPDATE`) para serializar la eliminación de cuenta (RN-IX-09, DC-36).
    """
    statement = (
        ACTIVE_MEMBERSHIP_OF_USER_FOR_UPDATE_SQL if for_update else ACTIVE_MEMBERSHIP_OF_USER_SQL
    )
    result = session.exec(statement, params={"usuario_id": usuario_id})
    row = result.mappings().first()
    if row is None:
        return None
    return MembershipSummaryRow(
        membresia_id=as_uuid(row["membresia_id"]),
        hogar_id=as_uuid(row["hogar_id"]),
        rol=row["rol"],
    )


def count_other_active_members(session: Session, hogar_id: UUID, usuario_id: UUID) -> int:
    """Miembros activos del hogar distintos de `usuario_id` (RN-IX-09, DC-36).

    0 significa que el usuario es el único miembro: al eliminar su cuenta se borra el hogar.
    """
    result = session.exec(
        COUNT_OTHER_ACTIVE_MEMBERS_SQL,
        params={"hogar_id": hogar_id, "usuario_id": usuario_id},
    )
    row = result.mappings().first()
    return int(row["total"]) if row is not None else 0


def close_membership(session: Session, membresia_id: UUID, closed_at: datetime) -> None:
    """Deja la membresía en 'inactivo' con `fecha_salida = closed_at` (RN-X-07, DC-36).

    El usuario_id queda en nulo después, por la cascada al borrar la cuenta en Auth. Sin commit.
    """
    session.exec(
        CLOSE_MEMBERSHIP_SQL,
        params={"membresia_id": membresia_id, "closed_at": closed_at},
    )


# SQLSTATE de Postgres para violación de unicidad.
_UNIQUE_VIOLATION = "23505"
# Índice único parcial de la migración 0003 (RN-II-01: una membresía activa por usuario).
ACTIVE_USER_INDEX = "uq_miembros_usuario_activo"

# RN-X-03, RN-II-02: quien crea el hogar entra como administrador activo.
INSERT_ADMIN_MEMBERSHIP_SQL = text(
    """
    insert into hogar_miembros (hogar_id, usuario_id, rol, estado, fecha_ingreso)
    values (:hogar_id, :usuario_id, 'administrador', 'activo', :joined_at)
    """
)


class ActiveMembershipExistsError(Exception):
    """El usuario ya tiene una membresía activa (23505 de uq_miembros_usuario_activo, RN-II-01).

    Caso: dos onboardings simultáneos del mismo usuario. El servicio la traduce a 409.
    """


def insert_admin_membership(
    session: Session, *, hogar_id: UUID, usuario_id: UUID, joined_at: datetime
) -> None:
    """Crea la membresía activa del administrador del hogar nuevo (RN-X-03, RN-II-01).

    ActiveMembershipExistsError si el usuario ya tiene otra membresía activa (SQLSTATE 23505 del
    índice uq_miembros_usuario_activo). Cualquier otra IntegrityError sube tal cual (por ejemplo,
    23503 si el usuario no tiene ficha). La transacción queda abortada. Sin commit.
    """
    try:
        session.exec(
            INSERT_ADMIN_MEMBERSHIP_SQL,
            params={"hogar_id": hogar_id, "usuario_id": usuario_id, "joined_at": joined_at},
        )
    except IntegrityError as exc:
        if _violates_active_user_index(exc):
            # `from None`: el detalle de Postgres lleva el id del usuario (S-01).
            raise ActiveMembershipExistsError("El usuario ya tiene un hogar activo.") from None
        raise


def _violates_active_user_index(exc: IntegrityError) -> bool:
    """True si el error es el 23505 de uq_miembros_usuario_activo.

    El nombre sale de `diag.constraint_name`; si el controlador no lo trae, del mensaje.
    """
    if getattr(exc.orig, "pgcode", None) != _UNIQUE_VIOLATION:
        return False
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name is not None:
        return constraint_name == ACTIVE_USER_INDEX
    return ACTIVE_USER_INDEX in str(exc.orig)


# RN-VI-02, RN-XIV-06 (entrega) y RN-VI-03, RN-XV-06 (consejos), R-01: miembros activos del hogar
# con sus interruptores de notificación. Sin fila de preferencias, los interruptores valen true
# (valor por defecto de la tabla). Entra por ix_miembros_hogar_estado. fecha_ingreso deja al
# servicio excluir a quien ingresó después del evento (RN-VI-02: sin efecto retroactivo;
# RN-XV-06: no recibe consejos anteriores).
ALERT_MEMBERS_SQL = text(
    """
    select m.usuario_id,
           m.rol,
           coalesce(p.notif_consumo, true) as notif_consumo,
           coalesce(p.notif_consejos, true) as notif_consejos,
           m.fecha_ingreso
      from hogar_miembros m
      left join preferencias_usuario p on p.usuario_id = m.usuario_id
     where m.hogar_id = :hogar_id
       and m.estado = 'activo'
       and m.usuario_id is not null
     order by m.usuario_id
    """
)

# RN-VI-02, RN-XVII: el permiso general «recibir alertas» del hogar.
ALERT_PERMISSION_SQL = text(
    """
    select permiso_recibir_alertas
      from hogares
     where id = :hogar_id
    """
)


@dataclass(frozen=True)
class AlertMemberRow:
    """Miembro activo, su fecha de ingreso y sus interruptores del momento (RN-VI-02, RN-XV-06)."""

    usuario_id: UUID
    rol: Literal["administrador", "miembro"]
    notif_consumo: bool
    notif_consejos: bool
    fecha_ingreso: datetime  # hogar_miembros.fecha_ingreso (timestamptz not null)


def list_alert_members(session: Session, hogar_id: UUID) -> list[AlertMemberRow]:
    """Miembros con estado 'activo' de `hogar_id` y sus interruptores (RN-VI-02, RN-VI-03, R-01).

    LEFT JOIN a preferencias_usuario: sin fila, notif_consumo y notif_consejos valen True. Incluye
    `fecha_ingreso` (con zona horaria) para no entregar eventos anteriores al ingreso (RN-VI-02,
    RN-XV-06). Orden por usuario_id. El servicio decide los destinatarios (alert_rules.alert_recipients). Sin commit.
    """
    result = session.exec(ALERT_MEMBERS_SQL, params={"hogar_id": hogar_id})
    return [
        AlertMemberRow(
            usuario_id=as_uuid(row["usuario_id"]),
            rol=row["rol"],
            notif_consumo=bool(row["notif_consumo"]),
            notif_consejos=bool(row["notif_consejos"]),
            fecha_ingreso=row["fecha_ingreso"],
        )
        for row in result.mappings().all()
    ]


def get_alert_permission(session: Session, hogar_id: UUID) -> bool | None:
    """`hogares.permiso_recibir_alertas` de `hogar_id`; None si el hogar no existe (RN-VI-02).

    Sin commit.
    """
    result = session.exec(ALERT_PERMISSION_SQL, params={"hogar_id": hogar_id})
    row = result.mappings().first()
    return None if row is None else bool(row["permiso_recibir_alertas"])


# --- Fase 9: miembros del hogar (RN-II-01, RN-II-02, RN-X-06, RN-X-07, RN-IX-09, DC-36) ---------

MembershipRole = Literal["administrador", "miembro"]
MEMBERSHIP_ROLES = frozenset({"administrador", "miembro"})

# RN-II-02, R-01: miembros activos del hogar con su ficha; el administrador primero, luego por
# fecha de ingreso. Una membresía activa siempre tiene usuario (miembros_activo_con_usuario).
ACTIVE_MEMBERS_SQL = text(
    """
    select m.id as membresia_id,
           m.usuario_id,
           u.nombre_completo,
           u.avatar_url,
           m.rol,
           m.fecha_ingreso
      from hogar_miembros m
      join usuarios u on u.id = m.usuario_id
     where m.hogar_id = :hogar_id
       and m.estado = 'activo'
     order by case when m.rol = 'administrador' then 0 else 1 end,
              m.fecha_ingreso,
              m.id
    """
)

# RN-II-02: miembros activos del hogar (límite de 5).
COUNT_ACTIVE_MEMBERS_SQL = text(
    """
    select count(*) as total
      from hogar_miembros
     where hogar_id = :hogar_id
       and estado = 'activo'
    """
)

# RN-X-07, R-01: una membresía por id solo si es de ese hogar (cualquier estado).
_HOUSEHOLD_MEMBERSHIP_BASE = """
    select id as membresia_id,
           hogar_id,
           usuario_id,
           rol,
           estado
      from hogar_miembros
     where id = :membresia_id
       and hogar_id = :hogar_id
    """
HOUSEHOLD_MEMBERSHIP_SQL = text(_HOUSEHOLD_MEMBERSHIP_BASE)
# Igual, bloqueando la fila (después de lock_household: orden hogar → membresía → usuario).
HOUSEHOLD_MEMBERSHIP_FOR_UPDATE_SQL = text(_HOUSEHOLD_MEMBERSHIP_BASE + " for update")

# RN-I-03, RN-II-02: la membresía activa del usuario en ese hogar.
_USER_MEMBERSHIP_IN_HOUSEHOLD_BASE = """
    select id as membresia_id,
           hogar_id,
           usuario_id,
           rol,
           estado
      from hogar_miembros
     where hogar_id = :hogar_id
       and usuario_id = :usuario_id
       and estado = 'activo'
    """
USER_MEMBERSHIP_IN_HOUSEHOLD_SQL = text(_USER_MEMBERSHIP_IN_HOUSEHOLD_BASE)
# Igual, bloqueando la fila (guardia de gestión del administrador).
USER_MEMBERSHIP_IN_HOUSEHOLD_FOR_UPDATE_SQL = text(
    _USER_MEMBERSHIP_IN_HOUSEHOLD_BASE + " for update"
)

# RN-II-02, RN-II-04, RN-X-07: cambia el rol de una membresía activa (transferir la administración).
SET_MEMBERSHIP_ROLE_SQL = text(
    """
    update hogar_miembros
       set rol = :rol
     where id = :membresia_id
       and estado = 'activo'
    """
)

# RN-X-06, RN-II-01: quien acepta una invitación entra como miembro activo.
INSERT_MEMBER_MEMBERSHIP_SQL = text(
    """
    insert into hogar_miembros (hogar_id, usuario_id, rol, estado, fecha_ingreso)
    values (:hogar_id, :usuario_id, 'miembro', 'activo', :fecha_ingreso)
    returning id
    """
)

# RN-X-05: ¿el correo ya es de un miembro activo del hogar? El correo vive en auth.users.
ACTIVE_MEMBER_EMAIL_SQL = text(
    """
    select 1 as existe
      from hogar_miembros m
      join auth.users au on au.id = m.usuario_id
     where m.hogar_id = :hogar_id
       and m.estado = 'activo'
       and lower(au.email) = lower(:correo)
     limit 1
    """
)


@dataclass(frozen=True)
class MemberRow:
    """Miembro activo del hogar con su ficha (RN-II-02, RN-X-07)."""

    membresia_id: UUID
    usuario_id: UUID
    nombre_completo: str
    avatar_url: str | None  # ruta en el bucket privado de avatares (DC-43)
    rol: MembershipRole
    fecha_ingreso: datetime


@dataclass(frozen=True)
class MembershipRow:
    """Fila de hogar_miembros: id, hogar, usuario (nulo si eliminó su cuenta), rol y estado."""

    membresia_id: UUID
    hogar_id: UUID
    usuario_id: UUID | None
    rol: MembershipRole
    estado: Literal["activo", "inactivo"]


def list_active_members(session: Session, hogar_id: UUID) -> list[MemberRow]:
    """Miembros activos del hogar con nombre y avatar (RN-II-02, R-01).

    Orden: administrador primero, luego `fecha_ingreso` y `membresia_id`. Sin commit.
    """
    result = session.exec(ACTIVE_MEMBERS_SQL, params={"hogar_id": hogar_id})
    return [
        MemberRow(
            membresia_id=as_uuid(row["membresia_id"]),
            usuario_id=as_uuid(row["usuario_id"]),
            nombre_completo=row["nombre_completo"],
            avatar_url=row["avatar_url"],
            rol=row["rol"],
            fecha_ingreso=row["fecha_ingreso"],
        )
        for row in result.mappings().all()
    ]


def count_active_members(session: Session, hogar_id: UUID) -> int:
    """Miembros activos del hogar (RN-II-02: máximo 5). Sin commit."""
    result = session.exec(COUNT_ACTIVE_MEMBERS_SQL, params={"hogar_id": hogar_id})
    row = result.mappings().first()
    return int(row["total"]) if row is not None else 0


def get_household_membership(
    session: Session, hogar_id: UUID, membresia_id: UUID, *, for_update: bool = False
) -> MembershipRow | None:
    """La membresía `membresia_id` solo si es de `hogar_id`, en cualquier estado (RN-X-07, R-01).

    Una membresía de otro hogar devuelve None (P-01). Con `for_update=True` bloquea la fila; se
    pide después de `lock_household` (orden hogar → membresía → usuario). Sin commit.
    """
    statement = HOUSEHOLD_MEMBERSHIP_FOR_UPDATE_SQL if for_update else HOUSEHOLD_MEMBERSHIP_SQL
    result = session.exec(
        statement,
        params={"hogar_id": hogar_id, "membresia_id": membresia_id},
    )
    row = result.mappings().first()
    return None if row is None else _to_membership_row(row)


def get_user_membership_in_household(
    session: Session, hogar_id: UUID, usuario_id: UUID, *, for_update: bool = False
) -> MembershipRow | None:
    """La membresía 'activo' del usuario en ese hogar; None si no la tiene (RN-I-03, RN-II-02).

    Con `for_update=True` bloquea la fila (guardia de gestión, después de `lock_household`).
    Sin commit.
    """
    statement = (
        USER_MEMBERSHIP_IN_HOUSEHOLD_FOR_UPDATE_SQL
        if for_update
        else USER_MEMBERSHIP_IN_HOUSEHOLD_SQL
    )
    result = session.exec(
        statement,
        params={"hogar_id": hogar_id, "usuario_id": usuario_id},
    )
    row = result.mappings().first()
    return None if row is None else _to_membership_row(row)


def set_membership_role(session: Session, membresia_id: UUID, rol: MembershipRole) -> None:
    """Cambia el rol de una membresía activa (RN-II-02, RN-X-07: transferir la administración).

    El servicio baja primero al administrador y luego sube al destino: el índice
    uq_miembros_admin_activo admite un solo administrador activo por hogar. ValueError con un rol
    desconocido. Sin commit.
    """
    if rol not in MEMBERSHIP_ROLES:
        raise ValueError("Rol de membresía no permitido.")
    session.exec(SET_MEMBERSHIP_ROLE_SQL, params={"membresia_id": membresia_id, "rol": rol})


def insert_member_membership(
    session: Session, *, hogar_id: UUID, usuario_id: UUID, fecha_ingreso: datetime
) -> UUID:
    """Crea la membresía 'miembro' y 'activo' de quien acepta una invitación (RN-X-06, RN-II-01).

    Devuelve el id nuevo. ActiveMembershipExistsError si el usuario ya tiene otra membresía activa
    (23505 de uq_miembros_usuario_activo). Cualquier otra IntegrityError sube tal cual (por
    ejemplo, 23514 del trigger de 5 miembros). La transacción queda abortada. Sin commit.
    """
    try:
        result = session.exec(
            INSERT_MEMBER_MEMBERSHIP_SQL,
            params={
                "hogar_id": hogar_id,
                "usuario_id": usuario_id,
                "fecha_ingreso": fecha_ingreso,
            },
        )
    except IntegrityError as exc:
        if _violates_active_user_index(exc):
            # `from None`: el detalle de Postgres lleva el id del usuario (S-01).
            raise ActiveMembershipExistsError("El usuario ya tiene un hogar activo.") from None
        raise
    return as_uuid(result.mappings().one()["id"])


def is_active_member_email(session: Session, hogar_id: UUID, correo: str) -> bool:
    """True si algún miembro activo del hogar tiene ese correo (RN-X-05: ya es miembro).

    Une auth.users (email) y compara con `lower()` en ambos lados. Solo lectura. Sin commit.
    """
    result = session.exec(
        ACTIVE_MEMBER_EMAIL_SQL,
        params={"hogar_id": hogar_id, "correo": correo},
    )
    return result.mappings().first() is not None


def _to_membership_row(row: Mapping[str, Any]) -> MembershipRow:
    """Convierte una fila de hogar_miembros en MembershipRow (usuario_id puede ser nulo)."""
    usuario_id = row["usuario_id"]
    return MembershipRow(
        membresia_id=as_uuid(row["membresia_id"]),
        hogar_id=as_uuid(row["hogar_id"]),
        usuario_id=None if usuario_id is None else as_uuid(usuario_id),
        rol=row["rol"],
        estado=row["estado"],
    )
