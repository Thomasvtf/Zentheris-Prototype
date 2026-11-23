"""Esquemas del contrato · Etiqueta «Onboarding».

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api.yaml y revisado a mano."""

import unicodedata
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.schemas.common import TipoVivienda, TipoZona


def _reject_control_characters(value: str) -> str:
    """Rechaza los caracteres de control Unicode (categoría Cc), sin recortar nada más.

    NUL no se puede guardar en PostgreSQL y CR/LF acabaría en el asunto del correo de
    invitación. No cambia el JSON Schema publicado. El mensaje no repite el valor enviado.
    """
    if any(unicodedata.category(char) == "Cc" for char in value):
        raise ValueError("no admite caracteres de control")
    return value


class OnboardingCrear(BaseModel):
    """Esquema `OnboardingCrear` del contrato.

    `uniqueItems` solo se publica en el OpenAPI: las zonas repetidas las rechaza el servicio con
    `ZONAS_DUPLICADAS` (RN-X-02).
    """

    model_config = ConfigDict(extra="forbid")

    nombre_hogar: Annotated[
        str, Field(min_length=1, max_length=80), AfterValidator(_reject_control_characters)
    ]
    tipo_vivienda: TipoVivienda
    zonas: list[TipoZona] = Field(
        min_length=3, max_length=9, json_schema_extra={"uniqueItems": True}
    )
