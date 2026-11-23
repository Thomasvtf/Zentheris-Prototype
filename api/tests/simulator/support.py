"""Apoyo de las pruebas del simulador.

Porta `pruebas/apoyo.py` y la parte de pruebas de `zentheris_sim/almacen.py` (hogares de prueba
y almacén en memoria) del Avance 03. El almacén solo prueba la lógica de recuperación e
idempotencia: no demuestra compatibilidad con PostgreSQL.
"""

from __future__ import annotations

import copy
import csv
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from app.domain.simulator.constants import BASE_COLUMNS, TIMEZONE
from app.domain.simulator.engine import hour_index, reading_row, simulate_zone
from app.domain.simulator.recovery import generate_missing_readings
from app.domain.simulator.validation import load_strict_json
from app.domain.zone_rules import (
    PERSONALITIES,
    assign_personality,
    resolve_active_personality,
)
from tests.zones.selections import applicable_zones

DATA_DIR = Path(__file__).resolve().parent / "data"
REPO_ROOT = Path(__file__).resolve().parents[3]
PROFILES_DIR = REPO_ROOT / "docs" / "datos" / "perfiles"

# Espacio de la referencia (solo pruebas): con él, los hogares tienen los mismos ids que allí.
TEST_NAMESPACE = UUID("6f1d3c3e-0000-4000-8000-7a656e746865")

Profile = dict[str, Any]


# ------------------------------------------------------------------ perfiles
def read_profile(path: Path) -> Profile:
    return load_strict_json(path.read_text(encoding="utf-8"))


def personality_file_name(name: str) -> str:
    """«Consumo compacto» -> «consumo_compacto.json»."""
    return f"{name.lower().replace(' ', '_')}.json"


def sample_profiles() -> dict[str, Profile]:
    """Los cinco conjuntos de PRUEBA de la referencia (no calibrados)."""
    return {n: read_profile(DATA_DIR / f"prueba_{n.split()[1]}.json") for n in PERSONALITIES}


def sample_profile(name: str = "Consumo familiar") -> Profile:
    return copy.deepcopy(sample_profiles()[name])


@lru_cache(maxsize=1)
def _final_profiles() -> dict[str, Profile]:
    return {n: read_profile(PROFILES_DIR / personality_file_name(n)) for n in PERSONALITIES}


def final_profiles() -> dict[str, Profile]:
    """Los cinco conjuntos oficiales (acta 04) de `docs/datos/perfiles/`."""
    return copy.deepcopy(_final_profiles())


@lru_cache(maxsize=1)
def frozen_references() -> dict[str, dict[str, Any]]:
    """Hogar de referencia y objetivos congelados por personalidad (extracto del zip)."""
    text = (DATA_DIR / "congelamiento_referencias.json").read_text(encoding="utf-8")
    return json.loads(text)["referencias"]


def read_csv(name: str) -> list[dict[str, str]]:
    """Filas de un CSV de resultados de la referencia copiado en `data/`."""
    with (DATA_DIR / name).open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def zones_without_parameters(profiles: Mapping[str, Profile]) -> list[str]:
    """Zonas aplicables a una personalidad cuya base es 0 (no tendrían consumo regular)."""
    return [
        f"{name}:{zone}"
        for name, zones in applicable_zones().items()
        for zone in zones
        if not profiles[name][BASE_COLUMNS[zone]] > 0
    ]


# ------------------------------------------------------------------ tiempo y números
def bogota(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=TIMEZONE)


def idx(year: int, month: int, day: int, hour: int = 0) -> int:
    return date(year, month, day).toordinal() * 24 + hour


def almost_equal(a: float, b: float, places: int) -> bool:
    """El mismo criterio de `unittest.assertAlmostEqual` (lo usa la referencia)."""
    return a == b or round(abs(a - b), places) == 0


# ------------------------------------------------------------------ credenciales
_CREDENTIAL_PATTERN = re.compile(
    r"(eyJ[A-Za-z0-9_-]{10,}\.|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|service_role)"
)


def contains_credential(text: str) -> bool:
    return bool(_CREDENTIAL_PATTERN.search(text))


# ------------------------------------------------------------------ hogares y almacén
def stable_id(*parts: str) -> UUID:
    return uuid5(TEST_NAMESPACE, "|".join(parts))


@dataclass(frozen=True)
class SampleHousehold:
    id: UUID
    zones: frozenset[str]
    assigned_personality: str
    personality: str
    sensors: dict[str, UUID]


def create_household(
    label: str, housing: str, zones: Iterable[str], active: Mapping[str, bool] | None = None
) -> SampleHousehold:
    """Equivalente de prueba de RN-X-03: valida, asigna personalidad y un sensor por zona."""
    zones = tuple(zones)
    assigned = assign_personality(housing, zones)
    effective = resolve_active_personality(assigned, active) if active is not None else assigned
    return SampleHousehold(
        id=stable_id("hogar", label),
        zones=frozenset(zones),
        assigned_personality=assigned,
        personality=effective,
        sensors={zone: stable_id("sensor", label, zone) for zone in sorted(zones)},
    )


class MemoryStore:
    """Lecturas en memoria con la restricción única (sensor_id, fecha_hora)."""

    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, datetime], dict[str, Any]] = {}

    def insert_if_absent(self, row: dict[str, Any]) -> bool:
        key = (row["sensor_id"], row["fecha_hora"])
        if key in self.rows:  # equivale a ON CONFLICT DO NOTHING
            return False
        if row["consumo_kwh"] < 0:
            raise ValueError("consumo_kwh >= 0")
        self.rows[key] = dict(row)
        return True

    def moments(self, sensor_id: UUID) -> list[datetime]:
        return [moment for (sensor, moment) in self.rows if sensor == sensor_id]


def generate_and_store(
    store: MemoryStore,
    household: SampleHousehold,
    profile: Profile,
    start: int,
    end: int,
    frontier: int,
) -> int:
    inserted = 0
    for zone, sensor_id in household.sensors.items():
        existing = {hour_index(moment) for moment in store.moments(sensor_id)}
        for reading in simulate_zone(household.id, profile, zone, start, end, frontier):
            if reading.index not in existing:
                row = reading_row(sensor_id, reading.index, reading.total)
                inserted += store.insert_if_absent(row)
    return inserted


def recover(store: MemoryStore, household: SampleHousehold, profile: Profile, now: datetime) -> int:
    """`recuperar` de la referencia, sobre la función de producción."""
    existing = {zone: store.moments(sensor) for zone, sensor in household.sensors.items()}
    rows = generate_missing_readings(household.id, profile, household.sensors, existing, now)
    return sum(store.insert_if_absent(row) for row in rows)
