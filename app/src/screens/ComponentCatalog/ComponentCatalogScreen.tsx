/**
 * Catálogo interno (solo __DEV__): tokens, fuentes, íconos, formatos y la prueba mínima de
 * gráficos (PENDIENTES #11, DC-12 y DC-63).
 *
 * - Barras, línea (Día, Semana y Mes) y anillo de zonas con react-native-gifted-charts; ver
 *   chartSamples.tsx (escala, etiquetas es-CO, pico con píldora, corte en null y volteo).
 * - Arco base del medidor con react-native-svg (gifted-charts no trae medidor). Proporción
 *   de ejemplo con la regla del arco: min(potencia_kw ÷ (referencia_kw × 1,6), 1).
 *
 * No es una pantalla del producto: los rótulos son nombres técnicos (tokens, librerías) y los
 * datos son de ejemplo. Ningún componente del sistema de diseño se implementa aquí.
 */
import { useFonts } from 'expo-font';
import { Bell, ChartColumn, House, Lightbulb, Settings, Zap } from 'lucide-react-native';
import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { PieChart } from 'react-native-gifted-charts';
import Svg, { Path } from 'react-native-svg';

import { DECIMALES, formatCOP, formatNumber, formatPercent } from '@/format';
import { t } from '@/texts';
import { colors, fontFamilyFor, fontFiles, hasSatoshi, radius, spacing, typography } from '@/theme';

import { BarSample, LineSample, type Point } from './chartSamples';

type TypographyStyle = (typeof typography)[keyof typeof typography];

const pad2 = (n: number) => String(n).padStart(2, '0');
/** Día: 24 horas en kW, con pico a las 12:00. */
const DAY_KW = [0.42, 0.38, 0.35, 0.33, 0.36, 0.55, 0.9, 1.25, 1.1, 0.95, 0.88, 0.92, 3.2, 1.4, 1.05, 0.98, 1.1, 1.6, 2.1, 2.4, 1.9, 1.3, 0.8, 0.5];
const DAY_POINTS: Point[] = DAY_KW.map((valor, h) => ({ etiqueta: `${pad2(h)}:00`, valor, eje: h % 3 === 0 ? pad2(h) : '' }));
/** Línea del Día con dos horas sin lectura (15:00 y 16:00): la línea se interrumpe. */
const DAY_POINTS_GAP: Point[] = DAY_POINTS.map((p, h) => (h === 15 || h === 16 ? { ...p, valor: null } : p));
const WEEK_KEYS = ['lun', 'mar', 'mie', 'jue', 'vie', 'sab', 'dom'];
/** Semana en kWh, con pico el sábado (cerca del borde derecho). */
const WEEK_POINTS: Point[] = [18.2, 17.5, 19.1, 18.8, 21.3, 28.4, 22.0].map((valor, i) => {
  const dia = t(`formato.dia_corto.${WEEK_KEYS[i]}`);
  return { etiqueta: dia, valor, eje: dia };
});
/** Mes de 30 días en kWh, con pico el día 28 (cerca del borde derecho). */
const MONTH_POINTS: Point[] = Array.from({ length: 30 }, (_, i) => {
  const dia = i + 1;
  const valor = dia === 28 ? 28 : 16 + ((dia * 7) % 9) * 0.9;
  return { etiqueta: t('formato.tiempo.fecha', { dd: pad2(dia), mm: '11' }), valor, eje: dia % 5 === 0 ? String(dia) : '' };
});
const SAMPLE_ZONES = [
  { value: 38, color: colors['chart-series1'] },
  { value: 24, color: colors['chart-series2'] },
  { value: 18, color: colors['chart-series3'] },
  { value: 12, color: colors['chart-series4'] },
  { value: 8, color: colors['chart-series5'] },
];
const SAMPLE_POWER_KW = 2.4;
const SAMPLE_REFERENCE_KW = 2.5;
const ICONS = { House, ChartColumn, Zap, Lightbulb, Settings, Bell };

function textStyle(style: TypographyStyle) {
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    lineHeight: 'lineHeight' in style ? style.lineHeight : undefined,
    color: colors['text-primary'],
  };
}

/** Semicírculo de izquierda a derecha; `fraction` entre 0 y 1. */
function arcPath(cx: number, cy: number, r: number, fraction: number): string {
  const angle = Math.PI * (1 - Math.min(Math.max(fraction, 0), 1));
  const x = cx + r * Math.cos(angle);
  const y = cy - r * Math.sin(angle);
  return `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${x} ${y}`;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={[textStyle(typography['ui-s-semibold']), styles.sectionTitle]}>{title}</Text>
      {children}
    </View>
  );
}

export function ComponentCatalogScreen() {
  const [fontsLoaded] = useFonts(fontFiles);
  const arcFraction = Math.min(SAMPLE_POWER_KW / (SAMPLE_REFERENCE_KW * 1.6), 1);

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Section title="theme.colors">
        <View style={styles.swatches}>
          {Object.entries(colors).map(([name, value]) => (
            <View key={name} style={[styles.swatch, { backgroundColor: value }]} accessibilityLabel={name} />
          ))}
        </View>
      </Section>

      <Section title={`theme.typography · fuentes ${fontsLoaded ? 'cargadas' : 'cargando'} · Satoshi ${hasSatoshi ? 'sí' : 'no (Inter Bold)'}`}>
        {Object.entries(typography).map(([name, style]) => (
          <Text key={name} style={textStyle(style)}>
            {name}
          </Text>
        ))}
      </Section>

      <Section title="lucide-react-native">
        <View style={styles.row}>
          {Object.entries(ICONS).map(([name, Icon]) => (
            <Icon key={name} color={colors['accent-primary']} size={24} accessibilityLabel={name} />
          ))}
        </View>
      </Section>

      <Section title="format (RN-XII-08)">
        <Text style={textStyle(typography['data-s-16'])}>
          {[
            `${formatNumber(SAMPLE_POWER_KW, DECIMALES.kW)} kW`,
            `${formatNumber(145.3, DECIMALES.kWh)} kWh`,
            formatCOP(14400),
            formatCOP(6500, { abreviar: true }),
            formatPercent(34),
          ].join(' · ')}
        </Text>
      </Section>

      <Section title="react-native-gifted-charts · BarChart (Día, kW)">
        <BarSample points={DAY_POINTS} unit="kW" periodo={t('formato.periodo.dia')} />
      </Section>

      <Section title="react-native-gifted-charts · LineChart (Día, kW, sin lectura 15:00 y 16:00)">
        <LineSample points={DAY_POINTS_GAP} unit="kW" periodo={t('formato.periodo.dia')} vista="dia" />
      </Section>

      <Section title="react-native-gifted-charts · LineChart (Semana, kWh)">
        <LineSample points={WEEK_POINTS} unit="kWh" periodo={t('formato.periodo.semana')} vista="semana" />
      </Section>

      <Section title="react-native-gifted-charts · LineChart (Mes, kWh)">
        <LineSample points={MONTH_POINTS} unit="kWh" periodo={t('formato.periodo.mes')} vista="mes" />
      </Section>

      <Section title="react-native-gifted-charts · PieChart (anillo de zonas)">
        <PieChart data={SAMPLE_ZONES} donut radius={80} innerRadius={52} innerCircleColor={colors['background-surface']} />
      </Section>

      <Section title={`react-native-svg · arco base (${formatPercent(arcFraction * 100)})`}>
        <Svg width={200} height={110} accessibilityLabel={`Arco al ${formatPercent(arcFraction * 100)}`}>
          <Path d={arcPath(100, 100, 80, 1)} stroke={colors['chart-grid']} strokeWidth={14} fill="none" strokeLinecap="round" />
          <Path d={arcPath(100, 100, 80, arcFraction)} stroke={colors['accent-primary']} strokeWidth={14} fill="none" strokeLinecap="round" />
        </Svg>
      </Section>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors['background-default'] },
  content: { padding: spacing['16'], gap: spacing['24'] },
  section: {
    gap: spacing['8'],
    padding: spacing['16'],
    borderRadius: radius.lg,
    backgroundColor: colors['background-surface'],
  },
  sectionTitle: { color: colors['text-muted'] },
  swatches: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing['4'] },
  swatch: { width: 24, height: 24, borderRadius: radius.xs },
  row: { flexDirection: 'row', gap: spacing['16'] },
});
