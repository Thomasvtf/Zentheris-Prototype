"""Etiqueta «Sistema» del contrato: estado del servicio."""

from fastapi import APIRouter

router = APIRouter(tags=["Sistema"])


@router.get("/salud", operation_id="obtenerSalud")
def get_health() -> dict[str, str]:
    """Indica que el servicio responde; no comprueba Supabase (contrato 0.2.5)."""
    return {"estado": "ok"}
