"""Promedios de las 5 personalidades de consumo, leídos de `docs/datos/perfiles/`.

Sirve para que las pruebas usen **los mismos promedios que el simulador** en vez de números
inventados: kWh/día por zona, curva horaria (participación de cada hora, suma 1), factor de
fin de semana, humor y ruido. Solo lee; no cambia los perfiles y no usa base de datos.

El archivo se comprueba por SHA-256 (`supabase/CLAUDE.md`): si cambia, las pruebas fallan a
propósito, porque cambiar un perfil cambia todas las lecturas (RN-IV-04).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROFILES_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "datos"
    / "perfiles"
    / "consolidado_perfiles_simulacion.json"
)
PROFILES_SHA256 = "6cfa97152a120edfdfde45921a1382e23025981d4ae1652c5f476e5489a90922"

# Orden de la regla de negocio: compacto < eficiente < intermedio < familiar < amplio.
PERSONALITY_ORDER = (
    "Consumo compacto",
    "Consumo eficiente",
    "Consumo intermedio",
    "Consumo familiar",
    "Consumo amplio",
)
ZONE_KEYS = (
    "cocina",
    "sala",
    "dormitorio",
    "bano",
    "oficina",
    "lavanderia",
    "terraza",
    "garaje",
    "cuarto_servicio",
)
DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class PersonalityAverages:
    """Promedios de una personalidad, tal como están en el consolidado."""

    name: str
    zone_kwh_per_day: dict[str, float]  # solo las zonas con base > 0
    hourly_share: dict[str, tuple[float, ...]]  # clave 'base' o una zona; 24 valores que suman 1
    weekend_factor: float
    humor_min: float
    humor_max: float
    noise_memory: float
    noise_intensity: float

    @property
    def kwh_per_day(self) -> float:
        """Consumo diario de un hogar con todas las zonas que contempla la personalidad."""
        return sum(self.zone_kwh_per_day.values())

    @property
    def kwh_per_month(self) -> float:
        """Consumo mensual de referencia (30 días, sin humor ni ruido ni fin de semana)."""
        return self.kwh_per_day * DAYS_PER_MONTH

    def zone_kwh_for_hour(self, zone: str, hour: int) -> float:
        """kWh esperados de una zona en una hora del día (base diaria × participación horaria).

        Es el promedio sin ruido: sirve como «referencia» al probar estados y alertas.
        Si la zona no tiene curva propia, usa la curva `base`.
        """
        if zone not in self.zone_kwh_per_day:
            raise KeyError(f"{self.name} no contempla la zona {zone!r}")
        curve = self.hourly_share.get(zone, self.hourly_share["base"])
        return self.zone_kwh_per_day[zone] * curve[hour]

    def household_kwh_for_hour(self, hour: int, zones: tuple[str, ...] | None = None) -> float:
        """kWh esperados de todo el hogar (o de las zonas indicadas) en una hora."""
        chosen = zones if zones is not None else tuple(self.zone_kwh_per_day)
        return sum(self.zone_kwh_for_hour(zone, hour) for zone in chosen)


def _read_profiles() -> list[dict]:
    raw = PROFILES_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != PROFILES_SHA256:
        raise AssertionError(
            "consolidado_perfiles_simulacion.json cambió "
            f"(SHA-256 {digest}); revisa la decisión antes de actualizar las pruebas"
        )
    return json.loads(raw.decode("utf-8"))


@lru_cache(maxsize=1)
def load_personalities() -> dict[str, PersonalityAverages]:
    """Las 5 personalidades por nombre, en el orden de la regla de negocio."""
    by_name = {}
    for item in _read_profiles():
        zones = {
            zone: float(item[f"base_{zone}_kwh_dia"])
            for zone in ZONE_KEYS
            if float(item[f"base_{zone}_kwh_dia"]) > 0
        }
        shares = {key: tuple(float(v) for v in values) for key, values in item["curva_horaria"].items()}
        by_name[item["nombre"]] = PersonalityAverages(
            name=item["nombre"],
            zone_kwh_per_day=zones,
            hourly_share=shares,
            weekend_factor=float(item["factor_fin_semana"]),
            humor_min=float(item["humor_min"]),
            humor_max=float(item["humor_max"]),
            noise_memory=float(item["ruido_config"]["memoria"]),
            noise_intensity=float(item["ruido_config"]["intensidad"]),
        )
    return {name: by_name[name] for name in PERSONALITY_ORDER}
