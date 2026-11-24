/**
 * ProgressBar (ProgressBar.md): etiqueta a la izquierda, porcentaje es-CO a la derecha y pista de 6.
 * La etiqueta va en el color del estado solo cuando es la palabra del estado («Normal», «Elevado»…),
 * como en Figma; cualquier otro texto va en `text-muted`. `neutro` es una participación sin estado.
 * Extensión de la app: `porcentaje` acepta `null` («sin dato»): muestra «—» y la pista vacía.
 */
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { formatPercent } from '@/format';
import { t } from '@/texts';
import { colors, radius, spacing, textStyle } from '@/theme';

import { estadoTokens } from './estado';

export interface ProgressBarProps {
  porcentaje: number | null;
  estado?: 'normal' | 'elevado' | 'critico' | 'neutro';
  etiqueta: string;
}

const TRACK_HEIGHT = 6;

export function ProgressBar({ porcentaje, estado = 'neutro', etiqueta }: ProgressBarProps) {
  const clamped = porcentaje === null ? 0 : Math.max(0, Math.min(100, porcentaje));
  const tk = estado === 'neutro' ? null : estadoTokens(estado);
  const etiquetaEsEstado = tk !== null && etiqueta === t(`estado.palabra.${estado}`);
  const valorTexto = formatPercent(porcentaje);
  return (
    <View
      accessible
      accessibilityRole="progressbar"
      accessibilityLabel={`${etiqueta}, ${valorTexto}`}
      accessibilityValue={{ min: 0, max: 100, now: Math.round(clamped) }}
    >
      <View style={styles.row}>
        <Text style={[styles.label, tk && etiquetaEsEstado ? { color: tk.word } : null]} numberOfLines={1}>
          {etiqueta}
        </Text>
        <Text style={styles.value}>{valorTexto}</Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${clamped}%`, backgroundColor: tk ? tk.fill : colors['chart-series1'] }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing['8'], marginBottom: spacing['4'] },
  label: { ...textStyle('body-xs-regular'), color: colors['text-muted'], flex: 1 },
  value: { ...textStyle('data-s'), color: colors['text-primary'] },
  track: { height: TRACK_HEIGHT, borderRadius: radius.full, backgroundColor: colors['border-medium'], overflow: 'hidden' },
  fill: { height: '100%', borderRadius: radius.full },
});
