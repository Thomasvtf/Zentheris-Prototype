"""Esquemas del contrato 0.2.5 · Etiqueta «Onboarding».

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api-v0.2.5.yaml y revisado a mano."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import TipoVivienda, TipoZona


class OnboardingCrear(BaseModel):
    """Esquema `OnboardingCrear` del contrato."""

    model_config = ConfigDict(extra="forbid")

    nombre_hogar: str = Field(min_length=1)
    tipo_vivienda: TipoVivienda
    zonas: list[TipoZona] = Field(min_length=3, max_length=9)
