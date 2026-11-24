"""Lecturas de consumo: inserción por lotes, huecos por sensor y series horarias por zona.

RN-IV-01, RN-IV-05, RN-X-03, RN-XI-01, RN-XI-05, DC-33, DC-34. Sentencias constantes con
parámetros con nombre; sin commit.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

from app.data._convert import as_uuid

# DC-33: todas las filas en UNA sentencia (nunca fila por fila). RN-IV-05: la restricción única
# (sensor_id, fecha_hora) descarta las horas que ya existían.
INSERT_READINGS_BATCH_SQL = text(
    """
    insert into lecturas (sensor_id, fecha_hora, consumo_kwh, calidad)
    select l.sensor_id, l.fecha_hora, l.consumo_kwh, l.calidad
      from unnest(
             cast(:sensor_ids as uuid[]),
             cast(:fechas_hora as timestamptz[]),
             cast(:consumos_kwh as numeric[]),
             cast(:calidades as text[])
           ) as l (sensor_id, fecha_hora, consumo_kwh, calidad)
    on conflict (sensor_id, fecha_hora) do nothing
    """
)


def insert_readings_batch(session: Session, lecturas: Sequence[dict[str, Any]]) -> int:
    """Inserta las lecturas en un solo lote; devuelve cuántas guardó (RN-X-03, RN-IV-05, DC-33).

    Cada lectura trae `sensor_id`, `fecha_hora` (con zona horaria), `consumo_kwh` y `calidad`.
    Las que ya existían para ese sensor y hora se ignoran y no cuentan (B-01). Lista vacía → 0
    sin SQL. Los sensores deben ser del hogar que el servicio ya verificó o acaba de crear
    (R-01). ValueError si una `fecha_hora` no tiene zona horaria. Sin commit.
    """
    if not lecturas:
        return 0
    fechas_hora: list[datetime] = [lectura["fecha_hora"] for lectura in lecturas]
    if any(fecha_hora.utcoffset() is None for fecha_hora in fechas_hora):
        raise ValueError("Todas las lecturas deben llevar fecha_hora con zona horaria.")
    result = session.exec(
        INSERT_READINGS_BATCH_SQL,
        params={
            "sensor_ids": [str(lectura["sensor_id"]) for lectura in lecturas],
            "fechas_hora": fechas_hora,
            "consumos_kwh": [lectura["consumo_kwh"] for lectura in lecturas],
            "calidades": [lectura["calidad"] for lectura in lecturas],
        },
    )
    return result.rowcount


# RN-IV-05, DC-34: candado de transacción por hogar para que la tarea programada y una consulta
# no recuperen el mismo hogar a la vez (las horas generadas son las que se guardan; base de las
# alertas de la fase 8, DC-35). pg_advisory_xact_lock se suelta solo en commit o rollback, por
# eso funciona con el Transaction Pooler (6543). No bloquea la fila de hogares (no es FOR UPDATE).
LOCK_HOUSEHOLD_RECOVERY_SQL = text(
    """
    select pg_advisory_xact_lock(hashtextextended(cast(:hogar_id as text), 0))
    """
)


def lock_household_recovery(session: Session, hogar_id: UUID) -> None:
    """Espera y toma el candado de recuperación del hogar hasta el fin de la transacción.

    RN-IV-05, DC-34. El servicio lo toma antes de leer los huecos (get_sensor_gaps). Sin commit.
    """
    session.exec(LOCK_HOUSEHOLD_RECOVERY_SQL, params={"hogar_id": hogar_id})


# RN-IV-05, DC-34, R-01: por cada sensor 'activo' de una zona 'activa' del hogar, su primera
# lectura (frontera, first_hour) y las horas sin lectura desde ella hasta :until inclusive.
#
# Costo: esta consulta corre antes de cada consulta de consumo y el historial crece ~24 filas
# por sensor y día, así que no se recorre siempre desde la primera lectura. El lateral `st` lee
# min, max y count(*) del sensor por el único lecturas_una_por_sensor_y_hora (sensor_id,
# fecha_hora). Como ese único impide horas repetidas y las horas están alineadas al inicio de
# hora, count = (max - min) en horas + 1 significa que no hay huecos internos: la serie empieza
# en max + 1 hora (solo las horas nuevas). Si no coincide (huecos internos, A13), la serie
# empieza en min, como antes. El resultado observable es el mismo en ambos casos.
#
# Sin lecturas: min, max y la comparación son NULL, la serie empieza en NULL y no produce filas.
# Si la serie empieza después de :until, tampoco. En ambos casos array_agg devuelve NULL (se
# convierte a lista vacía).
#
# Decidido el 23/11/2026 (Nicolás): los sensores 'pausado' y las zonas 'inactiva' NO reciben
# lecturas nuevas; por eso solo se buscan huecos de sensores 'activo' en zonas 'activa'. La misma
# regla en Python es app.domain.zone_rules.counts_for_total.
# TODO(pendiente: ¿al reactivar un sensor o una zona se rellena el periodo en que estuvo
# pausado? En el MVP no hay operación que cambie esos estados)
SENSOR_GAPS_SQL = text(
    """
    select s.id as sensor_id,
           z.tipo as zona_tipo,
           st.first_hour,
           g.missing_hours
      from sensores_zona s
      join zonas z on z.id = s.zona_id
     cross join lateral (
             select min(l.fecha_hora) as first_hour,
                    max(l.fecha_hora) as last_hour,
                    count(*) as stored_hours
               from lecturas l
              where l.sensor_id = s.id
           ) as st
     cross join lateral (
             select array_agg(h.missing_hour order by h.missing_hour) as missing_hours
               from generate_series(
                      case
                        when st.stored_hours
                             = extract(epoch from st.last_hour - st.first_hour) / 3600 + 1
                          then st.last_hour + interval '1 hour'
                        else st.first_hour
                      end,
                      cast(:until as timestamptz),
                      interval '1 hour'
                    ) as h (missing_hour)
              where not exists (
                      select 1
                        from lecturas e
                       where e.sensor_id = s.id
                         and e.fecha_hora = h.missing_hour
                    )
           ) as g
     where z.hogar_id = :hogar_id
       and z.estado = 'activa'
       and s.estado = 'activo'
     order by z.tipo, s.id
    """
)


@dataclass(frozen=True)
class SensorGapRow:
    """Huecos de un sensor activo del hogar (RN-IV-05)."""

    sensor_id: UUID
    zona_tipo: str
    first_hour: datetime | None  # min(fecha_hora) del sensor; None si no tiene lecturas
    missing_hours: list[datetime]  # horas sin lectura en [first_hour, until], ascendente


def get_sensor_gaps(session: Session, hogar_id: UUID, until: datetime) -> list[SensorGapRow]:
    """Primera lectura y horas faltantes de cada sensor activo del hogar (RN-IV-05, DC-34, R-01).

    Solo sensores con estado 'activo' de zonas con estado 'activa' de `hogar_id`. Las horas van
    de la primera lectura del sensor hasta `until` inclusive, en pasos de 1 hora, y son las que
    no tienen lectura (anti-join con generate_series sobre el único (sensor_id, fecha_hora); si
    no hay huecos internos, solo desde la última lectura). El SQL las entrega ascendentes y sin
    pasar de `until`. Orden por zona_tipo. Sensor sin lecturas → first_hour None y lista vacía;
    first_hour posterior a `until` → lista vacía. ValueError si `until` no tiene zona horaria
    (sin SQL). Sin commit.
    """
    if until.utcoffset() is None:
        raise ValueError("`until` debe llevar zona horaria.")
    result = session.exec(SENSOR_GAPS_SQL, params={"hogar_id": hogar_id, "until": until})
    return [_to_sensor_gap_row(row) for row in result.mappings().all()]


def _to_sensor_gap_row(row: Mapping[str, Any]) -> SensorGapRow:
    """Convierte la fila: id a UUID y el array NULL (sin horas faltantes) a lista vacía."""
    sensor_id = row["sensor_id"]
    missing_hours: Sequence[datetime] | None = row["missing_hours"]
    return SensorGapRow(
        sensor_id=as_uuid(sensor_id),
        zona_tipo=row["zona_tipo"],
        first_hour=row["first_hour"],
        missing_hours=list(missing_hours or ()),
    )


# RN-XI-01, RN-XI-05, DC-28, R-01: kWh por zona y hora entre :start y :end (ambos inclusive), solo
# de zonas de :hogar_id. Una zona pedida que no es del hogar no produce filas.
#
# Índice: el único lecturas_una_por_sensor_y_hora (sensor_id, fecha_hora). Las zonas salen por
# ix_zonas_hogar, cada una da su sensor por el único sensores_zona.zona_id y, por sensor, se lee
# un rango de fecha_hora en ese índice (sin recorrer el historial). Costo por consulta: la ventana
# del promedio (30 días anteriores + el día de la hora evaluada, ~31 días × 24 h = ~744 filas)
# por hasta 9 zonas → ~6.700 filas como máximo.
HOURLY_READINGS_SQL = text(
    """
    select z.id as zona_id,
           l.fecha_hora,
           l.consumo_kwh
      from lecturas l
      join sensores_zona s on s.id = l.sensor_id
      join zonas z on z.id = s.zona_id
     where z.hogar_id = :hogar_id
       and z.id = any(cast(:zona_ids as uuid[]))
       and l.fecha_hora between :start and :end
     order by z.id, l.fecha_hora
    """
)


@dataclass(frozen=True)
class HourlyReadingRow:
    """kWh de una zona en la hora [fecha_hora, fecha_hora + 1 h) (RN-IV-03, RN-XI-01)."""

    zona_id: UUID
    fecha_hora: datetime
    consumo_kwh: float


def get_hourly_readings(
    session: Session,
    hogar_id: UUID,
    zona_ids: Sequence[UUID],
    start: datetime,
    end: datetime,
) -> list[HourlyReadingRow]:
    """Lecturas horarias de las zonas pedidas de `hogar_id` en [start, end] (RN-XI-01, RN-XI-05).

    Filtra siempre por `hogar_id` (R-01): una zona de otro hogar no devuelve filas. Orden por zona
    y hora. `consumo_kwh` (numeric) llega como float; las horas, como las entrega el driver (con
    zona horaria). ValueError si `start` o `end` no tienen zona horaria o si `start > end` (sin
    SQL). `zona_ids` vacío → lista vacía sin SQL. Sin commit.
    """
    if start.utcoffset() is None or end.utcoffset() is None:
        raise ValueError("`start` y `end` deben llevar zona horaria.")
    if start > end:
        raise ValueError("`start` no puede ser posterior a `end`.")
    if not zona_ids:
        return []
    result = session.exec(
        HOURLY_READINGS_SQL,
        params={
            "hogar_id": hogar_id,
            "zona_ids": [str(zona_id) for zona_id in zona_ids],
            "start": start,
            "end": end,
        },
    )
    return [_to_hourly_reading_row(row) for row in result.mappings().all()]


def _to_hourly_reading_row(row: Mapping[str, Any]) -> HourlyReadingRow:
    """Convierte la fila: id a UUID y NUMERIC (Decimal) a float."""
    zona_id = row["zona_id"]
    return HourlyReadingRow(
        zona_id=as_uuid(zona_id),
        fecha_hora=row["fecha_hora"],
        consumo_kwh=float(row["consumo_kwh"]),
    )
