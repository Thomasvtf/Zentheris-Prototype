# Metric

Muestra una cifra energética o monetaria con su unidad, en formato es-CO: valor en JetBrains Mono y unidad más pequeña en `z-color-text-muted`.

**Figma:** sin componente propio; es el par valor + unidad de todas las cards (rol Data).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `valor` | `number \| null` | `null` = sin datos → «—». Cero se muestra como cero («0,00 kW»). |
| `unidad` | `'kW' \| 'kWh' \| 'COP' \| '%'` | kW = promedio de la última hora completa; kWh = energía de un periodo. Nunca mezclar. |
| `tamano` | `'xl' \| 'l' \| 'm' \| 's'` | xl = `data-xl-32` (KPI), l = `data-l` 24, m = `data-m` 20, s = `data-s-16`. |
| `decimales` | `number` | Por defecto según la unidad (RN-XII-08): kW **2**, kWh **1**, COP **0**, % 0. Solo se cambia por una razón documentada. |
| `tarifaVigente` | `boolean` | Obligatoria para COP: sin tarifa vigente no se pinta nada. |
| `abreviar` | `boolean` | Miles con «k» minúscula en cards y ejes: «$6,5k», «$28k». |

## Formato
- Coma decimal, punto de miles: «2,40 kW», «0,62 kW», «145,3 kWh», «$14.400», «$6,5k», «34 %» (RN-XII-08). Ejemplos anteriores con un decimal en kW se leen con dos.
- Helpers exportados: `DECIMALES` (`{kW: 2, kWh: 1, COP: 0, '%': 0}`), `formatNumber(v, dec, {abreviar})`, `formatCOP(v, {abreviar})` (sin decimales; abreviado con «k»), `formatPercent(v)` (con espacio).
- La unidad acompaña siempre a la cifra y la cifra siempre lleva su periodo en el contenedor («Última hora completa (14:00–15:00)», «Hoy hasta las 15:00»).

## Tokens
`z-color-text-primary` (valor), `z-color-text-muted` (unidad), `--font-data`, `--font-body`, `z-space-4`.

## Textos por estado
Sin datos: «—» con etiqueta accesible «Sin datos» *(propuesto)*.
