/**
 * Establecer meta (sección 6.14; RN-V, RN-XVII-04). Contrato:
 * GET /hogares/{hogar_id}/meta (obtenerMeta) y POST /hogares/{hogar_id}/metas (crearMeta).
 * Mapa: docs/MAPA-DE-INTEGRACION.md, filas 32 y 33.
 *
 * - La meta es mensual y en kWh (`valor_kwh_mensual`); el tipo (ahorro, eficiencia o
 *   presupuesto) solo cambia textos.
 * - Guardar crea la meta activa y deja la anterior inactiva (lo hace la API).
 * - Solo el administrador o quien tiene `permiso_modificar_metas` puede editar (`puede_editar`).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextStyle,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ChevronLeft, CircleAlert, CircleCheck, Info, Minus, Plus } from 'lucide-react-native';
import { useRouter } from 'expo-router';

import { createGoal, getGoal } from '@/api/goalsTariff';
import { toErrorTextKey } from '@/api/errors';
import type { SuccessBody } from '@/api/client';
import { DECIMALES, formatNumber } from '@/format';
import { colors, fontFamilyFor, radius, sizes, spacing, typography } from '@/theme';
import { t } from '@/texts';

type GoalView = SuccessBody<'/hogares/{hogar_id}/meta', 'get'>;
type GoalType = 'ahorro' | 'eficiencia' | 'presupuesto';

type GoalState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'ready'; data: GoalView };

const GOAL_TYPES: GoalType[] = ['ahorro', 'eficiencia', 'presupuesto'];
/** Paso de los botones − y + en kWh por mes. */
const STEP_KWH = 10;
const BOGOTA_OFFSET_MS = -5 * 60 * 60 * 1000;

/**
 * Hook de datos de la pantalla (cargando, error y datos).
 * TODO(pendiente: hogarId): aún no existe el estado de sesión/hogar (GET /hogares/actual,
 * fila 12 del mapa); la pantalla recibe `hogarId` por prop. Al existir el provider de React
 * Query, este hook pasa a `useEstablecerMetaData.ts` con useQuery/useMutation
 * (queryKey('obtenerMeta', hogarId)).
 */
function useGoalData(hogarId: string | null) {
  const [state, setState] = useState<GoalState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    // Sin hogar no se pide nada: el error se deriva abajo, sin setState aquí.
    if (!hogarId) return;
    let cancelled = false;
    getGoal(hogarId)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', errorKey: toErrorTextKey(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [hogarId, attempt]);

  // El esqueleto se muestra al pedir de nuevo (evento), no dentro del efecto.
  const reload = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((n) => n + 1);
  }, []);
  const visibleState: GoalState = hogarId
    ? state
    : { status: 'error', errorKey: 'error.app.no_encontrado' };
  return { state: visibleState, reload };
}

function textStyle(name: keyof typeof typography): TextStyle {
  const style = typography[name];
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    ...('lineHeight' in style ? { lineHeight: style.lineHeight } : {}),
  };
}

/** Mes en curso (hora de Bogotá): número de mes «01»–«12» y días que tiene. */
function currentMonthInfo(now: Date = new Date()): { mm: string; days: number } {
  const local = new Date(now.getTime() + BOGOTA_OFFSET_MS);
  const year = local.getUTCFullYear();
  const month = local.getUTCMonth() + 1;
  return {
    mm: String(month).padStart(2, '0'),
    days: new Date(Date.UTC(year, month, 0)).getUTCDate(),
  };
}

function Notice({
  tone,
  title,
  body,
}: {
  tone: 'error' | 'success' | 'neutral';
  title: string;
  body?: string;
}) {
  const palette =
    tone === 'error'
      ? { bg: colors['status-error-bg'], border: colors['status-error-border'], icon: CircleAlert }
      : tone === 'success'
        ? { bg: colors['status-success-bg'], border: colors['status-success-border'], icon: CircleCheck }
        : { bg: colors['background-surfaceAlt'], border: colors['border-medium'], icon: Info };
  return (
    <View
      style={[styles.notice, { backgroundColor: palette.bg, borderColor: palette.border }]}
      accessibilityRole="alert"
    >
      <palette.icon size={20} color={colors['text-muted']} />
      <View style={styles.noticeTexts}>
        <Text style={styles.noticeTitle}>{title}</Text>
        {body ? <Text style={styles.noticeBody}>{body}</Text> : null}
      </View>
    </View>
  );
}

export interface EstablecerMetaScreenProps {
  /** TODO(pendiente: hogarId): vendrá del estado de sesión/hogar cuando exista. */
  hogarId?: string | null;
}

export function EstablecerMetaScreen({ hogarId = null }: EstablecerMetaScreenProps) {
  const router = useRouter();
  const { state, reload } = useGoalData(hogarId);
  const { mm, days } = currentMonthInfo();

  const [goalKwh, setGoalKwh] = useState(0);
  const [goalType, setGoalType] = useState<GoalType>('ahorro');
  const [initialized, setInitialized] = useState(false);
  const [saving, setSaving] = useState(false);
  const [zeroError, setZeroError] = useState(false);
  const [saveErrorKey, setSaveErrorKey] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Valor inicial: la meta activa; si no hay, el promedio diario de 30 días × días del mes
  // redondeado a la decena. Sin ninguno de los dos queda en 0 (hay que elegir un valor).
  // Se ajusta durante el render, una sola vez, en lugar de con un efecto (patrón de React
  // «ajustar el estado cuando cambian los datos»).
  if (state.status === 'ready' && !initialized) {
    const { meta, promedio_diario_30d_kwh: average } = state.data;
    if (meta) {
      setGoalKwh(meta.valor_kwh_mensual);
      setGoalType(meta.tipo);
    } else if (average !== null) {
      setGoalKwh(Math.max(STEP_KWH, Math.round((average * days) / STEP_KWH) * STEP_KWH));
    }
    setInitialized(true);
  }

  const canEdit = state.status === 'ready' && state.data.puede_editar;

  const decrease = () => {
    setSaved(false);
    setGoalKwh((value) => Math.max(0, value - STEP_KWH));
  };
  const increase = () => {
    setSaved(false);
    setGoalKwh((value) => value + STEP_KWH);
  };

  const handleSave = async () => {
    setSaved(false);
    setSaveErrorKey(null);
    if (!(goalKwh > 0)) {
      setZeroError(true);
      return;
    }
    setZeroError(false);
    if (!hogarId) return;

    setSaving(true);
    try {
      await createGoal(hogarId, { tipo: goalType, valor_kwh_mensual: goalKwh });
      setSaved(true);
      reload();
    } catch (error: unknown) {
      setSaveErrorKey(toErrorTextKey(error));
    } finally {
      setSaving(false);
    }
  };

  const average = state.status === 'ready' ? state.data.promedio_diario_30d_kwh : null;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor={colors['background-default']} />

      <View style={styles.header}>
        <TouchableOpacity
          style={styles.headerBtn}
          activeOpacity={0.7}
          onPress={() => router.back()}
          hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
          accessibilityRole="button"
          accessibilityLabel={t('a11y.volver')}
        >
          <ChevronLeft size={24} color={colors['text-primary']} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t('meta.encabezado')}</Text>
        <View style={styles.headerBtn} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {state.status === 'loading' && (
          <View accessibilityRole="progressbar" accessibilityLabel={t('comun.cargando')}>
            <View style={[styles.skeleton, styles.skeletonShort]} />
            <View style={[styles.skeleton, styles.skeletonTall]} />
            <View style={[styles.skeleton, styles.skeletonShort]} />
          </View>
        )}

        {state.status === 'error' && (
          <View>
            <Notice
              tone="error"
              title={t(`${state.errorKey}.titulo`)}
              body={t(`${state.errorKey}.cuerpo`)}
            />
            <TouchableOpacity
              style={styles.retryBtn}
              onPress={reload}
              accessibilityRole="button"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Text style={styles.retryText}>{t('comun.reintentar')}</Text>
            </TouchableOpacity>
          </View>
        )}

        {state.status === 'ready' && (
          <>
            {!canEdit && (
              <Notice
                tone="neutral"
                title={t('meta.lectura_titulo')}
                body={t('meta.lectura_cuerpo')}
              />
            )}

            <View style={styles.avgCard}>
              <View style={styles.avgTopRow}>
                <Text style={styles.avgLabel}>{t('meta.promedio_titulo')}</Text>
                <Text style={styles.avgPeriod}>{t('meta.promedio_periodo')}</Text>
              </View>
              <Text style={styles.avgValue}>
                {t('meta.promedio_valor', { kwh_dia: formatNumber(average, DECIMALES.kWh) })}
              </Text>
              <View style={styles.avgBadge}>
                <Text style={styles.avgBadgeText}>{t('meta.promedio_ayuda')}</Text>
              </View>
            </View>

            <Text style={styles.sectionTitle}>{t('meta.define_titulo')}</Text>
            <Text style={styles.sectionSubtitle}>{t('meta.define_cuerpo')}</Text>

            <View style={styles.metaCard}>
              <View style={styles.metaTopRow}>
                <Text style={styles.metaTitle}>{t('meta.mensual')}</Text>
                <View style={styles.metaBadge}>
                  <Text style={styles.metaBadgeText}>{t('meta.por_mes')}</Text>
                </View>
              </View>

              <View style={styles.counterRow}>
                <TouchableOpacity
                  style={[styles.counterBtn, !canEdit && styles.counterBtnDisabled]}
                  activeOpacity={0.7}
                  onPress={decrease}
                  disabled={!canEdit}
                  hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
                  accessibilityRole="button"
                  accessibilityLabel={t('a11y.meta_menos')}
                >
                  <Minus size={24} color={colors['text-primary']} />
                </TouchableOpacity>

                <Text style={styles.counterValue}>
                  {t('meta.valor', { valor: formatNumber(goalKwh) })}
                </Text>

                <TouchableOpacity
                  style={[styles.counterBtn, !canEdit && styles.counterBtnDisabled]}
                  activeOpacity={0.7}
                  onPress={increase}
                  disabled={!canEdit}
                  hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
                  accessibilityRole="button"
                  accessibilityLabel={t('a11y.meta_mas')}
                >
                  <Plus size={24} color={colors['text-primary']} />
                </TouchableOpacity>
              </View>

              <View style={styles.metaDivider} />

              <Text style={styles.metaEquivText}>
                {t('meta.equivale', {
                  kwh_dia: formatNumber(goalKwh / days, DECIMALES.kWh),
                  mes: t(`formato.mes.${mm}`),
                  dias: days,
                })}
              </Text>
              {zeroError && <Text style={styles.fieldError}>{t('meta.error_cero')}</Text>}
            </View>

            <Text style={[styles.sectionTitle, styles.sectionSpaced]}>{t('meta.tipo_titulo')}</Text>
            <Text style={styles.sectionSubtitle}>{t('meta.tipo_ayuda')}</Text>

            <View style={styles.tipoMetaCard}>
              <View style={styles.tipoMetaPillsRow} accessibilityRole="radiogroup">
                {GOAL_TYPES.map((type) => {
                  const active = goalType === type;
                  return (
                    <TouchableOpacity
                      key={type}
                      style={[styles.tipoPill, active && styles.tipoPillActive]}
                      activeOpacity={0.8}
                      onPress={() => {
                        setGoalType(type);
                        setSaved(false);
                      }}
                      disabled={!canEdit}
                      hitSlop={{ top: 7, bottom: 7, left: 0, right: 0 }}
                      accessibilityRole="radio"
                      accessibilityState={{ checked: active, disabled: !canEdit }}
                    >
                      <Text style={[styles.tipoPillText, active && styles.tipoPillTextActive]}>
                        {t(`meta.tipo.${type}.etiqueta`)}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
              <Text style={styles.tipoDescText}>{t(`meta.tipo.${goalType}.descripcion`)}</Text>
            </View>

            {saveErrorKey && (
              <Notice
                tone="error"
                title={t(`${saveErrorKey}.titulo`)}
                body={t(`${saveErrorKey}.cuerpo`)}
              />
            )}
            {saved && <Notice tone="success" title={t('meta.guardada')} />}

            {canEdit && (
              <TouchableOpacity
                style={[styles.btnGuardar, saving && styles.btnDisabled]}
                activeOpacity={0.85}
                onPress={handleSave}
                disabled={saving}
                accessibilityRole="button"
                accessibilityState={{ disabled: saving, busy: saving }}
              >
                <Text style={styles.btnGuardarText}>
                  {saving ? t('comun.cargando') : t('meta.boton')}
                </Text>
              </TouchableOpacity>
            )}
          </>
        )}

        <View style={styles.bottomSpace} />
      </ScrollView>
    </SafeAreaView>
  );
}

/** Alto de la cabecera en Figma (64): el token `topBar-height` vale 56, así que se compone sin
 * tocar el token (decisión del 24/11/2026). */
const HEADER_HEIGHT = sizes['iconButtonLg-size'] + spacing['16'];

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors['background-default'],
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing[16],
    height: HEADER_HEIGHT,
    borderBottomWidth: 1,
    borderBottomColor: colors['border-subtle'],
  },
  headerBtn: {
    width: sizes['iconButton-size'],
    height: sizes['iconButton-size'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    ...textStyle('display-m'),
    color: colors['text-primary'],
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: spacing[16],
    paddingTop: spacing[8],
  },

  skeleton: {
    borderRadius: radius.lg,
    backgroundColor: colors['background-surfaceAlt'],
    marginBottom: spacing[16],
  },
  skeletonShort: {
    height: 96,
  },
  skeletonTall: {
    height: 180,
  },

  avgCard: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    padding: spacing[16],
    marginBottom: spacing[20],
  },
  avgTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing[8],
  },
  avgLabel: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
  },
  avgPeriod: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
  },
  avgValue: {
    ...textStyle('data-l'),
    color: colors['text-accent'],
    marginBottom: spacing[12],
  },
  avgBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors['accent-soft'],
    borderRadius: radius.full,
    paddingHorizontal: spacing[12],
    paddingVertical: spacing[4],
  },
  avgBadgeText: {
    ...textStyle('ui-s-semibold-12'),
    color: colors['text-accent'],
  },

  sectionTitle: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
    marginBottom: spacing[4],
  },
  sectionSpaced: {
    marginTop: spacing[8],
  },
  sectionSubtitle: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
    marginBottom: spacing[16],
  },

  metaCard: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors['border-accent'],
    padding: spacing[16],
    marginBottom: spacing[20],
  },
  metaTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing[16],
  },
  metaTitle: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
  },
  metaBadge: {
    backgroundColor: colors['accent-soft'],
    borderRadius: radius.full,
    paddingHorizontal: spacing[12],
    paddingVertical: spacing[4],
  },
  metaBadgeText: {
    ...textStyle('ui-s-semibold-12'),
    color: colors['text-accent'],
  },
  counterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  counterBtn: {
    width: sizes['iconButtonLg-size'],
    height: sizes['iconButtonLg-size'],
    borderRadius: radius.full,
    backgroundColor: colors['background-surfaceAlt'],
    borderWidth: 1,
    borderColor: colors['border-medium'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  counterBtnDisabled: {
    backgroundColor: colors['state-disabled-bg'],
    borderColor: colors['state-disabled-border'],
  },
  counterValue: {
    ...textStyle('data-xl-32'),
    color: colors['text-primary'],
  },
  metaDivider: {
    height: 1,
    backgroundColor: colors['border-subtle'],
    marginVertical: spacing[16],
  },
  metaEquivText: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
    textAlign: 'center',
  },
  fieldError: {
    ...textStyle('body-xs-regular'),
    color: colors['text-error'],
    textAlign: 'center',
    marginTop: spacing[8],
  },

  tipoMetaCard: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    padding: spacing[16],
    marginBottom: spacing[20],
  },
  tipoMetaPillsRow: {
    flexDirection: 'row',
    gap: spacing[8],
    marginBottom: spacing[12],
  },
  tipoPill: {
    flex: 1,
    height: 34,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  tipoPillActive: {
    backgroundColor: colors['accent-soft'],
    borderColor: colors['border-accent'],
  },
  tipoPillText: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-muted'],
  },
  tipoPillTextActive: {
    color: colors['text-accent'],
  },
  tipoDescText: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
  },

  notice: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing[12],
    borderRadius: radius.lg,
    borderWidth: 1,
    padding: spacing[16],
    marginBottom: spacing[16],
  },
  noticeTexts: {
    flex: 1,
    gap: spacing[4],
  },
  noticeTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
  },
  noticeBody: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
  },
  retryBtn: {
    alignSelf: 'flex-start',
    paddingVertical: spacing[8],
  },
  retryText: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-accent'],
  },

  btnGuardar: {
    backgroundColor: colors['accent-primary'],
    borderRadius: radius.md,
    height: sizes['button-height'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnDisabled: {
    backgroundColor: colors['state-disabled-bg'],
  },
  btnGuardarText: {
    ...textStyle('ui-m-semibold'),
    color: colors['text-inverse'],
  },
  bottomSpace: {
    height: spacing[24],
  },
});
