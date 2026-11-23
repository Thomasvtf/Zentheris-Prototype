"""Lecturas de consumo: inserción por lotes del backfill y de las horas recuperadas.

RN-IV-01, RN-IV-05, RN-X-03, DC-33. Sentencia constante con parámetros con nombre; sin commit.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlmodel import Session

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
