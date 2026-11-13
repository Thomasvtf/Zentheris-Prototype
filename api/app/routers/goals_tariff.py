"""Router de la etiqueta «Metas y tarifa» del contrato 0.2.5.

Solo valida la entrada y llama al servicio (api/CLAUDE.md).
"""

from uuid import UUID

from fastapi import APIRouter

from app.errors import error_responses
from app.schemas.goals_tariff import Meta, MetaCrear, MetaVista, Tarifa, TarifaCrear, TarifaVista
from app.security.dependencies import CurrentUser
from app.services import goals_tariff as service

router = APIRouter(tags=["Metas y tarifa"])


@router.get(
    "/hogares/{hogar_id}/meta",
    operation_id="obtenerMeta",
    summary="Meta activa del hogar y promedio de referencia (RN-V-03, RN-XVI-04)",
    response_model=MetaVista,
    responses=error_responses(401, 404),
)
def get_goal(hogar_id: UUID, user: CurrentUser) -> MetaVista:
    """Meta activa del hogar y promedio de referencia (RN-V-03, RN-XVI-04)."""
    return service.get_goal(user.id, hogar_id)


@router.post(
    "/hogares/{hogar_id}/metas",
    operation_id="crearMeta",
    summary="Guardar una meta nueva (RN-V-03, RN-XVI-04, RN-XVII-04)",
    response_model=Meta,
    status_code=201,
    responses=error_responses(401, 403, 404, 422),
)
def create_goal(hogar_id: UUID, user: CurrentUser, payload: MetaCrear) -> Meta:
    """Guardar una meta nueva (RN-V-03, RN-XVI-04, RN-XVII-04)."""
    return service.create_goal(user.id, hogar_id, payload)


@router.get(
    "/hogares/{hogar_id}/tarifa",
    operation_id="obtenerTarifa",
    summary="Tarifa vigente del hogar (RN-XVI-05)",
    response_model=TarifaVista,
    responses=error_responses(401, 404),
)
def get_tariff(hogar_id: UUID, user: CurrentUser) -> TarifaVista:
    """Tarifa vigente del hogar (RN-XVI-05)."""
    return service.get_tariff(user.id, hogar_id)


@router.post(
    "/hogares/{hogar_id}/tarifas",
    operation_id="crearTarifa",
    summary="Guardar una tarifa nueva (RN-V-01, RN-V-02, RN-XVI-05)",
    response_model=Tarifa,
    status_code=201,
    responses=error_responses(401, 403, 404, 422),
)
def create_tariff(hogar_id: UUID, user: CurrentUser, payload: TarifaCrear) -> Tarifa:
    """Guardar una tarifa nueva (RN-V-01, RN-V-02, RN-XVI-05)."""
    return service.create_tariff(user.id, hogar_id, payload)
