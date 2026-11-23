# domain/

Código puro y probado: `simulator/` (port de `zentheris_sim` del Avance 03, fase 4), `states.py`, `history.py`, `zone_rules.py`, `alert_rules.py` y `formats.py`. Ya están implementados `simulator/`, `zone_rules.py` (RN-X-02, RN-X-04) y los nombres de `formats.py`; el resto sigue como esqueleto.

- **Va:** cálculos y reglas de negocio sin efectos: estados, comparaciones, pico, proyección, validación de zonas, alertas, consejos y textos.
- **No va:** FastAPI, base de datos ni lectura de archivos fuera de lo que se le pase; tampoco reloj, red, log ni azar sin semilla. `tests/test_domain_purity.py` revisa imports y llamadas.
- **Ejemplo:** `calculate_state(valor, referencia, bloque) -> str` (debe reproducir `docs/datos/motor_estados_ref.py`).
