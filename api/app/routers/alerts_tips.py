"""Router de la etiqueta «Alertas y consejos» del contrato 0.2.5.

Solo valida la entrada y llama al servicio (api/CLAUDE.md).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.errors import error_responses
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
from app.security.dependencies import CurrentUser
from app.services import alerts_tips as service

router = APIRouter(tags=["Alertas y consejos"])


@router.get(
    "/hogares/{hogar_id}/alertas",
    operation_id="listarAlertas",
    summary="Alertas entregadas al usuario (RN-XIV-01, RN-XIV-04, RN-XIV-05)",
    response_model=AlertasLista,
    responses=error_responses(401, 403, 404),
)
def list_alerts(
    hogar_id: UUID,
    user: CurrentUser,
    categoria: Annotated[CategoriaAlerta | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AlertasLista:
    """Alertas entregadas al usuario (RN-XIV-01, RN-XIV-04, RN-XIV-05)."""
    return service.list_alerts(user.id, hogar_id, categoria, limite)


@router.get(
    "/hogares/{hogar_id}/alertas/no-leidas",
    operation_id="contarAlertasNoLeidas",
    summary="Indicador de la campana (RN-XII-02)",
    response_model=AlertasNoLeidas,
    responses=error_responses(401, 403, 404),
)
def count_unread_alerts(hogar_id: UUID, user: CurrentUser) -> AlertasNoLeidas:
    """Indicador de la campana (RN-XII-02)."""
    return service.count_unread_alerts(user.id, hogar_id)


@router.post(
    "/hogares/{hogar_id}/alertas/marcar-leidas",
    operation_id="marcarAlertasLeidas",
    summary="Marcar como leídas las alertas visibles al entrar (RN-XIV-03, RN-VI-05)",
    response_model=AlertasMarcadas,
    responses=error_responses(401, 403, 404, 422),
)
def mark_alerts_read(hogar_id: UUID, user: CurrentUser, payload: AlertasMarcar) -> AlertasMarcadas:
    """Marcar como leídas las alertas visibles al entrar (RN-XIV-03, RN-VI-05)."""
    return service.mark_alerts_read(user.id, hogar_id, payload)


@router.get(
    "/hogares/{hogar_id}/consejos",
    operation_id="listarConsejos",
    summary="Consejos visibles para el usuario (RN-VI-03, RN-XV-02, RN-XV-03, RN-XV-04, RN-XV-05)",
    response_model=ConsejosLista,
    responses=error_responses(401, 404),
)
def list_tips(hogar_id: UUID, user: CurrentUser) -> ConsejosLista:
    """Consejos visibles para el usuario (RN-VI-03, RN-XV-02, RN-XV-03, RN-XV-04, RN-XV-05)."""
    return service.list_tips(user.id, hogar_id)


@router.put(
    "/hogares/{hogar_id}/consejos/{consejo_id}/estado",
    operation_id="actualizarEstadoConsejo",
    summary="Marcar o desmarcar un consejo (RN-XV-03, RN-VI-05)",
    response_model=Consejo,
    responses=error_responses(401, 404, 422),
)
def update_tip_status(
    hogar_id: UUID, consejo_id: UUID, user: CurrentUser, payload: ConsejoEstadoActualizar
) -> Consejo:
    """Marcar o desmarcar un consejo (RN-XV-03, RN-VI-05)."""
    return service.update_tip_status(user.id, hogar_id, consejo_id, payload)
