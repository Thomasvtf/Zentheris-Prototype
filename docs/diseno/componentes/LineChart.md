# LineChart

Línea de consumo del periodo con el pico más alto marcado con un punto y la etiqueta «Pico». Es una de las tres formas del gráfico de consumo del Historial (barras, línea o anillo, RN-XIII-04). **Obligatorio** (decisión de Nicolás, 11/11/2026).

Figma: `Grafico/Historial/Linea` (537:109), dentro de `Card/Historial/Grafico` (2054:1030). **Ficha escrita el 11/11/2026 a partir de lo que ya está dibujado en Figma; el diseño no cambió.** Falta aprobación visual.

## Propiedades
Las mismas que `BarChart` (`datos`, `unidad`, `titulo`, `periodo`): Día = 24 puntos horarios en kW; Semana = Lun–Dom en kWh; Mes = días en kWh. COP solo con `tarifaVigente`. `null` = sin lectura: la línea se interrumpe y se muestra «—», nunca 0.

## Diseño (según Figma)
- Línea suave de 2 px en `z-color-chart-series1` (#5DD39E), sin relleno debajo.
- Rejilla horizontal punteada de 3 líneas en `z-color-chart-grid`; etiquetas del eje Y y X en `data-s-mono-regular-12` con `z-color-chart-label` (#C4D4CF), con los decimales de su unidad y miles con «k» (RN-XII-08). Eje Y desde 0.
- Línea de referencia punteada fina: el promedio histórico del periodo (RN-XIII-03).
- Pico: punto en `z-color-chart-peak` (#F59099) sobre el valor más alto, con la píldora de `PeakMarker` (opción A: fondo `z-color-accent-soft`, borde y texto en rojo claro): «Pico · 12:00 · 3,20 kW», «Pico · Sáb · 28,4 kWh» o «Pico · 15/07 · 28,0 kWh». Se aplican las reglas anti-choque con «Crítico» de `PeakMarker`.
- Sin datos: línea punteada plana y el texto «Sin datos para este periodo».

## Defecto de Figma que se corrige en el código
En las vistas Semana y Mes del laboratorio la píldora del pico se corta en el borde derecho («28,»). La píldora debe **voltearse hacia la izquierda** cuando no cabe a la derecha del punto.

## Cómo se construye
`react-native-gifted-charts` (`LineChart`) con curva suave, línea de referencia y punto personalizado en el pico (DC-12, DC-63). **Por verificar en la prueba mínima:** la interrupción de la línea con `null`, la píldora del pico y su volteo. Si algo falla, se pasa al siguiente nivel del orden de respaldo (Victory Native y luego `react-native-svg` a mano), solo para este gráfico.

## Accesibilidad y estados
Resumen accesible con el valor y el momento del pico, el promedio y el periodo. Error: `InlineNotice` «No pudimos cargar el historial» + Reintentar. Sin permiso: `StateMessage`.
