/**
 * ScreenHeader (ScreenHeader.md): título centrado, atrás opcional y campana opcional.
 * Alto 64 como en Figma (el token `topBar-height` vale 56; decisión del 24/11/2026) y línea inferior.
 * Extensión de la app: `onCampana` (el contrato no dice qué hace al tocarla).
 */
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { plural, t } from '@/texts';
import { colors, radius, sizes, spacing, textStyle } from '@/theme';

import { Icon } from './Icon';

export interface ScreenHeaderProps {
  titulo: string;
  onAtras?: (() => void) | false;
  /** Solo con permiso de recibir alertas (RN-XII-02). */
  campana?: boolean;
  noLeidas?: number;
  onCampana?: () => void;
}

/** 48 + 16 = 64 (Figma `Navegacion/Cabecera`). */
export const HEADER_HEIGHT = sizes['iconButtonLg-size'] + spacing['16'];

export function ScreenHeader({ titulo, onAtras, campana = false, noLeidas = 0, onCampana }: ScreenHeaderProps) {
  return (
    <View style={styles.header}>
      <View style={styles.side}>
        {onAtras ? (
          <Pressable
            onPress={onAtras}
            accessibilityRole="button"
            accessibilityLabel={t('a11y.volver')}
            style={({ pressed }) => [styles.button, pressed && styles.pressed]}
          >
            <Icon name="chevron-left" size={24} color={colors['text-primary']} />
          </Pressable>
        ) : null}
      </View>
      <Text style={styles.title} accessibilityRole="header" numberOfLines={1}>
        {titulo}
      </Text>
      <View style={styles.side}>
        {campana ? (
          <Pressable
            onPress={onCampana}
            accessibilityRole="button"
            accessibilityLabel={plural('a11y.campana_no_leidas', noLeidas)}
            style={({ pressed }) => [styles.button, pressed && styles.pressed]}
          >
            <Icon name="bell" size={24} />
            {noLeidas > 0 ? <View style={styles.dot} /> : null}
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    height: HEADER_HEIGHT,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing['4'],
    borderBottomWidth: 1,
    borderBottomColor: colors['border-subtle'],
  },
  side: { width: sizes['iconButtonLg-size'], alignItems: 'center' },
  title: { ...textStyle('display-l-24'), color: colors['text-primary'], flex: 1, textAlign: 'center' },
  button: {
    width: sizes['iconButtonLg-size'],
    height: sizes['iconButtonLg-size'],
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pressed: { backgroundColor: colors['state-active-bg'] },
  dot: {
    position: 'absolute',
    top: spacing['12'],
    right: spacing['12'],
    width: spacing['8'],
    height: spacing['8'],
    borderRadius: radius.full,
    backgroundColor: colors['accent-primary'],
  },
});
