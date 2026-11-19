/**
 * ZoneDonutChart.md: anillo de participación por zona (solo con el filtro General, RN-XIII-04).
 *
 * - Dos columnas: anillo a la izquierda con el total en el centro; a la derecha la píldora de
 *   la zona con mayor consumo y la lista de todas las zonas.
 * - Más de 4 zonas: las 4 de mayor participación + «Otras zonas» (suma); la lista muestra
 *   todas, las agrupadas con sangría y en `text-muted`.
 * - Colores por orden de participación (opción A); nunca rojo ni amarillo.
 * - Dibujado con `react-native-svg`, como el gauge y el anillo de consumo (DC-63).
 * - Textos y cifras llegan ya formateados (t() y @/format en la pantalla).
 */
import React from 'react';
import { StyleSheet, Text, TextStyle, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import { colors, fontFamilyFor, radius, spacing, typography } from '@/theme';

export interface DonutZone {
  id: string;
  nombre: string;
  participacion: number;
  /** Valor ya formateado («1,0 kWh», «$31,2k»). */
  valorTexto: string;
  /** Porcentaje ya formateado («34 %»). */
  pctTexto: string;
}

export interface ZoneDonutChartProps {
  zonas: DonutZone[];
  /** Cifra del total ya formateada («2,9», «$92,3k»). */
  totalValor: string;
  /** Unidad bajo la cifra («kWh»); vacía en COP (el «$» ya la dice). */
  totalUnidad: string;
  /** Leyenda bajo el total («Total hoy», «Esta semana»). */
  totalEtiqueta: string;
  /** Fila agrupada: nombre («Otras zonas») y textos ya formateados. */
  otras: { nombre: string; valorTexto: string; pctTexto: string };
  /** Píldora de la zona principal («Cocina · 1,0 kWh · 34 %»). */
  destacado: string;
  ancho: number;
  resumen: string;
}

const ZONE_COLORS = [colors['green-400'], colors['green-200'], colors['neutral-300'], colors['green-600']] as const;
const OTHER_COLOR = colors['neutral-500'];
const GAP = 2;

function textStyle(name: keyof typeof typography): TextStyle {
  const style = typography[name];
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    ...('lineHeight' in style ? { lineHeight: style.lineHeight } : {}),
  };
}

/** Las 4 de mayor participación y el resto agrupado (RN-XIII-04). */
export function groupZones<T extends { participacion: number }>(zonas: T[]): { top: T[]; rest: T[] } {
  const sorted = [...zonas].sort((a, b) => b.participacion - a.participacion);
  return sorted.length > 4 ? { top: sorted.slice(0, 4), rest: sorted.slice(4) } : { top: sorted, rest: [] };
}

/** Diámetro del anillo: ~40 % del ancho, entre 104 y 148 px. */
export function donutSize(ancho: number): number {
  return Math.round(Math.max(104, Math.min(148, ancho * 0.4)));
}

export function ZoneDonutChart({ zonas, totalValor, totalUnidad, totalEtiqueta, otras, destacado, ancho, resumen }: ZoneDonutChartProps) {
  const { top, rest } = groupZones(zonas);
  const restPct = rest.reduce((sum, z) => sum + z.participacion, 0);
  const slices = [
    ...top.map((z, i) => ({ key: z.id, value: z.participacion, color: ZONE_COLORS[i] })),
    ...(rest.length > 0 ? [{ key: 'otras', value: restPct, color: OTHER_COLOR }] : []),
  ];
  const totalPct = slices.reduce((sum, s) => sum + s.value, 0) || 1;

  const size = donutSize(ancho);
  const stroke = Math.round(size * 0.13);
  const r = (size - stroke) / 2;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  let offset = 0;

  return (
    <View style={styles.row} accessible accessibilityLabel={resumen}>
      <View style={{ width: size, height: size }}>
        <Svg width={size} height={size}>
          <Circle cx={c} cy={c} r={r} stroke={colors['neutral-700']} strokeWidth={stroke} fill="none" />
          {slices.map((s) => {
            const length = (s.value / totalPct) * circumference;
            const dash = Math.max(length - GAP, 0.5);
            const el = (
              <Circle
                key={s.key}
                cx={c}
                cy={c}
                r={r}
                stroke={s.color}
                strokeWidth={stroke}
                fill="none"
                strokeDasharray={`${dash} ${circumference}`}
                strokeDashoffset={-offset}
                transform={`rotate(-90 ${c} ${c})`}
              />
            );
            offset += length;
            return el;
          })}
        </Svg>
        <View style={[styles.center, { padding: stroke + spacing['4'] }]}>
          {/* La cifra baja a 16 px si es larga: dentro del anillo caben ~6 caracteres a 20 px. */}
          <Text style={totalValor.length > 5 ? styles.totalSmall : styles.total} numberOfLines={1}>
            {totalValor}
          </Text>
          {totalUnidad ? (
            <Text style={styles.totalLabel} numberOfLines={1}>
              {totalUnidad}
            </Text>
          ) : null}
          <Text style={styles.totalLabel} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8}>
            {totalEtiqueta}
          </Text>
        </View>
      </View>

      <View style={styles.legend}>
        {destacado ? (
          <View style={styles.highlight}>
            <Text style={styles.highlightText} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
              {destacado}
            </Text>
          </View>
        ) : null}
        {top.map((z, i) => (
          <LegendRow key={z.id} color={ZONE_COLORS[i]} nombre={z.nombre} pct={z.pctTexto} valor={z.valorTexto} />
        ))}
        {rest.length > 0 && (
          <>
            <LegendRow color={OTHER_COLOR} nombre={otras.nombre} pct={otras.pctTexto} valor={otras.valorTexto} />
            {rest.map((z) => (
              <LegendRow key={z.id} nombre={z.nombre} pct={z.pctTexto} valor={z.valorTexto} grouped />
            ))}
          </>
        )}
      </View>
    </View>
  );
}

function LegendRow({ color, nombre, pct, valor, grouped = false }: { color?: string; nombre: string; pct: string; valor: string; grouped?: boolean }) {
  return (
    <View style={[styles.legendRow, grouped && styles.grouped]}>
      {color ? <View style={[styles.dot, { backgroundColor: color }]} /> : null}
      <Text style={[styles.name, grouped && styles.nameGrouped]} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8}>
        {nombre}
      </Text>
      <Text style={styles.pct} numberOfLines={1}>
        {pct}
      </Text>
      <Text style={styles.value} numberOfLines={1}>
        {valor}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing['12'] },
  center: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  total: { ...textStyle('data-m'), color: colors['text-primary'] },
  totalSmall: { ...textStyle('data-s-16'), color: colors['text-primary'] },
  totalLabel: { ...textStyle('body-xs-regular'), color: colors['text-muted'] },
  legend: { flex: 1, minWidth: 0, gap: spacing['4'] },
  highlight: {
    alignSelf: 'flex-start',
    maxWidth: '100%',
    paddingHorizontal: spacing['8'],
    paddingVertical: 2,
    marginBottom: spacing['4'],
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    backgroundColor: colors['background-elevated'],
  },
  highlightText: { ...textStyle('data-s-mono-regular-12'), color: colors['text-primary'] },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: spacing['4'] },
  grouped: { paddingLeft: spacing['12'] },
  dot: { width: spacing['8'], height: spacing['8'], borderRadius: radius.full },
  name: { ...textStyle('body-xs-regular'), color: colors['text-primary'], flex: 1, minWidth: 0 },
  nameGrouped: { color: colors['text-muted'] },
  pct: { ...textStyle('data-s-mono-regular-12'), color: colors['text-primary'] },
  value: { ...textStyle('data-s-mono-regular-12'), color: colors['text-muted'] },
});
