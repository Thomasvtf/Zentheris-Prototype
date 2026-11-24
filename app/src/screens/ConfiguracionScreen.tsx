/**
 * Configuración (sección 6.10; RN-XVI-01 a RN-XVI-03, RN-IX-08, RN-IX-09). Contrato:
 * GET /usuarios/me (obtenerUsuarioActual), PATCH /usuarios/me/preferencias
 * (actualizarPreferencias) y DELETE /usuarios/me (eliminarCuenta). Mapa:
 * docs/MAPA-DE-INTEGRACION.md, filas 2, 5, 8 y 9.
 *
 * - Alertas = `notif_consumo`; Consejos = `notif_consejos`; Meta de consumo =
 *   `base_comparacion` (encendido «meta», apagado «promedio»).
 * - «Hogar y transición energética» es de la Fase 2: se muestra «Próximamente» y no navega.
 * - Cerrar sesión cierra la sesión en este dispositivo; Eliminar cuenta pide confirmación.
 * - No depende del hogar: todo sale de /usuarios/me.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  ScrollView,
  StatusBar,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  Bell,
  ChartLine,
  ChevronRight,
  CircleAlert,
  Cpu,
  Footprints,
  Leaf,
  Lightbulb,
  LogOut,
  Mail,
  Shield,
  Target,
  Trash2,
  User,
  Users,
  Zap,
} from 'lucide-react-native';
import { Image } from 'expo-image';
import { useRouter } from 'expo-router';

import { ConfirmDialog, ScreenHeader } from '@/components';
import { ApiRequestError } from '@/api/client';
import type { SuccessBody } from '@/api/client';
import { toErrorTextKey } from '@/api/errors';
import { deleteAccount, getCurrentUser, updatePreferences } from '@/api/users';
import { getSupabase } from '@/state/supabase';
import { colors, radius, sizes, spacing, textStyle } from '@/theme';
import { t } from '@/texts';

type CurrentUser = SuccessBody<'/usuarios/me', 'get'>;
type Preferences = CurrentUser['preferencias'];

type UserState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'ready'; user: CurrentUser };

/**
 * Hook de datos de la pantalla: usuario, preferencias (con cambio inmediato y reversión si
 * falla), cerrar sesión y eliminar cuenta.
 * TODO(pendiente: provider de React Query): al existir, este hook pasa a
 * `useConfiguracionData.ts` con useQuery/useMutation (queryKey('obtenerUsuarioActual')).
 */
function useSettingsData() {
  const [state, setState] = useState<UserState>({ status: 'loading' });
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [avatarUri, setAvatarUri] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [actionErrorKey, setActionErrorKey] = useState<string | null>(null);
  const [mustTransfer, setMustTransfer] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then((user) => {
        if (cancelled) return;
        setState({ status: 'ready', user });
        setPrefs(user.preferencias);
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
    // Sin ruta no se pide URL firmada; `shownAvatarUri` queda en null más abajo.
    if (!avatarPath) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await getSupabase().storage.from('avatares').createSignedUrl(avatarPath, 3600);
        if (!cancelled) setAvatarUri(data?.signedUrl ?? null);
      } catch {
        if (!cancelled) setAvatarUri(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [avatarPath]);

  // Al reintentar se muestra el esqueleto (salvo con datos ya cargados), desde el evento.
  const reload = useCallback(() => {
    setState((prev) => (prev.status === 'ready' ? prev : { status: 'loading' }));
    setAttempt((n) => n + 1);
  }, []);
  const shownAvatarUri = avatarPath ? avatarUri : null;

  const setPreference = useCallback(
    async (change: Partial<Preferences>) => {
      if (!prefs) return;
      const previous = prefs;
      setActionErrorKey(null);
      setPrefs({ ...prefs, ...change });
      try {
        const saved = await updatePreferences(change);
        setPrefs(saved);
      } catch (error: unknown) {
        setPrefs(previous);
        setActionErrorKey(toErrorTextKey(error));
      }
    },
    [prefs],
  );

  const signOut = useCallback(async () => {
    setActionErrorKey(null);
    setBusy(true);
    try {
      // TODO(pendiente: pantalla de inicio de sesión): al existir, navegar a ella tras cerrar.
      const { error } = await getSupabase().auth.signOut({ scope: 'local' });
      if (error) setActionErrorKey('error.app.desconocido');
    } catch {
      setActionErrorKey('error.app.desconocido');
    } finally {
      setBusy(false);
    }
  }, []);

  const removeAccount = useCallback(async () => {
    setActionErrorKey(null);
    setBusy(true);
    try {
      await deleteAccount();
      await getSupabase().auth.signOut({ scope: 'local' });
    } catch (error: unknown) {
      if (error instanceof ApiRequestError && error.body?.codigo === 'ADMIN_DEBE_TRANSFERIR') {
        setMustTransfer(true);
      } else {
        setActionErrorKey(toErrorTextKey(error));
      }
    } finally {
      setBusy(false);
    }
  }, []);

  return {
    state,
    prefs,
    avatarUri: shownAvatarUri,
    reload,
    setPreference,
    signOut,
    removeAccount,
    actionErrorKey,
    mustTransfer,
    clearMustTransfer: () => setMustTransfer(false),
    busy,
  };
}


function initialsOf(fullName: string): string {
  return fullName
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join('');
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.sectionCard}>
      <Text style={styles.sectionHeader}>{title}</Text>
      {children}
    </View>
  );
}

function Divider() {
  return <View style={styles.divider} />;
}

interface RowProps {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  danger?: boolean;
  right?: React.ReactNode;
}

function RowBody({ icon, title, subtitle, danger = false, right }: RowProps) {
  return (
    <>
      <View style={[styles.iconBox, danger && styles.iconBoxDanger]}>{icon}</View>
      <View style={styles.rowTextContainer}>
        <Text style={styles.rowTitle}>{title}</Text>
        <Text style={styles.rowSubtitle}>{subtitle}</Text>
      </View>
      {right}
    </>
  );
}

function NavRow({ onPress, ...props }: RowProps & { onPress: () => void }) {
  return (
    <TouchableOpacity
      style={styles.rowItem}
      activeOpacity={0.7}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${props.title}. ${props.subtitle}`}
    >
      <RowBody
        {...props}
        right={<ChevronRight size={18} color={colors['text-muted']} />}
      />
    </TouchableOpacity>
  );
}

function SwitchRow({
  value,
  onChange,
  ...props
}: RowProps & { value: boolean; onChange: (value: boolean) => void }) {
  return (
    <View style={styles.rowItem}>
      <RowBody
        {...props}
        right={
          <Switch
            value={value}
            onValueChange={onChange}
            trackColor={{ false: colors['neutral-700'], true: colors['accent-primary'] }}
            thumbColor={colors['text-primary']}
            ios_backgroundColor={colors['neutral-700']}
            accessibilityLabel={props.title}
          />
        }
      />
    </View>
  );
}

function SoonRow(props: RowProps) {
  return (
    <View style={styles.rowItem} accessibilityState={{ disabled: true }}>
      <RowBody
        {...props}
        right={
          <View style={styles.badgeSoon}>
            <Text style={styles.badgeSoonText}>{t('comun.proximamente')}</Text>
          </View>
        }
      />
    </View>
  );
}

const ICON_COLOR = colors['text-accent'];

export function ConfiguracionScreen() {
  const router = useRouter();
  const {
    state,
    prefs,
    avatarUri,
    reload,
    setPreference,
    signOut,
    removeAccount,
    actionErrorKey,
    mustTransfer,
    clearMustTransfer,
    busy,
  } = useSettingsData();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const user = state.status === 'ready' ? state.user : null;
  const isAdmin = user?.membresia?.rol === 'administrador';

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor={colors['background-default']} />

      <ScreenHeader titulo={t('config.encabezado')} onAtras={false} />

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {state.status === 'loading' && (
          <View accessibilityRole="progressbar" accessibilityLabel={t('comun.cargando')}>
            <View style={styles.skeletonAvatar} />
            <View style={[styles.skeleton, styles.skeletonTall]} />
            <View style={[styles.skeleton, styles.skeletonShort]} />
            <View style={[styles.skeleton, styles.skeletonTall]} />
          </View>
        )}

        {state.status === 'error' && (
          <View>
            <View style={styles.errorBox} accessibilityRole="alert">
              <CircleAlert size={20} color={colors['text-error']} />
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

        {user && prefs && (
          <>
            <TouchableOpacity
              style={styles.avatarSection}
              activeOpacity={0.8}
              onPress={() => router.push('/editar-perfil')}
              accessibilityRole="button"
              accessibilityLabel={`${user.nombre_completo}. ${t('config.perfil_t')}`}
            >
              <View style={styles.avatarCircle}>
                {avatarUri ? (
                  <Image source={{ uri: avatarUri }} style={styles.avatarImage} />
                ) : (
                  <Text style={styles.avatarInitials}>{initialsOf(user.nombre_completo)}</Text>
                )}
              </View>
              <Text style={styles.avatarName}>{user.nombre_completo}</Text>
            </TouchableOpacity>

            {actionErrorKey && (
              <View style={styles.errorBox} accessibilityRole="alert">
                <CircleAlert size={20} color={colors['text-error']} />
                <View style={styles.messageTexts}>
                  <Text style={styles.messageTitle}>{t(`${actionErrorKey}.titulo`)}</Text>
                  <Text style={styles.messageBody}>{t(`${actionErrorKey}.cuerpo`)}</Text>
                </View>
              </View>
            )}

            <Section title={t('config.sec_cuenta')}>
              <NavRow
                icon={<User size={20} color={ICON_COLOR} />}
                title={t('config.perfil_t')}
                subtitle={t('config.perfil_d')}
                onPress={() => router.push('/editar-perfil')}
              />
              <Divider />
              <NavRow
                icon={<Shield size={20} color={ICON_COLOR} />}
                title={t('config.contrasena_t')}
                subtitle={t('config.contrasena_d')}
                onPress={() => router.push('/cambiar-contrasena')}
              />
              <Divider />
              <NavRow
                icon={<Mail size={20} color={ICON_COLOR} />}
                title={t('config.correo_t')}
                subtitle={t('config.correo_d')}
                onPress={() => router.push('/gestionar-correo')}
              />
            </Section>

            <Section title={t('config.sec_notificaciones')}>
              <SwitchRow
                icon={<Bell size={20} color={ICON_COLOR} />}
                title={t('config.alertas_t')}
                subtitle={t('config.alertas_d')}
                value={prefs.notif_consumo}
                onChange={(value) => void setPreference({ notif_consumo: value })}
              />
              <Divider />
              <SwitchRow
                icon={<Lightbulb size={20} color={ICON_COLOR} />}
                title={t('config.consejos_t')}
                subtitle={t('config.consejos_d')}
                value={prefs.notif_consejos}
                onChange={(value) => void setPreference({ notif_consejos: value })}
              />
            </Section>

            <Section title={t('config.sec_energia')}>
              <SwitchRow
                icon={<ChartLine size={20} color={ICON_COLOR} />}
                title={t('config.meta_consumo_t')}
                subtitle={t('config.meta_consumo_d')}
                value={prefs.base_comparacion === 'meta'}
                onChange={(value) =>
                  void setPreference({ base_comparacion: value ? 'meta' : 'promedio' })
                }
              />
              <Divider />
              <NavRow
                icon={<Target size={20} color={ICON_COLOR} />}
                title={t('config.meta_t')}
                subtitle={t('config.meta_d')}
                onPress={() => router.push('/establecer-meta')}
              />
              <Divider />
              <NavRow
                icon={<Zap size={20} color={ICON_COLOR} />}
                title={t('config.tarifa_t')}
                subtitle={t('config.tarifa_d')}
                onPress={() => router.push('/configurar-tarifa')}
              />
              <Divider />
              <NavRow
                icon={<Cpu size={20} color={ICON_COLOR} />}
                title={t('config.fuentes_t')}
                subtitle={t('config.fuentes_d')}
                onPress={() => router.push('/fuentes-datos')}
              />
            </Section>

            <Section title={t('config.sec_familia')}>
              <NavRow
                icon={<Users size={20} color={ICON_COLOR} />}
                title={isAdmin ? t('config.miembros_t') : t('config.miembros_t_lectura')}
                subtitle={isAdmin ? t('config.miembros_d') : t('config.miembros_d_lectura')}
                onPress={() => router.push('/miembros')}
              />
            </Section>

            <Section title={t('config.sec_transicion')}>
              <SoonRow
                icon={<Leaf size={20} color={ICON_COLOR} />}
                title={t('config.hogar_t')}
                subtitle={t('config.hogar_d')}
              />
              <Divider />
              <SoonRow
                icon={<Footprints size={20} color={ICON_COLOR} />}
                title={t('config.huella_t')}
                subtitle={t('config.huella_d')}
              />
            </Section>

            <Section title={t('config.sec_otros')}>
              <View style={styles.rowItem}>
                <RowBody
                  danger
                  icon={<LogOut size={20} color={colors['text-error']} />}
                  title={t('config.salir_t')}
                  subtitle={t('config.salir_d')}
                  right={
                    <TouchableOpacity
                      style={[styles.btnAction, busy && styles.btnActionDisabled]}
                      activeOpacity={0.8}
                      onPress={() => void signOut()}
                      disabled={busy}
                      hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                      accessibilityRole="button"
                      accessibilityLabel={t('config.salir_t')}
                    >
                      <Text style={styles.btnActionText}>{t('config.salir_boton')}</Text>
                    </TouchableOpacity>
                  }
                />
              </View>
            </Section>

            <Section title={t('config.sec_riesgo')}>
              <View style={styles.rowItem}>
                <RowBody
                  danger
                  icon={<Trash2 size={20} color={colors['text-error']} />}
                  title={t('config.eliminar_t')}
                  subtitle={t('config.eliminar_d')}
                  right={
                    <TouchableOpacity
                      style={[styles.btnAction, styles.btnActionDanger, busy && styles.btnActionDisabled]}
                      activeOpacity={0.8}
                      onPress={() => setConfirmDelete(true)}
                      disabled={busy}
                      hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                      accessibilityRole="button"
                      accessibilityLabel={t('config.eliminar_t')}
                    >
                      <Text style={[styles.btnActionText, styles.btnActionDangerText]}>
                        {t('config.eliminar_boton')}
                      </Text>
                    </TouchableOpacity>
                  }
                />
              </View>
            </Section>
          </>
        )}

        <View style={styles.bottomSpace} />
      </ScrollView>

      {/* TODO(pendiente: hogar único): si el usuario es el único miembro corresponde
          dialogo.eliminar_cuenta_hogar (con {hogar}); /usuarios/me no trae esos datos. */}
      {confirmDelete && (
        <ConfirmDialog
          tono="destructivo"
          titulo={t('dialogo.eliminar_cuenta.titulo')}
          descripcion={t('dialogo.eliminar_cuenta.cuerpo')}
          confirmar={t('dialogo.eliminar_cuenta.confirmar')}
          cancelar={t('dialogo.eliminar_cuenta.cancelar')}
          onCancelar={() => setConfirmDelete(false)}
          onConfirmar={() => {
            setConfirmDelete(false);
            void removeAccount();
          }}
        />
      )}

      {mustTransfer && (
        <ConfirmDialog
          titulo={t('dialogo.debes_transferir.titulo')}
          descripcion={t('dialogo.debes_transferir.cuerpo', {
            accion_pendiente: t('config.eliminar_t').toLowerCase(),
          })}
          confirmar={t('dialogo.debes_transferir.confirmar')}
          cancelar={t('dialogo.debes_transferir.cancelar')}
          onCancelar={clearMustTransfer}
          onConfirmar={() => {
            clearMustTransfer();
            router.push('/miembros');
          }}
        />
      )}
    </SafeAreaView>
  );
}

const AVATAR_SIZE = spacing[64] + spacing[8];

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
    height: 160,
  },
  skeletonShort: {
    height: 80,
  },

  avatarSection: {
    alignItems: 'center',
    marginBottom: spacing[20],
    minHeight: sizes['button-height'],
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
    marginBottom: spacing[8],
  },
  avatarImage: {
    width: '100%',
    height: '100%',
  },
  avatarInitials: {
    ...textStyle('display-l-24'),
    color: colors['text-accent'],
  },
  avatarName: {
    ...textStyle('display-s-16'),
    color: colors['text-primary'],
  },

  sectionCard: {
    backgroundColor: colors['background-surface'],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors['border-subtle'],
    padding: spacing[16],
    marginBottom: spacing[16],
  },
  sectionHeader: {
    ...textStyle('ui-s-etiqueta-12'),
    // Etiqueta de sección en acento, también «Zona de riesgo» (Figma A7.1).
    color: colors['text-accent'],
    marginBottom: spacing[12],
    textTransform: 'uppercase',
  },
  rowItem: {
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
  iconBoxDanger: {
    backgroundColor: colors['status-error-bg'],
  },
  rowTextContainer: {
    flex: 1,
    marginRight: spacing[8],
  },
  rowTitle: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
    marginBottom: spacing[4],
  },
  rowSubtitle: {
    ...textStyle('body-xs-regular'),
    color: colors['text-muted'],
  },
  divider: {
    height: 1,
    backgroundColor: colors['border-subtle'],
    marginVertical: spacing[12],
  },
  badgeSoon: {
    backgroundColor: colors['background-surfaceAlt'],
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    paddingHorizontal: spacing[8],
    paddingVertical: spacing[4],
  },
  badgeSoonText: {
    ...textStyle('ui-s-semibold-12'),
    color: colors['text-muted'],
  },

  btnAction: {
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    paddingHorizontal: spacing[16],
    minHeight: spacing[40],
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnActionDanger: {
    borderColor: colors['status-error-border'],
    backgroundColor: colors['status-error-bg'],
  },
  btnActionDisabled: {
    opacity: 0.5,
  },
  btnActionText: {
    ...textStyle('ui-s-semibold'),
    color: colors['text-primary'],
  },
  btnActionDangerText: {
    color: colors['text-error'],
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

});
