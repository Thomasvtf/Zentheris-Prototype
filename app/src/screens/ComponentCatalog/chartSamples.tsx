/**
 * Muestras de la prueba mínima de gráficos (PENDIENTES #11) con react-native-gifted-charts,
 * según BarChart.md, LineChart.md y PeakMarker.md:
 * - Eje Y desde 0 hasta un máximo redondeado hacia arriba, 3 líneas de rejilla y etiquetas
 *   es-CO con los decimales de su unidad (RN-XII-08).
 * - Pico más alto del periodo con `chart-peak` y la píldora «Pico» (opción A de PeakMarker).
 * - Línea: se interrumpe donde falta la lectura (`null`, nunca 0) y la píldora se voltea a la
 *   izquierda cuando no cabe a la derecha del punto (defecto de Figma en Semana y Mes).
 * Datos de ejemplo; no es el componente final.
 */
import { Text, View } from 'react-native';
import { BarChart, LineChart } from 'react-native-gifted-charts';

import { DECIMALES, formatNumber } from '@/format';
import { t } from '@/texts';
import { colors, fontFamilyFor, radius, spacing, typography } from '@/theme';

type Unit = 'kW' | 'kWh';
export interface Point {
  etiqueta: string;
  valor: number | null;
  eje?: string;
}

const SECTIONS = 3;
const AXIS_TEXT = {
  fontFamily: fontFamilyFor('data', typography['data-s-mono-regular-12'].fontWeight),
  fontSize: typography['data-s-mono-regular-12'].fontSize,
  color: colors['chart-label'],
};

/** Paso «redondo» (1, 2, 2,5 o 5 × 10ⁿ) para que el máximo del eje quede hacia arriba. */
function niceStep(rawStep: number): number {
  const power = 10 ** Math.floor(Math.log10(rawStep));
  const factor = [1, 2, 2.5, 5, 10].find((f) => f * power >= rawStep) ?? 10;
  return factor * power;
}

/** Máximo del eje y sus etiquetas es-CO (de abajo hacia arriba). */
export function axisFor(values: (number | null)[], unit: Unit) {
  const max = Math.max(...values.filter((v): v is number => v !== null), 0);
  const step = niceStep(max > 0 ? max / SECTIONS : 1);
  const labels = Array.from({ length: SECTIONS + 1 }, (_, i) => formatNumber(step * i, DECIMALES[unit]));
  return { maxValue: step * SECTIONS, stepValue: step, labels };
}

/** Índice del valor más alto (ignora los `null`). */
export function peakIndex(points: Point[]): number {
  return points.reduce(
    (best, p, i) => (p.valor !== null && (best < 0 || p.valor > (points[best].valor ?? -Infinity)) ? i : best),
    -1,
  );
}

/** Píldora «Pico», opción A de PeakMarker: fondo accent-soft, borde y texto chart-peak. */
export function PeakPill({ texto, alinear = 'izquierda' }: { texto: string; alinear?: 'izquierda' | 'derecha' }) {
  return (
    // Fila: la píldora toma solo el ancho del texto y se pega al lado del punto.
    <View style={{ flexDirection: 'row', justifyContent: alinear === 'derecha' ? 'flex-end' : 'flex-start' }}>
      <View
        style={{
          paddingHorizontal: spacing['8'],
          paddingVertical: 2,
          borderRadius: radius.full,
          borderWidth: 1,
          borderColor: colors['chart-peak'],
          backgroundColor: colors['accent-soft'],
        }}
      >
        <Text
          numberOfLines={1}
          style={{
            fontFamily: fontFamilyFor('body', typography['ui-s-etiqueta-12'].fontWeight),
            fontSize: typography['ui-s-etiqueta-12'].fontSize,
            color: colors['chart-peak'],
          }}
        >
          {texto}
        </Text>
      </View>
    </View>
  );
}

export function BarSample({ points, unit, periodo }: { points: Point[]; unit: Unit; periodo: string }) {
  const peak = peakIndex(points);
  const axis = axisFor(points.map((p) => p.valor), unit);
  const peakPoint = points[peak];
  const summary = t('a11y.grafico_barras', {
    periodo,
    valor: `${formatNumber(peakPoint.valor, DECIMALES[unit])} ${unit}`,
    cuando: peakPoint.etiqueta,
  });
  return (
    <View accessible accessibilityLabel={summary}>
      <BarChart
        data={points.map((p, i) => ({
          value: p.valor ?? 0,
          label: p.eje ?? '',
          frontColor: i === peak ? colors['chart-peak'] : colors['chart-series1'],
          topLabelComponent:
            i === peak
              ? () => <PeakPill texto={t('estado.historial_pico.etiqueta')} />
              : p.valor === null
                ? () => <Text style={AXIS_TEXT}>{t('comun.sin_dato')}</Text>
                : undefined,
        }))}
        maxValue={axis.maxValue}
        stepValue={axis.stepValue}
        noOfSections={SECTIONS}
        yAxisLabelTexts={axis.labels}
        yAxisLabelWidth={44}
        yAxisTextStyle={AXIS_TEXT}
        xAxisLabelTextStyle={AXIS_TEXT}
        rulesColor={colors['chart-grid']}
        rulesType="dashed"
        yAxisColor="transparent"
        xAxisColor={colors['chart-grid']}
        barWidth={16}
        spacing={6}
        barBorderRadius={4}
        isAnimated={false}
      />
      <Text style={AXIS_TEXT}>{summary}</Text>
    </View>
  );
}

const LINE_SPACING = { dia: 22, semana: 70, mes: 16 } as const;
const PILL_WIDTH = 170;
const INITIAL_SPACING = 12;
/** Espacio sobre la rejilla para que la píldora no se recorte cuando el pico está arriba. */
const OVERFLOW_TOP = 32;

export function LineSample({
  points,
  unit,
  periodo,
  vista,
}: {
  points: Point[];
  unit: Unit;
  periodo: string;
  vista: 'dia' | 'semana' | 'mes';
}) {
  const peak = peakIndex(points);
  const axis = axisFor(points.map((p) => p.valor), unit);
  const spacingX = LINE_SPACING[vista];
  const plotWidth = INITIAL_SPACING + spacingX * (points.length - 1) + spacingX;
  const peakX = INITIAL_SPACING + spacingX * peak;
  const flip = peakX + PILL_WIDTH > plotWidth; // no cabe a la derecha → se voltea
  const valor = `${formatNumber(points[peak].valor, DECIMALES[unit])} ${unit}`;
  const label = t('estado.historial_pico.etiqueta_grafico', { cuando: points[peak].etiqueta, valor });
  const summary = t('a11y.grafico_linea', { periodo, valor, cuando: points[peak].etiqueta });
  const missing = points.filter((p) => p.valor === null).map((p) => p.etiqueta);

  return (
    <View accessible accessibilityLabel={summary} style={{ marginTop: OVERFLOW_TOP }}>
      <LineChart
        data={points.map((p, i) => ({
          ...(p.valor === null ? {} : { value: p.valor }),
          label: p.eje ?? '',
          hideDataPoint: i !== peak,
          ...(i === peak
            ? {
                dataPointColor: colors['chart-peak'],
                dataPointRadius: 5,
                dataPointLabelComponent: () => <PeakPill texto={label} alinear={flip ? 'derecha' : 'izquierda'} />,
                dataPointLabelWidth: PILL_WIDTH,
                // gifted-charts centra la etiqueta en el punto: borde izquierdo = x − ancho/2 + desplazamiento.
                dataPointLabelShiftX: flip ? -PILL_WIDTH / 2 - 8 : PILL_WIDTH / 2 + 8,
                // overflowTop también sube la etiqueta; se compensa para dejarla justo encima del punto.
                dataPointLabelShiftY: -22 + OVERFLOW_TOP,
              }
            : {}),
        }))}
        interpolateMissingValues={false}
        overflowTop={OVERFLOW_TOP}
        curved
        thickness={2}
        color={colors['chart-series1']}
        maxValue={axis.maxValue}
        stepValue={axis.stepValue}
        noOfSections={SECTIONS}
        yAxisLabelTexts={axis.labels}
        yAxisLabelWidth={44}
        yAxisTextStyle={AXIS_TEXT}
        xAxisLabelTextStyle={AXIS_TEXT}
        rulesColor={colors['chart-grid']}
        rulesType="dashed"
        yAxisColor="transparent"
        xAxisColor={colors['chart-grid']}
        initialSpacing={INITIAL_SPACING}
        spacing={spacingX}
        endSpacing={spacingX}
        isAnimated={false}
      />
      <Text style={AXIS_TEXT}>
        {summary}
        {missing.length > 0 ? ` · ${missing.join(', ')}: ${t('comun.sin_dato')}` : ''}
        {` · píldora ${flip ? 'volteada a la izquierda' : 'a la derecha'}`}
      </Text>
    </View>
  );
}
