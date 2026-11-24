/**
 * Gestionar correo (sección 6.13; RN-IX-03, RN-IX-06). Solo usa Supabase Auth (no hay
 * endpoint de la API; MAPA-DE-INTEGRACION.md, fila «Pantallas solo con Supabase Auth»):
 * el correo actual sale de la sesión y el cambio se pide con `auth.updateUser({ email })`.
 *
 * - El correo actual es solo lectura.
 * - Supabase envía un enlace de confirmación al nuevo correo; el correo cambia cuando se
 *   confirma, y mientras tanto se sigue usando el actual.
 * - «Continuar» se habilita solo con datos válidos.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CircleAlert, CircleCheck, CircleX, Mail, User } from 'lucide-react-native';
import { useRouter } from 'expo-router';

import { Button, ScreenHeader } from '@/components';
import { MOCK_EMAIL, USE_MOCKS } from '@/api/devMocks';
import { getSupabase } from '@/state/supabase';
import { colors, radius, sizes, spacing, textStyle } from '@/theme';
import { t } from '@/texts';

import { INPUT_LIMITS, sanitizeEmail } from './inputFilters';

type EmailState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'ready'; email: string };

type SendState =
  | { status: 'idle' }
  | { status: 'sending' }
  | { status: 'sent'; email: string }
  | { status: 'error'; errorKey: string };

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Hook de datos de la pantalla: correo actual (sesión de Supabase) y envío del enlace.
 * TODO(pendiente: mensajes de error de Auth): el catálogo no tiene textos para los errores
 * de Supabase Auth (p. ej. «correo ya registrado»); se usa `error.app.desconocido`.
 * TODO(pendiente: emailRedirectTo): definir el enlace de retorno del correo de confirmación.
 */
function useManageEmailData() {
  const [state, setState] = useState<EmailState>({ status: 'loading' });
  const [send, setSend] = useState<SendState>({ status: 'idle' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (USE_MOCKS) {
          // Modo de ejemplo (solo desarrollo): sin Supabase, correo simulado.
          await new Promise((resolve) => setTimeout(resolve, 450));
          if (!cancelled) setState({ status: 'ready', email: MOCK_EMAIL });
          return;
        }
        const { data, error } = await getSupabase().auth.getUser();
        if (cancelled) return;
        if (error || !data.user?.email) {
          setState({ status: 'error', errorKey: 'error.app.sesion_vencida' });
        } else {
          setState({ status: 'ready', email: data.user.email });
        }
      } catch {
        if (!cancelled) setState({ status: 'error', errorKey: 'error.app.desconocido' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  // El esqueleto se muestra al pedir de nuevo (evento), no dentro del efecto.
  const reload = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((n) => n + 1);
  }, []);

  const sendChange = useCallback(async (newEmail: string) => {
    setSend({ status: 'sending' });
    try {
      if (USE_MOCKS) {
        await new Promise((resolve) => setTimeout(resolve, 450));
        setSend({ status: 'sent', email: newEmail });
        return true;
      }
      const { error } = await getSupabase().auth.updateUser({ email: newEmail });
      if (error) {
        setSend({ status: 'error', errorKey: 'error.app.desconocido' });
        return false;
      }
      setSend({ status: 'sent', email: newEmail });
      return true;
    } catch {
      setSend({ status: 'error', errorKey: 'error.app.sin_conexion' });
      return false;
    }
  }, []);

  return { state, reload, send, sendChange };
}


interface EmailFieldProps {
  label: string;
  value: string;
  onChangeText?: (value: string) => void;
  placeholder?: string;
  readOnly?: boolean;
  error?: string;
}

function EmailField({ label, value, onChangeText, placeholder, readOnly = false, error }: EmailFieldProps) {
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View
        style={[
          styles.inputContainer,
          readOnly && styles.inputReadOnly,
          error ? styles.inputError : null,
        ]}
      >
        <TextInput
          style={[styles.textInput, readOnly && styles.textInputReadOnly]}
          value={value}
          onChangeText={(value) => onChangeText?.(sanitizeEmail(value))}
          maxLength={INPUT_LIMITS.emailLength}
          placeholder={placeholder}
          placeholderTextColor={colors['text-muted']}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          editable={!readOnly}
          accessibilityLabel={label}
        />
      </View>
      {error ? (
        <View style={styles.messageRow} accessibilityRole="alert">
          <CircleX size={16} color={colors['text-error']} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}
    </View>
  );
}

export function GestionarCorreoScreen() {
  const router = useRouter();
  const { state, reload, send, sendChange } = useManageEmailData();

  const [newEmail, setNewEmail] = useState('');
  const [confirmEmail, setConfirmEmail] = useState('');
  const [resent, setResent] = useState(false);

  const newTrim = newEmail.trim();
  const confirmTrim = confirmEmail.trim();
  const currentEmail = state.status === 'ready' ? state.email : '';

  const invalidFormat = newTrim.length > 0 && !EMAIL_PATTERN.test(newTrim);
  const mismatch = confirmTrim.length > 0 && newTrim !== confirmTrim;
  // TODO(pendiente: texto «el nuevo correo debe ser distinto al actual»): el catálogo no lo
  // define; mientras tanto, igual al actual deja «Continuar» deshabilitado sin mensaje.
  const sameAsCurrent = newTrim.toLowerCase() === currentEmail.toLowerCase();
  const isValid =
    state.status === 'ready' &&
    newTrim.length > 0 &&
    !invalidFormat &&
    confirmTrim === newTrim &&
    !sameAsCurrent;
  const sending = send.status === 'sending';
  /** Enlace enviado: la pantalla pasa a «Revisa tu correo». */
  const sent = state.status === 'ready' && send.status === 'sent' ? send : null;

  const handleContinue = async () => {
    if (!isValid || sending) return;
    setResent(false);
    await sendChange(newTrim);
  };

  const handleResend = async () => {
    if (send.status !== 'sent' || sending) return;
    const ok = await sendChange(send.email);
    setResent(ok);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor={colors['background-default']} />

      <ScreenHeader
        titulo={t(sent ? 'auth.revisa_correo.titulo' : 'correo.encabezado')}
        onAtras={() => router.back()}
      />

      {/* «Revisa tu correo» (Figma A7.7): ícono centrado, texto y acciones abajo. */}
      {sent ? (
        <View style={styles.sentScreen}>
          <View style={styles.sentContent}>
            <View style={styles.sentIcon}>
              <Mail size={32} color={colors['accent-primary']} />
            </View>
            <Text style={styles.sentTitle} accessibilityRole="header">
              {t('auth.revisa_correo.titulo')}
            </Text>
            <Text style={styles.sentBody}>{t('auth.revisa_correo.cambio_correo', { correo: sent.email })}</Text>
            <Text style={styles.sentHint}>{t('auth.revisa_correo.no_llego')}</Text>
            {resent && (
              <View style={styles.messageRow} accessibilityRole="alert">
                <CircleCheck size={16} color={colors['text-success']} />
                <Text style={styles.successText}>{t('auth.revisa_correo.reenviado')}</Text>
              </View>
            )}
          </View>
          <View style={styles.sentActions}>
            <Button variante="secundario" bloque estado={sending ? 'cargando' : 'normal'} onClick={() => void handleResend()}>
              {t('auth.revisa_correo.reenviar')}
            </Button>
            <Button variante="fantasma" bloque onClick={() => router.back()}>
              {t('auth.revisa_correo.volver_config')}
            </Button>
          </View>
        </View>
      ) : (
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
        {state.status === 'loading' && (
          <View accessibilityRole="progressbar" accessibilityLabel={t('comun.cargando')}>
            <View style={[styles.skeleton, styles.skeletonShort]} />
            <View style={[styles.skeleton, styles.skeletonTall]} />
          </View>
        )}

        {state.status === 'error' && (
          <View>
            <View style={styles.errorBox} accessibilityRole="alert">
              <CircleAlert size={20} color={colors['text-error']} />
              <View style={styles.errorTexts}>
                <Text style={styles.errorTitle}>{t(`${state.errorKey}.titulo`)}</Text>
                <Text style={styles.errorBody}>{t(`${state.errorKey}.cuerpo`)}</Text>
              </View>
            </View>
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

        {state.status === 'ready' && send.status !== 'sent' && (
          <>
            <View style={styles.bannerCard}>
              <View style={styles.bannerIconBox}>
                <User size={22} color={colors['text-accent']} />
              </View>
              <View style={styles.bannerTextContainer}>
                <Text style={styles.bannerTitle}>{t('correo.titulo')}</Text>
                <Text style={styles.bannerSubtitle}>{t('correo.cuerpo')}</Text>
              </View>
            </View>

            <View style={styles.formCard}>
              <EmailField label={t('correo.actual')} value={state.email} readOnly />
              <EmailField
                label={t('correo.nuevo')}
                value={newEmail}
                onChangeText={setNewEmail}
                placeholder={t('correo.nuevo_ph')}
                error={invalidFormat ? t('error.campo.correo_invalido') : undefined}
              />
              <EmailField
                label={t('correo.confirmar')}
                value={confirmEmail}
                onChangeText={setConfirmEmail}
                placeholder={t('correo.confirmar_ph')}
                error={mismatch ? t('error.campo.correos_no_coinciden') : undefined}
              />

              <View style={styles.infoBox}>
                <View style={styles.stepBadge}>
                  <Text style={styles.stepBadgeText}>{t('correo.paso')}</Text>
                </View>
                <View style={styles.infoTextContainer}>
                  <Text style={styles.infoTitle}>{t('correo.verif_titulo')}</Text>
                  <Text style={styles.infoSubtitle}>{t('correo.verif_cuerpo')}</Text>
                </View>
              </View>

              <View style={styles.divider} />

              {send.status === 'error' && (
                <View style={styles.errorBox} accessibilityRole="alert">
                  <CircleAlert size={20} color={colors['text-error']} />
                  <View style={styles.errorTexts}>
                    <Text style={styles.errorTitle}>{t(`${send.errorKey}.titulo`)}</Text>
                    <Text style={styles.errorBody}>{t(`${send.errorKey}.cuerpo`)}</Text>
                  </View>
                </View>
              )}

              <TouchableOpacity
                style={[styles.btnPrimary, (!isValid || sending) && styles.btnDisabled]}
                activeOpacity={0.85}
                onPress={handleContinue}
                disabled={!isValid || sending}
                accessibilityRole="button"
                accessibilityState={{ disabled: !isValid || sending, busy: sending }}
              >
                <Text style={[styles.btnPrimaryText, (!isValid || sending) && styles.btnDisabledText]}>
                  {sending ? t('comun.cargando') : t('correo.boton')}
                </Text>
              </TouchableOpacity>
            </View>
          </>
        )}

          <View style={styles.bottomSpace} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors['background-default'],
  },
  scrollView: {
    flex: 1,
  },
  sentScreen: { flex: 1, paddingHorizontal: spacing[16], paddingBottom: spacing[24] },
  sentContent: { flex: 1, alignItems: 'center', paddingTop: spacing[64], gap: spacing[16] },
  sentIcon: {
    width: spacing[64] + spacing[8],
    height: spacing[64] + spacing[8],
    borderRadius: radius.full,
    backgroundColor: colors['accent-soft'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  sentActions: { gap: spacing[12] },
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
    height: 80,
  },
  skeletonTall: {
    height: 300,
  },

  bannerCard: {
    backgroundColor: colors['status-info-bg'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['status-info-border'],
    padding: spacing[16],
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing[20],
  },
  bannerIconBox: {
    width: spacing[40] + spacing[4],
    height: spacing[40] + spacing[4],
    borderRadius: radius.lg,
    backgroundColor: colors['background-surfaceAlt'],
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing[12],
  },
  bannerTextContainer: {
    flex: 1,
  },
  bannerTitle: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
    marginBottom: spacing[4],
  },
  bannerSubtitle: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
  },

  formCard: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    padding: spacing[16],
  },
  fieldGroup: {
    marginBottom: spacing[16],
  },
  fieldLabel: {
    ...textStyle('body-s-medium'),
    color: colors['text-primary'],
    marginBottom: spacing[8],
  },
  inputContainer: {
    backgroundColor: colors['background-surfaceAlt'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    height: sizes['button-height'],
    paddingHorizontal: spacing[16],
    justifyContent: 'center',
  },
  inputReadOnly: {
    backgroundColor: colors['background-surface'],
    borderColor: colors['border-subtle'],
  },
  inputError: {
    borderColor: colors['border-error'],
  },
  textInput: {
    ...textStyle('body-m-regular'),
    color: colors['text-primary'],
  },
  textInputReadOnly: {
    color: colors['text-muted'],
  },
  messageRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[4],
    marginTop: spacing[8],
  },
  errorText: {
    ...textStyle('body-xs-regular'),
    color: colors['text-error'],
    flex: 1,
  },
  successText: {
    ...textStyle('body-xs-regular'),
    color: colors['text-success'],
    flex: 1,
  },

  infoBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors['background-surfaceAlt'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    padding: spacing[16],
    gap: spacing[12],
  },
  stepBadge: {
    backgroundColor: colors['accent-soft'],
    borderRadius: radius.full,
    paddingHorizontal: spacing[12],
    paddingVertical: spacing[4],
  },
  stepBadgeText: {
    ...textStyle('ui-s-semibold-12'),
    color: colors['text-accent'],
  },
  infoTextContainer: {
    flex: 1,
  },
  infoTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
    marginBottom: spacing[4],
  },
  infoSubtitle: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
  },
  divider: {
    height: 1,
    backgroundColor: colors['border-subtle'],
    marginVertical: spacing[16],
  },

  errorBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing[12],
    backgroundColor: colors['status-error-bg'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['status-error-border'],
    padding: spacing[16],
    marginBottom: spacing[16],
  },
  errorTexts: {
    flex: 1,
    gap: spacing[4],
  },
  errorTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
  },
  errorBody: {
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

  sentTitle: {
    ...textStyle('display-l-24'),
    color: colors['text-primary'],
    textAlign: 'center',
  },
  sentBody: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
    textAlign: 'center',
  },
  sentHint: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
    textAlign: 'center',
  },

  btnPrimary: {
    backgroundColor: colors['accent-primary'],
    borderRadius: radius.md,
    height: sizes['button-height'],
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing[12],
  },
  btnPrimaryText: {
    ...textStyle('ui-m-semibold'),
    color: colors['text-inverse'],
  },
  btnDisabled: {
    backgroundColor: colors['state-disabled-bg'],
  },
  btnDisabledText: {
    color: colors['state-disabled-text'],
  },
  bottomSpace: {
    height: spacing[24],
  },
});
