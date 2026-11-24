"""Consultas de tarifas del hogar (tarifas_hogar).

RN-V-01, RN-V-02, RN-XI-08, DC-39. Sentencias constantes con parámetros con nombre; sin commit.
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
