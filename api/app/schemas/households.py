"""Esquemas del contrato · Etiqueta «Hogares»: hogar, permisos y zonas.

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api.yaml y revisado a mano."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import PartialUpdate, Rol, TipoVivienda, TipoZona


class Permisos(BaseModel):
    """Esquema `Permisos` del contrato."""

    ver_consumo_actual: bool
    ver_historial: bool
    recibir_alertas: bool
    modificar_metas: bool


class PermisosActualizar(PartialUpdate):
    """Esquema `PermisosActualizar` del contrato (`minProperties: 1`).

    Cada campo es booleano y no admite null: solo se cambian los permisos enviados.
    """

    ver_consumo_actual: bool = Field(default=None)
    ver_historial: bool = Field(default=None)
    recibir_alertas: bool = Field(default=None)
    modificar_metas: bool = Field(default=None)


class Hogar(BaseModel):
    """Esquema `Hogar` del contrato."""

    id: UUID
    nombre: str
    tipo_vivienda: TipoVivienda
    rol_usuario: Rol
    permisos: Permisos


class Zona(BaseModel):
    """Esquema `Zona` del contrato."""

    id: UUID
    tipo: TipoZona
    nombre: str
    estado: Literal['activa', 'inactiva']


class ZonasLista(BaseModel):
    """Respuesta 200 de `listarZonas` (objeto en línea en el contrato)."""

    zonas: list[Zona]
