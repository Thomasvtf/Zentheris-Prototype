"""Router de la etiqueta «Sistema» del contrato 0.2.5.

Solo valida la entrada y llama al servicio (api/CLAUDE.md).
"""

from fastapi import APIRouter

from app.schemas.system import SaludRespuesta
from app.services import system as service

router = APIRouter(tags=["Sistema"])


@router.get(
    "/salud",
    operation_id="obtenerSalud",
    summary="Estado del servicio",
    response_model=SaludRespuesta,
)
def get_health() -> SaludRespuesta:
    """Estado del servicio."""
    return service.get_health()
