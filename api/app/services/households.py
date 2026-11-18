"""Casos de uso de la etiqueta «Hogares».

Esqueleto: cada función responde 501 con su operationId hasta su sesión.
Manejan las transacciones y llaman a domain/ y data/ (api/CLAUDE.md).
"""

from uuid import UUID

from app.errors import NotImplementedOperation
from app.schemas.households import Hogar, ZonasLista


def get_current_household(user_id: UUID) -> Hogar:
    """`obtenerHogarActual`: Hogar de la membresía activa del usuario (RN-II-01). TODO(obtenerHogarActual)."""
    raise NotImplementedOperation("obtenerHogarActual")


def get_household(user_id: UUID, hogar_id: UUID) -> Hogar:
    """`obtenerHogar`: Datos del hogar, rol del usuario y permisos (RN-II-03). TODO(obtenerHogar)."""
    raise NotImplementedOperation("obtenerHogar")


def list_zones(user_id: UUID, hogar_id: UUID) -> ZonasLista:
    """`listarZonas`: Zonas del hogar, en orden alfabético por nombre (RN-III-01, RN-XII-03). TODO(listarZonas)."""
    raise NotImplementedOperation("listarZonas")
