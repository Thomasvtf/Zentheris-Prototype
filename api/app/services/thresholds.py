"""Umbrales de estado compartidos por los servicios (RN-XI-07).

Lee una sola vez `config_files/umbrales-estado.v1.json` (ruta de `get_settings().thresholds_path`,
variable `RUTA_UMBRALES`) y lo convierte con `app.domain.states.parse_thresholds`. Lo usan el
consumo (fase 6) y lo usarán el historial y las alertas (fases 7 y 8).
"""

import json
from functools import cache

from app.config import get_settings
from app.domain.states import StateThresholds, parse_thresholds


@cache
def get_thresholds() -> StateThresholds:
    """Umbrales de estado del archivo configurado, leídos una vez por proceso.

    `ValueError` (de `parse_thresholds`) si falta una clave o un valor no es numérico.
    """
    path = get_settings().thresholds_path
    return parse_thresholds(json.loads(path.read_text(encoding="utf-8")))
