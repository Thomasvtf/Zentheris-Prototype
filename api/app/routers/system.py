"""Router de la etiqueta «Sistema» del contrato.

Solo valida la entrada y llama al servicio (api/CLAUDE.md).
"""

from fastapi import APIRouter

from app.errors import ErrorResponse
from app.schemas.system import SaludRespuesta
from app.services import system as service

router = APIRouter(tags=["Sistema"])


@router.get(
    "/salud",
    operation_id="obtenerSalud",
    summary="Estado del servicio",
    response_model=SaludRespuesta,
    responses={"4XX": {"model": ErrorResponse, "description": "Solicitud no válida."}},
)
def get_health() -> SaludRespuesta:
    """Estado del servicio."""
    return service.get_health()
