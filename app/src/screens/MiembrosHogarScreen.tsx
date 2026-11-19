/**
 * Miembros del hogar (reglas v4.9 §6.17 y §7.3; RN-X-05 a RN-X-08, RN-XVI-07, RN-XVII).
 * Datos: useMiembrosHogarData (filas 16 a 19, 21 y 22 de docs/MAPA-DE-INTEGRACION.md).
 *
 * - Resumen con el conteo de miembros activos, la lista (avatar con iniciales, nombre, rol y
 *   estado) y, solo para el administrador, las invitaciones pendientes aparte (RN-X-08).
 * - Menú de acciones (hoja inferior) solo para el administrador: transferir administración y
 *   expulsar en un miembro; cancelar invitación en una pendiente. Toda acción pide confirmación
 *   (RN-X-07). El administrador no tiene menú sobre sí mismo.
 * - «Permisos de los miembros»: cuatro interruptores para el administrador y, para los demás,
 *   solo lectura con la palabra «Permitido» o «No permitido» (RN-XVII, RN-XVI-07).
 * - «Invitar miembro» (solo administrador): formulario con el correo; desactivado sin cupos
 *   (5 entre activos y pendientes, RN-X-05).
 * - «Salir del hogar» para quien no es administrador (§7.3, RN-X-07).
 * - Estados: cargando (esqueleto), error (aviso con Reintentar) y vacío (hogar sin miembros
 *   adicionales ni invitaciones, con la invitación como acción).
 * - Colores, espacios y tipografía desde @/theme; textos con t() y plural(); fechas con el
 *   catálogo (formato.vence.dias); sin cifras sueltas.
 *
 * TODO(pendiente: componentes del sistema de diseño): src/components/ aún no tiene ActionItem,
 * BottomSheet, ConfirmDialog, PendingInvite, Chip, TextField, InlineNotice, Skeleton ni
 * ScreenHeader con las props de index.d.ts. Aquí son piezas locales de presentación para
 * moverlas a src/components/ cuando se apruebe.
 * TODO(pendiente: foto): `avatar_url` es una ruta del bucket privado; sin la URL firmada de cada
 * miembro (RN-I-02) se muestran las iniciales.
 * Ruta: `src/app/miembros.tsx` (oculta en el Tabs de `_layout.tsx`); se llega desde Configuración.
 * TODO(pendiente: navegación tras salir): al salir del hogar no hay a dónde ir hasta que exista
 * el estado de sesión/hogar; se muestra el aviso «Saliste del hogar».
 */
import React, { useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StatusBar,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TextStyle,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { ArrowLeftRight, Check, ChevronLeft, CircleCheck, CircleX, EllipsisVertical, LogOut, Mail, UserMinus, UserPlus, X } from 'lucide-react-native';

import { colors, fontFamilyFor, radius, sizes, spacing, typography } from '@/theme';
import { plural, t } from '@/texts';

import { daysLeft, freeSlots, isValidEmail, useMiembrosHogarData, visibleInvitations } from './useMiembrosHogarData';
import type { InviteResult, Member, MiembrosMockScenario, PendingInvitation, PermissionKey } from './useMiembrosHogarData';

/* ───────────────────────────── Utilidades ───────────────────────────────── */

function textStyle(name: keyof typeof typography): TextStyle {
  const style = typography[name];
  return {
    fontFamily: fontFamilyFor(style.family, style.fontWeight),
    fontSize: style.fontSize,
    ...('lineHeight' in style ? { lineHeight: style.lineHeight } : {}),
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

/** Permisos generales del hogar en el orden de RN-XVI-07, con su texto del catálogo. */
const PERMISSIONS: { key: PermissionKey; label: string }[] = [
  { key: 'ver_consumo_actual', label: 'miembros.perm_consumo' },
  { key: 'ver_historial', label: 'miembros.perm_historial' },
  { key: 'recibir_alertas', label: 'miembros.perm_alertas' },
  { key: 'modificar_metas', label: 'miembros.perm_metas' },
];

const SKELETON_ROWS = 3;
const TOUCH = 48;

/** Acción abierta: define la hoja de acciones y el diálogo de confirmación. */
type Pending =
  | { kind: 'member'; member: Member }
  | { kind: 'invitation'; invitation: PendingInvitation };
type Confirm =
  | { kind: 'transfer'; member: Member }
  | { kind: 'remove'; member: Member }
  | { kind: 'revoke'; invitation: PendingInvitation }
  | { kind: 'leave' };

/** Clave de `dialogo.*`, sus variables y el tono de cada confirmación (ConfirmDialog.md). */
function dialogFor(confirm: Confirm, hogar: string): { key: string; vars: Record<string, string>; destructivo: boolean } {
  switch (confirm.kind) {
    case 'transfer':
      return { key: 'transferir', vars: { nombre: confirm.member.nombre_completo }, destructivo: false };
    case 'remove':
      return { key: 'expulsar', vars: { nombre: confirm.member.nombre_completo, hogar }, destructivo: true };
    case 'revoke':
      return { key: 'cancelar_invitacion', vars: { correo: confirm.invitation.correo_invitado }, destructivo: true };
    case 'leave':
      return { key: 'salir_hogar', vars: { hogar }, destructivo: true };
  }
}

/* ─────────────────────── Piezas de presentación ─────────────────────────── */

function Avatar({ nombre }: { nombre: string }) {
  return (
    <View style={styles.avatar}>
      <Text style={styles.avatarText}>{initialsOf(nombre)}</Text>
    </View>
  );
}

function MenuButton({ nombre, onPress }: { nombre: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={t('a11y.menu_acciones', { nombre })} style={styles.menuButton}>
      <EllipsisVertical size={20} color={colors['text-muted']} />
    </Pressable>
  );
}

function MemberRow({ member, isSelf, onMenu }: { member: Member; isSelf: boolean; onMenu?: () => void }) {
  return (
    <View style={styles.row}>
      <Avatar nombre={member.nombre_completo} />
      <View style={styles.flex}>
        <Text style={styles.rowTitle} numberOfLines={1}>
          {member.nombre_completo}
          {isSelf ? ` ${t('comun.tu')}` : ''}
        </Text>
        <Text style={styles.rowSubtitle}>{`${t(`rol.${member.rol}`)} · ${t('miembros.estado_activo')}`}</Text>
      </View>
      {onMenu ? <MenuButton nombre={member.nombre_completo} onPress={onMenu} /> : null}
    </View>
  );
}

/** Invitación pendiente (PendingInvite.md): insignia «Pendiente» neutra; el amarillo es solo de severidad. */
function PendingInviteRow({ invitation, onMenu }: { invitation: PendingInvitation; onMenu: () => void }) {
  return (
    <View style={styles.row}>
      <View style={styles.avatar}>
        <Mail size={20} color={colors['text-accent']} />
      </View>
      <View style={styles.flex}>
        <Text style={styles.rowTitle} numberOfLines={1}>
          {invitation.correo_invitado}
        </Text>
        <Text style={styles.rowSubtitle}>{plural('formato.vence.dias', daysLeft(invitation.expira_en))}</Text>
      </View>
      <View style={styles.pendingBadge}>
        <Text style={styles.pendingBadgeText}>{t('miembros.estado_pendiente')}</Text>
      </View>
      <MenuButton nombre={invitation.correo_invitado} onPress={onMenu} />
    </View>
  );
}

function PermissionRow({ label, value, editable, onChange }: { label: string; value: boolean; editable: boolean; onChange: (v: boolean) => void }) {
  return (
    <View style={styles.permissionRow}>
      <Text style={[styles.rowTitle, styles.flex]}>{label}</Text>
      {editable ? (
        <Switch
          value={value}
          onValueChange={onChange}
          trackColor={{ false: colors['neutral-700'], true: colors['accent-primary'] }}
          thumbColor={colors['text-primary']}
          ios_backgroundColor={colors['neutral-700']}
          accessibilityLabel={label}
        />
      ) : (
        <View style={styles.permissionState} accessibilityLabel={`${label}: ${t(value ? 'miembros.perm_si' : 'miembros.perm_no')}`}>
          {value ? <Check size={16} color={colors['text-success']} /> : <X size={16} color={colors['text-muted']} />}
          <Text style={[styles.permissionStateText, value && { color: colors['text-success'] }]}>{t(value ? 'miembros.perm_si' : 'miembros.perm_no')}</Text>
        </View>
      )}
    </View>
  );
}

function Button({ label, onPress, tone = 'primary', disabled = false, busy = false, icon }: { label: string; onPress: () => void; tone?: 'primary' | 'secondary' | 'danger'; disabled?: boolean; busy?: boolean; icon?: React.ReactNode }) {
  const isDisabled = disabled || busy;
  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityState={{ disabled: isDisabled, busy }}
      style={[styles.button, tone === 'secondary' && styles.buttonSecondary, tone === 'danger' && styles.buttonDanger, isDisabled && styles.buttonDisabled]}
    >
      {busy ? <ActivityIndicator color={tone === 'primary' ? colors['text-inverse'] : colors['text-primary']} /> : icon}
      <Text style={[styles.buttonText, tone === 'primary' && styles.buttonTextPrimary, tone === 'danger' && styles.buttonTextDanger]}>{label}</Text>
    </Pressable>
  );
}

function InlineNotice({ titulo, descripcion, onReintentar }: { titulo: string; descripcion?: string; onReintentar?: () => void }) {
  return (
    <View style={styles.notice} accessibilityRole="alert">
      <View style={styles.noticeRow}>
        <CircleX size={16} color={colors['status-error-default']} />
        <View style={styles.flex}>
          <Text style={styles.noticeTitle}>{titulo}</Text>
          {descripcion ? <Text style={styles.mutedXs}>{descripcion}</Text> : null}
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

/** Esqueleto con la forma de la lista: avatar y dos líneas por fila. */
function MembersSkeleton() {
  return (
    <View style={styles.card} accessible accessibilityLabel={t('comun.cargando')}>
      <View style={[styles.skeletonBlock, styles.skeletonHeader]} />
      {Array.from({ length: SKELETON_ROWS }, (_, i) => (
        <View key={i} style={styles.row}>
          <View style={[styles.skeletonBlock, styles.skeletonAvatar]} />
          <View style={[styles.flex, styles.skeletonLines]}>
            <View style={[styles.skeletonBlock, styles.skeletonTitle]} />
            <View style={[styles.skeletonBlock, styles.skeletonSubtitle]} />
          </View>
        </View>
      ))}
    </View>
  );
}

/** Hoja inferior (BottomSheet.md) con el menú de acciones del miembro o de la invitación. */
function ActionSheet({ visible, titulo, descripcion, onClose, children }: { visible: boolean; titulo: string; descripcion: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <Pressable style={styles.overlay} onPress={onClose} accessibilityLabel={t('comun.cerrar')} />
      <View style={styles.sheet} accessibilityViewIsModal>
        <View style={styles.handle} />
        <View style={styles.sheetHeader}>
          <View style={styles.flex}>
            <Text style={styles.sheetTitle}>{titulo}</Text>
            <Text style={styles.rowSubtitle}>{descripcion}</Text>
          </View>
          <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel={t('comun.cerrar')} style={styles.menuButton}>
            <X size={24} color={colors['text-muted']} />
          </Pressable>
        </View>
        {children}
      </View>
    </Modal>
  );
}

function ActionItem({ texto, icono, destructivo = false, onPress }: { texto: string; icono: React.ReactNode; destructivo?: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={styles.actionItem}>
      {icono}
      <Text style={[styles.actionText, destructivo && { color: colors['text-error'] }]}>{texto}</Text>
    </Pressable>
  );
}

/** Confirmación de acciones irreversibles (ConfirmDialog.md): principal arriba, cancelar abajo. */
function ConfirmDialog({ visible, titulo, descripcion, confirmar, cancelar, destructivo, busy, onConfirm, onCancel }: { visible: boolean; titulo: string; descripcion: string; confirmar: string; cancelar: string; destructivo: boolean; busy: boolean; onConfirm: () => void; onCancel: () => void }) {
  return (
    <Modal visible={visible} animationType="fade" transparent onRequestClose={onCancel}>
      <View style={styles.dialogOverlay}>
        <View style={styles.dialogCard} accessibilityViewIsModal>
          <Text style={styles.dialogTitle}>{titulo}</Text>
          <Text style={styles.dialogBody}>{descripcion}</Text>
          <Button label={confirmar} onPress={onConfirm} tone={destructivo ? 'danger' : 'primary'} busy={busy} />
          <Button label={cancelar} onPress={onCancel} tone="secondary" disabled={busy} />
        </View>
      </View>
    </Modal>
  );
}

/** Formulario «Invitar miembro» (textos `invitar.*`); el éxito reemplaza al formulario. */
function InviteSheet({ visible, slots, busy, onInvite, onClose }: { visible: boolean; slots: number; busy: boolean; onInvite: (correo: string) => Promise<InviteResult>; onClose: () => void }) {
  const [correo, setCorreo] = useState('');
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [serverErrorKey, setServerErrorKey] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  const reset = () => {
    setCorreo('');
    setFieldError(null);
    setServerErrorKey(null);
    setSentTo(null);
  };
  const close = () => {
    reset();
    onClose();
  };
  const submit = async () => {
    setServerErrorKey(null);
    if (!isValidEmail(correo)) {
      setFieldError(t('error.campo.correo_invalido'));
      return;
    }
    setFieldError(null);
    const result = await onInvite(correo);
    if (result.ok) setSentTo(result.correo);
    else setServerErrorKey(result.errorKey);
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={close}>
      <Pressable style={styles.overlay} onPress={close} accessibilityLabel={t('comun.cerrar')} />
      <View style={styles.sheet} accessibilityViewIsModal>
        <View style={styles.handle} />
        <View style={styles.sheetHeader}>
          <Text style={[styles.sheetTitle, styles.flex]}>{t('invitar.encabezado')}</Text>
          <Pressable onPress={close} accessibilityRole="button" accessibilityLabel={t('comun.cerrar')} style={styles.menuButton}>
            <X size={24} color={colors['text-muted']} />
          </Pressable>
        </View>

        {sentTo ? (
          <View style={styles.sheetBody}>
            <View style={styles.successRow}>
              <CircleCheck size={24} color={colors['status-success-default']} />
              <View style={styles.flex}>
                <Text style={styles.rowTitle}>{t('invitar.enviada_titulo')}</Text>
                <Text style={styles.mutedXs}>{t('invitar.enviada_cuerpo', { correo: sentTo })}</Text>
              </View>
            </View>
            {slots > 0 ? <Button label={t('invitar.otra')} onPress={reset} tone="secondary" /> : null}
            <Button label={t('comun.cerrar')} onPress={close} />
          </View>
        ) : (
          <View style={styles.sheetBody}>
            <Text style={styles.rowTitle}>{t('invitar.titulo')}</Text>
            <Text style={styles.mutedXs}>{t('invitar.cuerpo')}</Text>
            <View style={styles.field}>
              <Text style={styles.fieldLabel}>{t('invitar.correo')}</Text>
              <TextInput
                value={correo}
                onChangeText={(v) => {
                  setCorreo(v);
                  setFieldError(null);
                }}
                placeholder={t('invitar.correo_ph')}
                placeholderTextColor={colors['text-muted']}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                editable={!busy}
                accessibilityLabel={t('invitar.correo')}
                style={[styles.input, fieldError ? styles.inputError : null]}
              />
              {fieldError ? <Text style={styles.fieldError}>{fieldError}</Text> : null}
            </View>
            <Text style={styles.mutedXs}>{plural('invitar.cupos', slots)}</Text>
            {serverErrorKey ? <InlineNotice titulo={t(`${serverErrorKey}.titulo`)} descripcion={t(`${serverErrorKey}.cuerpo`)} /> : null}
            <Button label={t('invitar.boton')} onPress={() => void submit()} busy={busy} disabled={slots === 0 || correo.trim().length === 0} />
          </View>
        )}
      </View>
    </Modal>
  );
}

/* ─────────────────────────────── Pantalla ───────────────────────────────── */

export interface MiembrosHogarScreenProps {
  /** TODO(pendiente: hogarId): vendrá del estado de sesión/hogar (fila 12 del mapa). */
  hogarId?: string | null;
  /** Solo desarrollo: fuerza un escenario del modo de ejemplo. */
  mockScenario?: MiembrosMockScenario;
}

export function MiembrosHogarScreen({ hogarId = null, mockScenario }: MiembrosHogarScreenProps) {
  const router = useRouter();
  const h = useMiembrosHogarData(hogarId, { mockScenario });
  const [pending, setPending] = useState<Pending | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [inviting, setInviting] = useState(false);

  const hogar = h.hogarNombre ?? '';

  const runConfirm = async () => {
    if (!confirm) return;
    if (confirm.kind === 'transfer') await h.transfer(confirm.member.membresia_id);
    else if (confirm.kind === 'remove') await h.remove(confirm.member.membresia_id);
    else if (confirm.kind === 'revoke') await h.revoke(confirm.invitation.id);
    else await h.leave();
    setConfirm(null);
  };

  const dialog = confirm ? dialogFor(confirm, hogar) : null;

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <StatusBar barStyle="light-content" backgroundColor={colors['background-default']} />

      <View style={styles.header}>
        <Pressable onPress={() => router.back()} accessibilityRole="button" accessibilityLabel={t('a11y.volver')} style={styles.headerButton}>
          <ChevronLeft size={24} color={colors['text-primary']} />
        </Pressable>
        <Text style={styles.headerTitle} accessibilityRole="header">
          {t('miembros.encabezado')}
        </Text>
        <View style={styles.headerButton} />
      </View>

      <ScrollView
        style={styles.flex}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={h.refreshing}
            onRefresh={h.refresh}
            tintColor={colors['accent-primary']}
            colors={[colors['accent-primary']]}
            progressBackgroundColor={colors['background-surface']}
          />
        }
      >
        {h.state.status === 'loading' && <MembersSkeleton />}

        {h.state.status === 'error' && <InlineNotice titulo={t(`${h.state.errorKey}.titulo`)} descripcion={t(`${h.state.errorKey}.cuerpo`)} onReintentar={h.retry} />}

        {h.state.status === 'ready' && h.left && (
          <View style={styles.card}>
            <View style={styles.successRow}>
              <CircleCheck size={24} color={colors['status-success-default']} />
              <Text style={[styles.rowTitle, styles.flex]}>{t('toast.saliste')}</Text>
            </View>
          </View>
        )}

        {h.state.status === 'ready' && !h.left && (() => {
          const data = h.state.data;
          const canManage = data.puede_gestionar;
          const invitations = canManage ? visibleInvitations(data.invitaciones_pendientes) : [];
          const slots = freeSlots({ miembros_activos: data.miembros_activos, invitaciones_pendientes: invitations });
          const alone = canManage && data.miembros_activos === 1 && invitations.length === 0;
          return (
            <>
              <Text style={styles.subtitle}>{t(canManage ? 'miembros.subtitulo_admin' : 'miembros.subtitulo_miembro')}</Text>
              {h.actionErrorKey ? <InlineNotice titulo={t(`${h.actionErrorKey}.titulo`)} descripcion={t(`${h.actionErrorKey}.cuerpo`)} /> : null}

              <View style={styles.card}>
                <Text style={styles.cardTitle} accessibilityRole="header">
                  {plural('miembros.resumen', data.miembros_activos)}
                </Text>
                {data.miembros.map((m) => {
                  // El administrador no tiene menú sobre sí mismo (no puede expulsarse ni transferirse a sí).
                  const isSelf = canManage && m.rol === 'administrador';
                  return <MemberRow key={m.membresia_id} member={m} isSelf={isSelf} onMenu={canManage && !isSelf ? () => setPending({ kind: 'member', member: m }) : undefined} />;
                })}
              </View>

              {alone && (
                <View style={styles.card}>
                  <View style={styles.successRow}>
                    <UserPlus size={32} color={colors['text-muted']} />
                    <View style={styles.flex}>
                      <Text style={styles.rowTitle}>{t('invitar.titulo')}</Text>
                      <Text style={styles.mutedXs}>{t('invitar.cuerpo')}</Text>
                    </View>
                  </View>
                </View>
              )}

              {canManage && invitations.length > 0 && (
                <View style={styles.card}>
                  <Text style={styles.cardTitle} accessibilityRole="header">
                    {t('miembros.pendientes_titulo')}
                  </Text>
                  <Text style={styles.mutedXs}>{t('miembros.pendientes_ayuda')}</Text>
                  {invitations.map((inv) => (
                    <PendingInviteRow key={inv.id} invitation={inv} onMenu={() => setPending({ kind: 'invitation', invitation: inv })} />
                  ))}
                </View>
              )}

              <View style={styles.card}>
                <Text style={styles.cardTitle} accessibilityRole="header">
                  {t('miembros.permisos_titulo')}
                </Text>
                <Text style={styles.mutedXs}>{t(canManage ? 'miembros.permisos_admin' : 'miembros.permisos_lectura')}</Text>
                {PERMISSIONS.map(({ key, label }) => (
                  <PermissionRow key={key} label={t(label)} value={data.permisos[key]} editable={canManage} onChange={(value) => h.setPermission(key, value)} />
                ))}
              </View>

              {canManage ? (
                <View style={styles.actions}>
                  <Button label={t('miembros.invitar')} onPress={() => setInviting(true)} disabled={slots === 0} icon={<UserPlus size={20} color={colors['text-inverse']} />} />
                  <Text style={styles.mutedXs}>{plural('miembros.cupos', slots)}</Text>
                </View>
              ) : (
                <View style={styles.actions}>
                  <Button label={t('miembros.salir')} onPress={() => setConfirm({ kind: 'leave' })} tone="danger" icon={<LogOut size={20} color={colors['text-error']} />} />
                </View>
              )}

              <InviteSheet
                visible={inviting}
                slots={slots}
                busy={h.busy}
                onInvite={h.invite}
                onClose={() => setInviting(false)}
              />
            </>
          );
        })()}
      </ScrollView>

      <ActionSheet
        visible={pending !== null}
        titulo={pending?.kind === 'member' ? pending.member.nombre_completo : (pending?.invitation.correo_invitado ?? '')}
        descripcion={
          pending?.kind === 'member'
            ? t('miembros.menu_miembro')
            : pending
              ? t('miembros.menu_invitacion', { vence: plural('formato.vence.dias', daysLeft(pending.invitation.expira_en)) })
              : ''
        }
        onClose={() => setPending(null)}
      >
        {pending?.kind === 'member' ? (
          <>
            <ActionItem
              texto={t('miembros.menu_transferir')}
              icono={<ArrowLeftRight size={20} color={colors['text-primary']} />}
              onPress={() => {
                setConfirm({ kind: 'transfer', member: pending.member });
                setPending(null);
              }}
            />
            <ActionItem
              texto={t('miembros.menu_expulsar')}
              icono={<UserMinus size={20} color={colors['status-error-default']} />}
              destructivo
              onPress={() => {
                setConfirm({ kind: 'remove', member: pending.member });
                setPending(null);
              }}
            />
          </>
        ) : pending ? (
          <ActionItem
            texto={t('miembros.menu_cancelar_inv')}
            icono={<X size={20} color={colors['status-error-default']} />}
            destructivo
            onPress={() => {
              setConfirm({ kind: 'revoke', invitation: pending.invitation });
              setPending(null);
            }}
          />
        ) : null}
      </ActionSheet>

      <ConfirmDialog
        visible={confirm !== null && !!dialog}
        titulo={dialog ? t(`dialogo.${dialog.key}.titulo`, dialog.vars) : ''}
        descripcion={dialog ? t(`dialogo.${dialog.key}.cuerpo`, dialog.vars) : ''}
        confirmar={dialog ? t(`dialogo.${dialog.key}.confirmar`) : ''}
        cancelar={dialog ? t(`dialogo.${dialog.key}.cancelar`) : ''}
        destructivo={dialog ? dialog.destructivo : false}
        busy={h.busy}
        onConfirm={() => void runConfirm()}
        onCancel={() => setConfirm(null)}
      />

      {h.toastKey ? (
        <Pressable style={styles.toast} onPress={h.dismissToast} accessibilityRole="alert" accessibilityLiveRegion="polite">
          <CircleCheck size={16} color={colors['status-success-default']} />
          <Text style={styles.toastText}>{t(h.toastKey)}</Text>
        </Pressable>
      ) : null}
    </SafeAreaView>
  );
}

/* ─────────────────────────────── Estilos ────────────────────────────────── */

const AVATAR = spacing['40'];

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors['background-default'] },
  flex: { flex: 1, minWidth: 0 },
  content: { paddingHorizontal: sizes['grid-margin'], paddingTop: spacing['16'], paddingBottom: spacing['40'], gap: spacing['16'] },

  // Cabecera (ScreenHeader.md)
  header: {
    height: sizes['topBar-height'],
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing['4'],
    borderBottomWidth: 1,
    borderBottomColor: colors['border-subtle'],
  },
  headerButton: { width: TOUCH, height: TOUCH, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { ...textStyle('display-l-24'), color: colors['text-primary'] },
  subtitle: { ...textStyle('body-s-regular'), color: colors['text-muted'] },

  // Card base
  card: {
    backgroundColor: colors['background-surface'],
    borderColor: colors['border-subtle'],
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: sizes['card-padding'],
    gap: spacing['12'],
  },
  cardTitle: { ...textStyle('body-s-medium'), color: colors['text-primary'] },
  mutedXs: { ...textStyle('body-xs-regular'), color: colors['text-muted'] },

  // Filas
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing['12'] },
  rowTitle: { ...textStyle('body-m-medium'), color: colors['text-primary'] },
  rowSubtitle: { ...textStyle('body-xs-regular'), color: colors['text-muted'] },
  avatar: { width: AVATAR, height: AVATAR, borderRadius: radius.full, backgroundColor: colors['accent-soft'], alignItems: 'center', justifyContent: 'center' },
  avatarText: { ...textStyle('ui-s-semibold'), color: colors['text-accent'] },
  menuButton: { width: TOUCH, height: TOUCH, alignItems: 'center', justifyContent: 'center' },
  pendingBadge: { paddingVertical: spacing['4'], paddingHorizontal: spacing['8'], borderRadius: radius.full, borderWidth: 1, borderColor: colors['border-medium'] },
  pendingBadgeText: { ...textStyle('body-xs-medium'), color: colors['text-muted'] },

  // Permisos
  permissionRow: { flexDirection: 'row', alignItems: 'center', gap: spacing['12'], minHeight: TOUCH },
  permissionState: { flexDirection: 'row', alignItems: 'center', gap: spacing['4'] },
  permissionStateText: { ...textStyle('body-xs-medium'), color: colors['text-muted'] },

  // Botones
  actions: { gap: spacing['8'] },
  button: {
    minHeight: sizes['button-height'],
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing['8'],
    paddingHorizontal: spacing['16'],
    borderRadius: radius.lg,
    backgroundColor: colors['accent-primary'],
  },
  buttonSecondary: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors['border-medium'] },
  buttonDanger: { backgroundColor: 'transparent', borderWidth: 1, borderColor: colors['status-error-border'] },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { ...textStyle('ui-m-semibold'), color: colors['text-primary'] },
  buttonTextPrimary: { color: colors['text-inverse'] },
  buttonTextDanger: { color: colors['text-error'] },

  // InlineNotice
  notice: { backgroundColor: colors['status-error-bg'], borderColor: colors['status-error-border'], borderWidth: 1, borderRadius: radius.md, padding: spacing['12'], gap: spacing['8'] },
  noticeRow: { flexDirection: 'row', gap: spacing['8'] },
  noticeTitle: { ...textStyle('ui-s-semibold'), color: colors['status-error-text'] },
  noticeAction: { alignSelf: 'flex-end', minHeight: spacing['48'], justifyContent: 'center' },
  linkText: { ...textStyle('ui-s-semibold-12'), color: colors['text-accent'] },
  successRow: { flexDirection: 'row', alignItems: 'center', gap: spacing['12'] },

  // Hoja inferior y diálogo
  overlay: { flex: 1, backgroundColor: colors['background-overlay'] },
  sheet: {
    backgroundColor: colors['background-surfaceAlt'],
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingTop: spacing['8'],
    paddingHorizontal: spacing['16'],
    paddingBottom: spacing['32'],
    gap: spacing['8'],
  },
  handle: { alignSelf: 'center', width: spacing['40'], height: spacing['4'], borderRadius: radius.full, backgroundColor: colors['text-muted'] },
  sheetHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing['8'] },
  sheetTitle: { ...textStyle('display-m'), color: colors['text-primary'] },
  sheetBody: { gap: spacing['12'] },
  actionItem: { minHeight: TOUCH, flexDirection: 'row', alignItems: 'center', gap: spacing['12'] },
  actionText: { ...textStyle('body-m-regular'), color: colors['text-primary'] },
  dialogOverlay: { flex: 1, backgroundColor: colors['background-overlay'], justifyContent: 'center', paddingHorizontal: spacing['24'] },
  dialogCard: { backgroundColor: colors['background-surfaceAlt'], borderColor: colors['border-subtle'], borderWidth: 1, borderRadius: radius.lg, padding: spacing['24'], gap: spacing['12'] },
  dialogTitle: { ...textStyle('display-m'), color: colors['text-primary'] },
  dialogBody: { ...textStyle('body-s-regular'), color: colors['text-muted'] },

  // Formulario de invitación
  field: { gap: spacing['4'] },
  fieldLabel: { ...textStyle('body-s-medium'), color: colors['text-primary'] },
  input: {
    minHeight: sizes['button-height'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['border-medium'],
    backgroundColor: colors['background-surface'],
    paddingHorizontal: spacing['16'],
    color: colors['text-primary'],
    ...textStyle('body-m-regular'),
  },
  inputError: { borderColor: colors['status-error-default'] },
  fieldError: { ...textStyle('body-xs-regular'), color: colors['text-error'] },

  // Aviso de éxito
  toast: {
    position: 'absolute',
    left: sizes['grid-margin'],
    right: sizes['grid-margin'],
    bottom: spacing['24'],
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing['8'],
    padding: spacing['12'],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors['status-success-border'],
    backgroundColor: colors['background-surfaceAlt'],
  },
  toastText: { ...textStyle('ui-s-semibold'), color: colors['text-primary'], flex: 1 },

  // Esqueleto
  skeletonBlock: { backgroundColor: colors['background-elevated'], borderRadius: radius.xs },
  skeletonHeader: { height: spacing['16'], width: '40%' },
  skeletonAvatar: { width: AVATAR, height: AVATAR, borderRadius: radius.full },
  skeletonLines: { gap: spacing['8'] },
  skeletonTitle: { height: spacing['16'], width: '60%' },
  skeletonSubtitle: { height: spacing['12'], width: '40%' },
});
