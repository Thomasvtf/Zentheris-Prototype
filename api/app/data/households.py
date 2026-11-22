"""Consultas de hogares, zonas, fuentes y sensores.

Las demás funciones se escriben en la sesión de cada endpoint (ver
docs/MAPA-DE-INTEGRACION.md). Sentencias constantes con parámetros con nombre; sin commit.
"""

from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

# RN-IX-09, DC-36: bloquea la fila del hogar para serializar altas y bajas de miembros.
LOCK_HOUSEHOLD_SQL = text(
    """
    select id
      from hogares
     where id = :hogar_id
       for update
    """
)

# RN-IX-09, DC-36: borra el hogar; el resto de sus datos cae en cascada (I-04).
DELETE_HOUSEHOLD_SQL = text(
    """
    delete from hogares
     where id = :hogar_id
    """
)


def lock_household(session: Session, hogar_id: UUID) -> None:
    """`SELECT ... FOR UPDATE` sobre el hogar hasta el fin de la transacción (RN-IX-09, DC-36).

    Evita que dos bajas simultáneas dejen el hogar sin miembros sin borrarlo. Sin commit.
    """
    session.exec(LOCK_HOUSEHOLD_SQL, params={"hogar_id": hogar_id})


def delete_household(session: Session, hogar_id: UUID) -> None:
    """Borra el hogar y, en cascada, todo lo que depende de él (RN-IX-09, DC-36, I-04).

    Solo se llama cuando el usuario que elimina su cuenta era el único miembro activo.
    Sin commit.
    """
    session.exec(DELETE_HOUSEHOLD_SQL, params={"hogar_id": hogar_id})
