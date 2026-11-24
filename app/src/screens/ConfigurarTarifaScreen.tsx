/**
 * Configurar tarifa (sección 6.15; RN-V-02, RN-XVI-05). Contrato:
 * GET /hogares/{hogar_id}/tarifa (obtenerTarifa) y POST /hogares/{hogar_id}/tarifas
 * (crearTarifa). Mapa: docs/MAPA-DE-INTEGRACION.md, filas 34 y 35.
 *
 * - Solo el administrador cambia la tarifa (`puede_editar`); los demás la consultan.
 * - «Vigente desde» es mes y año (se guarda el día 1), posterior a la tarifa vigente y
 *   sin meses futuros.
 * - COP sin decimales; el cargo fijo mensual no se prorratea.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Modal,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TextStyle,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Calendar, ChevronDown, ChevronLeft, CircleAlert, CircleCheck, CircleHelp, CircleX, Info } from 'lucide-react-native';
import { useRouter } from 'expo-router';

import { createTariff, getTariff } from '@/api/goalsTariff';
import { toErrorTextKey } from '@/api/errors';
import type { SuccessBody } from '@/api/client';
import { formatCOP, formatNumber } from '@/format';
import { colors, fontFamilyFor, radius, sizes, spacing, typography } from '@/theme';
import { t } from '@/texts';

import { INPUT_LIMITS, sanitizeCop, sanitizeDecimal } from './inputFilters';

type TariffView = SuccessBody<'/hogares/{hogar_id}/tarifa', 'get'>;

type TariffState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'ready'; data: TariffView };

const OPERATOR_IDS = ['1', '2', '3', '4', '5', '6', '7', '8'] as const;
const MONTH_KEYS = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'] as const;
const BOGOTA_OFFSET_MS = -5 * 60 * 60 * 1000;
const MAX_MONTHS = 12;

/**
 * Hook de datos de la pantalla (cargando, error y datos).
 * TODO(pendiente: hogarId): aún no existe el estado de sesión/hogar (GET /hogares/actual,
 * fila 12 del mapa); la pantalla recibe `hogarId` por prop. Al existir el provider de React
 * Query, este hook pasa a `useConfigurarTarifaData.ts` con useQuery/useMutation
 * (queryKey('obtenerTarifa', hogarId)).
 */
function useTariffData(hogarId: string | null) {
  const [state, setState] = useState<TariffState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    // Sin hogar no se pide nada: el error se deriva abajo, sin setState aquí.
    if (!hogarId) return;
    let cancelled = false;
    getTariff(hogarId)
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
  const visibleState: TariffState = hogarId
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

/** «2026-09» o «2026-09-01» → «septiembre de 2026» (catálogo formato.mes_anio). */
function monthYearLabel(value: string): string {
  const [anio, mes] = value.split('-');
  return t('formato.mes_anio', { mes: t(`formato.mes.${mes}`), anio });
}

/** Meses elegibles (más reciente primero): posteriores a la tarifa vigente, hasta el mes actual. */
function eligibleMonths(vigenteDesde: string | null, now: Date = new Date()): string[] {
  const local = new Date(now.getTime() + BOGOTA_OFFSET_MS);
  let year = local.getUTCFullYear();
  let month = local.getUTCMonth() + 1;
  const floor = vigenteDesde ? vigenteDesde.slice(0, 7) : null;
  const months: string[] = [];
  for (let i = 0; i < MAX_MONTHS; i += 1) {
    const key = `${year}-${String(month).padStart(2, '0')}`;
    if (floor !== null && key <= floor) break;
    months.push(key);
    month -= 1;
    if (month === 0) {
      month = 12;
      year -= 1;
    }
  }
  return months;
}

/** Texto es-CO («12.000», «892,5») → número, o NaN si no es válido. */
function parseEsCoNumber(text: string): number {
  const clean = text.trim().replace(/\./g, '').replace(',', '.');
  return clean === '' || !/^\d+(\.\d+)?$/.test(clean) ? Number.NaN : Number(clean);
}

type FieldErrors = { precio?: string; vigencia?: string; cargoFijo?: string };

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

/** Hoja inferior (BottomSheet.md): fondo `surfaceAlt`, tirador, título, descripción y cerrar de 48. */
function SheetFrame({
  visible,
  title,
  support,
  onClose,
  children,
}: {
  visible: boolean;
  title: string;
  support?: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.modalOverlay}>
        <TouchableOpacity style={styles.modalBackdrop} activeOpacity={1} onPress={onClose} accessible={false} />
        <View style={styles.modalContent} accessibilityViewIsModal>
          <View style={styles.sheetHandle} />
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle} accessibilityRole="header">
              {title}
            </Text>
            <TouchableOpacity
              onPress={onClose}
              style={styles.sheetClose}
              accessibilityRole="button"
              accessibilityLabel={t('comun.cerrar')}
            >
              <CircleX size={24} color={colors['text-muted']} />
            </TouchableOpacity>
          </View>
          {support ? <Text style={styles.modalSupport}>{support}</Text> : null}
          {children}
        </View>
      </View>
    </Modal>
  );
}

/** Lista de opciones (OptionItem.md): la elegida con fondo, texto de acento y check. */
function SelectSheet({
  visible,
  title,
  support,
  options,
  selected,
  onSelect,
  onClose,
}: {
  visible: boolean;
  title: string;
  support?: string;
  options: { value: string; label: string }[];
  selected: string | null;
  onSelect: (value: string) => void;
  onClose: () => void;
}) {
  return (
    <SheetFrame visible={visible} title={title} support={support} onClose={onClose}>
      <ScrollView>
        {options.map((option) => {
          const active = option.value === selected;
          return (
            <TouchableOpacity
              key={option.value}
              style={[styles.modalItem, active && styles.modalItemActive]}
              onPress={() => onSelect(option.value)}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
            >
              <Text style={[styles.modalItemText, active && styles.modalItemTextActive]}>{option.label}</Text>
              {active && <CircleCheck size={18} color={colors['text-accent']} />}
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </SheetFrame>
  );
}

/** Chip de la cuadrícula de mes y año (Chip.md): activo con acento, deshabilitado con `state-disabled-*`. */
function PickerChip({
  label,
  active,
  disabled = false,
  onPress,
}: {
  label: string;
  active: boolean;
  disabled?: boolean;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity
      style={styles.pickerChipTouch}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="radio"
      accessibilityState={{ checked: active, disabled }}
    >
      <View style={[styles.pickerChip, active && styles.pickerChipActive, disabled && styles.pickerChipDisabled]}>
        <Text style={[styles.pickerChipText, active && styles.pickerChipTextActive, disabled && styles.pickerChipTextDisabled]}>
          {label}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

/**
 * Hoja «Vigente desde» (BottomSheet.md + Select.md): año y cuadrícula de meses con Chip; solo se
 * eligen meses posteriores a la tarifa vigente y no futuros; «Aplicar · mes de año» confirma.
 */
export function SinceSheet({
  months,
  selected,
  support,
  onApply,
  onClose,
}: {
  /** Meses elegibles («2026-09») de más reciente a más antiguo. */
  months: string[];
  selected: string | null;
  support?: string;
  onApply: (value: string) => void;
  onClose: () => void;
}) {
  const years = useMemo(() => Array.from(new Set(months.map((m) => m.slice(0, 4)))).sort(), [months]);
  const initial = selected && months.includes(selected) ? selected : (months[0] ?? null);
  const [year, setYear] = useState(initial ? initial.slice(0, 4) : (years[years.length - 1] ?? ''));
  const [month, setMonth] = useState<string | null>(initial ? initial.slice(5, 7) : null);

  const draft = month ? `${year}-${month}` : null;
  const canApply = draft !== null && months.includes(draft);

  return (
    <SheetFrame visible title={t('tarifa.hoja_vigencia_titulo')} support={support} onClose={onClose}>
      <Text style={styles.pickerLabel}>{t('tarifa.hoja_vigencia_anio')}</Text>
      <View style={styles.pickerRow} accessibilityRole="radiogroup">
        {years.map((y) => (
          <PickerChip key={y} label={y} active={y === year} onPress={() => setYear(y)} />
        ))}
      </View>

      <Text style={styles.pickerLabel}>{t('tarifa.hoja_vigencia_mes')}</Text>
      <View style={styles.pickerRow} accessibilityRole="radiogroup">
        {MONTH_KEYS.map((m) => (
          <PickerChip
            key={m}
            label={t(`formato.mes_corto.${m}`)}
            active={m === month}
            disabled={!months.includes(`${year}-${m}`)}
            onPress={() => setMonth(m)}
          />
        ))}
      </View>

      <TouchableOpacity
        style={[styles.btnGuardar, !canApply && styles.btnDisabled]}
        onPress={() => draft && canApply && onApply(draft)}
        disabled={!canApply}
        accessibilityRole="button"
        accessibilityState={{ disabled: !canApply }}
      >
        <Text style={[styles.btnGuardarText, !canApply && styles.pickerChipTextDisabled]}>
          {draft && canApply ? t('tarifa.hoja_vigencia_aplicar', { mes_anio: monthYearLabel(draft) }) : t('tarifa.vigencia_ph')}
        </Text>
      </TouchableOpacity>
    </SheetFrame>
  );
}

export interface ConfigurarTarifaScreenProps {
  /** TODO(pendiente: hogarId): vendrá del estado de sesión/hogar cuando exista. */
  hogarId?: string | null;
}

export function ConfigurarTarifaScreen({ hogarId = null }: ConfigurarTarifaScreenProps) {
  const router = useRouter();
  const { state, reload } = useTariffData(hogarId);

  const [operator, setOperator] = useState<string | null>(null);
  const [price, setPrice] = useState('');
  const [since, setSince] = useState<string | null>(null);
  const [fixedCharge, setFixedCharge] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const [saveErrorKey, setSaveErrorKey] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [sheet, setSheet] = useState<'operator' | 'since' | null>(null);

  const activeTariff = state.status === 'ready' ? state.data.tarifa : null;
  const canEdit = state.status === 'ready' && state.data.puede_editar;
  const months = useMemo(
    () => eligibleMonths(activeTariff?.vigente_desde ?? null),
    [activeTariff?.vigente_desde],
  );
  const activeMonthYear = activeTariff ? monthYearLabel(activeTariff.vigente_desde) : '';

  /** «Editar tarifa»: precarga el formulario con la tarifa vigente. */
  const prefillFromActive = () => {
    if (!activeTariff) return;
    setOperator(activeTariff.operador);
    setPrice(String(activeTariff.precio_kwh).replace('.', ','));
    setFixedCharge(
      activeTariff.cargo_fijo_mensual === null ? '' : formatNumber(activeTariff.cargo_fijo_mensual),
    );
    setSince(null);
    setFieldErrors({});
    setSaved(false);
    setSaveErrorKey(null);
  };

  const handleSave = async () => {
    const errors: FieldErrors = {};
    const priceValue = parseEsCoNumber(price);
    if (price.trim() === '') errors.precio = t('error.campo.precio_requerido');
    else if (!(priceValue > 0)) errors.precio = t('error.campo.precio_mayor_cero');

    if (since === null) errors.vigencia = t('error.campo.vigencia_requerida');

    let chargeValue: number | null = null;
    if (fixedCharge.trim() !== '') {
      chargeValue = parseEsCoNumber(fixedCharge);
      if (Number.isNaN(chargeValue) || chargeValue < 0) {
        errors.cargoFijo = t('error.campo.cargo_fijo_invalido');
      }
    }

    setFieldErrors(errors);
    setSaved(false);
    setSaveErrorKey(null);
    if (Object.keys(errors).length > 0 || !hogarId || since === null) return;

    setSaving(true);
    try {
      await createTariff(hogarId, {
        operador: operator,
        precio_kwh: priceValue,
        vigente_desde: since,
        cargo_fijo_mensual: chargeValue,
      });
      setSaved(true);
      setPrice('');
      setFixedCharge('');
      setSince(null);
      setOperator(null);
      reload();
    } catch (error: unknown) {
      setSaveErrorKey(toErrorTextKey(error));
    } finally {
      setSaving(false);
    }
  };

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
        <Text style={styles.headerTitle}>{t('tarifa.encabezado')}</Text>
        <View style={styles.headerBtn} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {state.status === 'loading' && (
          <View accessibilityRole="progressbar" accessibilityLabel={t('comun.cargando')}>
            <View style={[styles.activeCard, styles.skeletonCard]} />
            <View style={[styles.skeletonLine, styles.skeletonWide]} />
            <View style={styles.skeletonLine} />
            <View style={styles.skeletonLine} />
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
            {activeTariff ? (
              <View style={styles.activeCard}>
                <View style={styles.activeTopRow}>
                  <View style={styles.activeTitleBox}>
                    <Text style={styles.activeTitle}>{t('tarifa.activa')}</Text>
                    {activeTariff.operador ? (
                      <Text style={styles.activeSubtitle}>{activeTariff.operador}</Text>
                    ) : null}
                  </View>
                  <View style={styles.badgeActiva}>
                    <View style={styles.badgeDot} />
                    <Text style={styles.badgeActivaText}>{t('tarifa.activa_chip')}</Text>
                  </View>
                </View>

                <Text style={styles.metricCurrency}>
                  {t('tarifa.valor_kwh', { valor: formatCOP(activeTariff.precio_kwh) })}
                </Text>
                <Text style={styles.activeInfoText}>
                  {t('tarifa.vigente_desde_resumen', { mes_anio: activeMonthYear })}
                </Text>

                {canEdit && (
                  <TouchableOpacity
                    style={styles.btnEditarTarifa}
                    activeOpacity={0.7}
                    onPress={prefillFromActive}
                    accessibilityRole="button"
                  >
                    <Text style={styles.btnEditarTarifaText}>{t('tarifa.editar')}</Text>
                  </TouchableOpacity>
                )}
              </View>
            ) : (
              <Notice
                tone="neutral"
                title={t('tarifa.sin_tarifa_titulo')}
                body={t('tarifa.sin_tarifa_cuerpo')}
              />
            )}

            {!canEdit && (
              <Notice
                tone="neutral"
                title={t('tarifa.lectura_titulo')}
                body={t('tarifa.lectura_cuerpo')}
              />
            )}

            {canEdit && (
              <>
                <Text style={styles.sectionTitle}>{t('tarifa.actualizar_titulo')}</Text>
                <Text style={styles.sectionSubtitle}>{t('tarifa.actualizar_cuerpo')}</Text>

                <Text style={styles.fieldLabel}>{t('tarifa.operador')}</Text>
                <TouchableOpacity
                  style={styles.selectInput}
                  activeOpacity={0.7}
                  onPress={() => setSheet('operator')}
                  accessibilityRole="button"
                >
                  <Text style={operator ? styles.selectInputText : styles.placeholderText}>
                    {operator ?? t('tarifa.operador_ph')}
                  </Text>
                  <ChevronDown size={20} color={colors['text-muted']} />
                </TouchableOpacity>

                <Text style={[styles.fieldLabel, styles.fieldSpaced]}>{t('tarifa.precio')}</Text>
                <View style={[styles.textInputBox, fieldErrors.precio && styles.inputError]}>
                  <Text style={styles.inputPrefix}>$</Text>
                  <TextInput
                    style={styles.textInput}
                    value={price}
                    onChangeText={(value) => setPrice(sanitizeDecimal(value))}
                    maxLength={INPUT_LIMITS.priceIntDigits + INPUT_LIMITS.priceDecimals + 1}
                    keyboardType="decimal-pad"
                    placeholder="892"
                    placeholderTextColor={colors['text-muted']}
                    accessibilityLabel={t('tarifa.precio')}
                  />
                  <Text style={styles.inputSuffix}>{t('tarifa.valor_kwh', { valor: '' }).trim()}</Text>
                </View>
                {fieldErrors.precio ? (
                  <Text style={styles.fieldError}>{fieldErrors.precio}</Text>
                ) : (
                  <Text style={styles.fieldHint}>{t('tarifa.precio_ayuda')}</Text>
                )}

                <Text style={[styles.fieldLabel, styles.fieldSpaced]}>{t('tarifa.vigencia')}</Text>
                <TouchableOpacity
                  style={[styles.selectInput, fieldErrors.vigencia && styles.inputError]}
                  activeOpacity={0.7}
                  onPress={() => setSheet('since')}
                  accessibilityRole="button"
                >
                  <View style={styles.selectLeftGroup}>
                    <Calendar
                      size={19}
                      color={colors['text-muted']}
                      style={styles.selectIcon}
                    />
                    <Text style={since ? styles.selectInputText : styles.placeholderText}>
                      {since ? monthYearLabel(since) : t('tarifa.vigencia_ph')}
                    </Text>
                  </View>
                  <ChevronDown size={20} color={colors['text-muted']} />
                </TouchableOpacity>
                {fieldErrors.vigencia ? (
                  <Text style={styles.fieldError}>{fieldErrors.vigencia}</Text>
                ) : null}

                <Text style={[styles.fieldLabel, styles.fieldSpaced]}>{t('tarifa.cargo_fijo')}</Text>
                <View style={[styles.textInputBox, fieldErrors.cargoFijo && styles.inputError]}>
                  <Text style={styles.inputPrefix}>$</Text>
                  <TextInput
                    style={styles.textInput}
                    value={fixedCharge}
                    onChangeText={(value) => setFixedCharge(sanitizeCop(value))}
                    maxLength={INPUT_LIMITS.fixedChargeDigits + 2}
                    keyboardType="number-pad"
                    placeholder={t('tarifa.cargo_fijo_ph')}
                    placeholderTextColor={colors['text-muted']}
                    accessibilityLabel={t('tarifa.cargo_fijo')}
                  />
                </View>
                {fieldErrors.cargoFijo ? (
                  <Text style={styles.fieldError}>{fieldErrors.cargoFijo}</Text>
                ) : null}

                <View style={styles.avisoCard}>
                  <CircleHelp
                    size={18}
                    color={colors['text-muted']}
                    style={styles.avisoIcon}
                  />
                  <Text style={styles.avisoText}>{t('tarifa.aviso')}</Text>
                </View>

                {saveErrorKey && (
                  <Notice
                    tone="error"
                    title={t(`${saveErrorKey}.titulo`)}
                    body={t(`${saveErrorKey}.cuerpo`, { mes_anio: activeMonthYear })}
                  />
                )}
                {saved && <Notice tone="success" title={t('tarifa.guardada')} />}

                <TouchableOpacity
                  style={[styles.btnGuardar, saving && styles.btnDisabled]}
                  activeOpacity={0.85}
                  onPress={handleSave}
                  disabled={saving}
                  accessibilityRole="button"
                  accessibilityState={{ disabled: saving, busy: saving }}
                >
                  <Text style={styles.btnGuardarText}>
                    {saving ? t('comun.cargando') : t('tarifa.guardar')}
                  </Text>
                </TouchableOpacity>
              </>
            )}
          </>
        )}

        <View style={styles.bottomSpace} />
      </ScrollView>

      <SelectSheet
        visible={sheet === 'operator'}
        title={t('tarifa.hoja_operador_titulo')}
        support={t('tarifa.hoja_operador_apoyo')}
        options={OPERATOR_IDS.map((id) => ({
          value: t(`tarifa.operadores.${id}`),
          label: t(`tarifa.operadores.${id}`),
        }))}
        selected={operator}
        onSelect={(value) => {
          setOperator(value);
          setSheet(null);
        }}
        onClose={() => setSheet(null)}
      />

      {sheet === 'since' && (
        <SinceSheet
          months={months}
          selected={since}
          support={activeTariff ? t('tarifa.hoja_vigencia_ayuda', { mes_anio: activeMonthYear }) : undefined}
          onApply={(value) => {
            setSince(value);
            setFieldErrors((prev) => ({ ...prev, vigencia: undefined }));
            setSheet(null);
          }}
          onClose={() => setSheet(null)}
        />
      )}
    </SafeAreaView>
  );
}

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
    paddingTop: spacing[12],
    paddingBottom: spacing[8],
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

  activeCard: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors['border-accent'],
    padding: spacing[16],
    marginBottom: spacing[20],
  },
  skeletonCard: {
    height: 160,
    backgroundColor: colors['background-surfaceAlt'],
    borderColor: colors['border-subtle'],
  },
  skeletonLine: {
    height: spacing[48],
    borderRadius: radius.md,
    backgroundColor: colors['background-surfaceAlt'],
    marginBottom: spacing[12],
  },
  skeletonWide: {
    width: '60%',
  },
  activeTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing[12],
  },
  activeTitleBox: {
    flex: 1,
    marginRight: spacing[8],
  },
  activeTitle: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
    marginBottom: spacing[4],
  },
  activeSubtitle: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
  },
  badgeActiva: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors['accent-soft'],
    borderRadius: radius.full,
    paddingHorizontal: spacing[12],
    paddingVertical: spacing[4],
    gap: spacing[8],
  },
  badgeDot: {
    width: spacing[8],
    height: spacing[8],
    borderRadius: radius.full,
    backgroundColor: colors['accent-primary'],
  },
  badgeActivaText: {
    ...textStyle('ui-s-semibold-12'),
    color: colors['text-accent'],
  },
  metricCurrency: {
    ...textStyle('data-xl-32'),
    color: colors['text-accent'],
    marginBottom: spacing[8],
  },
  activeInfoText: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
  },
  btnEditarTarifa: {
    backgroundColor: colors['background-surfaceAlt'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    height: sizes['button-height'],
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing[16],
  },
  btnEditarTarifaText: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-accent'],
  },

  sectionTitle: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
    marginBottom: spacing[4],
  },
  sectionSubtitle: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
    marginBottom: spacing[16],
  },
  fieldLabel: {
    ...textStyle('body-s-medium'),
    color: colors['text-primary'],
    marginBottom: spacing[8],
  },
  fieldSpaced: {
    marginTop: spacing[16],
  },
  selectInput: {
    backgroundColor: colors['background-surfaceAlt'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    height: sizes['button-height'],
    paddingHorizontal: spacing[16],
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  selectLeftGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  selectIcon: {
    marginRight: spacing[12],
  },
  selectInputText: {
    ...textStyle('body-m-regular'),
    color: colors['text-primary'],
  },
  placeholderText: {
    ...textStyle('body-m-regular'),
    color: colors['text-muted'],
  },
  textInputBox: {
    backgroundColor: colors['background-surfaceAlt'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    height: sizes['button-height'],
    paddingHorizontal: spacing[16],
    flexDirection: 'row',
    alignItems: 'center',
  },
  inputError: {
    borderColor: colors['border-error'],
  },
  inputPrefix: {
    ...textStyle('body-m-regular'),
    color: colors['text-muted'],
    marginRight: spacing[8],
  },
  textInput: {
    ...textStyle('body-m-regular'),
    flex: 1,
    color: colors['text-primary'],
  },
  inputSuffix: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
    marginLeft: spacing[8],
  },
  fieldHint: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
    marginTop: spacing[8],
  },
  fieldError: {
    ...textStyle('body-xs-regular'),
    color: colors['text-error'],
    marginTop: spacing[8],
  },

  avisoCard: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    padding: spacing[16],
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginTop: spacing[16],
    marginBottom: spacing[20],
  },
  avisoIcon: {
    marginRight: spacing[12],
  },
  avisoText: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
    flex: 1,
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

  modalOverlay: {
    flex: 1,
    backgroundColor: colors['background-overlay'],
    justifyContent: 'flex-end',
  },
  modalBackdrop: {
    flex: 1,
  },
  modalContent: {
    backgroundColor: colors['background-surfaceAlt'],
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingTop: spacing[8],
    paddingHorizontal: spacing[16],
    paddingBottom: spacing[32],
    maxHeight: '80%',
  },
  sheetHandle: {
    alignSelf: 'center',
    width: spacing[40],
    height: spacing[4],
    borderRadius: radius.full,
    backgroundColor: colors['text-muted'],
  },
  sheetClose: {
    width: spacing[48],
    height: spacing[48],
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modalTitle: {
    ...textStyle('display-m'),
    color: colors['text-primary'],
    flex: 1,
  },
  pickerLabel: {
    ...textStyle('body-s-medium'),
    color: colors['text-primary'],
    marginTop: spacing[8],
  },
  pickerRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: -spacing[4],
  },
  pickerChipTouch: {
    width: '25%',
    minHeight: spacing[48],
    justifyContent: 'center',
    paddingHorizontal: spacing[4],
  },
  pickerChip: {
    minHeight: spacing[32] + spacing[4],
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors['border-medium'],
  },
  pickerChipActive: {
    backgroundColor: colors['accent-soft'],
    borderColor: colors['border-accent'],
  },
  pickerChipDisabled: {
    backgroundColor: colors['state-disabled-bg'],
    borderColor: colors['state-disabled-border'],
  },
  pickerChipText: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-muted'],
  },
  pickerChipTextActive: {
    color: colors['text-accent'],
  },
  pickerChipTextDisabled: {
    color: colors['state-disabled-text'],
  },
  modalSupport: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
    marginBottom: spacing[12],
  },
  modalItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    minHeight: sizes['button-height'],
    paddingVertical: spacing[12],
    borderBottomWidth: 1,
    borderBottomColor: colors['border-subtle'],
  },
  modalItemActive: {
    backgroundColor: colors['state-selected-bg'],
    paddingHorizontal: spacing[12],
    borderRadius: radius.sm,
  },
  modalItemText: {
    ...textStyle('body-m-regular'),
    color: colors['text-muted'],
  },
  modalItemTextActive: {
    ...textStyle('body-m-medium'),
    color: colors['text-accent'],
  },
});
