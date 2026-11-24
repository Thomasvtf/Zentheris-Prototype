/**
 * StateMessage (StateMessage.md): reemplaza una card de datos o una lista vacía. Ícono 32 a la
 * izquierda, título, descripción y enlace de acción opcional (Figma A3.3, A5.8).
 * Los textos llegan por props desde el catálogo; `tipo` decide el ícono por defecto.
 * `todo_bajo_control` solo a través de TipList.
 */
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, radius, sizes, spacing, textStyle } from '@/theme';

import { Icon } from './Icon';
import type { IconName } from './Icon';

export interface StateMessageProps {
  tipo: 'sin_datos' | 'sin_permiso' | 'sin_tarifa' | 'sin_referencia' | 'vacio' | 'todo_bajo_control';
  /** Solo sin permiso: completa el título cuando no llega `titulo`. */
  recurso?: string;
  titulo?: string;
  descripcion?: string;
  icono?: IconName;
  accion?: string;
  onAccion?: () => void;
}

const ICONO_POR_TIPO: Record<StateMessageProps['tipo'], IconName> = {
  sin_datos: 'clock',
  sin_permiso: 'shield',
  sin_tarifa: 'coins',
  sin_referencia: 'info',
  vacio: 'bell',
  todo_bajo_control: 'circle-check',
};

export function StateMessage({ tipo, recurso, titulo, descripcion, icono, accion, onAccion }: StateMessageProps) {
  const title = titulo ?? recurso;
  return (
    <View style={styles.card}>
      <Icon name={icono ?? ICONO_POR_TIPO[tipo]} size={32} color={colors['text-muted']} />
      <View style={styles.texts}>
        {title ? <Text style={styles.title}>{title}</Text> : null}
        {descripcion ? <Text style={styles.description}>{descripcion}</Text> : null}
        {accion && onAccion ? (
          <Pressable onPress={onAccion} accessibilityRole="link" hitSlop={spacing['12']} style={styles.action}>
            <Text style={styles.actionText}>{accion}</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing['12'],
    backgroundColor: colors['background-surface'],
    borderColor: colors['border-subtle'],
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: sizes['card-padding'],
  },
  texts: { flex: 1, gap: spacing['4'] },
  title: { ...textStyle('body-s-medium'), color: colors['text-primary'] },
  description: { ...textStyle('body-xs-regular'), color: colors['text-muted'] },
  action: { minHeight: spacing['48'], justifyContent: 'center', alignSelf: 'flex-start' },
  actionText: { ...textStyle('ui-s-semibold-12'), color: colors['text-accent'] },
});
