"""Esquemas del contrato 0.2.5 · Etiqueta «Sistema».

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api-v0.2.5.yaml y revisado a mano."""

from typing import Literal

from pydantic import BaseModel


class SaludRespuesta(BaseModel):
    """Respuesta 200 de `obtenerSalud` (objeto en línea en el contrato)."""

    estado: Literal['ok']
