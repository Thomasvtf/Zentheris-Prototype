"""Esquemas del contrato 0.2.5 · Enumeraciones y tipos comunes del contrato.

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api-v0.2.5.yaml y revisado a mano."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class EstadoConsumo(StrEnum):
    """Enum `EstadoConsumo` del contrato."""

    NORMAL = 'normal'
    ELEVADO = 'elevado'
    CRITICO = 'critico'
    SIN_REFERENCIA = 'sin_referencia'
    SIN_DATOS = 'sin_datos'


class ReferenciaTipo(StrEnum):
    """Enum `ReferenciaTipo` del contrato."""

    PROMEDIO = 'promedio'
    META = 'meta'


class MensajeCodigo(StrEnum):
    """Enum `MensajeCodigo` del contrato."""

    CONSUMO_ACTUAL_NORMAL = 'consumo_actual.normal'
    CONSUMO_ACTUAL_ELEVADO = 'consumo_actual.elevado'
    CONSUMO_ACTUAL_CRITICO = 'consumo_actual.critico'
    CONSUMO_ACTUAL_SIN_DATOS = 'consumo_actual.sin_datos'
    CONSUMO_ACTUAL_SIN_REFERENCIA = 'consumo_actual.sin_referencia'
    ACUMULADO_META_NORMAL = 'acumulado.meta.normal'
    ACUMULADO_META_ELEVADO = 'acumulado.meta.elevado'
    ACUMULADO_META_CRITICO = 'acumulado.meta.critico'
    ACUMULADO_PROMEDIO_NORMAL = 'acumulado.promedio.normal'
    ACUMULADO_PROMEDIO_ELEVADO = 'acumulado.promedio.elevado'
    ACUMULADO_PROMEDIO_CRITICO = 'acumulado.promedio.critico'
    ACUMULADO_META_SIN_REFERENCIA = 'acumulado.meta.sin_referencia'
    ACUMULADO_META_SIN_DATOS = 'acumulado.meta.sin_datos'
    ACUMULADO_PROMEDIO_SIN_REFERENCIA = 'acumulado.promedio.sin_referencia'
    ACUMULADO_PROMEDIO_SIN_DATOS = 'acumulado.promedio.sin_datos'
    ZONA_ESTADO_NORMAL = 'zona_estado.normal'
    ZONA_ESTADO_ELEVADO = 'zona_estado.elevado'
    ZONA_ESTADO_CRITICO = 'zona_estado.critico'
    ZONA_ESTADO_SIN_DATOS = 'zona_estado.sin_datos'
    ZONA_ESTADO_SIN_REFERENCIA = 'zona_estado.sin_referencia'
    HISTORIAL_COMPARACION_MENOR = 'historial_comparacion.menor'
    HISTORIAL_COMPARACION_SIMILAR = 'historial_comparacion.similar'
    HISTORIAL_COMPARACION_MAYOR = 'historial_comparacion.mayor'
    HISTORIAL_COMPARACION_MUY_MAYOR = 'historial_comparacion.muy_mayor'
    HISTORIAL_COMPARACION_SIN_ANTERIOR = 'historial_comparacion.sin_anterior'
    HISTORIAL_COMPARACION_SIN_REFERENCIA = 'historial_comparacion.sin_referencia'


class TipoVivienda(StrEnum):
    """Enum `TipoVivienda` del contrato."""

    APARTAMENTO = 'apartamento'
    CASA = 'casa'
    APARTAESTUDIO = 'apartaestudio'
    DUPLEX = 'duplex'
    CASA_CAMPESTRE = 'casa_campestre'


class TipoZona(StrEnum):
    """Enum `TipoZona` del contrato."""

    COCINA = 'cocina'
    SALA = 'sala'
    DORMITORIO = 'dormitorio'
    BANO = 'bano'
    OFICINA = 'oficina'
    LAVANDERIA = 'lavanderia'
    TERRAZA = 'terraza'
    GARAJE = 'garaje'
    CUARTO_SERVICIO = 'cuarto_servicio'


class Rol(StrEnum):
    """Enum `Rol` del contrato."""

    ADMINISTRADOR = 'administrador'
    MIEMBRO = 'miembro'


class IntervaloHora(BaseModel):
    """Esquema `IntervaloHora` del contrato."""

    inicio: datetime
    fin: datetime
