"""Consultas de hogar_miembros y permisos.

Las demás funciones se escriben en la sesión de cada endpoint (ver
docs/MAPA-DE-INTEGRACION.md).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

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


def _as_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _to_active_membership_row(row: Mapping[str, Any]) -> ActiveMembershipRow:
    """Convierte la fila de ACTIVE_MEMBERSHIP_SQL en ActiveMembershipRow."""
    return ActiveMembershipRow(
        membresia_id=_as_uuid(row["membresia_id"]),
        hogar_id=_as_uuid(row["hogar_id"]),
        usuario_id=_as_uuid(row["usuario_id"]),
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
        membresia_id=_as_uuid(row["membresia_id"]),
        hogar_id=_as_uuid(row["hogar_id"]),
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
