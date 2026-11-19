/**
 * Geometría compartida de los gráficos del Historial (BarChart.md, LineChart.md, PeakMarker.md).
 * Funciones puras: las posiciones se calculan aquí y se prueban sin dibujar.
 *
 * - El área de dibujo se divide en `slots` iguales (24 horas en Día, 7 días en Semana, los días
 *   con dato en Mes). Los slots sin dato quedan vacíos para que el eje sea siempre el completo.
 * - Eje Y desde 0 hasta un máximo «redondo» hacia arriba, con 3 líneas de rejilla.
 * - Toda etiqueta (eje X y píldora del pico) se mantiene dentro del ancho del contenedor.
 */

export const SECTIONS = 3;
/** Ancho de la columna de etiquetas del eje Y. */
export const Y_LABEL_WIDTH = 40;
/** Margen derecho del área de dibujo. */
export const RIGHT_PAD = 8;
/** Franja superior reservada para la píldora del pico. */
export const PILL_BAND = 36;
/** Alto del área de dibujo. */
export const PLOT_HEIGHT = 150;
/** Franja inferior para las etiquetas del eje X. */
export const X_LABEL_BAND = 22;
/** Ancho reservado para cada etiqueta del eje X («06h», «Mié», «15/11»). */
export const X_LABEL_WIDTH = 44;
/** Ancho máximo de una barra (BarChart.md: hasta 24 px). */
export const MAX_BAR_WIDTH = 24;

export const CHART_HEIGHT = PILL_BAND + PLOT_HEIGHT + X_LABEL_BAND;

export interface PlotLayout {
  width: number;
  plotLeft: number;
  plotWidth: number;
  plotTop: number;
  plotHeight: number;
  slot: number;
  barWidth: number;
}

export function plotLayout(width: number, slots: number): PlotLayout {
  const plotLeft = Y_LABEL_WIDTH;
  const plotWidth = Math.max(width - plotLeft - RIGHT_PAD, 1);
  const slot = plotWidth / Math.max(slots, 1);
  // 60 % del slot para la barra y 40 % de separación; nunca más de 24 px.
  const barWidth = Math.max(2, Math.min(MAX_BAR_WIDTH, slot * 0.6));
  return { width, plotLeft, plotWidth, plotTop: PILL_BAND, plotHeight: PLOT_HEIGHT, slot, barWidth };
}

/** Centro horizontal del slot `i`. */
export function slotCenter(layout: PlotLayout, i: number): number {
  return layout.plotLeft + (i + 0.5) * layout.slot;
}

/** Borde izquierdo del slot `i` (marcas de hora en Día). */
export function slotEdge(layout: PlotLayout, i: number): number {
  return layout.plotLeft + i * layout.slot;
}

/** Y de un valor dentro del área de dibujo. */
export function valueY(layout: PlotLayout, value: number, maxValue: number): number {
  const ratio = maxValue > 0 ? Math.min(value / maxValue, 1) : 0;
  return layout.plotTop + layout.plotHeight * (1 - ratio);
}

/** Paso «redondo» (1, 1,5, 2, 2,5, 3, 4, 5, 6 u 8 × 10ⁿ): el máximo del eje queda hacia arriba sin dejar media gráfica vacía. */
const STEP_FACTORS = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
export function niceStep(rawStep: number): number {
  if (!(rawStep > 0)) return 1;
  const power = 10 ** Math.floor(Math.log10(rawStep));
  const factor = STEP_FACTORS.find((f) => f * power >= rawStep - 1e-12) ?? 10;
  return Number((factor * power).toPrecision(12));
}

/** Decimales mínimos para escribir `step` y sus múltiplos sin repetir etiquetas. */
function decimalsFor(step: number): number {
  for (let d = 0; d < 3; d++) {
    if (Math.abs(Math.round(step * 10 ** d) - step * 10 ** d) < 1e-9) return d;
  }
  return 2;
}

export interface YAxis {
  maxValue: number;
  step: number;
  /** Valores de las líneas de rejilla de abajo hacia arriba (0, step, 2·step, 3·step). */
  ticks: number[];
  /** Decimales mínimos para que las etiquetas no se repitan («0,2», «0,4», «0,6»). */
  decimals: number;
}

export function yAxisFor(values: (number | null)[], reference: number | null = null): YAxis {
  const max = Math.max(...values.map((v) => v ?? 0), reference ?? 0, 0);
  const step = niceStep(max > 0 ? max / SECTIONS : 1);
  return {
    maxValue: step * SECTIONS,
    step,
    ticks: Array.from({ length: SECTIONS + 1 }, (_, i) => step * i),
    decimals: decimalsFor(step),
  };
}

/** Borde izquierdo de una caja de `boxWidth` centrada en `center`, sin salirse de [0, width]. */
export function clampBox(center: number, boxWidth: number, width: number): number {
  const left = center - boxWidth / 2;
  return Math.max(0, Math.min(left, Math.max(width - boxWidth, 0)));
}

/** Ancho estimado de la píldora antes de medirla (texto de 12 px + padding y borde). */
export function estimatePillWidth(text: string): number {
  return Math.ceil(text.length * 6.6) + 18;
}

/** Índices del eje X con etiqueta: cada 6 h en Día (0–24), cada día en Semana, cada 7 en Mes. */
export function xLabelIndexes(periodo: 'dia' | 'semana' | 'mes', slots: number): number[] {
  if (periodo === 'dia') return [0, 6, 12, 18, 24];
  if (periodo === 'semana') return Array.from({ length: slots }, (_, i) => i);
  const out: number[] = [];
  for (let i = 0; i < slots; i += 7) out.push(i);
  return out;
}

/** Trazos SVG de una línea suave (Catmull-Rom → Bézier) que se corta en los `null`. */
export function smoothPaths(
  points: ({ x: number; y: number } | null)[],
  bounds: { top: number; bottom: number } = { top: -Infinity, bottom: Infinity },
): string[] {
  // Los puntos de control se limitan al área de dibujo para que la curva no baje de 0.
  const clampY = (y: number) => Math.max(bounds.top, Math.min(bounds.bottom, y));
  const segments: { x: number; y: number }[][] = [];
  let current: { x: number; y: number }[] = [];
  for (const p of points) {
    if (p) current.push(p);
    else if (current.length) {
      segments.push(current);
      current = [];
    }
  }
  if (current.length) segments.push(current);

  return segments.map((seg) => {
    if (seg.length === 1) return `M ${seg[0].x} ${seg[0].y} L ${seg[0].x + 0.01} ${seg[0].y}`;
    let d = `M ${seg[0].x} ${seg[0].y}`;
    for (let i = 0; i < seg.length - 1; i++) {
      const p0 = seg[i - 1] ?? seg[i];
      const p1 = seg[i];
      const p2 = seg[i + 1];
      const p3 = seg[i + 2] ?? p2;
      const c1x = p1.x + (p2.x - p0.x) / 6;
      const c1y = clampY(p1.y + (p2.y - p0.y) / 6);
      const c2x = p2.x - (p3.x - p1.x) / 6;
      const c2y = clampY(p2.y - (p3.y - p1.y) / 6);
      d += ` C ${c1x} ${c1y} ${c2x} ${c2y} ${p2.x} ${p2.y}`;
    }
    return d;
  });
}
