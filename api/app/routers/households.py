"""Router de la etiqueta «Hogares» del contrato 0.2.5.

Solo valida la entrada y llama al servicio (api/CLAUDE.md).
"""

from uuid import UUID

from fastapi import APIRouter

from app.errors import error_responses
from app.schemas.households import Hogar, ZonasLista
from app.security.dependencies import CurrentUser
from app.services import households as service

router = APIRouter(tags=["Hogares"])


@router.get(
    "/hogares/actual",
    operation_id="obtenerHogarActual",
    summary="Hogar de la membresía activa del usuario (RN-II-01)",
    response_model=Hogar,
    responses=error_responses(401, 404),
)
def get_current_household(user: CurrentUser) -> Hogar:
    """Hogar de la membresía activa del usuario (RN-II-01)."""
    return service.get_current_household(user.id)


@router.get(
    "/hogares/{hogar_id}",
    operation_id="obtenerHogar",
    summary="Datos del hogar, rol del usuario y permisos (RN-II-03)",
    response_model=Hogar,
    responses=error_responses(401, 404),
)
def get_household(hogar_id: UUID, user: CurrentUser) -> Hogar:
    """Datos del hogar, rol del usuario y permisos (RN-II-03)."""
    return service.get_household(user.id, hogar_id)


@router.get(
    "/hogares/{hogar_id}/zonas",
    operation_id="listarZonas",
    summary="Zonas del hogar, en orden alfabético por nombre (RN-III-01, RN-XII-03)",
    response_model=ZonasLista,
    responses=error_responses(401, 404),
)
def list_zones(hogar_id: UUID, user: CurrentUser) -> ZonasLista:
    """Zonas del hogar, en orden alfabético por nombre (RN-III-01, RN-XII-03)."""
    return service.list_zones(user.id, hogar_id)
