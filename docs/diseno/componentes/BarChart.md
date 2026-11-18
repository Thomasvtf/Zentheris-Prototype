# BarChart

Barras de consumo del periodo con el pico más alto marcado con la etiqueta «Pico» y color propio (rojo claro #F59099). Figma: `Grafico/Historial/Barras` (565:281).

## Propiedades
| Prop | Tipo | Notas |
|---|---|---|
| `datos` | `{etiqueta, valor \| null, eje?}[]` | Día: 24 barras horarias en kW. Semana: Lun–Dom en kWh. Mes: días o semanas en kWh. `null` = sin lectura → sin barra y «—» (nunca 0). `eje` (opcional) es el texto del eje cuando no caben todas las etiquetas (p. ej. cada 3 horas en Día). |
| `unidad` | `'kW' \| 'kWh' \| 'COP'` | kW solo para horas; totales de periodo en kWh (RN-XIII-06). COP solo con `tarifaVigente`. |
| `titulo`, `periodo` | texto | Para el resumen accesible; la referencia temporal va visible en la card. |

## Pico (RN-XIII-03, decisión D5 de la v4.5)
- El gráfico marca el **pico más alto del periodo**, que puede no ser el último pico de la card de Pico.
- **Marcador:** la barra del pico usa `z-color-chart-peak` (rojo claro #F59099, D17) y el resto de la serie conserva `z-color-chart-series1`. Encima lleva la píldora «Pico» de `PeakMarker` (opción A), con sus reglas anti-choque con «Crítico».
- El pico se distingue por la palabra «Pico» y por su posición; el color ayuda pero no es el único aviso. El rojo de estado (`-series4`) sigue reservado para crítico.
- El valor del pico va en el resumen accesible y en el tooltip («Mié · 6,1 kWh»).

## Escala y formato
Eje Y desde 0 hasta un máximo redondeado hacia arriba; 3 líneas de rejilla `z-color-chart-grid`. Etiquetas en `data-s-mono-regular-12` con `z-color-chart-label`, con los decimales de su unidad y miles con «k» (RN-XII-08). Ancho FILL de la card; barras de hasta 24 px con radio 4.

## Estados
Sin datos: «Sin datos para este periodo». Datos parciales: huecos con «—». Error: `InlineNotice` «No pudimos cargar el historial» + Reintentar. Sin permiso: la card se reemplaza (`StateMessage`).

## Pendiente
Librería elegida: `react-native-gifted-charts` (DC-12, DC-63), con prueba mínima pendiente; este componente es una referencia en SVG. El marcador es una propuesta de diseño: falta aprobación visual.
