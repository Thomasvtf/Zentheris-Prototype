/**
 * Consejos (reglas v4.9 §6.8 y §7.3; RN-XV-01 a RN-XV-07; RN-VI-05).
 * Datos: useConsejosData (filas 39 y 40 de docs/MAPA-DE-INTEGRACION.md:
 * listarConsejos y actualizarEstadoConsejo).
 *
 * - Cabecera «Consejos», sin ícono de chatbot (RN-XV, §6.8: el chatbot no entra en el MVP).
 * - Lista (TipList): pendientes de alta a baja prioridad y, al final, los completados
 *   atenuados. Con pendientes no se muestra «¡Todo bajo control!»; sin pendientes, la card y
 *   debajo los completados aún visibles (RN-XV-02).
 * - Casilla: marcar pasa el consejo a completado solo para esta persona; desmarcar lo vuelve
 *   a pendiente (RN-XV-03, RN-VI-05). Es optimista y se revierte con aviso si falla.
 * - Prioridad solo con acento y neutros, nunca rojo ni amarillo (PriorityTag.md).
 * - Estados: cargando (Skeleton), error (InlineNotice + Reintentar) y vacío («¡Todo bajo
 *   control!»). El contrato no devuelve 403 en consejos; no hay estado de sin permiso.
 * - El contrato no trae ahorro en kWh/COP, categorías de filtro ni «descartar»; no se muestran.
 * - Colores, espacios y tipografía desde @/theme; textos con t().
 *
 * TODO(pendiente: componentes del sistema de diseño): src/components/ aún no tiene TipCard,
 * TipList, PriorityTag, StateMessage, InlineNotice, Skeleton ni ScreenHeader con las props de
 * index.d.ts. Aquí son piezas locales de presentación para moverlas a src/components/ cuando
 * se apruebe.
 * TODO(pendiente: casilla): TipCard.md dice que la casilla aún no está diseñada; esta usa
 * `border-medium` sin marcar y `accent-primary` marcada, con área táctil de 44 pt.
 */
import React, { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, Pressable, RefreshControl, ScrollView, StatusBar, StyleSheet, Text, TextStyle, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Check, CircleCheck, CircleX } from 'lucide-react-native';

import { colors, fontFamilyFor, radius, sizes, spacing, typography } from '@/theme';
import { t } from '@/texts';

import { hasPendingTips, useConsejosData } from './useConsejosData';
import type { ConsejosMockScenario, Tip, TipPriority } from './useConsejosData';

/* ───────────────────────────── Utilidades ───────────────────────────────── */

function textStyle(name: keyof typeof typography): TextStyle {
  const style = typography[name];
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    ...('lineHeight' in style ? { lineHeight: style.lineHeight } : {}),
  };
}

/** Área táctil mínima de la casilla (app/CLAUDE.md: 44 pt o más). */
const CHECKBOX_TOUCH = 44;
const CHECKBOX_SIZE = 24;
const SKELETON_CARDS = 3;

/* ─────────────────────── Piezas de presentación ─────────────────────────── */

/** Etiqueta de prioridad (PriorityTag.md): solo acento y neutros. */
function PriorityTag({ prioridad }: { prioridad: TipPriority }) {
  const tone = TAG_TONES[prioridad];
  return (
    <View style={[styles.tag, { backgroundColor: tone.bg, borderColor: tone.border }]}>
      <Text style={[styles.tagText, { color: tone.text }]}>{t(`consejos.prioridad_${prioridad}`)}</Text>
    </View>
  );
}

const TAG_TONES: Record<TipPriority, { bg: string; border: string; text: string }> = {
  alta: { bg: colors['accent-soft'], border: colors['border-accent'], text: colors['text-accent'] },
  media: { bg: 'transparent', border: colors['border-medium'], text: colors['text-muted'] },
  baja: { bg: 'transparent', border: colors['border-subtle'], text: colors['text-muted'] },
};

function Checkbox({ checked, disabled, label, onPress }: { checked: boolean; disabled: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="checkbox"
      accessibilityState={{ checked, disabled }}
      accessibilityLabel={label}
      style={styles.checkboxTouch}
    >
      <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
        {checked ? <Check size={16} color={colors['text-inverse']} strokeWidth={3} /> : null}
      </View>
    </Pressable>
  );
}

/** Consejo (TipCard.md): pendiente con su prioridad o completado atenuado, al final de la lista. */
function TipCard({ tip, saving, onToggle }: { tip: Tip; saving: boolean; onToggle: () => void }) {
  const done = tip.estado === 'completada';
  return (
    <View style={[styles.tipCard, done && styles.tipCardDone]}>
      <Checkbox
        checked={done}
        disabled={saving}
        label={`${t(done ? 'a11y.consejo_desmarcar' : 'a11y.consejo_marcar')}: ${tip.titulo}`}
        onPress={onToggle}
      />
      <View style={styles.flex}>
        <Text style={[styles.tipTitle, done && styles.tipTitleDone]}>{tip.titulo}</Text>
        <Text style={styles.tipDescription}>{tip.descripcion}</Text>
        <View style={styles.tipFooter}>
          {done ? (
            <View style={styles.doneRow}>
              <CircleCheck size={16} color={colors['text-success']} />
              <Text style={styles.doneText}>{t('consejos.completado')}</Text>
            </View>
          ) : (
            <PriorityTag prioridad={tip.prioridad} />
          )}
        </View>
      </View>
    </View>
  );
}

/** Card «¡Todo bajo control!» (StateMessage tipo `todo_bajo_control`, solo sin pendientes). */
function AllClearCard() {
  return (
    <View style={styles.stateCard}>
      <CircleCheck size={32} color={colors['text-muted']} />
      <View style={styles.flex}>
        <Text style={styles.stateTitle}>{t('consejos.vacio_titulo')}</Text>
        <Text style={styles.stateBody}>{t('consejos.vacio_cuerpo')}</Text>
      </View>
    </View>
  );
}

function InlineNotice({ titulo, descripcion, onReintentar }: { titulo: string; descripcion?: string; onReintentar?: () => void }) {
  return (
    <View style={styles.notice} accessibilityRole="alert">
      <View style={styles.noticeRow}>
        <CircleX size={16} color={colors['status-error-default']} />
        <View style={styles.flex}>
          <Text style={styles.noticeTitle}>{titulo}</Text>
          {descripcion ? <Text style={styles.stateBody}>{descripcion}</Text> : null}
        </View>
      </View>
      {onReintentar ? (
        <Pressable onPress={onReintentar} accessibilityRole="button" hitSlop={spacing['12']} style={styles.noticeAction}>
          <Text style={styles.linkText}>{t('comun.reintentar')}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

/** Pulso suave; se detiene con «reducir movimiento» (ficha Skeleton). */
function useSkeletonPulse() {
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

/** Esqueleto con la forma de un consejo: casilla, título, descripción y etiqueta. */
function TipSkeleton() {
  const opacity = useSkeletonPulse();
  return (
    <Animated.View style={[styles.tipCard, { opacity }]} accessible accessibilityLabel={t('comun.cargando')}>
      <View style={[styles.skeletonBlock, styles.skeletonCheckbox]} />
      <View style={[styles.flex, styles.skeletonBody]}>
        <View style={[styles.skeletonBlock, styles.skeletonTitle]} />
        <View style={[styles.skeletonBlock, styles.skeletonLine]} />
        <View style={[styles.skeletonBlock, styles.skeletonTag]} />
      </View>
    </Animated.View>
  );
}

/* ─────────────────────────────── Pantalla ───────────────────────────────── */

export interface ConsejosScreenProps {
  /** TODO(pendiente: hogarId): vendrá del estado de sesión/hogar (fila 12 del mapa). */
  hogarId?: string | null;
  /** Solo desarrollo: fuerza un escenario del modo de ejemplo. */
  mockScenario?: ConsejosMockScenario;
}

export function ConsejosScreen({ hogarId = null, mockScenario }: ConsejosScreenProps) {
  const { state, retry, refresh, refreshing, toggle, savingIds, actionErrorKey } = useConsejosData(hogarId, { mockScenario });

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <StatusBar barStyle="light-content" backgroundColor={colors['background-default']} />
      <View style={styles.header}>
        <Text style={styles.headerTitle} accessibilityRole="header">
          {t('consejos.encabezado')}
        </Text>
      </View>

      <ScrollView
        style={styles.flex}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={refresh}
            tintColor={colors['accent-primary']}
            colors={[colors['accent-primary']]}
            progressBackgroundColor={colors['background-surface']}
          />
        }
      >
        {state.status === 'loading' &&
          Array.from({ length: SKELETON_CARDS }, (_, i) => <TipSkeleton key={i} />)}

        {state.status === 'error' && (
          <InlineNotice titulo={t(`${state.errorKey}.titulo`)} descripcion={t(`${state.errorKey}.cuerpo`)} onReintentar={retry} />
        )}

        {state.status === 'ready' && (
          <>
            {actionErrorKey ? <InlineNotice titulo={t(`${actionErrorKey}.titulo`)} descripcion={t(`${actionErrorKey}.cuerpo`)} /> : null}
            {!hasPendingTips(state.tips) && <AllClearCard />}
            {state.tips.map((tip) => (
              <TipCard key={tip.id} tip={tip} saving={savingIds.includes(tip.id)} onToggle={() => toggle(tip.id)} />
            ))}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

/* ─────────────────────────────── Estilos ────────────────────────────────── */

/** Alto de la cabecera en Figma (64): el token `topBar-height` vale 56, así que se compone sin
 * tocar el token (decisión del 24/11/2026). */
const HEADER_HEIGHT = sizes['iconButtonLg-size'] + spacing['16'];

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors['background-default'] },
  flex: { flex: 1 },
  content: {
    paddingHorizontal: spacing['16'],
    paddingTop: spacing['16'],
    paddingBottom: spacing['40'],
    gap: spacing['12'],
  },

  // Cabecera (ScreenHeader.md)
  header: {
    height: HEADER_HEIGHT,
    alignItems: 'center',
    justifyContent: 'center',
    borderBottomWidth: 1,
    borderBottomColor: colors['border-subtle'],
  },
  headerTitle: { ...textStyle('display-l-24'), color: colors['text-primary'] },

  // TipCard
  tipCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing['8'],
    backgroundColor: colors['background-surface'],
    borderColor: colors['border-subtle'],
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing['16'],
  },
  // Completado: atenuado, sin fondo y con el título en `text-muted`.
  tipCardDone: { backgroundColor: 'transparent' },
  tipTitle: { ...textStyle('body-m-medium'), color: colors['text-primary'] },
  tipTitleDone: { color: colors['text-muted'] },
  tipDescription: { ...textStyle('body-s-regular'), color: colors['text-muted'], marginTop: spacing['4'] },
  tipFooter: { flexDirection: 'row', marginTop: spacing['12'] },
  doneRow: { flexDirection: 'row', alignItems: 'center', gap: spacing['4'] },
  doneText: { ...textStyle('body-xs-medium'), color: colors['text-success'] },

  // Casilla
  checkboxTouch: {
    width: CHECKBOX_TOUCH,
    height: CHECKBOX_TOUCH,
    marginTop: -(CHECKBOX_TOUCH - CHECKBOX_SIZE) / 2,
    marginLeft: -(CHECKBOX_TOUCH - CHECKBOX_SIZE) / 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkbox: {
    width: CHECKBOX_SIZE,
    height: CHECKBOX_SIZE,
    borderRadius: radius.xs,
    borderWidth: 2,
    borderColor: colors['border-medium'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxChecked: { backgroundColor: colors['accent-primary'], borderColor: colors['accent-primary'] },

  // PriorityTag
  tag: { paddingVertical: spacing['4'], paddingHorizontal: spacing['8'], borderRadius: radius.full, borderWidth: 1 },
  tagText: { ...textStyle('body-xs-medium') },

  // StateMessage «Todo bajo control»
  stateCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing['12'],
    backgroundColor: colors['background-surface'],
    borderColor: colors['border-subtle'],
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: sizes['card-padding'],
  },
  stateTitle: { ...textStyle('body-s-medium'), color: colors['text-primary'] },
  stateBody: { ...textStyle('body-xs-regular'), color: colors['text-muted'] },

  // InlineNotice
  notice: {
    backgroundColor: colors['status-error-bg'],
    borderColor: colors['status-error-border'],
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing['12'],
    gap: spacing['8'],
  },
  noticeRow: { flexDirection: 'row', gap: spacing['8'] },
  noticeTitle: { ...textStyle('ui-s-semibold'), color: colors['status-error-text'] },
  noticeAction: { alignSelf: 'flex-end', minHeight: spacing['48'], justifyContent: 'center' },
  linkText: { ...textStyle('ui-s-semibold-12'), color: colors['text-accent'] },

  // Skeleton
  skeletonBlock: { backgroundColor: colors['background-elevated'], borderRadius: radius.xs },
  skeletonCheckbox: { width: CHECKBOX_SIZE, height: CHECKBOX_SIZE },
  skeletonBody: { gap: spacing['8'] },
  skeletonTitle: { height: spacing['16'], width: '70%' },
  skeletonLine: { height: spacing['12'], width: '95%' },
  skeletonTag: { height: spacing['24'], width: '35%', borderRadius: radius.full },
});
