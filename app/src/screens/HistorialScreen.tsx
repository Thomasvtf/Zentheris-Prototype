/**
 * Historial (reglas v4.9 §6.5 y §7.3; RN-XIII-01 a RN-XIII-07).
 * Datos: useHistorialData (fila 30 de docs/MAPA-DE-INTEGRACION.md, obtenerHistorial).
 *
 * - Botones Día · Semana · Mes cambian todas las cards (RN-XIII-02); sin flechas ni calendario.
 * - Cards: Pico del periodo, Consumo (barras, línea o anillo; selector de unidad y filtro por
 *   zona), Comparación y Costo estimado; botón Ver consejos.
 * - Pico (RN-XIII-03): el gráfico marca `es_pico_maximo` con `chart-peak` y la etiqueta
 *   «Pico», sin componentes ni palabras de estado; la card de Pico muestra su estado en texto.
 * - Anillo solo con General; más de 4 zonas → 4 + «Otras zonas»; la lista muestra todas
 *   (RN-XIII-04). Colores de zona, nunca rojo ni amarillo (ZoneDonutChart).
 * - Unidades (RN-XIII-06): Día por hora en kW; Semana y Mes por día en kWh; totales en kWh.
 * - Estados: cargando (Skeleton), error (InlineNotice + Reintentar), sin permiso
 *   (StateMessage; encabezado y selector visibles), vacío (sin lecturas en el periodo),
 *   falta la última hora, sin tarifa (sin COP y card «Configura tu tarifa») y sin periodo
 *   anterior («—» y estado neutro).
 * - Colores, espacios y tipografía desde @/theme; textos con t(); cifras con @/format.
 *
 * - Barras, línea y anillo: src/components/charts/ (SVG a mano, DC-63: gifted-charts no deja
 *   fijar las etiquetas del eje X ni contener la píldora del pico). Aquí solo se arman sus datos.
 *
 * TODO(pendiente: componentes del sistema de diseño): src/components/ aún no tiene
 * PeakMarker, StatusBadge, Chip, Skeleton, StateMessage, InlineNotice ni ScreenHeader con
 * las props de index.d.ts. Aquí son piezas locales de presentación para moverlas a
 * src/components/ cuando se apruebe.
 * TODO(pendiente: formato de fechas): @/format solo trae relativeTime; las etiquetas de hora,
 * día y fecha se arman aquí con las plantillas del catálogo (formato.dia_corto.*,
 * formato.dia.*, formato.tiempo.fecha) hasta tener un helper en @/format.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AccessibilityInfo,
  Animated,
  LayoutChangeEvent,
  Pressable,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextStyle,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import {
  Bath,
  Bed,
  CalendarDays,
  Car,
  ChartColumn,
  ChartPie,
  ChartSpline,
  CircleAlert,
  CircleCheck,
  CircleX,
  Clock,
  Coins,
  CookingPot,
  DoorClosed,
  Fence,
  Info,
  MapPin,
  Monitor,
  Shield,
  Sofa,
  TrendingUp,
  TriangleAlert,
  WashingMachine,
  Zap,
} from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';

import { BarChart, LineChart } from '@/components/charts/SeriesChart';
import type { SeriesDatum, XLabel } from '@/components/charts/SeriesChart';
import { CHART_HEIGHT, xLabelIndexes } from '@/components/charts/chartGeometry';
import { groupZones, ZoneDonutChart } from '@/components/charts/ZoneDonutChart';
import type { DonutZone, ZoneDonutChartProps } from '@/components/charts/ZoneDonutChart';
import { DECIMALES, formatCOP, formatNumber, formatPercent } from '@/format';
import { colors, fontFamilyFor, radius, sizes, spacing, typography } from '@/theme';
import { t } from '@/texts';

import { isEmptyHistory, isMissingLastHour, useHistorialData } from './useHistorialData';
import type {
  ConsumptionState,
  History,
  HistorialMockScenario,
  Period,
  SeriesPoint,
  ZoneOption,
  ZoneShare,
} from './useHistorialData';

/* ───────────────────────────── Utilidades ───────────────────────────────── */

type Severity = 'normal' | 'elevado' | 'critico';
type ChartView = 'barras' | 'linea' | 'anillo';
/** Unidad del gráfico: energía del periodo (kW en Día, kWh en Semana y Mes) o COP. */
type ChartUnit = 'energia' | 'COP';

const PERIODS: Period[] = ['dia', 'semana', 'mes'];

function textStyle(name: keyof typeof typography): TextStyle {
  const style = typography[name];
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    ...('lineHeight' in style ? { lineHeight: style.lineHeight } : {}),
  };
}

function isSeverity(estado: ConsumptionState): estado is Severity {
  return estado === 'normal' || estado === 'elevado' || estado === 'critico';
}

/* Fechas en hora de Bogotá (UTC−5, sin horario de verano), con plantillas del catálogo. */
const BOGOTA_OFFSET_MS = -5 * 60 * 60 * 1000;
const DAY_KEYS = ['dom', 'lun', 'mar', 'mie', 'jue', 'vie', 'sab'] as const;

function local(iso: string, shiftMs = 0): Date {
  return new Date(new Date(iso).getTime() + BOGOTA_OFFSET_MS + shiftMs);
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

/** «14:00». */
function hourLabel(iso: string): string {
  return `${pad2(local(iso).getUTCHours())}:00`;
}

/** «15/07» (formato.tiempo.fecha). */
function dateLabel(iso: string, shiftMs = 0): string {
  const d = local(iso, shiftMs);
  return t('formato.tiempo.fecha', { dd: pad2(d.getUTCDate()), mm: pad2(d.getUTCMonth() + 1) });
}

/** «Lun» (formato.dia_corto.*). */
function shortDay(iso: string, shiftMs = 0): string {
  return t(`formato.dia_corto.${DAY_KEYS[local(iso, shiftMs).getUTCDay()]}`);
}

/** Tramo del periodo para los títulos: «00:00–15:00», «Lun–Mié», «01/07–18/07». */
function tramoLabel(data: History): string {
  if (data.periodo === 'dia') return `${hourLabel(data.inicio)}–${hourLabel(data.fin)}`;
  if (data.periodo === 'semana') return `${shortDay(data.inicio)}–${shortDay(data.fin, -1)}`;
  return `${dateLabel(data.inicio)}–${dateLabel(data.fin, -1)}`;
}

/** Momento de un punto: hora en Día, día corto en Semana, fecha en Mes. */
function pointWhen(periodo: Period, point: { inicio: string }): string {
  if (periodo === 'dia') return hourLabel(point.inicio);
  if (periodo === 'semana') return shortDay(point.inicio);
  return dateLabel(point.inicio);
}

/** «Último pico: 11:00–12:00 · sábado · 15/07». */
function peakWhen(periodo: Period, peak: { inicio: string; fin: string }): string {
  if (periodo === 'dia') return `${hourLabel(peak.inicio)}–${hourLabel(peak.fin)}`;
  if (periodo === 'semana') return t(`formato.dia.${DAY_KEYS[local(peak.inicio).getUTCDay()]}`);
  return dateLabel(peak.inicio);
}

/** Texto de la unidad de energía: kW por hora en Día, kWh por día (RN-XIII-06). */
function energyUnitKey(periodo: Period): 'comun.kw' | 'comun.kwh' {
  return periodo === 'dia' ? 'comun.kw' : 'comun.kwh';
}

function energyText(v: number | null, periodo: Period): string {
  if (v === null) return formatNumber(null);
  const dec = periodo === 'dia' ? DECIMALES.kW : DECIMALES.kWh;
  return `${formatNumber(v, dec)} ${t(energyUnitKey(periodo))}`;
}

function kwhText(v: number | null): string {
  return v === null ? formatNumber(null) : `${formatNumber(v, DECIMALES.kWh)} ${t('comun.kwh')}`;
}

/** Colores de severidad desde los tokens; los estados sin severidad van en neutro. */
function stateTokens(estado: ConsumptionState) {
  switch (estado) {
    case 'normal':
      return { bg: colors['status-success-bg'], border: colors['status-success-border'], text: colors['status-success-text'], icon: colors['status-success-default'], Glyph: CircleCheck };
    case 'elevado':
      return { bg: colors['status-warning-bg'], border: colors['status-warning-border'], text: colors['status-warning-text'], icon: colors['status-warning-default'], Glyph: TriangleAlert };
    case 'critico':
      return { bg: colors['status-error-bg'], border: colors['status-error-border'], text: colors['text-error'], icon: colors['status-error-default'], Glyph: CircleAlert };
    default:
      return { bg: colors['background-surfaceAlt'], border: colors['border-subtle'], text: colors['text-muted'], icon: colors['text-muted'], Glyph: estado === 'sin_datos' ? Clock : Info };
  }
}

const ZONE_TYPES = ['bano', 'cocina', 'cuarto_servicio', 'dormitorio', 'garaje', 'lavanderia', 'oficina', 'sala', 'terraza'] as const;
const ZONE_ICONS: Record<(typeof ZONE_TYPES)[number], LucideIcon> = {
  bano: Bath,
  cocina: CookingPot,
  cuarto_servicio: DoorClosed,
  dormitorio: Bed,
  garaje: Car,
  lavanderia: WashingMachine,
  oficina: Monitor,
  sala: Sofa,
  terraza: Fence,
};

/** Ícono por nombre de zona (el contrato del historial trae `nombre`, no `tipo`). */
function zoneIcon(nombre: string): LucideIcon {
  const tipo = ZONE_TYPES.find((z) => t(`zona.${z}`) === nombre);
  return tipo ? ZONE_ICONS[tipo] : MapPin;
}

/* ─────────────────────── Piezas de presentación ─────────────────────────── */

function StatusBadge({ estado }: { estado: Severity }) {
  const tk = stateTokens(estado);
  return (
    <View style={[styles.badge, { backgroundColor: tk.bg, borderColor: tk.border }]}>
      <Text style={[styles.badgeText, { color: tk.text }]}>{t(`estado.palabra.${estado}`)}</Text>
    </View>
  );
}

function StateBlock({ estado, titulo, cuerpo }: { estado: ConsumptionState; titulo: string; cuerpo?: string }) {
  const tk = stateTokens(estado);
  return (
    <View style={[styles.stateBlock, { backgroundColor: tk.bg, borderColor: tk.border }]}>
      <tk.Glyph size={16} color={tk.icon} />
      <View style={styles.flex}>
        <Text style={[styles.stateBlockTitle, { color: tk.text }]}>{titulo}</Text>
        {cuerpo ? <Text style={styles.mutedXs}>{cuerpo}</Text> : null}
      </View>
    </View>
  );
}

function Chip({ activo, icono: Icono, onPress, children }: { activo: boolean; icono: LucideIcon; onPress: () => void; children: string }) {
  const color = activo ? colors['text-accent'] : colors['text-muted'];
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ checked: activo }}
      hitSlop={spacing['8']}
      style={[styles.chip, activo && styles.chipActive]}
    >
      <Icono size={20} color={color} />
      <Text style={[styles.chipText, { color }]}>{children}</Text>
    </Pressable>
  );
}

function ViewToggle({ activo, icono: Icono, onPress }: { activo: boolean; icono: LucideIcon; onPress: () => void }) {
  return (
    // TODO(pendiente: a11y): el catálogo no tiene etiquetas para «ver barras/línea/anillo».
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: activo }}
      style={[styles.iconButton, activo && styles.iconButtonActive]}
    >
      <Icono size={20} color={activo ? colors['accent-primary'] : colors['text-muted']} />
    </Pressable>
  );
}

function CardHeader({ icono: Icono, titulo, estado }: { icono: LucideIcon; titulo: string; estado?: ConsumptionState }) {
  return (
    <View style={styles.cardHeaderRow}>
      <View style={styles.cardIcon}>
        <Icono size={24} color={colors['accent-primary']} />
      </View>
      <Text style={[styles.cardTitle, styles.flex]}>{titulo}</Text>
      {estado && isSeverity(estado) ? <StatusBadge estado={estado} /> : null}
    </View>
  );
}

function Metric({ value, unit, size = 'xl' }: { value: string; unit: string; size?: 'xl' | 'l' }) {
  return (
    <View style={styles.metricRow}>
      <Text style={size === 'xl' ? styles.metricValue : styles.metricValueL} adjustsFontSizeToFit numberOfLines={1}>
        {value}
      </Text>
      {unit ? <Text style={styles.metricUnit}>{unit}</Text> : null}
    </View>
  );
}

function StateMessage({ icono: Icono, titulo, descripcion, accion, onAccion }: { icono: LucideIcon; titulo: string; descripcion?: string; accion?: string; onAccion?: () => void }) {
  return (
    <View style={[styles.card, styles.stateMessage]}>
      <Icono size={32} color={colors['text-muted']} />
      <View style={styles.flex}>
        <Text style={styles.stateMessageTitle}>{titulo}</Text>
        {descripcion ? <Text style={styles.mutedXs}>{descripcion}</Text> : null}
        {accion && onAccion ? (
          <Pressable onPress={onAccion} accessibilityRole="link" hitSlop={spacing['12']} style={styles.linkTouch}>
            <Text style={styles.linkText}>{accion}</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

function InlineNotice({ tono, titulo, descripcion, onReintentar }: { tono: 'error' | 'informacion'; titulo: string; descripcion?: string; onReintentar?: () => void }) {
  const isError = tono === 'error';
  const Glyph = isError ? CircleX : Info;
  return (
    <View
      style={[
        styles.notice,
        isError
          ? { backgroundColor: colors['status-error-bg'], borderColor: colors['status-error-border'] }
          : { backgroundColor: colors['status-info-bg'], borderColor: colors['border-subtle'] },
      ]}
      accessibilityRole={isError ? 'alert' : 'summary'}
    >
      <View style={styles.noticeRow}>
        <Glyph size={16} color={isError ? colors['status-error-default'] : colors['status-info-default']} />
        <View style={styles.flex}>
          <Text style={[styles.stateBlockTitle, { color: isError ? colors['status-error-text'] : colors['text-primary'] }]}>{titulo}</Text>
          {descripcion ? <Text style={styles.mutedXs}>{descripcion}</Text> : null}
        </View>
      </View>
      {onReintentar ? (
        <Pressable onPress={onReintentar} accessibilityRole="button" hitSlop={spacing['12']} style={styles.noticeAction}>
          <Text style={styles.linkText}>{t('comun.reintentar')}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

/** Pulso suave; se detiene con «reducir movimiento» (ficha Skeleton). */
function useSkeletonPulse() {
  const opacity = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    let loop: Animated.CompositeAnimation | null = null;
    let cancelled = false;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((reduce) => {
        if (cancelled || reduce) return;
        loop = Animated.loop(
          Animated.sequence([
            Animated.timing(opacity, { toValue: 0.5, duration: 700, useNativeDriver: true }),
            Animated.timing(opacity, { toValue: 1, duration: 700, useNativeDriver: true }),
          ]),
        );
        loop.start();
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      loop?.stop();
    };
  }, [opacity]);
  return opacity;
}

function Skeleton({ tamano = 'estandar' }: { tamano?: 'estandar' | 'grafico' }) {
  const opacity = useSkeletonPulse();
  return (
    <Animated.View style={[styles.card, { opacity }]} accessible accessibilityLabel={t('comun.cargando')}>
      <View style={styles.cardHeaderRow}>
        <View style={[styles.skeletonBlock, styles.skeletonIcon]} />
        <View style={[styles.skeletonBlock, styles.skeletonLine, styles.flex]} />
      </View>
      {tamano === 'grafico' ? (
        <View style={[styles.skeletonBlock, styles.skeletonChart]} />
      ) : (
        <>
          <View style={[styles.skeletonBlock, styles.skeletonValue]} />
          <View style={[styles.skeletonBlock, styles.skeletonStateBlock]} />
        </>
      )}
    </Animated.View>
  );
}

/* ──────────────────── Gráficos: modelos para los componentes ──────────────────── */

const DAY_MS = 24 * 60 * 60 * 1000;
/** Slots del eje X: 24 horas en Día y 7 días en Semana, aunque aún no haya datos; en Mes, los días con dato. */
const FIXED_SLOTS: Partial<Record<Period, number>> = { dia: 24, semana: 7 };

/** «11h» (eje X de Día y píldora del pico). */
// TODO(pendiente: texto): el catálogo no trae la marca de hora corta «{hh}h» (ficha BarChart, Figma).
function hourMark(hour: number): string {
  return `${pad2(hour)}h`;
}

/** Momento de un punto en el gráfico: «11h» en Día, «Mar» en Semana, «06/11» en Mes. */
function chartWhen(periodo: Period, point: { inicio: string }): string {
  return periodo === 'dia' ? hourMark(local(point.inicio).getUTCHours()) : pointWhen(periodo, point);
}

function unitText(unit: ChartUnit, periodo: Period): string {
  return unit === 'COP' ? t('comun.cop') : t(energyUnitKey(periodo));
}

/** Valor con su unidad para la píldora y el resumen: «0,48 kW», «7,0 kWh», «$14.400». */
function seriesValueText(v: number | null, unit: ChartUnit, periodo: Period): string {
  if (unit === 'COP') return formatCOP(v);
  if (v === null) return formatNumber(null);
  return `${formatNumber(v, periodo === 'dia' ? DECIMALES.kW : DECIMALES.kWh)} ${t(energyUnitKey(periodo))}`;
}

/** Etiqueta de un valor del eje Y: decimales mínimos que no repiten etiquetas («0,2»); COP abreviado. */
function tickFormatter(unit: ChartUnit) {
  return (v: number, decimals: number) => (unit === 'COP' ? formatCOP(v, { abreviar: true }) : formatNumber(v, decimals));
}

interface SeriesModel {
  datos: SeriesDatum[];
  xLabels: XLabel[];
  etiquetaPico: string | null;
  resumen: string;
}

function toSeriesModel(data: History, unit: ChartUnit, kind: 'barras' | 'linea'): SeriesModel {
  const { periodo, serie } = data;
  const slots = FIXED_SLOTS[periodo] ?? Math.max(serie.length, 1);
  const valueOf = (p: SeriesPoint) => (unit === 'COP' ? p.costo_cop : p.energia_kwh);
  const datos: SeriesDatum[] = Array.from({ length: slots }, (_, i) => {
    const p = serie[i];
    return p ? { valor: valueOf(p), pico: p.es_pico_maximo } : { valor: null, pico: false };
  });

  // Semana y Mes: el nombre o la fecha del slot sale del primer punto (también donde aún no hay dato).
  const base = serie[0]?.inicio ?? data.inicio;
  const xLabels: XLabel[] = xLabelIndexes(periodo, slots).map((index) => ({
    index,
    texto:
      periodo === 'dia'
        ? hourMark(index)
        : periodo === 'semana'
          ? shortDay(base, index * DAY_MS)
          : dateLabel(base, index * DAY_MS),
    posicion: periodo === 'dia' ? 'borde' : 'centro',
  }));

  const peakPoint = serie.find((p) => p.es_pico_maximo && valueOf(p) !== null);
  const periodoText = t(`formato.periodo.${periodo}`);
  let etiquetaPico: string | null = null;
  let resumen = t('a11y.grafico_sin_pico', { periodo: periodoText });
  if (peakPoint) {
    const cuando = chartWhen(periodo, peakPoint);
    const valor = seriesValueText(valueOf(peakPoint), unit, periodo);
    etiquetaPico = t('estado.historial_pico.etiqueta_grafico', { cuando, valor });
    resumen = t(kind === 'barras' ? 'a11y.grafico_barras' : 'a11y.grafico_linea', { periodo: periodoText, valor, cuando });
  }
  return { datos, xLabels, etiquetaPico, resumen };
}

/** Promedio histórico del pico (contrato) como línea de referencia; solo en energía, no hay equivalente en COP. */
function referenceFor(data: History, unit: ChartUnit): number | null {
  return unit === 'COP' || !data.ultimo_pico ? null : data.ultimo_pico.promedio_historico_kwh;
}

function toDonutProps(data: History, zonas: ZoneShare[], unit: ChartUnit, ancho: number): ZoneDonutChartProps {
  // Totales de periodo en kWh (RN-XIII-06). En COP, el contrato no trae costo por zona:
  // TODO(pendiente: costo por zona) se reparte el costo del periodo según la participación en kWh.
  const costs = data.serie.map((p) => p.costo_cop);
  const totalCost = costs.every((c) => c === null) ? null : costs.reduce<number>((sum, c) => sum + (c ?? 0), 0);
  const money = (kwhPct: number) => formatCOP(totalCost === null ? null : (totalCost * kwhPct) / 100, { abreviar: true });
  const valueOf = (z: ZoneShare) => (unit === 'COP' ? money(z.participacion_pct) : kwhText(z.energia_kwh));

  const toZone = (z: ZoneShare): DonutZone => ({
    id: z.zona_id,
    nombre: z.nombre,
    participacion: z.participacion_pct,
    valorTexto: valueOf(z),
    pctTexto: formatPercent(z.participacion_pct),
  });
  const donutZones = zonas.map(toZone);
  const { top, rest } = groupZones(donutZones);
  const restPct = rest.reduce((sum, z) => sum + z.participacion, 0);
  const restKwh = zonas.filter((z) => rest.some((r) => r.id === z.zona_id)).reduce((sum, z) => sum + z.energia_kwh, 0);
  const main = top[0];

  const summaryZones = [
    ...top.map((z) => `${z.nombre} ${z.pctTexto}`),
    ...(rest.length > 0
      ? [`${t('historial.anillo_otras')} ${formatPercent(restPct)} (${rest.map((z) => `${z.nombre} ${z.pctTexto}`).join(', ')})`]
      : []),
  ].join(', ');

  return {
    zonas: donutZones,
    totalValor: unit === 'COP' ? formatCOP(totalCost, { abreviar: true }) : formatNumber(data.total_kwh, DECIMALES.kWh),
    totalUnidad: unit === 'COP' ? '' : t('comun.kwh'),
    totalEtiqueta: t(`historial.anillo_total_${data.periodo}`),
    otras: {
      nombre: t('historial.anillo_otras'),
      valorTexto: unit === 'COP' ? money(restPct) : kwhText(restKwh),
      pctTexto: formatPercent(restPct),
    },
    destacado: main ? [main.nombre, main.valorTexto, main.pctTexto].join(' · ') : '',
    ancho,
    resumen: t('a11y.grafico_anillo', { periodo: t(`formato.periodo.${data.periodo}`), zonas: summaryZones }),
  };
}

/* ─────────────────────────────── Cards ──────────────────────────────────── */

/** Card Pico del periodo (RN-XIII-03): estado en texto, nunca con el color del pico. */
function PeakCard({ data }: { data: History }) {
  const peak = data.ultimo_pico;
  const title = t(`historial.pico_${data.periodo}`);
  if (!peak) {
    return (
      <View style={styles.card}>
        <CardHeader icono={TrendingUp} titulo={title} />
        <StateBlock estado="sin_datos" titulo={t('estado.historial_pico.ninguno.titulo')} cuerpo={t('estado.historial_pico.ninguno.cuerpo')} />
      </View>
    );
  }
  const dec = data.periodo === 'dia' ? DECIMALES.kW : DECIMALES.kWh;
  return (
    <View style={styles.card}>
      <CardHeader icono={TrendingUp} titulo={title} estado={peak.estado} />
      <View>
        <Metric value={formatNumber(peak.energia_kwh, dec)} unit={t(energyUnitKey(data.periodo))} />
        <Text style={styles.mutedXs}>{t('estado.historial_pico.ultimo', { cuando: peakWhen(data.periodo, peak) })}</Text>
      </View>
      <View style={styles.divider} />
      <StateBlock
        estado={peak.estado}
        titulo={isSeverity(peak.estado) ? t(`estado.historial_pico.${peak.estado}.titulo`) : t(`estado.palabra.${peak.estado}`)}
        cuerpo={t(data.periodo === 'dia' ? 'estado.historial_pico.cuerpo.dia' : 'estado.historial_pico.cuerpo.periodo')}
      />
    </View>
  );
}

interface ConsumptionCardProps {
  data: History;
  zones: ZoneOption[];
  zonaId: string | null;
  onZona: (id: string | null) => void;
}

/** Card Consumo: barras, línea o anillo (solo General), unidad y filtro por zona (RN-XIII-04). */
function ConsumptionChartCard({ data, zones, zonaId, onZona }: ConsumptionCardProps) {
  const [view, setView] = useState<ChartView>('barras');
  const [unitChoice, setUnitChoice] = useState<ChartUnit>('energia');
  const [width, setWidth] = useState(0);

  const general = zonaId === null;
  const effectiveView: ChartView = view === 'anillo' && (!general || !data.participacion_zonas) ? 'barras' : view;
  // COP solo con tarifa vigente (RN-XIII-05); el selector se ve también con el anillo.
  const unit: ChartUnit = data.tarifa_vigente ? unitChoice : 'energia';
  const empty = isEmptyHistory(data);
  const model = useMemo(() => toSeriesModel(data, unit, effectiveView === 'linea' ? 'linea' : 'barras'), [data, unit, effectiveView]);
  const sortedZones = useMemo(() => [...zones].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es')), [zones]);

  const tramo = tramoLabel(data);
  const title =
    effectiveView === 'anillo'
      ? t('historial.anillo_titulo', { periodo: t(`formato.periodo.${data.periodo}`), tramo })
      : t(`historial.consumo_${data.periodo}`, { tramo });

  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);

  return (
    <View style={styles.card}>
      <View style={styles.cardHeaderRow}>
        <Text style={[styles.cardTitle, styles.flex]}>{title}</Text>
        {!empty && (
          <View style={styles.toggleRow}>
            <ViewToggle activo={effectiveView === 'barras'} icono={ChartColumn} onPress={() => setView('barras')} />
            <ViewToggle activo={effectiveView === 'linea'} icono={ChartSpline} onPress={() => setView('linea')} />
            {general && data.participacion_zonas ? (
              <ViewToggle activo={effectiveView === 'anillo'} icono={ChartPie} onPress={() => setView('anillo')} />
            ) : null}
          </View>
        )}
      </View>

      <View testID="historial-grafico" onLayout={onLayout}>
        {empty ? (
          <View style={styles.emptyChart}>
            <Clock size={32} color={colors['text-muted']} />
            {/* TODO(pendiente: texto): el catálogo no trae «Sin datos para este periodo» (BarChart.md). */}
            <Text style={styles.stateMessageTitle}>{t('estado.palabra.sin_datos')}</Text>
          </View>
        ) : width > 0 ? (
          effectiveView === 'anillo' && data.participacion_zonas ? (
            <ZoneDonutChart {...toDonutProps(data, data.participacion_zonas, unit, width)} />
          ) : effectiveView === 'linea' ? (
            <LineChart
              ancho={width}
              datos={model.datos}
              unidad={unitText(unit, data.periodo)}
              formatTick={tickFormatter(unit)}
              etiquetaPico={model.etiquetaPico}
              xLabels={model.xLabels}
              resumen={model.resumen}
              referencia={referenceFor(data, unit)}
            />
          ) : (
            <BarChart
              ancho={width}
              datos={model.datos}
              unidad={unitText(unit, data.periodo)}
              formatTick={tickFormatter(unit)}
              etiquetaPico={model.etiquetaPico}
              xLabels={model.xLabels}
              resumen={model.resumen}
            />
          )
        ) : null}
      </View>

      {!empty && (
        <View style={styles.chipRow} accessibilityRole="radiogroup">
          <Chip activo={unit === 'energia'} icono={Zap} onPress={() => setUnitChoice('energia')}>
            {t(energyUnitKey(data.periodo))}
          </Chip>
          {data.tarifa_vigente && (
            <Chip activo={unit === 'COP'} icono={Coins} onPress={() => setUnitChoice('COP')}>
              {t('comun.cop')}
            </Chip>
          )}
        </View>
      )}

      {sortedZones.length > 0 && (
        <View style={styles.filterBlock}>
          <Text style={styles.filterLabel}>{t('historial.filtrar_zona')}</Text>
          <View style={styles.chipWrap} accessibilityRole="radiogroup">
            <Chip activo={general} icono={CalendarDays} onPress={() => onZona(null)}>
              {t('comun.general')}
            </Chip>
            {sortedZones.map((z) => (
              <Chip key={z.zona_id} activo={zonaId === z.zona_id} icono={zoneIcon(z.nombre)} onPress={() => onZona(z.zona_id)}>
                {z.nombre}
              </Chip>
            ))}
          </View>
        </View>
      )}
    </View>
  );
}

/** Card Comparación (RN-XIII-01): mismo tramo del periodo anterior; sin anterior → «—». */
function ComparisonCard({ data }: { data: History }) {
  const c = data.comparacion;
  const tramo = tramoLabel(data);
  return (
    <View style={styles.card}>
      <CardHeader icono={CalendarDays} titulo={t(`historial.comparacion_${data.periodo}`, { tramo })} estado={c.estado} />
      <View style={styles.compareRow}>
        <View style={styles.flex}>
          <Text style={styles.compareLabel}>{t('historial.este_periodo')}</Text>
          <Metric value={formatNumber(c.actual_kwh, DECIMALES.kWh)} unit={t('comun.kwh')} size="l" />
        </View>
        <View style={styles.compareDivider} />
        <View style={styles.flex}>
          <Text style={styles.compareLabel}>{t('historial.periodo_anterior')}</Text>
          <Metric value={formatNumber(c.anterior_kwh, DECIMALES.kWh)} unit={t('comun.kwh')} size="l" />
        </View>
      </View>
      <View style={styles.divider} />
      <StateBlock
        estado={c.estado}
        titulo={c.mensaje_codigo ? t(`estado.${c.mensaje_codigo}.titulo`) : t(`estado.palabra.${c.estado}`)}
        cuerpo={c.mensaje_codigo ? t(`estado.${c.mensaje_codigo}.cuerpo`) : undefined}
      />
    </View>
  );
}

/** Card Costo estimado (RN-XIII-05; §7.3 «Sin tarifa»): sin barra de progreso. */
function CostCard({ data, onConfigureTariff }: { data: History; onConfigureTariff: () => void }) {
  if (!data.tarifa_vigente) {
    return (
      <StateMessage
        icono={Coins}
        titulo={t('estado.historial_costo.sin_tarifa.titulo')}
        descripcion={t('estado.historial_costo.sin_tarifa.cuerpo')}
        accion={t('comun.configurar_tarifa')}
        onAccion={onConfigureTariff}
      />
    );
  }
  const c = data.costo;
  // El costo sigue el código de la comparación (contrato, opción A): historial_comparacion.<x>.
  const suffix = c.mensaje_codigo?.split('.').pop();
  const projection = c.incluye_cargo_fijo
    ? t('historial.proyeccion_mes', { valor: formatCOP(c.proyeccion_cierre_cop) })
    : t('historial.proyeccion', { periodo_cierre: t(`formato.cierre.${data.periodo}`), valor: formatCOP(c.proyeccion_cierre_cop) });
  return (
    <View style={styles.card}>
      <CardHeader icono={Coins} titulo={t(`historial.costo_${data.periodo}`)} estado={c.estado} />
      <View>
        <Metric value={formatCOP(c.costo_cop)} unit={c.costo_cop === null ? '' : t('comun.cop')} />
        <Text style={styles.mutedXs}>{projection}</Text>
      </View>
      <View style={styles.divider} />
      <StateBlock
        estado={c.estado}
        titulo={suffix ? t(`estado.historial_costo.${suffix}.titulo`) : t(`estado.palabra.${c.estado}`)}
        cuerpo={suffix ? t(`estado.historial_costo.${suffix}.cuerpo`) : undefined}
      />
    </View>
  );
}

/* ─────────────────────────────── Pantalla ───────────────────────────────── */

export interface HistorialScreenProps {
  /** TODO(pendiente: hogarId): vendrá del estado de sesión/hogar (fila 12 del mapa). */
  hogarId?: string | null;
  /** Solo desarrollo: fuerza un escenario del modo de ejemplo. */
  mockScenario?: HistorialMockScenario;
}

export function HistorialScreen({ hogarId = null, mockScenario }: HistorialScreenProps) {
  const router = useRouter();
  const [periodo, setPeriodo] = useState<Period>('dia');
  const [zonaId, setZonaId] = useState<string | null>(null);
  const { state, zones, retry, refresh, refreshing } = useHistorialData(hogarId, periodo, zonaId, { mockScenario });

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <StatusBar barStyle="light-content" backgroundColor={colors['background-default']} />
      <View style={styles.header}>
        <Text style={styles.headerTitle} accessibilityRole="header">
          {t('historial.encabezado')}
        </Text>
      </View>

      <ScrollView
        style={styles.flex}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            tintColor={colors['accent-primary']}
            colors={[colors['accent-primary']]}
            progressBackgroundColor={colors['background-surface']}
          />
        }
      >
        <View style={styles.periodRow} accessibilityRole="radiogroup">
          {PERIODS.map((p) => (
            <Chip key={p} activo={periodo === p} icono={CalendarDays} onPress={() => setPeriodo(p)}>
              {t(`formato.periodo.${p}`)}
            </Chip>
          ))}
        </View>

        {state.status === 'loading' && (
          <>
            <Skeleton />
            <Skeleton tamano="grafico" />
            <Skeleton />
            <Skeleton />
          </>
        )}

        {state.status === 'error' && (
          <InlineNotice tono="error" titulo={t(`${state.errorKey}.titulo`)} descripcion={t(`${state.errorKey}.cuerpo`)} onReintentar={retry} />
        )}

        {state.status === 'forbidden' && (
          <StateMessage icono={Shield} titulo={t('error.sin_permiso_ver_historial.titulo')} descripcion={t('error.sin_permiso_ver_historial.cuerpo')} />
        )}

        {state.status === 'ready' && (
          <>
            {isMissingLastHour(state.data) && (
              <InlineNotice tono="informacion" titulo={t('historial.faltan_titulo')} descripcion={t('historial.faltan_cuerpo')} />
            )}
            {!isEmptyHistory(state.data) && <PeakCard data={state.data} />}
            <ConsumptionChartCard data={state.data} zones={zones} zonaId={zonaId} onZona={setZonaId} />
            {!isEmptyHistory(state.data) && (
              <>
                <ComparisonCard data={state.data} />
                <CostCard data={state.data} onConfigureTariff={() => router.push('/configurar-tarifa')} />
              </>
            )}
            <Pressable
              onPress={() => router.push('/consejos')}
              accessibilityRole="button"
              style={({ pressed }) => [styles.primaryButton, pressed && { backgroundColor: colors['accent-primaryActive'] }]}
            >
              <Text style={styles.primaryButtonText}>{t('comun.ver_consejos')}</Text>
            </Pressable>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

/* ─────────────────────────────── Estilos ────────────────────────────────── */

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors['background-default'] },
  flex: { flex: 1 },
  content: {
    paddingHorizontal: sizes['grid-margin'],
    paddingTop: spacing['16'],
    paddingBottom: spacing['40'],
    gap: spacing['16'],
  },

  // Cabecera
  header: {
    height: sizes['topBar-height'],
    alignItems: 'center',
    justifyContent: 'center',
    borderBottomWidth: 1,
    borderBottomColor: colors['border-subtle'],
  },
  headerTitle: { ...textStyle('display-l-24'), color: colors['text-primary'] },

  // Selector de periodo
  periodRow: { flexDirection: 'row', justifyContent: 'center', gap: spacing['8'] },

  // Card base
  card: {
    backgroundColor: colors['background-surface'],
    borderColor: colors['border-subtle'],
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: sizes['card-padding'],
    gap: spacing['12'],
  },
  cardHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing['8'] },
  cardIcon: {
    width: spacing['40'],
    height: spacing['40'],
    borderRadius: radius.md,
    backgroundColor: colors['accent-soft'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: { ...textStyle('body-s-medium'), color: colors['text-primary'] },
  mutedXs: { ...textStyle('body-xs-regular'), color: colors['text-muted'] },
  divider: { height: 1, backgroundColor: colors['border-subtle'] },

  // Metric
  metricRow: { flexDirection: 'row', alignItems: 'baseline', gap: spacing['4'] },
  metricValue: { ...textStyle('data-xl-32'), color: colors['text-primary'], flexShrink: 1 },
  metricValueL: { ...textStyle('data-l'), color: colors['text-primary'], flexShrink: 1 },
  metricUnit: { ...textStyle('body-s-regular'), color: colors['text-muted'] },

  // StatusBadge y bloque de estado
  badge: {
    paddingVertical: spacing['4'],
    paddingHorizontal: spacing['8'],
    borderRadius: radius.full,
    borderWidth: 1,
  },
  badgeText: { ...textStyle('ui-s-semibold-12') },
  stateBlock: {
    flexDirection: 'row',
    gap: spacing['8'],
    padding: spacing['12'],
    borderRadius: radius.md,
    borderWidth: 1,
  },
  stateBlockTitle: { ...textStyle('ui-s-semibold') },

  // Selectores
  toggleRow: { flexDirection: 'row', gap: spacing['4'] },
  iconButton: {
    width: sizes['iconButtonLg-size'],
    height: sizes['iconButtonLg-size'],
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconButtonActive: { backgroundColor: colors['accent-soft'] },
  chipRow: { flexDirection: 'row', justifyContent: 'center', gap: spacing['8'] },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing['8'] },
  chip: {
    minHeight: 34,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing['4'],
    paddingHorizontal: spacing['16'],
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors['border-medium'],
  },
  chipActive: { backgroundColor: colors['accent-soft'], borderColor: colors['border-accent'] },
  chipText: { ...textStyle('ui-s-semibold') },
  filterBlock: { gap: spacing['8'] },
  filterLabel: { ...textStyle('body-s-medium'), color: colors['text-primary'] },

  // Gráficos
  emptyChart: { alignItems: 'center', gap: spacing['8'], paddingVertical: spacing['32'] },

  // Comparación
  compareRow: { flexDirection: 'row', gap: spacing['16'] },
  compareDivider: { width: 1, backgroundColor: colors['border-subtle'] },
  compareLabel: { ...textStyle('body-xs-medium'), color: colors['text-muted'] },

  // StateMessage e InlineNotice
  stateMessage: { flexDirection: 'row', alignItems: 'flex-start' },
  stateMessageTitle: { ...textStyle('body-s-medium'), color: colors['text-primary'] },
  linkTouch: { minHeight: spacing['48'], justifyContent: 'center', alignSelf: 'flex-start' },
  linkText: { ...textStyle('ui-s-semibold-12'), color: colors['text-accent'] },
  notice: { borderWidth: 1, borderRadius: radius.md, padding: spacing['12'], gap: spacing['8'] },
  noticeRow: { flexDirection: 'row', gap: spacing['8'] },
  noticeAction: { alignSelf: 'flex-end', minHeight: spacing['48'], justifyContent: 'center' },

  // Botón principal
  primaryButton: {
    height: sizes['button-height'],
    borderRadius: radius.lg,
    backgroundColor: colors['accent-primary'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryButtonText: { ...textStyle('ui-m-semibold'), color: colors['text-inverse'] },

  // Skeleton
  skeletonBlock: { backgroundColor: colors['background-elevated'], borderRadius: radius.xs },
  skeletonIcon: { width: spacing['40'], height: spacing['40'] },
  skeletonLine: { height: spacing['12'] },
  skeletonValue: { height: spacing['32'], width: '50%' },
  skeletonStateBlock: { height: spacing['48'] },
  skeletonChart: { height: CHART_HEIGHT },
});
