"""Casos de uso de la etiqueta «Alertas y consejos».

Esqueleto: cada función responde 501 con su operationId hasta su sesión.
Manejan las transacciones y llaman a domain/ y data/ (api/CLAUDE.md).
"""

from uuid import UUID

from app.errors import NotImplementedOperation
from app.schemas.alerts_tips import (
    AlertasLista,
    AlertasMarcadas,
    AlertasMarcar,
    AlertasNoLeidas,
    CategoriaAlerta,
    Consejo,
    ConsejoEstadoActualizar,
    ConsejosLista,
)


def list_alerts(
    user_id: UUID, hogar_id: UUID, categoria: CategoriaAlerta | None, limite: int
) -> AlertasLista:
    """`listarAlertas`: Alertas entregadas al usuario (RN-XIV-01, RN-XIV-04, RN-XIV-05). TODO(listarAlertas)."""
    raise NotImplementedOperation("listarAlertas")


def count_unread_alerts(user_id: UUID, hogar_id: UUID) -> AlertasNoLeidas:
    """`contarAlertasNoLeidas`: Indicador de la campana (RN-XII-02). TODO(contarAlertasNoLeidas)."""
    raise NotImplementedOperation("contarAlertasNoLeidas")


def mark_alerts_read(user_id: UUID, hogar_id: UUID, payload: AlertasMarcar) -> AlertasMarcadas:
    """`marcarAlertasLeidas`: Marcar como leídas las alertas visibles al entrar (RN-XIV-03, RN-VI-05). TODO(marcarAlertasLeidas)."""
    raise NotImplementedOperation("marcarAlertasLeidas")


def list_tips(user_id: UUID, hogar_id: UUID) -> ConsejosLista:
    """`listarConsejos`: Consejos visibles para el usuario (RN-VI-03, RN-XV-02, RN-XV-03, RN-XV-04, RN-XV-05). TODO(listarConsejos)."""
    raise NotImplementedOperation("listarConsejos")


def update_tip_status(
    user_id: UUID, hogar_id: UUID, consejo_id: UUID, payload: ConsejoEstadoActualizar
) -> Consejo:
    """`actualizarEstadoConsejo`: Marcar o desmarcar un consejo (RN-XV-03, RN-VI-05). TODO(actualizarEstadoConsejo)."""
    raise NotImplementedOperation("actualizarEstadoConsejo")
