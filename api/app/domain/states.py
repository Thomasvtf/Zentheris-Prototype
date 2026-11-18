"""Motor de estados normal/elevado/crítico (RN-XI-02, RN-XI-07).

Debe reproducir docs/datos/motor_estados_ref.py y pasar los 13 escenarios de
test_escenarios_umbrales.py (prueba U-01), con los umbrales de umbrales-estado.v1.json.
Esqueleto: se implementa en la sesión 5.
"""


def calculate_state(valor: float | None, referencia: float | None, bloque: str) -> str:
    """Devuelve `normal`, `elevado`, `critico`, `sin_referencia` o `sin_datos` para un bloque."""
    raise NotImplementedError("TODO(sesión 5): motor de estados (U-01)")
