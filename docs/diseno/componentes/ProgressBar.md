# ProgressBar

Barra de progreso o participación con etiqueta y porcentaje. Figma: `Estado/Barra-progreso` (514:1335; rediseñada el 2026-11-02, aprobada por Nicolás). **Vigente.**

| Prop | Tipo | Notas |
|---|---|---|
| `porcentaje` | número 0–100 | Cualquier valor (no solo 25/50/75/95). Se limita a 0–100. |
| `estado` | `'normal' \| 'elevado' \| 'critico' \| 'neutro'` | Normal, elevado y crítico son estados (severidad); `neutro` es una participación sin estado. |
| `etiqueta` | texto | A la izquierda: la palabra del estado («Normal», «Elevado», «Crítico») o un nombre («Participación»). |

## Diseño
- Fila superior con la etiqueta a la izquierda (`body-xs`, muted; en Figma el texto de estado usa su color de estado) y el porcentaje a la derecha en `JetBrains Mono` Bold 12 `z-color-text-primary`.
- Pista de 6 px, `z-color-border-medium`, radio `z-radius-full`. El relleno usa el mismo radio.
- Relleno: `z-color-status-success-default` (normal), `-warning-` (elevado), `-error-` (crítico) y `z-color-chart-series1` (neutro). El color de severidad se usa solo para estado, nunca como categoría.
- El texto del porcentaje sigue las reglas es-CO del sistema (`formatPercent`).
- Accesibilidad: `role="progressbar"` con `aria-valuenow`, `aria-valuemin`, `aria-valuemax` y etiqueta. El estado no depende solo del color (lleva su palabra). Sin certificación; falta verificarlo con lectores de pantalla.

## En Figma
Variantes `State` (Normal · Neutral · Warning · Critical) × `Type card` (large 358 · Small 145). Para otro porcentaje en una instancia: cambiar el texto «Porcentaje» y el margen derecho de «Pista» = (100 − porcentaje) × ancho de la pista ÷ 100 (el relleno ocupa el resto). Se usa dentro de `Card/Zona/Resumen`.

## Cambios respecto a la versión anterior
La versión anterior tenía solo 4 porcentajes fijos como variantes, el texto de estado siempre decía «Normal», la pista medía 4 px y el relleno normal usaba `chart/series2` (distinto del gauge). Ahora hay un porcentaje libre, el estado correcto, 6 px y los mismos colores que el gauge.
