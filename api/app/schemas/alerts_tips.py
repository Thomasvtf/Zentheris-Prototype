"""Esquemas del contrato 0.2.5 · Etiqueta «Alertas y consejos».

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api-v0.2.5.yaml y revisado a mano."""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoriaAlerta(StrEnum):
    """Enum `CategoriaAlerta` del contrato."""

    CONSUMO = 'consumo'
    CONSEJO = 'consejo'
    INFORMACION = 'informacion'


class Alerta(BaseModel):
    """Esquema `Alerta` del contrato."""

    id: UUID
    categoria: CategoriaAlerta
    severidad: Literal['informativa', 'advertencia', 'critica']
    titulo: str
    mensaje: str
    zona_id: UUID | None
    zona_nombre: str | None
    creada_en: datetime
    leida_en: datetime | None


class AlertasMarcar(BaseModel):
    """Esquema `AlertasMarcar` del contrato."""

    model_config = ConfigDict(extra="forbid")

    alerta_ids: list[UUID] = Field(min_length=1)


class Consejo(BaseModel):
    """Esquema `Consejo` del contrato."""

    id: UUID
    categoria: str
    prioridad: Literal['alta', 'media', 'baja']
    titulo: str
    descripcion: str
    zona_id: UUID | None
    zona_nombre: str | None
    estado: Literal['pendiente', 'completada']
    completada_en: datetime | None
    creado_en: datetime


class ConsejoEstadoActualizar(BaseModel):
    """Esquema `ConsejoEstadoActualizar` del contrato."""

    model_config = ConfigDict(extra="forbid")

    estado: Literal['pendiente', 'completada']


class AlertasLista(BaseModel):
    """Respuesta 200 de `listarAlertas` (objeto en línea en el contrato)."""

    alertas: list[Alerta]


class AlertasNoLeidas(BaseModel):
    """Respuesta 200 de `contarAlertasNoLeidas` (objeto en línea en el contrato)."""

    cantidad: int = Field(ge=0)


class AlertasMarcadas(BaseModel):
    """Respuesta 200 de `marcarAlertasLeidas` (objeto en línea en el contrato)."""

    marcadas: int = Field(ge=0)


class ConsejosLista(BaseModel):
    """Respuesta 200 de `listarConsejos` (objeto en línea en el contrato)."""

    consejos: list[Consejo]
