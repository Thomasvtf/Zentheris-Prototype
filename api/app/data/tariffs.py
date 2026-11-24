"""Consultas de tarifas del hogar (tarifas_hogar).

RN-V-01, RN-V-02, RN-XI-08, RN-XIII-05, DC-39. Sentencias constantes con parámetros con nombre; sin commit.
Las demás funciones se escriben en la sesión de cada endpoint (ver docs/MAPA-DE-INTEGRACION.md).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

from app.data._convert import as_uuid

# RN-V-01, RN-XI-08, DC-39, R-01: la tarifa vigente del hogar en :today, con la vigencia
# [desde, hasta) de la restricción de exclusión tarifas_sin_solapamiento (a lo sumo una fila;
# vigente_hasta NULL = abierta). Usa ix_tarifas_hogar_desde (hogar_id, vigente_desde).
CURRENT_TARIFF_SQL = text(
    """
    select id,
           precio_kwh,
           cargo_fijo_mensual,
           vigente_desde,
           vigente_hasta
      from tarifas_hogar
     where hogar_id = :hogar_id
       and vigente_desde <= :today
       and (vigente_hasta is null or vigente_hasta > :today)
    """
)

# RN-V-01, RN-V-02, RN-XIII-05, DC-39, R-01: las tarifas de :hogar_id cuya vigencia
# [desde, hasta) toca alguna fecha de [:start, :end] (ambas inclusive), en orden de vigencia.
# tarifas_sin_solapamiento garantiza a lo sumo una tarifa por fecha. Usa ix_tarifas_hogar_desde.
TARIFFS_BETWEEN_SQL = text(
    """
    select id,
           precio_kwh,
           cargo_fijo_mensual,
           vigente_desde,
           vigente_hasta
      from tarifas_hogar
     where hogar_id = :hogar_id
       and vigente_desde <= :end
       and (vigente_hasta is null or vigente_hasta > :start)
     order by vigente_desde
    """
)


@dataclass(frozen=True)
class TariffRow:
    """Tarifa del hogar: precio por kWh y cargo fijo opcional (RN-V-01, RN-V-02)."""

    id: UUID
    precio_kwh: float
    cargo_fijo_mensual: float | None
    vigente_desde: date
    vigente_hasta: date | None  # None = vigencia abierta


def get_current_tariff(session: Session, hogar_id: UUID, today: date) -> TariffRow | None:
    """La tarifa de `hogar_id` vigente en `today`, o None si no hay (RN-V-01, RN-XI-08, DC-39).

    Vigente = `vigente_desde <= today < vigente_hasta` (o `vigente_hasta` nula). `today` es la
    fecha de Bogotá que calcula el servicio: un `datetime` da TypeError sin SQL (se compararía
    como instante y no como fecha). Los numeric llegan como float. Sin commit.
    """
    if isinstance(today, datetime):
        raise TypeError("`today` debe ser una fecha (date), no un datetime.")
    result = session.exec(CURRENT_TARIFF_SQL, params={"hogar_id": hogar_id, "today": today})
    row = result.mappings().first()
    return None if row is None else _to_tariff_row(row)


def list_tariffs_between(
    session: Session, hogar_id: UUID, start: date, end: date
) -> list[TariffRow]:
    """Tarifas de `hogar_id` vigentes en alguna fecha de [start, end], ambas inclusive.

    Para el costo del historial: cada fecha usa la tarifa vigente en esa fecha (RN-XIII-05,
    RN-V-01, RN-V-02). Vigencia [vigente_desde, vigente_hasta) como en la restricción de
    exclusión tarifas_sin_solapamiento (DC-39): sin solapes, a lo sumo una tarifa por fecha.
    Ordenadas por `vigente_desde`; lista vacía si no hay. Solo filas de `hogar_id` (R-01).
    Un `datetime` en `start` o `end` da TypeError y `start > end` da ValueError, ambos sin SQL.
    Los numeric llegan como float. Sin commit.
    """
    if isinstance(start, datetime) or isinstance(end, datetime):
        raise TypeError("`start` y `end` deben ser fechas (date), no datetime.")
    if start > end:
        raise ValueError("`start` no puede ser posterior a `end`.")
    result = session.exec(
        TARIFFS_BETWEEN_SQL, params={"hogar_id": hogar_id, "start": start, "end": end}
    )
    return [_to_tariff_row(row) for row in result.mappings().all()]


def _to_tariff_row(row: Mapping[str, Any]) -> TariffRow:
    """Convierte la fila: id a UUID y NUMERIC (Decimal) a float; cargo fijo NULL a None."""
    tariff_id = row["id"]
    fixed_charge: Decimal | None = row["cargo_fijo_mensual"]
    return TariffRow(
        id=as_uuid(tariff_id),
        precio_kwh=float(row["precio_kwh"]),
        cargo_fijo_mensual=None if fixed_charge is None else float(fixed_charge),
        vigente_desde=row["vigente_desde"],
        vigente_hasta=row["vigente_hasta"],
    )
