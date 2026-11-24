/**
 * InlineNotice (InlineNotice.md): aviso dentro de la pantalla (no es la campana). «Reintentar» solo
 * en tono error y solo si llega `onReintentar`.
 */
import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { t } from '@/texts';
import { colors, radius, spacing, textStyle } from '@/theme';

import { Icon } from './Icon';
import type { IconName } from './Icon';

export interface InlineNoticeProps {
  tono: 'error' | 'advertencia' | 'informacion' | 'exito';
  titulo: string;
  descripcion?: string;
  onReintentar?: (() => void) | false;
}

const TONOS: Record<InlineNoticeProps['tono'], { bg: string; border: string; text: string; icon: string; glyph: IconName }> = {
  error: { bg: colors['status-error-bg'], border: colors['status-error-border'], text: colors['status-error-text'], icon: colors['status-error-default'], glyph: 'circle-x' },
  advertencia: { bg: colors['status-warning-bg'], border: colors['status-warning-border'], text: colors['status-warning-text'], icon: colors['status-warning-default'], glyph: 'triangle-alert' },
  informacion: { bg: colors['status-info-bg'], border: colors['status-info-border'], text: colors['status-info-text'], icon: colors['status-info-default'], glyph: 'info' },
  exito: { bg: colors['status-success-bg'], border: colors['status-success-border'], text: colors['status-success-text'], icon: colors['status-success-default'], glyph: 'circle-check' },
};

export function InlineNotice({ tono, titulo, descripcion, onReintentar }: InlineNoticeProps) {
  const tk = TONOS[tono];
  return (
    <View style={[styles.notice, { backgroundColor: tk.bg, borderColor: tk.border }]} accessibilityRole={tono === 'error' ? 'alert' : 'summary'}>
      <View style={styles.row}>
        <Icon name={tk.glyph} size={16} color={tk.icon} />
        <View style={styles.texts}>
          <Text style={[styles.title, { color: tk.text }]}>{titulo}</Text>
          {descripcion ? <Text style={styles.description}>{descripcion}</Text> : null}
        </View>
      </View>
      {tono === 'error' && onReintentar ? (
        <Pressable onPress={onReintentar} accessibilityRole="button" hitSlop={spacing['12']} style={styles.action}>
          <Text style={styles.actionText}>{t('comun.reintentar')}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  notice: { borderWidth: 1, borderRadius: radius.md, padding: spacing['12'], gap: spacing['8'] },
  row: { flexDirection: 'row', gap: spacing['8'] },
  texts: { flex: 1 },
  title: { ...textStyle('ui-s-semibold') },
  description: { ...textStyle('body-xs-regular'), color: colors['text-muted'] },
  action: { alignSelf: 'flex-end', minHeight: spacing['48'], justifyContent: 'center' },
  actionText: { ...textStyle('ui-s-semibold-12'), color: colors['text-accent'] },
});
