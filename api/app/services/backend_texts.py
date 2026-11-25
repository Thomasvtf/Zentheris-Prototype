"""Textos del backend para alertas y consejos (RN-XI-09, DC-24).

Lee una sola vez `config_files/textos-backend.es-CO.json` (ruta de
`get_settings().backend_texts_path`, variable `RUTA_TEXTOS_BACKEND`) y lo convierte con
`app.domain.formats.parse_backend_texts`, como `services/thresholds.py` con los umbrales. El
dominio no lee archivos: recibe el resultado por parámetro.
"""

import json
from functools import cache

from app.config import get_settings
from app.domain.formats import BackendTexts, parse_backend_texts


@cache
def get_backend_texts() -> BackendTexts:
    """Plantillas de alertas y consejos del archivo configurado, leídas una vez por proceso.

    `ValueError` (de `parse_backend_texts`) si falta una plantilla o un campo.
    """
    path = get_settings().backend_texts_path
    return parse_backend_texts(json.loads(path.read_text(encoding="utf-8")))
