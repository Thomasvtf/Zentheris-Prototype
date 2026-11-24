/**
 * Button (Button.md y CORRECCIONES): primario relleno, secundario con borde de acento, fantasma
 * sin borde con texto de acento (acciones terciarias) y destructivo con fondo y borde de error
 * (Figma A10.1 y A11.1). Alto `button-height` (48).
 */
import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';

import { colors, radius, sizes, spacing, textStyle } from '@/theme';

import { Icon } from './Icon';
import type { IconName } from './Icon';

export interface ButtonProps {
  variante?: 'primario' | 'secundario' | 'fantasma' | 'destructivo';
  estado?: 'normal' | 'presionado' | 'deshabilitado' | 'cargando';
  icono?: IconName;
  /** A todo el ancho del contenedor. */
  bloque?: boolean;
  /** Solo web en el contrato; en la app no cambia nada. */
  type?: 'button' | 'submit';
  onClick?: () => void;
  children?: React.ReactNode;
}

const TEXT_COLOR = {
  primario: colors['text-inverse'],
  secundario: colors['text-accent'],
  fantasma: colors['text-accent'],
  destructivo: colors['text-error'],
} as const;

export function Button({ variante = 'primario', estado = 'normal', icono, bloque = false, onClick, children }: ButtonProps) {
  const disabled = estado === 'deshabilitado' || estado === 'cargando';
  const color = disabled && variante === 'primario' ? colors['state-disabled-text'] : TEXT_COLOR[variante];
  return (
    <Pressable
      onPress={onClick}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ disabled, busy: estado === 'cargando' }}
      style={({ pressed }) => [
        styles.base,
        styles[variante],
        bloque && styles.bloque,
        (pressed || estado === 'presionado') && styles[`${variante}Presionado`],
        disabled && (variante === 'primario' ? styles.primarioDeshabilitado : styles.deshabilitado),
      ]}
    >
      {estado === 'cargando' ? <ActivityIndicator color={color} /> : icono ? <Icon name={icono} size={20} color={color} /> : null}
      {typeof children === 'string' ? <Text style={[styles.text, { color }]}>{children}</Text> : children}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: sizes['button-height'],
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing['8'],
    paddingHorizontal: spacing['16'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  bloque: { alignSelf: 'stretch' },
  primario: { backgroundColor: colors['accent-primary'] },
  primarioPresionado: { backgroundColor: colors['accent-primaryActive'] },
  primarioDeshabilitado: { backgroundColor: colors['state-disabled-bg'] },
  secundario: { borderColor: colors['border-accent'] },
  secundarioPresionado: { backgroundColor: colors['state-active-bg'] },
  fantasma: {},
  fantasmaPresionado: { backgroundColor: colors['state-active-bg'] },
  destructivo: { backgroundColor: colors['status-error-bg'], borderColor: colors['status-error-border'] },
  destructivoPresionado: { borderColor: colors['status-error-default'] },
  deshabilitado: { opacity: 0.5 },
  text: { ...textStyle('ui-m-semibold') },
});
