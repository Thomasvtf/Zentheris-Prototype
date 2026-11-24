/**
 * Panel principal (reglas v4.9 §6.4 y §7.3; RN-XI-01 a RN-XI-09, RN-XII-01 a RN-XII-05).
 * Datos: useDashboardData (fila de DashboardScreen en docs/MAPA-DE-INTEGRACION.md).
 *
 * - Estados: cargando (Skeleton), error (InlineNotice + Reintentar), sin permiso
 *   (StateMessage; cabecera y saludo visibles), sin datos (`—`, nunca cero), sin tarifa
 *   (se oculta COP) y sin meta (barra contra el promedio, sin «Límite»).
 * - Estado = color + ícono + palabra. Rojo y amarillo solo para severidad.
 * - Colores, espacios, radios y tipografía desde @/theme; textos con t(); cifras con @/format.
 *
 * - StatusBadge, ProgressBar, Chip, Skeleton, StateMessage, InlineNotice y ScreenHeader vienen
 *   de @/components.
 *
 * TODO(pendiente: componentes del sistema de diseño): ConsumptionGauge y ConsumptionRing siguen
 * aquí como piezas locales; pasan a src/components/ con las props de index.d.ts en otro cambio.
 */
import React, { useMemo, useState } from 'react';
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Circle, Path } from 'react-native-svg';
import {
  Activity,
  Bath,
  Bed,
  Car,
  CookingPot,
  DoorClosed,
  Donut,
  Fence,
  Gauge as GaugeIcon,
  LayoutGrid,
  List,
  Monitor,
  Sofa,
  TrendingDown,
  TrendingUp,
  WashingMachine,
  Zap,
} from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';

import {
  bogotaHour,
  DECIMALES,
  formatCOP,
  formatNumber,
  formatPercent,
  hourLabel,
  intervalLabel,
} from '@/format';
import { colors, radius, sizes, spacing, textStyle } from '@/theme';
import { t } from '@/texts';

import {
  Chip,
  estadoTokens,
  Icon,
  InlineNotice,
  ProgressBar,
  ScreenHeader,
  Skeleton,
  StateMessage,
  StatusBadge,
} from '@/components';

import { useDashboardData } from './useDashboardData';
import type {
  ConsumptionState,
  CurrentConsumption,
  DashboardData,
  DashboardMockScenario,
  ZoneConsumptionItem,
  ZonesConsumption,
} from './useDashboardData';

/* ───────────────────────────── Utilidades ───────────────────────────────── */

type Unit = 'kW' | 'COP';
type Severity = 'normal' | 'elevado' | 'critico';
type ChartView = 'gauge' | 'anillo';
type ZonesView = 'larga' | 'compacta';


function isSeverity(estado: ConsumptionState): estado is Severity {
  return estado === 'normal' || estado === 'elevado' || estado === 'critico';
}

/** RN-XII-01: 5:00–11:59 mañana, 12:00–18:59 tarde, 19:00–4:59 noche (hora de Bogotá). */
function greetingKey(now: Date): string {
  const h = bogotaHour(now);
  if (h >= 5 && h < 12) return 'formato.saludo.manana';
  if (h >= 12 && h < 19) return 'formato.saludo.tarde';
  return 'formato.saludo.noche';
}

function kwhText(v: number | null): string {
  return v === null ? formatNumber(null) : `${formatNumber(v, DECIMALES.kWh)} ${t('comun.kwh')}`;
}

/** Texto de un valor de card en la unidad elegida (RN-XII-08: miles con «k» en cards). */
function valueParts(kw: number | null, costCop: number | null, unit: Unit, energy = false) {
  if (unit === 'COP') return { value: formatCOP(costCop, { abreviar: true }), unit: costCop === null ? '' : t('comun.cop') };
  if (kw === null) return { value: formatNumber(null), unit: '' };
  return energy
    ? { value: formatNumber(kw, DECIMALES.kWh), unit: t('comun.kwh') }
    : { value: formatNumber(kw, DECIMALES.kW), unit: t('comun.kw') };
}

/** Ficha ConsumptionGauge: proporcion = min(potencia_kw ÷ (referencia_kw × 1,6), 1). */
function gaugeProportion(actual: CurrentConsumption['actual']): number {
  const { potencia_kw: kw, referencia_kw: ref, estado } = actual;
  if (!isSeverity(estado) || kw === null || ref === null || ref <= 0) return 0;
  return Math.min(kw / (ref * 1.6), 1);
}

/** Texto de catálogo de un `mensaje_codigo`; si falta, la palabra del estado. */
function stateText(code: string | null, part: 'titulo' | 'cuerpo' | 'leyenda', estado: ConsumptionState, vars?: Record<string, string>) {
  return code ? t(`estado.${code}.${part}`, vars) : t(`estado.palabra.${estado}`);
}

const ZONE_ICONS: Record<ZoneConsumptionItem['tipo'], LucideIcon> = {
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

/* ─────────────────────── Piezas de presentación ─────────────────────────── */

/** Bloque de estado de la card (fondo y borde por severidad; neutro sin severidad). */
function StateBlock({ estado, titulo, cuerpo }: { estado: ConsumptionState; titulo: string; cuerpo?: string }) {
  const tk = estadoTokens(estado);
  return (
    <View style={[styles.stateBlock, { backgroundColor: tk.bg, borderColor: tk.border }]}>
      <Icon name={tk.glyph} size={16} color={tk.icon} />
      <View style={styles.flex}>
        <Text style={[styles.stateBlockTitle, { color: tk.text }]}>{titulo}</Text>
        {cuerpo ? <Text style={styles.mutedXs}>{cuerpo}</Text> : null}
      </View>
    </View>
  );
}

function ViewToggle({ activo, icono: Icono, label, onPress }: { activo: boolean; icono: LucideIcon; label: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: activo }}
      style={[styles.iconButton, activo && styles.iconButtonActive]}
    >
      <Icono size={20} color={activo ? colors['accent-primary'] : colors['text-muted']} />
    </Pressable>
  );
}

/* ───────────────────────── Gráficos de consumo ──────────────────────────── */

interface ConsumptionChartProps {
  valor: number | null;
  unidad: Unit;
  estado: ConsumptionState;
  proporcion: number;
  leyenda: string;
}

function chartValue(valor: number | null, unidad: Unit) {
  if (valor === null) return { value: formatNumber(null), unit: '' };
  return unidad === 'COP'
    ? { value: formatNumber(valor, DECIMALES.COP, { abreviar: true }), unit: t('comun.cop') }
    : { value: formatNumber(valor, DECIMALES.kW), unit: t('comun.kw') };
}

function chartA11y(valor: number | null, unidad: Unit, estado: ConsumptionState, proporcion: number) {
  const v = chartValue(valor, unidad);
  return {
    accessible: true,
    accessibilityRole: 'progressbar' as const,
    accessibilityLabel: t('a11y.gauge', { valor: `${v.value} ${v.unit}`.trim(), estado: t(`estado.palabra.${estado}`) }),
    accessibilityValue: { min: 0, max: 100, now: Math.round(proporcion * 100) },
  };
}

const GAUGE_SIZE = 240;
const GAUGE_STROKE = Math.round(GAUGE_SIZE * 0.18);

/** Ficha ConsumptionGauge: semicírculo que se llena de izquierda a derecha. */
function ConsumptionGauge({ valor, unidad, estado, proporcion, leyenda }: ConsumptionChartProps) {
  const tk = estadoTokens(estado);
  const r = (GAUGE_SIZE - GAUGE_STROKE) / 2;
  const cx = GAUGE_SIZE / 2;
  const cy = r + GAUGE_STROKE / 2;
  const length = Math.PI * r;
  const arc = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;
  const v = chartValue(valor, unidad);
  return (
    <View style={styles.chartBox} {...chartA11y(valor, unidad, estado, proporcion)}>
      <Svg width={GAUGE_SIZE} height={cy + GAUGE_STROKE / 2}>
        <Path d={arc} stroke={colors['neutral-700']} strokeWidth={GAUGE_STROKE} fill="none" />
        {proporcion > 0 && (
          <Path
            d={arc}
            stroke={tk.fill}
            strokeWidth={GAUGE_STROKE}
            fill="none"
            strokeDasharray={`${length * proporcion} ${length}`}
          />
        )}
      </Svg>
      <View style={styles.chartValueRow}>
        <Text style={styles.chartValue}>{v.value}</Text>
        {v.unit ? <Text style={styles.chartUnitInline}>{v.unit}</Text> : null}
      </View>
      <Text style={[styles.chartLegend, { color: tk.word }]}>{leyenda}</Text>
    </View>
  );
}

const RING_SIZE = 180;
const RING_STROKE = Math.round(RING_SIZE * 0.12);

/** Ficha ConsumptionRing: anillo de un solo valor que empieza a las 12 en sentido horario. */
function ConsumptionRing({ valor, unidad, estado, proporcion, leyenda }: ConsumptionChartProps) {
  const tk = estadoTokens(estado);
  const r = (RING_SIZE - RING_STROKE) / 2;
  const c = RING_SIZE / 2;
  const circumference = 2 * Math.PI * r;
  const v = chartValue(valor, unidad);
  return (
    <View style={styles.chartBox} {...chartA11y(valor, unidad, estado, proporcion)}>
      <View>
        <Svg width={RING_SIZE} height={RING_SIZE}>
          <Circle cx={c} cy={c} r={r} stroke={colors['neutral-700']} strokeWidth={RING_STROKE} fill="none" />
          {proporcion > 0 && (
            <Circle
              cx={c}
              cy={c}
              r={r}
              stroke={tk.fill}
              strokeWidth={RING_STROKE}
              fill="none"
              strokeDasharray={`${circumference * proporcion} ${circumference}`}
              transform={`rotate(-90 ${c} ${c})`}
            />
          )}
        </Svg>
        <View style={styles.ringCenter}>
          <Text style={styles.chartValue}>{v.value}</Text>
          {v.unit ? <Text style={styles.ringUnit}>{v.unit}</Text> : null}
        </View>
      </View>
      <Text style={[styles.chartLegend, { color: tk.word }]}>{leyenda}</Text>
    </View>
  );
}

/* ─────────────────────────────── Cards ──────────────────────────────────── */

function CardHeader({ icono: Icono, titulo, estado }: { icono: LucideIcon; titulo: string; estado?: ConsumptionState }) {
  return (
    <View style={styles.cardHeaderRow}>
      <View style={styles.cardIcon}>
        <Icono size={24} color={colors['accent-primary']} />
      </View>
      <Text style={[styles.cardTitle, styles.flex]}>{titulo}</Text>
      {estado && isSeverity(estado) ? <StatusBadge estado={estado} icono={false} /> : null}
    </View>
  );
}

function Metric({ value, unit }: { value: string; unit: string }) {
  return (
    <View style={styles.metricRow}>
      <Text style={styles.metricValue} adjustsFontSizeToFit numberOfLines={1}>
        {value}
      </Text>
      {unit ? <Text style={styles.metricUnit}>{unit}</Text> : null}
    </View>
  );
}

/** Card 1 · Consumo actual (RN-XI-01, RN-XI-03, RN-XI-09). */
function CurrentCard({ data, unit }: { data: CurrentConsumption; unit: Unit }) {
  const { actual } = data;
  const parts = valueParts(actual.potencia_kw, actual.costo_cop, unit);
  const variation = actual.variacion_hora_anterior_pct;
  const rounded = variation === null ? null : Math.round(variation);
  const variationText =
    rounded === null
      ? t('estado.variacion_hora.sin_dato')
      : rounded === 0
        ? t('estado.variacion_hora.igual')
        : t(rounded > 0 ? 'estado.variacion_hora.mas' : 'estado.variacion_hora.menos', { pct: formatPercent(Math.abs(rounded)) });
  const Trend = rounded !== null && rounded !== 0 ? (rounded > 0 ? TrendingUp : TrendingDown) : null;

  return (
    <View style={styles.card}>
      <CardHeader icono={Zap} titulo={t('panel.consumo_actual', { intervalo: intervalLabel(data.hora) })} estado={actual.estado} />
      <Metric value={parts.value} unit={parts.unit} />
      {isSeverity(actual.estado) && (
        <View style={styles.trendRow}>
          {Trend && <Trend size={16} color={colors['text-muted']} />}
          <Text style={styles.mutedXs}>{variationText}</Text>
        </View>
      )}
      <View style={styles.divider} />
      <StateBlock
        estado={actual.estado}
        titulo={stateText(actual.mensaje_codigo, 'titulo', actual.estado)}
        cuerpo={actual.mensaje_codigo ? t(`estado.${actual.mensaje_codigo}.cuerpo`) : undefined}
      />
    </View>
  );
}

/** Card 2 · Consumo actual en gauge o anillo, con el selector kW/COP (RN-XII-04). */
function ChartCard({ data, unit, onUnit }: { data: CurrentConsumption; unit: Unit; onUnit: (u: Unit) => void }) {
  const [view, setView] = useState<ChartView>('gauge');
  const { actual } = data;
  const chartProps: ConsumptionChartProps = {
    valor: unit === 'COP' ? actual.costo_cop : actual.potencia_kw,
    unidad: unit,
    estado: actual.estado,
    proporcion: gaugeProportion(actual),
    leyenda: stateText(actual.mensaje_codigo, 'leyenda', actual.estado),
  };
  return (
    <View style={styles.card}>
      <View style={styles.cardHeaderRow}>
        <Text style={[styles.cardTitle, styles.flex]}>{t('panel.consumo_actual', { intervalo: intervalLabel(data.hora) })}</Text>
        <View style={styles.toggleRow}>
          <ViewToggle activo={view === 'gauge'} icono={GaugeIcon} label={t('a11y.ver_gauge')} onPress={() => setView('gauge')} />
          <ViewToggle activo={view === 'anillo'} icono={Donut} label={t('a11y.ver_anillo')} onPress={() => setView('anillo')} />
        </View>
      </View>
      {view === 'gauge' ? <ConsumptionGauge {...chartProps} /> : <ConsumptionRing {...chartProps} />}
      <View style={styles.chipRow} accessibilityRole="radiogroup">
        <Chip activo={unit === 'kW'} icono="zap" onClick={() => onUnit('kW')}>
          {t('comun.kw')}
        </Chip>
        {data.tarifa_vigente && (
          <Chip activo={unit === 'COP'} icono="coins" onClick={() => onUnit('COP')}>
            {t('comun.cop')}
          </Chip>
        )}
      </View>
    </View>
  );
}

/** Card 3 · Consumo acumulado hoy (RN-XI-04; §7.3 «Sin meta»). */
function TodayCard({ data, unit }: { data: CurrentConsumption; unit: Unit }) {
  const today = data.acumulado_hoy;
  const parts = valueParts(today.energia_kwh, today.costo_cop, unit, true);
  const ref = today.referencia_kwh;
  const pct = ref !== null && ref > 0 ? (today.energia_kwh / ref) * 100 : null;
  const vars = { pct: formatPercent(pct), objetivo_dia: kwhText(ref), promedio: kwhText(ref) };
  const severity = isSeverity(today.estado) ? today.estado : 'neutro';

  return (
    <View style={styles.card}>
      <CardHeader icono={Activity} titulo={t('panel.acumulado', { hora: hourLabel(data.hora.fin) })} estado={today.estado} />
      <Metric value={parts.value} unit={parts.unit} />
      {pct !== null && (
        <ProgressBar
          porcentaje={pct}
          estado={severity}
          etiqueta={t(today.muestra_limite ? 'panel.progreso_meta' : 'panel.progreso_promedio')}
        />
      )}
      {today.muestra_limite && (
        <View style={styles.limitBox}>
          <Text style={styles.limitLabel}>{t('panel.limite')}</Text>
          <Text style={styles.limitValue}>{kwhText(ref)}</Text>
        </View>
      )}
      <View style={styles.divider} />
      <StateBlock
        estado={today.estado}
        titulo={stateText(today.mensaje_codigo, 'titulo', today.estado)}
        cuerpo={today.mensaje_codigo ? t(`estado.${today.mensaje_codigo}.cuerpo`, vars) : undefined}
      />
    </View>
  );
}

/* ─────────────────────────────── Zonas ──────────────────────────────────── */

/** Agrupa de a dos para la cuadrícula compacta (filas con su propio espacio entre columnas). */
function pairs<T>(items: T[]): [T, T | undefined][] {
  const out: [T, T | undefined][] = [];
  for (let i = 0; i < items.length; i += 2) out.push([items[i], items[i + 1]]);
  return out;
}

function ZoneCard({ zone, unit, compact }: { zone: ZoneConsumptionItem; unit: Unit; compact: boolean }) {
  const Icono = ZONE_ICONS[zone.tipo];
  const name = t(`zona.${zone.tipo}`);
  const parts = valueParts(zone.potencia_kw, zone.costo_cop, unit);
  const tk = estadoTokens(zone.estado_participacion);
  const severity = isSeverity(zone.estado_participacion) ? zone.estado_participacion : 'neutro';
  return (
    <View style={[styles.card, styles.zoneCard, compact && styles.flex]}>
      <View style={styles.cardHeaderRow}>
        <Icono size={20} color={colors['text-primary']} />
        <Text style={[styles.cardTitle, styles.flex]} numberOfLines={1}>
          {name}
        </Text>
        {/* La palabra del estado va bajo la cifra (ProgressBar); aquí solo su ícono. */}
        <Icon name={tk.glyph} size={16} color={tk.icon} />
      </View>
      <View style={styles.metricRow}>
        <Text style={compact ? styles.zoneValueCompact : styles.zoneValue}>{parts.value}</Text>
        {parts.unit ? <Text style={styles.metricUnit}>{parts.unit}</Text> : null}
      </View>
      <ProgressBar
        porcentaje={zone.participacion_pct}
        estado={severity}
        etiqueta={t(`estado.palabra.${zone.estado_participacion}`)}
      />
    </View>
  );
}

function ZonesSection({ data, unit }: { data: ZonesConsumption; unit: Unit }) {
  const [view, setView] = useState<ZonesView>('larga');
  // RN-XII-03: nombres en español tomados del tipo y en orden alfabético.
  const zones = useMemo(
    () => [...data.zonas].sort((a, b) => t(`zona.${a.tipo}`).localeCompare(t(`zona.${b.tipo}`), 'es')),
    [data.zonas],
  );
  return (
    <View>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle} accessibilityRole="header">
          {t('panel.zonas')}
        </Text>
        <View style={styles.toggleRow}>
          <ViewToggle activo={view === 'compacta'} icono={LayoutGrid} label={t('a11y.vista_compacta')} onPress={() => setView('compacta')} />
          <ViewToggle activo={view === 'larga'} icono={List} label={t('a11y.vista_larga')} onPress={() => setView('larga')} />
        </View>
      </View>
      {zones.length === 0 ? (
        <StateMessage tipo="sin_datos" titulo={t('estado.zona_participacion.sin_datos.titulo')} descripcion={t('estado.zona_participacion.sin_datos.cuerpo')} />
      ) : (
        <View style={styles.zonesList}>
          {view === 'compacta'
            ? pairs(zones).map(([a, b]) => (
                <View key={a.zona_id} style={styles.zonesRow}>
                  <ZoneCard zone={a} unit={unit} compact />
                  {b ? <ZoneCard zone={b} unit={unit} compact /> : <View style={styles.flex} />}
                </View>
              ))
            : zones.map((zone) => <ZoneCard key={zone.zona_id} zone={zone} unit={unit} compact={false} />)}
        </View>
      )}
    </View>
  );
}

/* ─────────────────────────────── Pantalla ───────────────────────────────── */

function DashboardContent({ data }: { data: DashboardData }) {
  const [unitChoice, setUnitChoice] = useState<Unit>('kW');
  // RN-XI-08 / RN-XII-04: COP solo con tarifa vigente.
  const unit: Unit = data.current?.tarifa_vigente ? unitChoice : 'kW';

  if (!data.canSeeConsumption || !data.current || !data.zones) {
    return (
      <StateMessage
        tipo="sin_permiso"
        titulo={t('error.sin_permiso_ver_consumo.titulo')}
        descripcion={t('error.sin_permiso_ver_consumo.cuerpo')}
      />
    );
  }
  return (
    <>
      {data.current.actual.estado === 'sin_datos' ? (
        <StateMessage
          tipo="sin_datos"
          icono="loader"
          titulo={t('estado.consumo_actual.sin_datos.titulo')}
          descripcion={t('estado.consumo_actual.sin_datos.cuerpo')}
        />
      ) : (
        <>
          <CurrentCard data={data.current} unit={unit} />
          <ChartCard data={data.current} unit={unit} onUnit={setUnitChoice} />
        </>
      )}
      <TodayCard data={data.current} unit={unit} />
      <ZonesSection data={data.zones} unit={unit} />
    </>
  );
}

export interface DashboardScreenProps {
  /** TODO(pendiente: hogarId): vendrá del estado de sesión/hogar (fila 12 del mapa). */
  hogarId?: string | null;
  /** TODO(pendiente: ruta Alertas): aún no existe la pantalla de Alertas (RN-XII-02). */
  onOpenAlerts?: () => void;
  /** Solo desarrollo: fuerza un escenario del modo de ejemplo. */
  mockScenario?: DashboardMockScenario;
}

export function DashboardScreen({ hogarId = null, onOpenAlerts, mockScenario }: DashboardScreenProps) {
  const { state, retry, refresh, refreshing } = useDashboardData(hogarId, { mockScenario });
  const ready = state.status === 'ready' ? state.data : null;

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <StatusBar barStyle="light-content" backgroundColor={colors['background-default']} />
      <ScreenHeader
        titulo={t('panel.encabezado')}
        onAtras={false}
        campana={ready?.canReceiveAlerts ?? false}
        noLeidas={ready?.unreadAlerts ?? 0}
        onCampana={onOpenAlerts}
      />
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
        {ready && <Text style={styles.greeting}>{t(greetingKey(new Date()), { nombre: ready.firstName })}</Text>}

        {state.status === 'loading' && (
          <>
            <Skeleton />
            <Skeleton />
            <Skeleton />
            <Skeleton tamano="compacta" />
          </>
        )}

        {state.status === 'error' && (
          <InlineNotice tono="error" titulo={t(`${state.errorKey}.titulo`)} descripcion={t(`${state.errorKey}.cuerpo`)} onReintentar={retry} />
        )}

        {ready && <DashboardContent data={ready} />}
      </ScrollView>
    </SafeAreaView>
  );
}

/* ─────────────────────────────── Estilos ────────────────────────────────── */

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors['background-default'] },
  flex: { flex: 1 },
  content: {
    paddingHorizontal: spacing['16'],
    paddingBottom: spacing['40'],
    gap: spacing['16'],
  },

  // Cabecera (ScreenHeader)
  greeting: { ...textStyle('body-m-regular'), color: colors['text-primary'], textAlign: 'center', marginTop: spacing['16'] },

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
  metricUnit: { ...textStyle('body-s-regular'), color: colors['text-muted'] },
  trendRow: { flexDirection: 'row', alignItems: 'center', gap: spacing['4'] },

  // StatusBadge y bloque de estado
  stateBlock: {
    flexDirection: 'row',
    gap: spacing['8'],
    padding: spacing['12'],
    borderRadius: radius.md,
    borderWidth: 1,
  },
  stateBlockTitle: { ...textStyle('ui-s-semibold') },

  // Límite
  limitBox: { gap: spacing['4'] },
  limitLabel: { ...textStyle('body-xs-medium'), color: colors['text-muted'] },
  limitValue: { ...textStyle('data-s-16'), color: colors['text-primary'] },

  // Gráficos
  chartBox: { alignItems: 'center', gap: spacing['8'], paddingVertical: spacing['8'] },
  chartValueRow: { flexDirection: 'row', alignItems: 'baseline', gap: spacing['4'] },
  chartValue: { ...textStyle('data-xl-32'), color: colors['text-primary'] },
  chartUnitInline: { ...textStyle('data-l'), color: colors['text-primary'] },
  chartLegend: { ...textStyle('body-s-medium'), textAlign: 'center' },
  ringCenter: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, alignItems: 'center', justifyContent: 'center' },
  ringUnit: { ...textStyle('ui-m-semibold'), color: colors['text-muted'] },

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

  // Zonas
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing['16'],
  },
  sectionTitle: { ...textStyle('display-m'), color: colors['text-primary'] },
  zonesList: { gap: spacing['12'] },
  zonesRow: { flexDirection: 'row', gap: spacing['8'] },
  zoneCard: { gap: spacing['8'] },
  zoneValue: { ...textStyle('data-l'), color: colors['text-primary'] },
  zoneValueCompact: { ...textStyle('data-m'), color: colors['text-primary'] },

});
