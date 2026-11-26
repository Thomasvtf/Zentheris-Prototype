"""Consultas de tarifas del hogar (tarifas_hogar).

RN-V-01, RN-V-02, RN-XI-08, RN-XIII-05, RN-XVI-05, DC-39, DC-41. Sentencias constantes con
parámetros con nombre; sin commit (la transacción y el bloqueo del hogar son del servicio).
Las demás funciones se escriben en la sesión de cada endpoint (ver docs/MAPA-DE-INTEGRACION.md).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.data._convert import as_uuid
from app.data._integrity import (
    CHECK_VIOLATION,
    EXCLUSION_VIOLATION,
    UNIQUE_VIOLATION,
    violated_constraint,
)

# Restricciones que rechazan una vigencia nueva (nombre → SQLSTATE): la exclusión de la migración
# 0002 (DC-39), el único parcial de la migración 0003 (DC-41: una abierta por hogar) y el check
# de rango de la 0002 (vigente_hasta > vigente_desde).
OVERLAP_CONSTRAINT = "tarifas_sin_solapamiento"
OPEN_TARIFF_INDEX = "uq_tarifa_abierta_por_hogar"
RANGE_CONSTRAINT = "tarifas_rango_valido"
VALIDITY_CONSTRAINTS = {
    OVERLAP_CONSTRAINT: EXCLUSION_VIOLATION,
    OPEN_TARIFF_INDEX: UNIQUE_VIOLATION,
    RANGE_CONSTRAINT: CHECK_VIOLATION,
}

# RN-V-01, RN-XI-08, DC-39, R-01: la tarifa vigente del hogar en :today, con la vigencia
# [desde, hasta) de la restricción de exclusión tarifas_sin_solapamiento (a lo sumo una fila;
# vigente_hasta NULL = abierta). Usa ix_tarifas_hogar_desde (hogar_id, vigente_desde).
CURRENT_TARIFF_SQL = text(
    """
    select id,
           precio_kwh,
           cargo_fijo_mensual,
           vigente_desde,
           vigente_hasta,
           operador
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
           vigente_hasta,
           operador
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
    operador: str | None = None  # RN-V-01: opcional; al final con default para no romper llamadas


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
        # `.get`: las filas fabricadas de pruebas anteriores a la fase 10 no traen la columna;
        # las sentencias de este módulo siempre la seleccionan.
        operador=row.get("operador"),
    )


# ------------------------------------------------------------ guardar tarifa (RN-XVI-05, DC-39)

# RN-XVI-05, DC-39, DC-41, R-01: la tarifa abierta (vigente_hasta NULL) del hogar; el único
# parcial uq_tarifa_abierta_por_hogar garantiza a lo sumo una fila y la consulta lo usa.
OPEN_TARIFF_SQL = text(
    """
    select id,
           precio_kwh,
           cargo_fijo_mensual,
           vigente_desde,
           vigente_hasta,
           operador
      from tarifas_hogar
     where hogar_id = :hogar_id
       and vigente_hasta is null
    """
)

# RN-XVI-05, DC-39, R-01: cierra una vigencia en :vigente_hasta (exclusivo, [desde, hasta)). El
# servicio pasa el id de la abierta que leyó bajo lock_household; el filtro por hogar impide tocar
# una tarifa de otro hogar aunque el id no corresponda.
CLOSE_TARIFF_SQL = text(
    """
    update tarifas_hogar
       set vigente_hasta = :vigente_hasta,
           updated_at = now()
     where id = :tarifa_id
       and hogar_id = :hogar_id
    """
)

# RN-V-01, RN-V-02, RN-XVI-05, DC-39, DC-41: tarifa nueva y abierta desde :vigente_desde. Si se
# solapa con otra del hogar la rechaza tarifas_sin_solapamiento (23P01); si ya hay otra abierta,
# uq_tarifa_abierta_por_hogar (23505).
INSERT_TARIFF_SQL = text(
    """
    insert into tarifas_hogar
           (hogar_id, operador, precio_kwh, cargo_fijo_mensual, vigente_desde, vigente_hasta)
    values (:hogar_id, :operador, :precio_kwh, :cargo_fijo_mensual, :vigente_desde, null)
    returning id,
              precio_kwh,
              cargo_fijo_mensual,
              vigente_desde,
              vigente_hasta,
              operador
    """
)


class TariffOverlapError(Exception):
    """La vigencia choca con otra del hogar (DC-39, DC-41).

    Viola tarifas_sin_solapamiento, uq_tarifa_abierta_por_hogar o tarifas_rango_valido. El
    servicio la traduce a 422 VIGENCIA_NO_POSTERIOR. La transacción queda abortada.
    """

    def __init__(self, constraint: str) -> None:
        super().__init__("La vigencia de la tarifa se solapa con otra del hogar.")
        self.constraint = constraint


def get_open_tariff(session: Session, hogar_id: UUID) -> TariffRow | None:
    """La tarifa abierta (`vigente_hasta` nula) de `hogar_id`, o None (RN-XVI-05, DC-39, R-01).

    Es la que se compara y se cierra al guardar una nueva (D4). Sin commit.
    """
    result = session.exec(OPEN_TARIFF_SQL, params={"hogar_id": hogar_id})
    row = result.mappings().first()
    return None if row is None else _to_tariff_row(row)


def close_tariff(session: Session, hogar_id: UUID, tarifa_id: UUID, vigente_hasta: date) -> None:
    """Fija `vigente_hasta` (exclusivo) de la tarifa `tarifa_id` de `hogar_id` (RN-XVI-05, DC-39).

    Solo toca la fila si pertenece a `hogar_id` (R-01); si no, no cambia nada. TariffOverlapError
    si `vigente_hasta <= vigente_desde` (tarifas_rango_valido); cualquier otra IntegrityError sube
    tal cual. Un `datetime` da TypeError sin SQL. Sin commit.
    """
    if isinstance(vigente_hasta, datetime):
        raise TypeError("`vigente_hasta` debe ser una fecha (date), no un datetime.")
    try:
        session.exec(
            CLOSE_TARIFF_SQL,
            params={"hogar_id": hogar_id, "tarifa_id": tarifa_id, "vigente_hasta": vigente_hasta},
        )
    except IntegrityError as exc:
        _raise_if_validity_violation(exc)
        raise


def insert_tariff(
    session: Session,
    *,
    hogar_id: UUID,
    operador: str | None,
    precio_kwh: float,
    cargo_fijo_mensual: float | None,
    vigente_desde: date,
) -> TariffRow:
    """Crea la tarifa abierta de `hogar_id` desde `vigente_desde` (RN-V-01, RN-V-02, RN-XVI-05).

    `vigente_hasta` queda nula. TariffOverlapError si viola tarifas_sin_solapamiento (DC-39),
    uq_tarifa_abierta_por_hogar (DC-41) o tarifas_rango_valido; cualquier otra IntegrityError sube
    tal cual. Un `datetime` en `vigente_desde` da TypeError sin SQL. Los numeric vuelven como
    float. Sin commit.
    """
    if isinstance(vigente_desde, datetime):
        raise TypeError("`vigente_desde` debe ser una fecha (date), no un datetime.")
    try:
        result = session.exec(
            INSERT_TARIFF_SQL,
            params={
                "hogar_id": hogar_id,
                "operador": operador,
                "precio_kwh": precio_kwh,
                "cargo_fijo_mensual": cargo_fijo_mensual,
                "vigente_desde": vigente_desde,
            },
        )
    except IntegrityError as exc:
        _raise_if_validity_violation(exc)
        raise
    return _to_tariff_row(result.mappings().one())


def _raise_if_validity_violation(exc: IntegrityError) -> None:
    """Lanza TariffOverlapError si `exc` viola una de VALIDITY_CONSTRAINTS; si no, no hace nada."""
    constraint = violated_constraint(exc, VALIDITY_CONSTRAINTS)
    if constraint is not None:
        raise TariffOverlapError(constraint) from None
