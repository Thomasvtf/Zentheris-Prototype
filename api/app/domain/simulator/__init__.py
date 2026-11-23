"""Simulador de consumo (RN-IV, DC-53): port de `zentheris_sim` (Avance 03).

Puro: sin archivos, sin reloj, sin FastAPI ni SQL. Los perfiles entran por parámetro.
"""

from app.domain.simulator.constants import HOURS_BACKFILL, TIMEZONE, VERSION_MODELO
from app.domain.simulator.engine import (
    DegenerateRealizationError,
    generate_backfill,
    hour_from_index,
    hour_index,
    last_complete_hour,
)
from app.domain.simulator.recovery import (
    SensorGaps,
    generate_missing_readings,
    generate_readings_for_gaps,
    recovery_end_hour,
)
from app.domain.simulator.validation import (
    ProfileParameterError,
    validate_or_raise,
    validate_profile,
)

__all__ = [
    "HOURS_BACKFILL",
    "TIMEZONE",
    "VERSION_MODELO",
    "DegenerateRealizationError",
    "ProfileParameterError",
    "SensorGaps",
    "generate_backfill",
    "generate_missing_readings",
    "generate_readings_for_gaps",
    "hour_from_index",
    "hour_index",
    "last_complete_hour",
    "recovery_end_hour",
    "validate_or_raise",
    "validate_profile",
]
