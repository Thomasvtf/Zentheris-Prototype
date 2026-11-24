"""Esquemas del contrato 0.2.5 · Etiqueta «Consumo»: actual, zonas, historial y fuentes de datos.

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api-v0.2.5.yaml y revisado a mano."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import EstadoConsumo, IntervaloHora, MensajeCodigo, ReferenciaTipo, TipoZona
from app.schemas.households import Zona


class ConsumoActualHogarActual(BaseModel):
    """Objeto `actual` de `ConsumoActualHogar` (en línea en el contrato)."""

    potencia_kw: float | None = Field(ge=0)
    costo_cop: float | None = Field(ge=0)
    variacion_hora_anterior_pct: float | None
    referencia_tipo: ReferenciaTipo
    referencia_kw: float | None
    estado: EstadoConsumo
    mensaje_codigo: MensajeCodigo | None


class ConsumoActualHogarAcumuladoHoy(BaseModel):
    """Objeto `acumulado_hoy` de `ConsumoActualHogar` (en línea en el contrato)."""

    energia_kwh: float = Field(ge=0)
    costo_cop: float | None = Field(ge=0)
    referencia_tipo: ReferenciaTipo
    referencia_kwh: float | None
    muestra_limite: bool
    estado: EstadoConsumo
    mensaje_codigo: MensajeCodigo | None


class ConsumoActualHogar(BaseModel):
    """Esquema `ConsumoActualHogar` del contrato."""

    hora: IntervaloHora
    tarifa_vigente: bool
    actual: ConsumoActualHogarActual
    acumulado_hoy: ConsumoActualHogarAcumuladoHoy


class ConsumoZonaItem(BaseModel):
    """Esquema `ConsumoZonaItem` del contrato."""

    zona_id: UUID
    tipo: TipoZona
    nombre: str
    potencia_kw: float | None = Field(ge=0)
    costo_cop: float | None = Field(ge=0)
    participacion_pct: float | None = Field(ge=0, le=100)
    estado_participacion: EstadoConsumo


class ConsumoZonas(BaseModel):
    """Esquema `ConsumoZonas` del contrato."""

    hora: IntervaloHora
    tarifa_vigente: bool
    total_kw: float | None = Field(ge=0)
    zonas: list[ConsumoZonaItem]


class ConsumoZonaDetalleEstadoConsumo(BaseModel):
    """Objeto `estado_consumo` de `ConsumoZonaDetalle` (en línea en el contrato)."""

    promedio_misma_hora_kw: float | None = Field(ge=0)
    variacion_pct: float | None
    estado: EstadoConsumo
    mensaje_codigo: MensajeCodigo | None


class ConsumoZonaDetalleParticipacion(BaseModel):
    """Objeto `participacion` de `ConsumoZonaDetalle` (en línea en el contrato)."""

    participacion_pct: float | None = Field(ge=0, le=100)
    total_hogar_kw: float | None = Field(ge=0)
    estado: EstadoConsumo


class ConsumoZonaDetalle(BaseModel):
    """Esquema `ConsumoZonaDetalle` del contrato."""

    zona: Zona
    hora: IntervaloHora
    tarifa_vigente: bool
    potencia_kw: float | None = Field(ge=0)
    costo_cop: float | None = Field(ge=0)
    estado_consumo: ConsumoZonaDetalleEstadoConsumo
    participacion: ConsumoZonaDetalleParticipacion


class PuntoSerie(BaseModel):
    """Esquema `PuntoSerie` del contrato."""

    inicio: datetime
    fin: datetime
    energia_kwh: float | None = Field(ge=0)
    costo_cop: float | None = Field(ge=0)
    es_pico_maximo: bool


class HistorialParticipacionZona(BaseModel):
    """Objeto `participacion_zona` de `Historial` (en línea en el contrato)."""

    zona_id: UUID
    nombre: str
    energia_kwh: float = Field(ge=0)
    participacion_pct: float = Field(ge=0, le=100)


class HistorialUltimoPico(BaseModel):
    """Objeto `ultimo_pico` de `Historial` (en línea en el contrato)."""

    inicio: datetime
    fin: datetime
    energia_kwh: float = Field(ge=0)
    promedio_historico_kwh: float = Field(ge=0)
    exceso_pct: float
    estado: EstadoConsumo


class HistorialComparacion(BaseModel):
    """Objeto `comparacion` de `Historial` (en línea en el contrato)."""

    actual_kwh: float = Field(ge=0)
    anterior_kwh: float | None = Field(ge=0)
    variacion_pct: float | None
    estado: EstadoConsumo
    mensaje_codigo: MensajeCodigo | None


class HistorialCosto(BaseModel):
    """Objeto `costo` de `Historial` (en línea en el contrato)."""

    costo_cop: float | None = Field(ge=0)
    proyeccion_cierre_cop: float | None = Field(ge=0)
    incluye_cargo_fijo: bool
    estado: EstadoConsumo
    mensaje_codigo: MensajeCodigo | None


class Historial(BaseModel):
    """Esquema `Historial` del contrato."""

    periodo: Literal['dia', 'semana', 'mes']
    zona_id: UUID | None
    inicio: datetime
    fin: datetime
    granularidad: Literal['hora', 'dia']
    tarifa_vigente: bool
    total_kwh: float = Field(ge=0)
    serie: list[PuntoSerie]
    participacion_zonas: list[HistorialParticipacionZona] | None
    ultimo_pico: HistorialUltimoPico | None
    comparacion: HistorialComparacion
    costo: HistorialCosto


class FuentesDatosFuentePrincipal(BaseModel):
    """Objeto `fuente_principal` de `FuentesDatos` (en línea en el contrato)."""

    id: UUID
    nombre: str
    estado: Literal['activa', 'inactiva']
    potencia_kw: float | None = Field(ge=0)


class FuentesDatosSensor(BaseModel):
    """Objeto `sensor` de `FuentesDatos` (en línea en el contrato)."""

    id: UUID
    nombre: str
    zona_id: UUID
    zona_nombre: str
    potencia_kw: float | None = Field(ge=0)
    estado: Literal['activo', 'pausado', 'sin_datos']


class FuentesDatos(BaseModel):
    """Esquema `FuentesDatos` del contrato."""

    valores_ocultos: bool
    hora: IntervaloHora
    fuente_principal: FuentesDatosFuentePrincipal
    sensores: list[FuentesDatosSensor]
