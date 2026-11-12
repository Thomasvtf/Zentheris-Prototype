"""Casos de uso de la etiqueta «Sistema».

Esqueleto: cada función responde 501 con su operationId hasta su sesión.
Manejan las transacciones y llaman a domain/ y data/ (api/CLAUDE.md).
"""

from app.schemas.system import SaludRespuesta


def get_health() -> SaludRespuesta:
    """Indica que el servicio responde; no consulta Supabase (contrato 0.2.5)."""
    return SaludRespuesta(estado="ok")
