"""Consultas de metas de consumo (metas_consumo).

RN-V-03, RN-XVI-04, RN-XI-03. Sentencias constantes con parámetros con nombre; sin commit. Las
demás funciones se escriben en la sesión de cada endpoint (ver docs/MAPA-DE-INTEGRACION.md).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

from app.data._convert import as_uuid

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
