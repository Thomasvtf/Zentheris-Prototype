/**
 * Colores e ícono de cada estado de consumo desde los tokens (StatusBadge.md, ConsumptionGauge.md).
 * Rojo y amarillo solo para severidad; sin datos y sin referencia van en neutro.
 */
import { colors } from '@/theme';

import type { IconName } from './Icon';

export type EstadoConsumo = 'normal' | 'elevado' | 'critico' | 'sin_datos' | 'sin_referencia';
export type Severidad = 'normal' | 'elevado' | 'critico';

export interface EstadoTokens {
  /** Fondo y borde de cápsulas y bloques de estado. */
  bg: string;
  border: string;
  /** Texto de la cápsula o del bloque. */
  text: string;
  /** Ícono de severidad. */
  icon: string;
  /** Relleno de gauge, anillo y barras de progreso. */
  fill: string;
  /** Palabra o leyenda del estado fuera de la cápsula. */
  word: string;
  glyph: IconName;
}

export function esSeveridad(estado: string): estado is Severidad {
  return estado === 'normal' || estado === 'elevado' || estado === 'critico';
}

export function estadoTokens(estado: EstadoConsumo): EstadoTokens {
  switch (estado) {
    case 'normal':
      return {
        bg: colors['status-success-bg'],
        border: colors['status-success-border'],
        text: colors['status-success-text'],
        icon: colors['status-success-default'],
        fill: colors['status-success-default'],
        word: colors['text-accentSoft'],
        glyph: 'circle-check',
      };
    case 'elevado':
      return {
        bg: colors['status-warning-bg'],
        border: colors['status-warning-border'],
        text: colors['status-warning-text'],
        icon: colors['status-warning-default'],
        fill: colors['status-warning-default'],
        word: colors['text-warning'],
        glyph: 'triangle-alert',
      };
    case 'critico':
      return {
        bg: colors['status-error-bg'],
        border: colors['status-error-border'],
        text: colors['text-error'],
        icon: colors['status-error-default'],
        fill: colors['status-error-default'],
        word: colors['text-error'],
        glyph: 'circle-alert',
      };
    default:
      return {
        bg: colors['background-surfaceAlt'],
        border: colors['border-subtle'],
        text: colors['text-muted'],
        icon: colors['text-muted'],
        fill: colors['chart-series1'],
        word: colors['text-muted'],
        glyph: estado === 'sin_datos' ? 'clock' : 'info',
      };
  }
}
