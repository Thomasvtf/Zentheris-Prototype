"""Esquemas del contrato 0.2.5 · Etiqueta «Metas y tarifa».

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api-v0.2.5.yaml y revisado a mano."""

from datetime import date
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TipoMeta(StrEnum):
    """Enum `TipoMeta` del contrato."""

    AHORRO = 'ahorro'
    EFICIENCIA = 'eficiencia'
    PRESUPUESTO = 'presupuesto'


class Meta(BaseModel):
    """Esquema `Meta` del contrato."""

    id: UUID
    tipo: TipoMeta
    valor_kwh_mensual: float = Field(gt=0)
    estado: Literal['activa', 'inactiva']
    fecha_inicio: date
    fecha_fin: date | None


class MetaCrear(BaseModel):
    """Esquema `MetaCrear` del contrato."""

    model_config = ConfigDict(extra="forbid")

    tipo: TipoMeta
    valor_kwh_mensual: float = Field(gt=0)


class MetaVista(BaseModel):
    """Esquema `MetaVista` del contrato."""

    meta: Meta | None
    limite_diario_kwh: float | None
    promedio_diario_30d_kwh: float | None
    puede_editar: bool


class Tarifa(BaseModel):
    """Esquema `Tarifa` del contrato."""

    id: UUID
    operador: str | None
    precio_kwh: float = Field(ge=0)
    cargo_fijo_mensual: float | None = Field(ge=0)
    vigente_desde: date
    vigente_hasta: date | None


class TarifaCrear(BaseModel):
    """Esquema `TarifaCrear` del contrato."""

    model_config = ConfigDict(extra="forbid")

    operador: str | None = Field(default=None)
    precio_kwh: float = Field(ge=0)
    vigente_desde: str = Field(pattern=r'^[0-9]{4}-(0[1-9]|1[0-2])$')
    cargo_fijo_mensual: float | None = Field(default=None, ge=0)


class TarifaVista(BaseModel):
    """Esquema `TarifaVista` del contrato."""

    tarifa: Tarifa | None
    puede_editar: bool
