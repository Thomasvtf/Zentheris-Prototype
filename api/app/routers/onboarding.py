"""Router de la etiqueta «Onboarding» del contrato 0.2.5.

Solo valida la entrada y llama al servicio (api/CLAUDE.md).
"""

from fastapi import APIRouter

from app.errors import error_responses
from app.schemas.households import Hogar
from app.schemas.onboarding import OnboardingCrear
from app.security.dependencies import CurrentUser
from app.services import onboarding as service

router = APIRouter(tags=["Onboarding"])


@router.post(
    "/onboarding",
    operation_id="crearHogarOnboarding",
    summary="Crear el hogar y generar el backfill (RN-X-02, RN-X-03, RN-X-04, RN-IV-01, RN-IV-07)",
    response_model=Hogar,
    status_code=201,
    responses=error_responses(401, 409, 422, 500),
)
def create_household_onboarding(user: CurrentUser, payload: OnboardingCrear) -> Hogar:
    """Crear el hogar y generar el backfill (RN-X-02, RN-X-03, RN-X-04, RN-IV-01, RN-IV-07)."""
    return service.create_household_onboarding(user.id, payload)
