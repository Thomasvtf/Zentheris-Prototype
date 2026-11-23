"""Constantes del simulador (contrato v4.3, DC-53).

Los catálogos (zonas y personalidades) viven en `app.domain.zone_rules`; aquí no se duplican.
"""

from zoneinfo import ZoneInfo

from app.domain.zone_rules import ZONE_TYPES

# Entra en la semilla (RN-IV-04). Cambiarla cambia todas las lecturas sintéticas.
VERSION_MODELO = "zentheris-4.3-ref-1"

TIMEZONE = ZoneInfo("America/Bogota")

HOURS_BACKFILL = 720  # RN-IV-01: 30 días
READING_QUALITY = "simulada"
KWH_SCALE = 4  # NUMERIC(12,4) en lecturas

BASE_COLUMNS = {zone: f"base_{zone}_kwh_dia" for zone in ZONE_TYPES}

REQUIRED_FIELDS = (
    ("nombre", "activo")
    + tuple(BASE_COLUMNS.values())
    + (
        "curva_horaria",
        "humor_min",
        "humor_max",
        "ruido_config",
        "picos_config",
        "factor_fin_semana",
    )
)
# Gestionados por la base de datos: se aceptan, no son obligatorios.
OPTIONAL_FIELDS = ("id", "created_at", "updated_at")

NOISE_KEYS = ("memoria", "intensidad")
PEAK_KEYS = (
    "probabilidad",
    "franjas",
    "potencia_w",
    "duracion_min",
    "minuto_inicio",
    "fraccion_uso",
)
SLOT_KEYS = ("desde", "hasta", "multiplicador")

CURVE_SUM_TOLERANCE = 1e-10  # CT03
CONSERVATION_TOLERANCE = 1e-10  # CT06/CT07, relativa a max(1, T)
