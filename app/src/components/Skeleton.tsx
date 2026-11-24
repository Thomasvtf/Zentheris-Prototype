/**
 * Skeleton (Skeleton.md): forma de la card sin números ni ejes falsos. Pulso suave que se detiene
 * con «reducir movimiento». `useSkeletonPulse` queda exportado para esqueletos con otra forma.
 */
import React, { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, StyleSheet, View } from 'react-native';

import { t } from '@/texts';
import { colors, radius, sizes, spacing } from '@/theme';

/** Opacidad que late entre 1 y 0,5; el valor animado se guarda con useState (no se lee un ref en el render). */
export function useSkeletonPulse(): Animated.Value {
  const [opacity] = useState(() => new Animated.Value(1));
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

export interface SkeletonProps {
  tamano?: 'estandar' | 'compacta';
}

export function Skeleton({ tamano = 'estandar' }: SkeletonProps) {
  const opacity = useSkeletonPulse();
  return (
    <Animated.View style={[styles.card, { opacity }]} accessible accessibilityLabel={t('comun.cargando')}>
      <View style={styles.headerRow}>
        <View style={[styles.block, styles.icon]} />
        <View style={[styles.block, styles.line, styles.flex]} />
      </View>
      <View style={[styles.block, styles.value]} />
      {tamano === 'estandar' && (
        <>
          <View style={[styles.block, styles.line]} />
          <View style={[styles.block, styles.stateBlock]} />
        </>
      )}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors['background-surface'],
    borderColor: colors['border-subtle'],
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: sizes['card-padding'],
    gap: spacing['12'],
  },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: spacing['8'] },
  flex: { flex: 1 },
  block: { backgroundColor: colors['background-elevated'], borderRadius: radius.xs },
  icon: { width: spacing['40'], height: spacing['40'] },
  line: { height: spacing['12'] },
  value: { height: spacing['32'], width: '50%' },
  stateBlock: { height: spacing['48'] },
});
