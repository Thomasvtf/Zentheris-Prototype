/**
 * Gráficos de serie del Historial: barras (BarChart.md) y línea (LineChart.md), con el pico más
 * alto marcado según PeakMarker.md (opción A) y RN-XIII-03.
 *
 * Se dibujan con `react-native-svg` (nivel 3 del orden de respaldo, DC-12/DC-63) porque
 * `react-native-gifted-charts` no permite fijar la posición de las etiquetas del eje X ni
 * mantener la píldora del pico dentro del contenedor: truncaba las fechas («0..»), desbordaba
 * la Semana y cortaba la píldora en los bordes. Victory Native no está instalado.
 *
 * - El pico usa `chart-peak` (barra o punto) y la píldora «Pico · cuándo · valor»; nunca
 *   componentes ni palabras de estado.
 * - `null` = sin lectura: sin barra y la línea se corta (nunca 0).
 * - La etiqueta de unidad («kW», «kWh», «COP») va en el origen del eje Y, sobre el eje X.
 * - Colores, espacios y tipografía solo desde @/theme; textos y cifras llegan ya formateados.
 */
import React, { useState } from 'react';
import { LayoutChangeEvent, StyleSheet, Text, TextStyle, View } from 'react-native';
import Svg, { Circle, Line, Path, Rect } from 'react-native-svg';

import { colors, fontFamilyFor, radius, spacing, typography } from '@/theme';

import {
  CHART_HEIGHT,
  X_LABEL_WIDTH,
  Y_LABEL_WIDTH,
  clampBox,
  estimatePillWidth,
  plotLayout,
  slotCenter,
  slotEdge,
  smoothPaths,
  valueY,
  yAxisFor,
} from './chartGeometry';
import type { PlotLayout } from './chartGeometry';

export interface SeriesDatum {
  /** `null` = sin lectura o slot sin dato. */
  valor: number | null;
  /** Pico más alto del periodo (`es_pico_maximo` del contrato). */
  pico: boolean;
}

export interface XLabel {
  /** Slot al que pertenece la etiqueta. */
  index: number;
  texto: string;
  /** `borde`: en el inicio del slot (horas de Día); `centro`: bajo la barra. */
  posicion: 'borde' | 'centro';
}

export interface SeriesChartProps {
  datos: SeriesDatum[];
  /** Ancho disponible (el de la card); el gráfico nunca lo supera. */
  ancho: number;
  /** Texto de la unidad en el origen («kW», «kWh», «COP»). */
  unidad: string;
  /** Etiqueta de un valor del eje Y con sus decimales («0,2», «$2k»). */
  formatTick: (valor: number, decimales: number) => string;
  /** Texto de la píldora del pico («Pico · 11h · 0,48 kW»); `null` sin pico. */
  etiquetaPico: string | null;
  xLabels: XLabel[];
  /** Resumen accesible del gráfico (un resumen en texto por gráfico). */
  resumen: string;
}

function textStyle(name: keyof typeof typography): TextStyle {
  const style = typography[name];
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    ...('lineHeight' in style ? { lineHeight: style.lineHeight } : {}),
  };
}

/** Píldora del pico (PeakMarker opción A), medida y recolocada para no salirse del contenedor. */
export function PeakPill({ texto, centro, ancho }: { texto: string; centro: number; ancho: number }) {
  const [width, setWidth] = useState(() => estimatePillWidth(texto));
  const onLayout = (e: LayoutChangeEvent) => {
    const measured = Math.ceil(e.nativeEvent.layout.width);
    if (measured > 0 && measured !== width) setWidth(measured);
  };
  return (
    <View style={[styles.pill, { left: clampBox(centro, width, ancho), maxWidth: ancho }]} onLayout={onLayout}>
      <Text numberOfLines={1} style={styles.pillText}>
        {texto}
      </Text>
    </View>
  );
}

/** Rejilla, etiquetas de ejes y píldora: lo común a barras y línea. */
function ChartFrame({
  layout,
  ticks,
  decimals,
  maxValue,
  props,
  peakIndex,
  children,
}: {
  layout: PlotLayout;
  ticks: number[];
  decimals: number;
  maxValue: number;
  props: SeriesChartProps;
  peakIndex: number;
  children: React.ReactNode;
}) {
  const baseline = valueY(layout, 0, maxValue);
  const right = layout.plotLeft + layout.plotWidth;
  return (
    <View style={{ width: props.ancho, height: CHART_HEIGHT }} accessible accessibilityLabel={props.resumen}>
      <Svg width={props.ancho} height={CHART_HEIGHT}>
        {ticks.slice(1).map((tick) => {
          const y = valueY(layout, tick, maxValue);
          return (
            <Line key={tick} x1={layout.plotLeft} x2={right} y1={y} y2={y} stroke={colors['border-medium']} strokeWidth={1} strokeDasharray="3 4" />
          );
        })}
        <Line x1={layout.plotLeft} x2={right} y1={baseline} y2={baseline} stroke={colors['border-medium']} strokeWidth={1} />
        {children}
      </Svg>

      {/* Eje Y: valores con coma decimal; en el origen, la unidad (a la izquierda, sobre el eje X). */}
      {ticks.map((tick, i) => (
        <Text
          key={`y${tick}`}
          numberOfLines={1}
          style={[
            styles.axisText,
            i === 0 ? styles.unitLabel : styles.yLabel,
            { top: valueY(layout, tick, maxValue) - 8, width: Y_LABEL_WIDTH - spacing['4'] },
          ]}
        >
          {i === 0 ? props.unidad : props.formatTick(tick, decimals)}
        </Text>
      ))}

      {/* Eje X: cada etiqueta en una caja de ancho fijo que no se sale del contenedor. */}
      {props.xLabels.map((label) => {
        const x = label.posicion === 'borde' ? slotEdge(layout, label.index) : slotCenter(layout, label.index);
        return (
          <Text
            key={`x${label.index}`}
            numberOfLines={1}
            style={[styles.axisText, styles.xLabel, { left: clampBox(x, X_LABEL_WIDTH, props.ancho), top: baseline + spacing['4'] }]}
          >
            {label.texto}
          </Text>
        );
      })}

      {props.etiquetaPico && peakIndex >= 0 ? (
        <PeakPill texto={props.etiquetaPico} centro={slotCenter(layout, peakIndex)} ancho={props.ancho} />
      ) : null}
    </View>
  );
}

/** BarChart.md: barras por slot; el pico en `chart-peak`, el resto en `chart-series1`. */
export function BarChart(props: SeriesChartProps) {
  const layout = plotLayout(props.ancho, props.datos.length);
  const axis = yAxisFor(props.datos.map((d) => d.valor));
  const peakIndex = props.datos.findIndex((d) => d.pico && d.valor !== null);
  const baseline = valueY(layout, 0, axis.maxValue);
  return (
    <ChartFrame layout={layout} ticks={axis.ticks} decimals={axis.decimals} maxValue={axis.maxValue} props={props} peakIndex={peakIndex}>
      {props.datos.map((d, i) => {
        if (d.valor === null || d.valor <= 0) return null;
        const top = valueY(layout, d.valor, axis.maxValue);
        return (
          <Rect
            key={i}
            x={slotCenter(layout, i) - layout.barWidth / 2}
            y={top}
            width={layout.barWidth}
            height={Math.max(baseline - top, 1)}
            rx={Math.min(radius.xs, layout.barWidth / 2)}
            fill={d.pico ? colors['chart-peak'] : colors['chart-series1']}
          />
        );
      })}
    </ChartFrame>
  );
}

export interface LineChartProps extends SeriesChartProps {
  /** Promedio histórico como línea punteada de referencia (LineChart.md); `null` la oculta. */
  referencia: number | null;
}

/** LineChart.md: línea suave de 2 px que se corta en los `null`, con punto en el pico. */
export function LineChart(props: LineChartProps) {
  const layout = plotLayout(props.ancho, props.datos.length);
  const axis = yAxisFor(props.datos.map((d) => d.valor), props.referencia);
  const peakIndex = props.datos.findIndex((d) => d.pico && d.valor !== null);
  const bounds = { top: layout.plotTop, bottom: valueY(layout, 0, axis.maxValue) };

  // Solo hasta el último dato: los slots sin dato al final no cortan la línea con un hueco falso.
  const lastIndex = props.datos.reduce((last, d, i) => (d.valor !== null ? i : last), -1);
  const points = props.datos
    .slice(0, lastIndex + 1)
    .map((d, i) => (d.valor === null ? null : { x: slotCenter(layout, i), y: valueY(layout, d.valor, axis.maxValue) }));
  const paths = smoothPaths(points, bounds);
  const peak = peakIndex >= 0 ? points[peakIndex] : null;
  const refY = props.referencia !== null ? valueY(layout, props.referencia, axis.maxValue) : null;

  return (
    <ChartFrame layout={layout} ticks={axis.ticks} decimals={axis.decimals} maxValue={axis.maxValue} props={props} peakIndex={peakIndex}>
      {refY !== null ? (
        <Line
          x1={layout.plotLeft}
          x2={layout.plotLeft + layout.plotWidth}
          y1={refY}
          y2={refY}
          stroke={colors['green-600']}
          strokeWidth={1.5}
          strokeDasharray="6 4"
        />
      ) : null}
      {paths.map((d, i) => (
        <Path key={i} d={d} stroke={colors['chart-series1']} strokeWidth={2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      ))}
      {peak ? <Circle cx={peak.x} cy={peak.y} r={5} fill={colors['chart-peak']} stroke={colors['background-surface']} strokeWidth={2} /> : null}
    </ChartFrame>
  );
}

const styles = StyleSheet.create({
  axisText: {
    ...textStyle('data-s-mono-regular-12'),
    color: colors['chart-label'],
    position: 'absolute',
  },
  yLabel: { left: 0, textAlign: 'right' },
  unitLabel: { left: 0, textAlign: 'left' },
  xLabel: { width: X_LABEL_WIDTH, textAlign: 'center' },
  pill: {
    position: 'absolute',
    top: spacing['4'],
    paddingHorizontal: spacing['8'],
    paddingVertical: 2,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors['chart-peak'],
    backgroundColor: colors['accent-soft'],
  },
  // PeakMarker (regla 2): texto neutro `text/primary`; el rojo claro solo en el borde.
  pillText: { ...textStyle('data-s-mono-regular-12'), color: colors['text-primary'] },
});
