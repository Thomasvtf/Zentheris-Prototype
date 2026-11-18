# format/

Formato es-CO según RN-XII-08, hecho a mano (sin `Intl`), con las firmas de `index.d.ts`: `DECIMALES`, `formatNumber`, `formatCOP` y `formatPercent` (`numbers.ts`); y `relativeTime` (`time.ts`, RN-XIV-04). Los casos que la regla no define están escritos al inicio de cada archivo, con la fecha de la decisión.

- **Ejemplo:** `formatNumber(2.4, DECIMALES.kW)` → «2,40»; `formatCOP(6500, { abreviar: true })` → «$6,5k»; `formatPercent(34)` → «34 %» (con espacio sin ruptura).
- **Pruebas:** `__tests__/` (`npm test`).
