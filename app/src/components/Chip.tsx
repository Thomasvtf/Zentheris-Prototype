/**
 * Chip (Chip.md): opción única (kW/COP, Día/Semana/Mes, filtro de zona). En grupo es un radio
 * dentro de un `radiogroup`. Alto visual 34 y área táctil 48 (hitSlop); radio píldora (CORRECCIONES).
 */
import React from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';

import { colors, radius, sizes, spacing, textStyle } from '@/theme';

import { Icon } from './Icon';
import type { IconName } from './Icon';

export interface ChipProps {
  activo?: boolean;
  deshabilitado?: boolean;
  icono?: IconName;
  onClick?: () => void;
  children?: React.ReactNode;
}

/** Alto visual de la ficha (34) y relleno táctil hasta 48. */
const CHIP_HEIGHT = spacing['32'] + 2;
const HIT = (sizes['button-height'] - CHIP_HEIGHT) / 2;

export function Chip({ activo = false, deshabilitado = false, icono, onClick, children }: ChipProps) {
  const color = deshabilitado ? colors['state-disabled-text'] : activo ? colors['text-accent'] : colors['text-muted'];
  return (
    <Pressable
      onPress={onClick}
      disabled={deshabilitado}
      accessibilityRole="radio"
      accessibilityState={{ checked: activo, disabled: deshabilitado }}
      hitSlop={{ top: HIT, bottom: HIT }}
      style={[styles.chip, activo && styles.activo, deshabilitado && styles.deshabilitado]}
    >
      {icono ? <Icon name={icono} size={20} color={color} /> : null}
      {typeof children === 'string' ? <Text style={[styles.text, { color }]}>{children}</Text> : children}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    minHeight: CHIP_HEIGHT,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing['4'],
    paddingHorizontal: spacing['16'],
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors['border-medium'],
  },
  activo: { backgroundColor: colors['accent-soft'], borderColor: colors['border-accent'] },
  deshabilitado: { backgroundColor: colors['state-disabled-bg'], borderColor: colors['state-disabled-bg'] },
  text: { ...textStyle('ui-s-semibold') },
});
