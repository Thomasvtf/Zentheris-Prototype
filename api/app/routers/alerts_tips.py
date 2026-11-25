"""Router de la etiqueta «Alertas y consejos» del contrato.

Solo valida la entrada y llama al servicio (api/CLAUDE.md). Cada operación recibe la sesión de la
petición (`get_session`), la misma que usó la guardia de membresía; las consultas completan las
horas faltantes en el servicio antes de leer (RN-IV-05, DC-34).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.data.database import get_session
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
from app.security.dependencies import (
    CurrentMembership,
    CurrentUser,
    Membership,
    require_permission,
)
from app.services import alerts_tips as service

router = APIRouter(tags=["Alertas y consejos"])

# La misma sesión que reciben las dependencias de la petición (la guardia de membresía).
DbSession = Annotated[Session, Depends(get_session)]


@router.get(
    "/hogares/{hogar_id}/alertas",
    operation_id="listarAlertas",
    summary="Alertas entregadas al usuario (RN-XIV-01, RN-XIV-04, RN-XIV-05)",
    response_model=AlertasLista,
    responses=error_responses(401, 403, 404, 422),
)
def list_alerts(
    hogar_id: UUID,
    user: CurrentUser,
    member: Annotated[Membership, Depends(require_permission("recibir_alertas"))],
    session: DbSession,
    categoria: Annotated[CategoriaAlerta | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AlertasLista:
    """Alertas entregadas al usuario (RN-XIV-01, RN-XIV-04, RN-XIV-05)."""
    return service.list_alerts(session, user.id, hogar_id, categoria, limite)


@router.get(
    "/hogares/{hogar_id}/alertas/no-leidas",
    operation_id="contarAlertasNoLeidas",
    summary="Indicador de la campana (RN-XII-02)",
    response_model=AlertasNoLeidas,
    responses=error_responses(401, 403, 404, 422),
)
def count_unread_alerts(
    hogar_id: UUID,
    user: CurrentUser,
    member: Annotated[Membership, Depends(require_permission("recibir_alertas"))],
    session: DbSession,
) -> AlertasNoLeidas:
    """Indicador de la campana (RN-XII-02)."""
    return service.count_unread_alerts(session, user.id, hogar_id)


@router.post(
    "/hogares/{hogar_id}/alertas/marcar-leidas",
    operation_id="marcarAlertasLeidas",
    summary="Marcar como leídas las alertas visibles al entrar (RN-XIV-03, RN-VI-05)",
    response_model=AlertasMarcadas,
    responses=error_responses(401, 403, 404, 422),
)
def mark_alerts_read(
    hogar_id: UUID,
    user: CurrentUser,
    member: Annotated[Membership, Depends(require_permission("recibir_alertas"))],
    payload: AlertasMarcar,
    session: DbSession,
) -> AlertasMarcadas:
    """Marcar como leídas las alertas visibles al entrar (RN-XIV-03, RN-VI-05)."""
    return service.mark_alerts_read(session, user.id, hogar_id, payload)


@router.get(
    "/hogares/{hogar_id}/consejos",
    operation_id="listarConsejos",
    summary="Consejos visibles para el usuario (RN-VI-03, RN-XV-02, RN-XV-03, RN-XV-04, RN-XV-05)",
    response_model=ConsejosLista,
    responses=error_responses(401, 404, 422),
)
def list_tips(
    hogar_id: UUID, user: CurrentUser, member: CurrentMembership, session: DbSession
) -> ConsejosLista:
    """Consejos visibles para el usuario (RN-VI-03, RN-XV-02, RN-XV-03, RN-XV-04, RN-XV-05)."""
    return service.list_tips(session, user.id, hogar_id)


@router.put(
    "/hogares/{hogar_id}/consejos/{consejo_id}/estado",
    operation_id="actualizarEstadoConsejo",
    summary="Marcar o desmarcar un consejo (RN-XV-03, RN-VI-05)",
    response_model=Consejo,
    responses=error_responses(401, 404, 422),
)
def update_tip_status(
    hogar_id: UUID,
    consejo_id: UUID,
    user: CurrentUser,
    member: CurrentMembership,
    payload: ConsejoEstadoActualizar,
    session: DbSession,
) -> Consejo:
    """Marcar o desmarcar un consejo (RN-XV-03, RN-VI-05)."""
    return service.update_tip_status(session, user.id, hogar_id, consejo_id, payload)
