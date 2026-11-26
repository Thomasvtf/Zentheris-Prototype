"""Consultas de metas de consumo (metas_consumo).

RN-V-03, RN-XVI-04, RN-XI-03, DC-41. Sentencias constantes con parámetros con nombre; sin commit
(la transacción y el bloqueo del hogar son del servicio). Las demás funciones se escriben en la
sesión de cada endpoint (ver docs/MAPA-DE-INTEGRACION.md).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.data._convert import as_uuid
from app.data._integrity import UNIQUE_VIOLATION, violated_constraint

# Índice único parcial de la migración 0003 (DC-41: una meta activa por hogar).
ACTIVE_GOAL_INDEX = "uq_meta_activa_por_hogar"

# RN-V-03, RN-XVI-04, R-01: la meta activa del hogar. Guardar otra cierra la anterior, y el único
# parcial uq_meta_activa_por_hogar (hogar_id) where estado = 'activa' garantiza que hay a lo
# sumo una fila; la consulta usa ese mismo índice.
ACTIVE_GOAL_SQL = text(
    """
    select id,
           tipo,
           valor_kwh_mensual,
           fecha_inicio
      from metas_consumo
     where hogar_id = :hogar_id
       and estado = 'activa'
    """
)


@dataclass(frozen=True)
class ActiveGoalRow:
    """Meta activa del hogar: límite mensual en kWh (RN-V-03, RN-XI-03)."""

    id: UUID
    tipo: Literal["ahorro", "eficiencia", "presupuesto"]
    valor_kwh_mensual: float
    fecha_inicio: date


def get_active_goal(session: Session, hogar_id: UUID) -> ActiveGoalRow | None:
    """La meta con estado 'activa' de `hogar_id`, o None si no hay (RN-V-03, RN-XVI-04, R-01).

    `valor_kwh_mensual` (numeric) llega como float. Sin commit.
    """
    result = session.exec(ACTIVE_GOAL_SQL, params={"hogar_id": hogar_id})
    row = result.mappings().first()
    return None if row is None else _to_active_goal_row(row)


def _to_active_goal_row(row: Mapping[str, Any]) -> ActiveGoalRow:
    """Convierte la fila: id a UUID y NUMERIC (Decimal) a float."""
    goal_id = row["id"]
    return ActiveGoalRow(
        id=as_uuid(goal_id),
        tipo=row["tipo"],
        valor_kwh_mensual=float(row["valor_kwh_mensual"]),
        fecha_inicio=row["fecha_inicio"],
    )


# DC-32, RN-XIV-07 (cierre de mes), R-01: la meta que estaba vigente el día :day, aunque después se haya cerrado (por eso
# no filtra por estado). Rango [fecha_inicio, fecha_fin). Si hubiera varias, la de fecha_inicio más
# reciente y, a igual fecha, la última creada. Entra por ix_metas_hogar.
GOAL_ACTIVE_ON_SQL = text(
    """
    select id,
           tipo,
           valor_kwh_mensual,
           fecha_inicio
      from metas_consumo
     where hogar_id = :hogar_id
       and fecha_inicio <= :day
       and (fecha_fin is null or fecha_fin > :day)
     order by fecha_inicio desc, created_at desc, id desc
     limit 1
    """
)


def get_goal_active_on(session: Session, hogar_id: UUID, day: date) -> ActiveGoalRow | None:
    """La meta de `hogar_id` vigente el día `day`, o None (DC-32, RN-XIV-07 cierre de mes, RN-XI-03, R-01).

    Vigente: `fecha_inicio <= day` y (`fecha_fin` nula o `fecha_fin > day`), sin mirar el estado
    (la meta pudo cerrarse después). Para la referencia del cierre de mes. Sin commit.
    """
    result = session.exec(GOAL_ACTIVE_ON_SQL, params={"hogar_id": hogar_id, "day": day})
    row = result.mappings().first()
    return None if row is None else _to_active_goal_row(row)


# ------------------------------------------------------------------ guardar meta (RN-V-03, RN-XVI-04)

# RN-V-03, RN-XVI-04, R-01: la meta activa del hogar pasa a 'inactiva' con :fecha_fin (la
# fecha_inicio de la nueva, o NULL si la anterior empezó el mismo día: metas_rango_valido exige
# fecha_fin > fecha_inicio). A lo sumo una fila por uq_meta_activa_por_hogar.
DEACTIVATE_ACTIVE_GOAL_SQL = text(
    """
    update metas_consumo
       set estado = 'inactiva',
           fecha_fin = :fecha_fin,
           updated_at = now()
     where hogar_id = :hogar_id
       and estado = 'activa'
    """
)

# RN-V-03, RN-XVI-04, DC-41: meta nueva 'activa' y abierta (fecha_fin NULL). Si ya hay otra
# activa, uq_meta_activa_por_hogar la rechaza (23505).
INSERT_GOAL_SQL = text(
    """
    insert into metas_consumo
           (hogar_id, tipo, valor_kwh_mensual, estado, fecha_inicio, fecha_fin)
    values (:hogar_id, :tipo, :valor_kwh_mensual, 'activa', :fecha_inicio, null)
    returning id,
              tipo,
              valor_kwh_mensual,
              estado,
              fecha_inicio,
              fecha_fin
    """
)


@dataclass(frozen=True)
class GoalRow:
    """Fila completa de metas_consumo que ve el servicio al guardar (RN-V-03, RN-XVI-04)."""

    id: UUID
    tipo: Literal["ahorro", "eficiencia", "presupuesto"]
    valor_kwh_mensual: float
    estado: Literal["activa", "inactiva"]
    fecha_inicio: date
    fecha_fin: date | None  # None = abierta (o cerrada el mismo día en que empezó)


class ActiveGoalExistsError(Exception):
    """El hogar ya tiene una meta activa (23505 de uq_meta_activa_por_hogar, DC-41).

    Bajo `lock_household` no debería ocurrir; si ocurre, la transacción queda abortada.
    """


def deactivate_active_goal(session: Session, hogar_id: UUID, fecha_fin: date | None) -> int:
    """Pasa a 'inactiva' la meta activa de `hogar_id` con `fecha_fin` (RN-V-03, RN-XVI-04, R-01).

    `fecha_fin` es la `fecha_inicio` de la meta nueva, o None si la anterior empezó ese mismo día
    (metas_rango_valido). Devuelve las filas cambiadas (0 o 1). Un `datetime` da TypeError sin
    SQL. Sin commit.
    """
    if isinstance(fecha_fin, datetime):
        raise TypeError("`fecha_fin` debe ser una fecha (date), no un datetime.")
    result = session.exec(
        DEACTIVATE_ACTIVE_GOAL_SQL, params={"hogar_id": hogar_id, "fecha_fin": fecha_fin}
    )
    return result.rowcount


def insert_goal(
    session: Session,
    *,
    hogar_id: UUID,
    tipo: str,
    valor_kwh_mensual: float,
    fecha_inicio: date,
) -> GoalRow:
    """Crea la meta 'activa' de `hogar_id` desde `fecha_inicio`, sin fecha_fin (RN-V-03, RN-XVI-04).

    ActiveGoalExistsError si viola uq_meta_activa_por_hogar (DC-41); cualquier otra
    IntegrityError (por ejemplo, el check de `valor_kwh_mensual > 0`) sube tal cual. Un
    `datetime` en `fecha_inicio` da TypeError sin SQL. El numeric vuelve como float. Sin commit.
    """
    if isinstance(fecha_inicio, datetime):
        raise TypeError("`fecha_inicio` debe ser una fecha (date), no un datetime.")
    try:
        result = session.exec(
            INSERT_GOAL_SQL,
            params={
                "hogar_id": hogar_id,
                "tipo": tipo,
                "valor_kwh_mensual": valor_kwh_mensual,
                "fecha_inicio": fecha_inicio,
            },
        )
    except IntegrityError as exc:
        if violated_constraint(exc, {ACTIVE_GOAL_INDEX: UNIQUE_VIOLATION}) is not None:
            raise ActiveGoalExistsError("El hogar ya tiene una meta activa.") from None
        raise
    return _to_goal_row(result.mappings().one())


def _to_goal_row(row: Mapping[str, Any]) -> GoalRow:
    """Convierte la fila: id a UUID y NUMERIC (Decimal) a float."""
    return GoalRow(
        id=as_uuid(row["id"]),
        tipo=row["tipo"],
        valor_kwh_mensual=float(row["valor_kwh_mensual"]),
        estado=row["estado"],
        fecha_inicio=row["fecha_inicio"],
        fecha_fin=row["fecha_fin"],
    )
