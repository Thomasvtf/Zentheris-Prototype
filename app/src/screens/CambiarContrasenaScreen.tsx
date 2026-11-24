/**
 * Cambiar contraseña (sección 6.12; RN-IX-02). Contrato:
 * POST /usuarios/me/contrasena/verificar (verificarContrasenaActual) y
 * POST /usuarios/me/contrasena (cambiarContrasena). Mapa: docs/MAPA-DE-INTEGRACION.md,
 * filas 10 y 11.
 *
 * - Primero se verifica la contraseña actual; solo con la actual correcta se habilitan
 *   «Nueva» y «Confirmar».
 * - Requisitos: mínimo 8 caracteres, una mayúscula, un número y diferente a la actual
 *   (ícono + texto, nunca solo color). El botón se habilita solo al cumplirlos todos.
 * - Las contraseñas nunca se guardan ni se muestran en registros; solo viven en el estado.
 * - Esta pantalla no tiene `hogarId`: no depende del hogar.
 */
import React, { useCallback, useState } from 'react';
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
import { Circle, CircleCheck, CircleX, Eye, EyeOff, Shield } from 'lucide-react-native';
import { useRouter } from 'expo-router';

import { ScreenHeader } from '@/components';
import { toErrorTextKey } from '@/api/errors';
import { changePassword, verifyCurrentPassword } from '@/api/users';
import { colors, radius, sizes, spacing, textStyle } from '@/theme';
import { t } from '@/texts';

type VerifyState =
  | { status: 'idle' }
  | { status: 'verifying' }
  | { status: 'verified' }
  | { status: 'error'; errorKey: string };

type SaveState =
  | { status: 'idle' }
  | { status: 'saving' }
  | { status: 'saved' }
  | { status: 'error'; errorKey: string };

/**
 * Hook de datos de la pantalla: verificar la actual y guardar la nueva.
 * TODO(pendiente: provider de React Query): cuando exista, este hook pasa a
 * `useCambiarContrasenaData.ts` con useMutation. Aquí usa estado local.
 */
function useChangePasswordData() {
  const [verify, setVerify] = useState<VerifyState>({ status: 'idle' });
  const [save, setSave] = useState<SaveState>({ status: 'idle' });

  const verifyCurrent = useCallback(async (current: string) => {
    if (current.length === 0) return;
    setVerify({ status: 'verifying' });
    try {
      await verifyCurrentPassword({ contrasena_actual: current });
      setVerify({ status: 'verified' });
    } catch (error: unknown) {
      setVerify({ status: 'error', errorKey: toErrorTextKey(error) });
    }
  }, []);

  const resetVerification = useCallback(() => {
    setVerify({ status: 'idle' });
    setSave({ status: 'idle' });
  }, []);

  /** Devuelve `true` si se guardó, para que la pantalla limpie los campos. */
  const savePassword = useCallback(async (current: string, next: string) => {
    setSave({ status: 'saving' });
    try {
      await changePassword({ contrasena_actual: current, contrasena_nueva: next });
      setSave({ status: 'saved' });
      setVerify({ status: 'idle' });
      return true;
    } catch (error: unknown) {
      setSave({ status: 'error', errorKey: toErrorTextKey(error) });
      return false;
    }
  }, []);

  return { verify, save, verifyCurrent, resetVerification, savePassword };
}


interface PasswordFieldProps {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  disabled?: boolean;
  hasError?: boolean;
  onBlur?: () => void;
  onSubmitEditing?: () => void;
  busy?: boolean;
}

function PasswordField({
  label,
  value,
  onChangeText,
  disabled = false,
  hasError = false,
  onBlur,
  onSubmitEditing,
  busy = false,
}: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View
        style={[
          styles.inputContainer,
          hasError && styles.inputError,
          disabled && styles.inputDisabled,
        ]}
      >
        <TextInput
          style={[styles.textInput, disabled && styles.textInputDisabled]}
          value={value}
          onChangeText={onChangeText}
          secureTextEntry={!visible}
          autoCapitalize="none"
          autoCorrect={false}
          editable={!disabled && !busy}
          onBlur={onBlur}
          onSubmitEditing={onSubmitEditing}
          returnKeyType="done"
          accessibilityLabel={label}
        />
        <TouchableOpacity
          style={styles.eyeBtn}
          onPress={() => setVisible((v) => !v)}
          activeOpacity={0.7}
          disabled={disabled}
          hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
          accessibilityRole="button"
          accessibilityLabel={t(visible ? 'a11y.ocultar_contrasena' : 'a11y.mostrar_contrasena')}
        >
          {visible ? (
            <Eye size={20} color={disabled ? colors['text-disabled'] : colors['text-muted']} />
          ) : (
            <EyeOff size={20} color={disabled ? colors['text-disabled'] : colors['text-muted']} />
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

function FieldMessage({ children, tone }: { children: string; tone: 'error' | 'success' }) {
  return (
    <View style={styles.messageRow} accessibilityRole="alert">
      {tone === 'error' ? (
        <CircleX size={16} color={colors['text-error']} />
      ) : (
        <CircleCheck size={16} color={colors['text-success']} />
      )}
      <Text
        style={[styles.messageText, { color: tone === 'error' ? colors['text-error'] : colors['text-success'] }]}
      >
        {children}
      </Text>
    </View>
  );
}

function Requirement({ text, met }: { text: string; met: boolean }) {
  return (
    <View
      style={[styles.reqChip, met && styles.reqChipSatisfied]}
      accessible
      accessibilityLabel={text}
      accessibilityState={{ checked: met }}
    >
      {met ? (
        <CircleCheck size={14} color={colors['accent-primary']} />
      ) : (
        <Circle size={14} color={colors['text-disabled']} />
      )}
      <Text style={[styles.reqChipText, met && styles.reqChipTextSatisfied]}>{text}</Text>
    </View>
  );
}

export function CambiarContrasenaScreen() {
  const router = useRouter();
  const { verify, save, verifyCurrent, resetVerification, savePassword } = useChangePasswordData();

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');

  const verified = verify.status === 'verified';
  const hasMinLen = next.length >= 8;
  const hasUpperCase = /[A-Z]/.test(next);
  const hasNumber = /[0-9]/.test(next);
  const isDifferent = next.length > 0 && current.length > 0 && next !== current;
  const mismatch = confirm.length > 0 && next !== confirm;

  const isValid =
    verified && hasMinLen && hasUpperCase && hasNumber && isDifferent && next === confirm;
  const saving = save.status === 'saving';

  const handleCurrentChange = (value: string) => {
    setCurrent(value);
    if (verify.status !== 'idle') resetVerification();
  };

  const handleSave = async () => {
    if (!isValid || saving) return;
    const ok = await savePassword(current, next);
    // Tras guardar con éxito se limpian los campos (nunca se conservan contraseñas en pantalla).
    if (ok) {
      setCurrent('');
      setNext('');
      setConfirm('');
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor={colors['background-default']} />

      <ScreenHeader titulo={t('contrasena.encabezado')} onAtras={() => router.back()} />

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.bannerCard}>
          <View style={styles.bannerIconBox}>
            <Shield size={24} color={colors['text-accent']} />
          </View>
          <View style={styles.bannerTextContainer}>
            <Text style={styles.bannerTitle}>{t('contrasena.titulo')}</Text>
            <Text style={styles.bannerSubtitle}>{t('contrasena.cuerpo')}</Text>
          </View>
        </View>

        <View style={styles.formCard}>
          <PasswordField
            label={t('contrasena.actual')}
            value={current}
            onChangeText={handleCurrentChange}
            hasError={verify.status === 'error'}
            onBlur={() => void verifyCurrent(current)}
            onSubmitEditing={() => void verifyCurrent(current)}
            busy={verify.status === 'verifying'}
          />
          {verify.status === 'verifying' && (
            <Text style={styles.statusText}>{t('comun.cargando')}</Text>
          )}
          {verify.status === 'error' && (
            <FieldMessage tone="error">{t(`${verify.errorKey}.titulo`)}</FieldMessage>
          )}

          <PasswordField
            label={t('contrasena.nueva')}
            value={next}
            onChangeText={setNext}
            disabled={!verified}
          />
          <PasswordField
            label={t('contrasena.confirmar')}
            value={confirm}
            onChangeText={setConfirm}
            disabled={!verified}
            hasError={mismatch}
          />
          {mismatch && (
            <FieldMessage tone="error">{t('error.campo.contrasenas_no_coinciden')}</FieldMessage>
          )}

          <View style={styles.requirementsBox}>
            <Text style={styles.requirementsTitle}>{t('auth.requisitos.titulo')}</Text>
            <View style={styles.chipsRow}>
              <Requirement text={t('auth.requisitos.minimo')} met={hasMinLen} />
              <Requirement text={t('auth.requisitos.mayuscula')} met={hasUpperCase} />
              <Requirement text={t('auth.requisitos.numero')} met={hasNumber} />
              <Requirement text={t('auth.requisitos.diferente')} met={isDifferent} />
            </View>
          </View>

          <View style={styles.divider} />

          {save.status === 'error' && (
            <View style={styles.saveError} accessibilityRole="alert">
              <Text style={styles.saveErrorTitle}>{t(`${save.errorKey}.titulo`)}</Text>
              <Text style={styles.saveErrorBody}>{t(`${save.errorKey}.cuerpo`)}</Text>
            </View>
          )}
          {save.status === 'saved' && (
            <FieldMessage tone="success">{t('toast.contrasena_cambiada')}</FieldMessage>
          )}

          <TouchableOpacity
            style={[styles.btnGuardar, (!isValid || saving) && styles.btnDisabled]}
            activeOpacity={0.85}
            onPress={handleSave}
            disabled={!isValid || saving}
            accessibilityRole="button"
            accessibilityState={{ disabled: !isValid || saving, busy: saving }}
          >
            <Text style={[styles.btnGuardarText, (!isValid || saving) && styles.btnDisabledText]}>
              {saving ? t('comun.cargando') : t('contrasena.boton')}
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.bottomSpace} />
      </ScrollView>
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
  scrollContent: {
    paddingHorizontal: spacing[16],
    paddingTop: spacing[8],
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
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors['background-surfaceAlt'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    height: sizes['button-height'],
    paddingLeft: spacing[16],
  },
  inputError: {
    borderColor: colors['border-error'],
  },
  inputDisabled: {
    backgroundColor: colors['state-disabled-bg'],
    borderColor: colors['state-disabled-border'],
  },
  textInput: {
    ...textStyle('body-m-regular'),
    flex: 1,
    color: colors['text-primary'],
  },
  textInputDisabled: {
    color: colors['state-disabled-text'],
  },
  eyeBtn: {
    width: sizes['button-height'],
    height: sizes['button-height'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusText: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
    marginTop: -spacing[8],
    marginBottom: spacing[16],
  },
  messageRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[4],
    marginTop: -spacing[8],
    marginBottom: spacing[16],
  },
  messageText: {
    ...textStyle('body-xs-regular'),
    flex: 1,
  },

  requirementsBox: {
    marginTop: spacing[4],
  },
  requirementsTitle: {
    ...textStyle('body-s-medium'),
    color: colors['text-primary'],
    marginBottom: spacing[12],
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing[8],
  },
  reqChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[4],
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    paddingHorizontal: spacing[12],
    paddingVertical: spacing[4],
  },
  reqChipSatisfied: {
    backgroundColor: colors['accent-soft'],
    borderColor: colors['border-accent'],
  },
  reqChipText: {
    ...textStyle('body-xs-medium'),
    color: colors['text-muted'],
  },
  reqChipTextSatisfied: {
    color: colors['text-primary'],
  },
  divider: {
    height: 1,
    backgroundColor: colors['border-subtle'],
    marginVertical: spacing[16],
  },

  saveError: {
    backgroundColor: colors['status-error-bg'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['status-error-border'],
    padding: spacing[12],
    marginBottom: spacing[16],
    gap: spacing[4],
  },
  saveErrorTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
  },
  saveErrorBody: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
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
  btnDisabledText: {
    color: colors['state-disabled-text'],
  },
  bottomSpace: {
    height: spacing[24],
  },
});
