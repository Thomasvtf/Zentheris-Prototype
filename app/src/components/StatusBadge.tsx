/** StatusBadge (StatusBadge.md): estado = color + ícono + palabra. «Crítico», nunca «sobreconsumo». */
import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { t } from '@/texts';
import { radius, spacing, textStyle } from '@/theme';

import { estadoTokens } from './estado';
import type { Severidad } from './estado';
import { Icon } from './Icon';

export interface StatusBadgeProps {
  estado: Severidad;
  /** Cápsula con fondo y borde, o solo ícono + palabra. Por defecto cápsula. */
  variante?: 'capsula' | 'texto';
  /** Se apaga solo cuando el ícono ya está al lado. Por defecto `true`. */
  icono?: boolean;
}

export function StatusBadge({ estado, variante = 'capsula', icono = true }: StatusBadgeProps) {
  const tk = estadoTokens(estado);
  return (
    <View style={[styles.row, variante === 'capsula' && [styles.capsula, { backgroundColor: tk.bg, borderColor: tk.border }]]}>
      {icono ? <Icon name={tk.glyph} size={16} color={tk.icon} /> : null}
      <Text style={[styles.text, { color: tk.text }]}>{t(`estado.palabra.${estado}`)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing['4'], alignSelf: 'flex-start' },
  capsula: {
    paddingVertical: spacing['4'],
    paddingHorizontal: spacing['8'],
    borderRadius: radius.full,
    borderWidth: 1,
  },
  text: { ...textStyle('ui-s-semibold-12') },
});
