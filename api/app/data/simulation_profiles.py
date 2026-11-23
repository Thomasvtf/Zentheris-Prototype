"""Consultas de perfiles_simulacion (tabla 12): las 5 personalidades del simulador.

RN-X-04, RN-IV-01, DC-37, DC-45. Es un catálogo interno sin datos de ningún hogar: no se filtra
por `hogar_id` y nunca se expone en la API. Solo lectura; la semilla es de las migraciones.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session

# Columnas NUMERIC que el simulador usa como float.
NUMERIC_FIELDS = (
    "base_cocina_kwh_dia",
    "base_sala_kwh_dia",
    "base_dormitorio_kwh_dia",
    "base_bano_kwh_dia",
    "base_lavanderia_kwh_dia",
    "base_oficina_kwh_dia",
    "base_terraza_kwh_dia",
    "base_garaje_kwh_dia",
    "base_cuarto_servicio_kwh_dia",
    "humor_min",
    "humor_max",
    "factor_fin_semana",
)

# Columnas JSONB.
JSON_FIELDS = ("curva_horaria", "ruido_config", "picos_config")

# RN-X-04: perfiles por nombre, también los inactivos (el respaldo lo decide el dominio).
PROFILES_BY_NAME_SQL = text(
    """
    select id,
           nombre,
           activo,
           base_cocina_kwh_dia,
           base_sala_kwh_dia,
           base_dormitorio_kwh_dia,
           base_bano_kwh_dia,
           base_lavanderia_kwh_dia,
           base_oficina_kwh_dia,
           base_terraza_kwh_dia,
           base_garaje_kwh_dia,
           base_cuarto_servicio_kwh_dia,
           curva_horaria,
           humor_min,
           humor_max,
           ruido_config,
           picos_config,
           factor_fin_semana
      from perfiles_simulacion
     where nombre = any(cast(:nombres as text[]))
    """
)


@dataclass(frozen=True)
class SimulationProfileRow:
    """Fila de perfiles_simulacion; `params` trae solo los campos que exige el simulador."""

    id: UUID
    nombre: str
    activo: bool
    params: dict[str, Any]


def get_profiles(session: Session, names: Sequence[str]) -> dict[str, SimulationProfileRow]:
    """Perfiles con esos nombres, por nombre; incluye los inactivos (RN-X-04, DC-37).

    Un nombre que no existe no aparece en el resultado. Sin nombres no consulta la base.
    """
    if not names:
        return {}
    result = session.exec(PROFILES_BY_NAME_SQL, params={"nombres": list(names)})
    profiles = [_to_simulation_profile_row(row) for row in result.mappings().all()]
    return {profile.nombre: profile for profile in profiles}


def _to_simulation_profile_row(row: Mapping[str, Any]) -> SimulationProfileRow:
    """Convierte la fila: NUMERIC (Decimal) a float y JSONB (dict o texto) a dict."""
    params: dict[str, Any] = {"nombre": row["nombre"], "activo": bool(row["activo"])}
    for field in NUMERIC_FIELDS:
        params[field] = float(row[field])
    for field in JSON_FIELDS:
        value = row[field]
        params[field] = json.loads(value) if isinstance(value, str) else value
    profile_id = row["id"]
    return SimulationProfileRow(
        id=profile_id if isinstance(profile_id, UUID) else UUID(str(profile_id)),
        nombre=params["nombre"],
        activo=params["activo"],
        params=params,
    )
