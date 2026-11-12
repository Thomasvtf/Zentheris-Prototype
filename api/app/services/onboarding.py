"""Casos de uso de la etiqueta «Onboarding».

Esqueleto: cada función responde 501 con su operationId hasta su sesión.
Manejan las transacciones y llaman a domain/ y data/ (api/CLAUDE.md).
"""

from uuid import UUID

from app.errors import NotImplementedOperation
from app.schemas.households import Hogar
from app.schemas.onboarding import OnboardingCrear


def create_household_onboarding(user_id: UUID, payload: OnboardingCrear) -> Hogar:
    """`crearHogarOnboarding`: Crear el hogar y generar el backfill (RN-X-02, RN-X-03, RN-X-04, RN-IV-01, RN-IV-07). TODO(crearHogarOnboarding)."""
    raise NotImplementedOperation("crearHogarOnboarding")
