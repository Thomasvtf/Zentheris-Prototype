"""Consultas de hogar_miembros y permisos.

Las demás funciones se escriben en la sesión de cada endpoint (ver
docs/MAPA-DE-INTEGRACION.md).
"""

from collections.abc import Mapping
from dataclasses import dataclass
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
