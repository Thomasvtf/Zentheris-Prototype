"""Consultas de perfiles_simulacion (tabla 12): las 5 personalidades del simulador.

RN-X-04, RN-IV-01, DC-37, DC-45. Es un catálogo interno sin datos de ningún hogar: no se filtra
por `hogar_id` y nunca se expone en la API. Solo lectura; la semilla es de las migraciones.
`get_household_profile` (RN-IV-05) sí parte de un hogar: lee el perfil que tiene asignado.
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

# Columnas que leen las dos consultas, en este orden: una sola lista para que no diverjan.
PROFILE_COLUMNS = (
    "id",
    "nombre",
    "activo",
    "base_cocina_kwh_dia",
    "base_sala_kwh_dia",
    "base_dormitorio_kwh_dia",
    "base_bano_kwh_dia",
    "base_lavanderia_kwh_dia",
    "base_oficina_kwh_dia",
    "base_terraza_kwh_dia",
    "base_garaje_kwh_dia",
    "base_cuarto_servicio_kwh_dia",
    "curva_horaria",
    "humor_min",
    "humor_max",
    "ruido_config",
    "picos_config",
    "factor_fin_semana",
)

# RN-X-04: perfiles por nombre, también los inactivos (el respaldo lo decide el dominio).
# Constante de módulo: solo se concatenan nombres de columna fijos, nunca valores.
PROFILES_BY_NAME_SQL = text(
    "select "
    + ", ".join(PROFILE_COLUMNS)
    + " from perfiles_simulacion"
    + " where nombre = any(cast(:nombres as text[]))"
)

# RN-IV-05, DC-37: el perfil asignado al hogar, aunque hoy esté inactivo (la serie no cambia).
# Mismas columnas que PROFILES_BY_NAME_SQL, con el alias de la tabla.
HOUSEHOLD_PROFILE_SQL = text(
    "select "
    + ", ".join("p." + column for column in PROFILE_COLUMNS)
    + " from hogares h"
    + " join perfiles_simulacion p on p.id = h.perfil_simulacion_id"
    + " where h.id = :hogar_id"
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


def get_household_profile(session: Session, hogar_id: UUID) -> SimulationProfileRow | None:
    """Perfil asignado al hogar, aunque hoy esté inactivo (RN-IV-05, DC-37).

    La recuperación de horas debe seguir la misma serie con la que se hizo el backfill. None si
    el hogar no existe. Sin commit.
    """
    result = session.exec(HOUSEHOLD_PROFILE_SQL, params={"hogar_id": hogar_id})
    row = result.mappings().first()
    return None if row is None else _to_simulation_profile_row(row)


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
