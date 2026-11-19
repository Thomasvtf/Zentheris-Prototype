/**
 * Editar perfil (sección 6.11; RN-IX-07, RN-I-02). Contrato: GET /usuarios/me
 * (obtenerUsuarioActual), PATCH /usuarios/me (actualizarPerfil) y DELETE /usuarios/me/avatar
 * (eliminarAvatar). Mapa: docs/MAPA-DE-INTEGRACION.md, filas 2, 4, 6 y 7.
 *
 * - Solo se editan nombre completo y teléfono (opcional), en la misma pantalla. El correo es
 *   solo lectura y se cambia en Gestionar correo.
 * - Sin foto se muestran las iniciales. No hay «Cerrar sesión» aquí (RN-IX-08).
 * - Esta pantalla no depende del hogar: solo usa /usuarios/me.
 */
import React, { useCallback, useEffect, useState } from 'react';
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
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useRouter } from 'expo-router';

import { deleteAvatar, getCurrentUser, updateProfile } from '@/api/users';
import { toErrorTextKey } from '@/api/errors';
import type { SuccessBody } from '@/api/client';
import { getSupabase } from '@/state/supabase';
import { colors, fontFamilyFor, radius, sizes, spacing, typography } from '@/theme';
import { t } from '@/texts';

import { INPUT_LIMITS, sanitizeName, sanitizePhone } from './inputFilters';

type CurrentUser = SuccessBody<'/usuarios/me', 'get'>;

type UserState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'ready'; user: CurrentUser };

type ActionState =
  | { status: 'idle' }
  | { status: 'working' }
  | { status: 'done'; message: string }
  | { status: 'error'; errorKey: string };

/**
 * Hook de datos de la pantalla: usuario actual, guardar nombre y teléfono, eliminar foto y
 * URL firmada de la foto (bucket privado `avatares`, RN-I-02).
 * TODO(pendiente: provider de React Query): al existir, este hook pasa a
 * `useEditarPerfilData.ts` con useQuery/useMutation (queryKey('obtenerUsuarioActual')).
 * TODO(pendiente: subir foto): falta instalar `expo-image-picker` para elegir de la galería,
 * subir a Storage (`{usuario_id}/avatar.{jpg|png|webp}`, máx. 2 MB) y llamar a guardarAvatar.
 */
function useEditProfileData() {
  const [state, setState] = useState<UserState>({ status: 'loading' });
  const [action, setAction] = useState<ActionState>({ status: 'idle' });
  const [avatarUri, setAvatarUri] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState((prev) => (prev.status === 'ready' ? prev : { status: 'loading' }));
    getCurrentUser()
      .then((user) => {
        if (!cancelled) setState({ status: 'ready', user });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', errorKey: toErrorTextKey(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const avatarPath = state.status === 'ready' ? state.user.avatar_url : null;
  useEffect(() => {
    let cancelled = false;
    if (!avatarPath) {
      setAvatarUri(null);
      return;
    }
    (async () => {
      try {
        const { data } = await getSupabase().storage.from('avatares').createSignedUrl(avatarPath, 3600);
        if (!cancelled) setAvatarUri(data?.signedUrl ?? null);
      } catch {
        // Sin URL firmada se muestran las iniciales.
        if (!cancelled) setAvatarUri(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [avatarPath]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  const saveProfile = useCallback(
    async (nombreCompleto: string, telefono: string | null) => {
      setAction({ status: 'working' });
      try {
        await updateProfile({ nombre_completo: nombreCompleto, telefono });
        setAction({ status: 'done', message: t('toast.cambios_guardados') });
        reload();
        return true;
      } catch (error: unknown) {
        setAction({ status: 'error', errorKey: toErrorTextKey(error) });
        return false;
      }
    },
    [reload],
  );

  const removePhoto = useCallback(async () => {
    setAction({ status: 'working' });
    try {
      await deleteAvatar();
      setAction({ status: 'done', message: t('toast.foto_eliminada') });
      reload();
    } catch (error: unknown) {
      setAction({ status: 'error', errorKey: toErrorTextKey(error) });
    }
  }, [reload]);

  const clearAction = useCallback(() => setAction({ status: 'idle' }), []);

  return { state, action, avatarUri, reload, saveProfile, removePhoto, clearAction };
}

function textStyle(name: keyof typeof typography): TextStyle {
  const style = typography[name];
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    ...('lineHeight' in style ? { lineHeight: style.lineHeight } : {}),
  };
}

/** Iniciales para el avatar sin foto: primera letra de las dos primeras palabras. */
function initialsOf(fullName: string): string {
  return fullName
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join('');
}

/**
 * Celular colombiano opcional: vacío es válido; si se escribe, 10 dígitos (con o sin +57).
 * TODO(pendiente: regla de teléfono): el contrato solo dice `string | null`; confirmar el
 * formato aceptado con el equipo.
 */
function isValidPhone(value: string): boolean {
  const digits = value.replace(/[\s\-()]/g, '');
  if (digits === '') return true;
  return /^(\+?57)?\d{10}$/.test(digits);
}

export function EditarPerfilScreen() {
  const router = useRouter();
  const { state, action, avatarUri, reload, saveProfile, removePhoto, clearAction } =
    useEditProfileData();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [errors, setErrors] = useState<{ name?: string; phone?: string }>({});
  const [photoSheet, setPhotoSheet] = useState(false);

  const user = state.status === 'ready' ? state.user : null;
  const working = action.status === 'working';

  const startEditing = () => {
    if (!user) return;
    setName(user.nombre_completo);
    setPhone(user.telefono ?? '');
    setErrors({});
    clearAction();
    setEditing(true);
  };

  const cancelEditing = () => {
    setEditing(false);
    setErrors({});
    clearAction();
  };

  const handleSave = async () => {
    const next: { name?: string; phone?: string } = {};
    if (name.trim() === '') next.name = t('error.campo.nombre_requerido');
    if (!isValidPhone(phone)) next.phone = t('error.campo.telefono_invalido');
    setErrors(next);
    if (Object.keys(next).length > 0) return;
    const ok = await saveProfile(name.trim(), phone.trim() === '' ? null : phone.trim());
    if (ok) setEditing(false);
  };

  const handleRemovePhoto = async () => {
    setPhotoSheet(false);
    await removePhoto();
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
          <Ionicons name="chevron-back" size={24} color={colors['text-primary']} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t('perfil.encabezado')}</Text>
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
            <View style={styles.skeletonAvatar} />
            <View style={[styles.skeleton, styles.skeletonTall]} />
            <View style={[styles.skeleton, styles.skeletonShort]} />
          </View>
        )}

        {state.status === 'error' && (
          <View>
            <View style={styles.errorBox} accessibilityRole="alert">
              <Ionicons name="alert-circle-outline" size={20} color={colors['text-error']} />
              <View style={styles.messageTexts}>
                <Text style={styles.messageTitle}>{t(`${state.errorKey}.titulo`)}</Text>
                <Text style={styles.messageBody}>{t(`${state.errorKey}.cuerpo`)}</Text>
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

        {user && (
          <>
            <View style={styles.avatarSection}>
              <View style={styles.avatarWrapper}>
                <View style={styles.avatarCircle}>
                  {avatarUri ? (
                    <Image
                      source={{ uri: avatarUri }}
                      style={styles.avatarImage}
                      accessibilityLabel={user.nombre_completo}
                    />
                  ) : (
                    <Text style={styles.avatarInitials}>{initialsOf(user.nombre_completo)}</Text>
                  )}
                </View>
                <TouchableOpacity
                  style={styles.editBadge}
                  activeOpacity={0.8}
                  onPress={() => setPhotoSheet(true)}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  accessibilityRole="button"
                  accessibilityLabel={t('a11y.cambiar_foto')}
                >
                  <Ionicons name="pencil" size={15} color={colors['text-inverse']} />
                </TouchableOpacity>
              </View>
              <Text style={styles.avatarName}>{user.nombre_completo}</Text>
              <Text style={styles.avatarEmail}>{user.correo}</Text>
            </View>

            {action.status === 'done' && (
              <View style={styles.successBox} accessibilityRole="alert">
                <Ionicons name="checkmark-circle-outline" size={18} color={colors['text-success']} />
                <Text style={styles.successText}>{action.message}</Text>
              </View>
            )}
            {action.status === 'error' && (
              <View style={styles.errorBox} accessibilityRole="alert">
                <Ionicons name="alert-circle-outline" size={20} color={colors['text-error']} />
                <View style={styles.messageTexts}>
                  <Text style={styles.messageTitle}>{t(`${action.errorKey}.titulo`)}</Text>
                  <Text style={styles.messageBody}>{t(`${action.errorKey}.cuerpo`)}</Text>
                </View>
              </View>
            )}

            <View style={styles.card}>
              <Text style={styles.cardTitle}>{t('perfil.seccion')}</Text>
              <Text style={styles.cardSubtitle}>{t('perfil.seccion_d')}</Text>
              <View style={styles.divider} />

              {editing ? (
                <>
                  <View style={styles.fieldGroup}>
                    <Text style={styles.fieldLabel}>{t('perfil.nombre')}</Text>
                    <TextInput
                      style={[styles.textInput, errors.name ? styles.inputError : null]}
                      value={name}
                      onChangeText={(value) => setName(sanitizeName(value))}
                      maxLength={INPUT_LIMITS.nameLength}
                      autoCapitalize="words"
                      accessibilityLabel={t('perfil.nombre')}
                    />
                    {errors.name ? <Text style={styles.fieldError}>{errors.name}</Text> : null}
                  </View>

                  <View style={styles.fieldGroup}>
                    <Text style={styles.fieldLabel}>{t('perfil.correo_edicion')}</Text>
                    <View style={styles.readOnlyBox}>
                      <Text style={styles.readOnlyText}>{user.correo}</Text>
                    </View>
                  </View>

                  <View style={styles.fieldGroup}>
                    <Text style={styles.fieldLabel}>{t('perfil.telefono_edicion')}</Text>
                    <TextInput
                      style={[styles.textInput, errors.phone ? styles.inputError : null]}
                      value={phone}
                      onChangeText={(value) => setPhone(sanitizePhone(value))}
                      maxLength={INPUT_LIMITS.phoneDigits + 1}
                      keyboardType="phone-pad"
                      accessibilityLabel={t('perfil.telefono_edicion')}
                    />
                    {errors.phone ? <Text style={styles.fieldError}>{errors.phone}</Text> : null}
                  </View>

                  <View style={styles.editActions}>
                    <TouchableOpacity
                      style={styles.btnSecondary}
                      onPress={cancelEditing}
                      disabled={working}
                      accessibilityRole="button"
                    >
                      <Text style={styles.btnSecondaryText}>{t('perfil.cancelar')}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.btnPrimary, working && styles.btnDisabled]}
                      onPress={handleSave}
                      disabled={working}
                      accessibilityRole="button"
                      accessibilityState={{ disabled: working, busy: working }}
                    >
                      <Text style={[styles.btnPrimaryText, working && styles.btnDisabledText]}>
                        {working ? t('comun.cargando') : t('perfil.guardar')}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </>
              ) : (
                <>
                  <View style={styles.fieldGroup}>
                    <Text style={styles.fieldLabel}>{t('perfil.nombre')}</Text>
                    <Text style={styles.fieldValue}>{user.nombre_completo}</Text>
                  </View>
                  <View style={styles.fieldGroup}>
                    <Text style={styles.fieldLabel}>{t('perfil.correo')}</Text>
                    <Text style={styles.fieldValue}>{user.correo}</Text>
                  </View>
                  <View style={[styles.fieldGroup, styles.fieldLast]}>
                    <Text style={styles.fieldLabel}>{t('perfil.telefono')}</Text>
                    {/* Sin teléfono es «sin dato» (—), nunca un valor inventado. */}
                    <Text style={styles.fieldValue}>{user.telefono ?? t('comun.sin_dato')}</Text>
                  </View>
                </>
              )}
            </View>

            {!editing && (
              <View style={styles.card}>
                <Text style={styles.cardTitle}>{t('perfil.acciones')}</Text>
                <Text style={styles.cardSubtitle}>{t('perfil.acciones_d')}</Text>
                <View style={styles.divider} />

                <TouchableOpacity
                  style={styles.actionRow}
                  activeOpacity={0.7}
                  onPress={startEditing}
                  accessibilityRole="button"
                >
                  <View style={styles.iconBox}>
                    <Ionicons name="create-outline" size={20} color={colors['text-accent']} />
                  </View>
                  <View style={styles.actionTextContainer}>
                    <Text style={styles.actionTitle}>{t('perfil.editar')}</Text>
                    <Text style={styles.actionSubtitle}>{t('perfil.editar_d')}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={colors['text-muted']} />
                </TouchableOpacity>
              </View>
            )}
          </>
        )}

        <View style={styles.bottomSpace} />
      </ScrollView>

      <Modal
        visible={photoSheet}
        animationType="slide"
        transparent
        onRequestClose={() => setPhotoSheet(false)}
      >
        <View style={styles.modalOverlay}>
          <TouchableOpacity
            style={styles.modalBackdrop}
            activeOpacity={1}
            onPress={() => setPhotoSheet(false)}
          />
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>{t('perfil.foto_titulo')}</Text>
            <Text style={styles.modalSubtitle}>{t('perfil.foto_cuerpo')}</Text>

            {/* TODO(pendiente: expo-image-picker): sin el paquete no se puede elegir de la galería. */}
            <TouchableOpacity
              style={[styles.sheetOption, styles.sheetOptionDisabled]}
              disabled
              accessibilityRole="button"
              accessibilityState={{ disabled: true }}
            >
              <Ionicons name="images-outline" size={20} color={colors['text-disabled']} />
              <Text style={styles.sheetOptionDisabledText}>{t('perfil.foto_galeria')}</Text>
            </TouchableOpacity>

            {user?.avatar_url ? (
              <TouchableOpacity
                style={styles.sheetOption}
                onPress={handleRemovePhoto}
                accessibilityRole="button"
              >
                <Ionicons name="trash-outline" size={20} color={colors['text-error']} />
                <Text style={styles.sheetOptionDangerText}>{t('perfil.foto_eliminar')}</Text>
              </TouchableOpacity>
            ) : null}

            <TouchableOpacity
              style={styles.btnSecondary}
              onPress={() => setPhotoSheet(false)}
              accessibilityRole="button"
            >
              <Text style={styles.btnSecondaryText}>{t('perfil.cancelar')}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const AVATAR_SIZE = spacing[64] + spacing[24] + spacing[8];

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

  skeletonAvatar: {
    width: AVATAR_SIZE,
    height: AVATAR_SIZE,
    borderRadius: radius.full,
    backgroundColor: colors['background-surfaceAlt'],
    alignSelf: 'center',
    marginBottom: spacing[20],
  },
  skeleton: {
    borderRadius: radius.lg,
    backgroundColor: colors['background-surfaceAlt'],
    marginBottom: spacing[16],
  },
  skeletonTall: {
    height: 200,
  },
  skeletonShort: {
    height: 100,
  },

  avatarSection: {
    alignItems: 'center',
    marginBottom: spacing[24],
  },
  avatarWrapper: {
    marginBottom: spacing[12],
  },
  avatarCircle: {
    width: AVATAR_SIZE,
    height: AVATAR_SIZE,
    borderRadius: radius.full,
    backgroundColor: colors['accent-soft'],
    borderWidth: 2,
    borderColor: colors['border-accent'],
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  avatarImage: {
    width: '100%',
    height: '100%',
  },
  avatarInitials: {
    ...textStyle('display-l-24'),
    color: colors['text-accent'],
  },
  editBadge: {
    position: 'absolute',
    right: 0,
    bottom: 0,
    width: sizes['iconButton-size'],
    height: sizes['iconButton-size'],
    borderRadius: radius.full,
    backgroundColor: colors['accent-primary'],
    borderWidth: 2,
    borderColor: colors['background-default'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarName: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
    marginBottom: spacing[4],
  },
  avatarEmail: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
  },

  card: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    padding: spacing[16],
    marginBottom: spacing[16],
  },
  cardTitle: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
    marginBottom: spacing[4],
  },
  cardSubtitle: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
  },
  divider: {
    height: 1,
    backgroundColor: colors['border-subtle'],
    marginVertical: spacing[16],
  },
  fieldGroup: {
    marginBottom: spacing[16],
  },
  fieldLast: {
    marginBottom: 0,
  },
  fieldLabel: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
    marginBottom: spacing[4],
  },
  fieldValue: {
    ...textStyle('body-m-medium'),
    color: colors['text-primary'],
  },
  textInput: {
    ...textStyle('body-m-regular'),
    color: colors['text-primary'],
    backgroundColor: colors['background-surfaceAlt'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    height: sizes['button-height'],
    paddingHorizontal: spacing[16],
    marginTop: spacing[4],
  },
  inputError: {
    borderColor: colors['border-error'],
  },
  readOnlyBox: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    height: sizes['button-height'],
    paddingHorizontal: spacing[16],
    marginTop: spacing[4],
    justifyContent: 'center',
  },
  readOnlyText: {
    ...textStyle('body-m-regular'),
    color: colors['text-muted'],
  },
  fieldError: {
    ...textStyle('body-xs-regular'),
    color: colors['text-error'],
    marginTop: spacing[8],
  },

  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: sizes['button-height'],
  },
  iconBox: {
    width: spacing[40],
    height: spacing[40],
    borderRadius: radius.md,
    backgroundColor: colors['background-surfaceAlt'],
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing[12],
  },
  actionTextContainer: {
    flex: 1,
  },
  actionTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
  },
  actionSubtitle: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
  },

  editActions: {
    flexDirection: 'row',
    gap: spacing[12],
  },
  btnPrimary: {
    flex: 1,
    backgroundColor: colors['accent-primary'],
    borderRadius: radius.md,
    height: sizes['button-height'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnPrimaryText: {
    ...textStyle('ui-m-semibold'),
    color: colors['text-inverse'],
  },
  btnSecondary: {
    flex: 1,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    height: sizes['button-height'],
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnSecondaryText: {
    ...textStyle('ui-m-semibold'),
    color: colors['text-accent'],
  },
  btnDisabled: {
    backgroundColor: colors['state-disabled-bg'],
  },
  btnDisabledText: {
    color: colors['state-disabled-text'],
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
  messageTexts: {
    flex: 1,
    gap: spacing[4],
  },
  messageTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
  },
  messageBody: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
  },
  successBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[8],
    backgroundColor: colors['status-success-bg'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['status-success-border'],
    padding: spacing[12],
    marginBottom: spacing[16],
  },
  successText: {
    ...textStyle('body-s-regular'),
    color: colors['text-success'],
    flex: 1,
  },
  retryBtn: {
    alignSelf: 'flex-start',
    paddingVertical: spacing[8],
  },
  retryText: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-accent'],
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
    backgroundColor: colors['background-elevated'],
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    padding: spacing[20],
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    gap: spacing[8],
  },
  modalTitle: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
  },
  modalSubtitle: {
    ...textStyle('body-s-regular'),
    color: colors['text-muted'],
    marginBottom: spacing[8],
  },
  sheetOption: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[12],
    minHeight: sizes['button-height'],
    paddingHorizontal: spacing[12],
    borderRadius: radius.md,
    backgroundColor: colors['background-surfaceAlt'],
  },
  sheetOptionDisabled: {
    backgroundColor: colors['state-disabled-bg'],
  },
  sheetOptionDisabledText: {
    ...textStyle('body-m-medium'),
    color: colors['text-disabled'],
  },
  sheetOptionDangerText: {
    ...textStyle('body-m-medium'),
    color: colors['text-error'],
  },
});
