# domain/

Código puro y probado: `simulator/` (se porta en la sesión 4), `states.py`, `history.py`, `zone_rules.py`, `alert_rules.py` y `formats.py`.

- **Va:** cálculos y reglas de negocio sin efectos: estados, comparaciones, pico, proyección, validación de zonas, alertas, consejos y textos.
- **No va:** FastAPI, base de datos ni lectura de archivos fuera de lo que se le pase. Una prueba revisa los imports.
- **Ejemplo:** `calculate_state(valor, referencia, bloque) -> str` (debe reproducir `docs/datos/motor_estados_ref.py`).
