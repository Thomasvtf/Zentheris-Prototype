"""Casos de uso de la etiqueta «Metas y tarifa».

Esqueleto: cada función responde 501 con su operationId hasta su sesión.
Manejan las transacciones y llaman a domain/ y data/ (api/CLAUDE.md).
"""

from uuid import UUID

from app.errors import NotImplementedOperation
from app.schemas.goals_tariff import Meta, MetaCrear, MetaVista, Tarifa, TarifaCrear, TarifaVista


def get_goal(user_id: UUID, hogar_id: UUID) -> MetaVista:
    """`obtenerMeta`: Meta activa del hogar y promedio de referencia (RN-V-03, RN-XVI-04). TODO(obtenerMeta)."""
    raise NotImplementedOperation("obtenerMeta")


def create_goal(user_id: UUID, hogar_id: UUID, payload: MetaCrear) -> Meta:
    """`crearMeta`: Guardar una meta nueva (RN-V-03, RN-XVI-04, RN-XVII-04). TODO(crearMeta)."""
    raise NotImplementedOperation("crearMeta")


def get_tariff(user_id: UUID, hogar_id: UUID) -> TarifaVista:
    """`obtenerTarifa`: Tarifa vigente del hogar (RN-XVI-05). TODO(obtenerTarifa)."""
    raise NotImplementedOperation("obtenerTarifa")


def create_tariff(user_id: UUID, hogar_id: UUID, payload: TarifaCrear) -> Tarifa:
    """`crearTarifa`: Guardar una tarifa nueva (RN-V-01, RN-V-02, RN-XVI-05). TODO(crearTarifa)."""
    raise NotImplementedOperation("crearTarifa")
