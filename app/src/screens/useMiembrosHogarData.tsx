/**
 * Hook de datos de Miembros del hogar (reglas v4.9 §6.17 y §7.3; RN-X-05 a RN-X-08, RN-XVI-07,
 * RN-XVII; RN-II-03, RN-II-04). Filas 16 a 19, 21 y 22 de docs/MAPA-DE-INTEGRACION.md:
 *   GET    /hogares/{hogar_id}/miembros                                       listarMiembros → listMembers
 *   PATCH  /hogares/{hogar_id}/permisos                                       actualizarPermisos → updatePermissions
 *   DELETE /hogares/{hogar_id}/miembros/{membresia_id}                        expulsarMiembro → removeMember
 *   POST   /hogares/{hogar_id}/miembros/{membresia_id}/transferir-administracion
 *                                                                             transferirAdministracion → transferAdmin
 *   POST   /hogares/{hogar_id}/invitaciones                                   crearInvitacion → createInvitation
 *   DELETE /hogares/{hogar_id}/invitaciones/{invitacion_id}                   revocarInvitacion → revokeInvitation
 *   POST   /hogares/{hogar_id}/salir                                          salirDelHogar → leaveHousehold
 *   GET    /hogares/{hogar_id}                                                obtenerHogar → getHousehold (solo el nombre,
 *          para los diálogos: `listarMiembros` no lo trae)
 *
 * El contrato no tiene «cambiar rol» como acción suelta: el único cambio de rol es transferir
 * la administración (RN-X-07), sin que el destinatario deba aceptar. Quien gestiona es solo el
 * administrador (`puede_gestionar`, RN-X-08); los demás ven la lista y los permisos en solo
 * lectura y no reciben `invitaciones_pendientes` (llega `null`).
 *
 * Fuente de datos: `MembersSource` es la única puerta. `apiSource` llama a src/api/members.ts;
 * `createMockSource` responde con la forma exacta de `MiembrosHogar` del contrato 0.2.5, aplica
 * en memoria las mismas reglas del backend (límite de 5, correo repetido, ya es miembro,
 * transferir, expulsar, cancelar) y devuelve los mismos errores `409`. Para pasar a la API real
 * no se toca la pantalla: basta con apagar el modo de ejemplo.
 *
 * Modo de ejemplo (solo `__DEV__`):
 *   - Se enciende con EXPO_PUBLIC_USE_MOCKS=true en app/.env (bandera ya existente).
 *   - Escenario con EXPO_PUBLIC_MIEMBROS_MOCK=<escenario> (por defecto `admin`) o con la
 *     opción `mockScenario`:
 *       admin         Ana (administradora) + 2 miembros + 1 invitación pendiente (queda 1 cupo)
 *       miembro       la misma casa vista por un miembro: solo lectura, sin invitaciones, con «Salir del hogar»
 *       solo_admin    hogar sin miembros adicionales ni invitaciones (estado vacío)
 *       lleno         5 miembros activos: sin cupos para invitar
 *       error         falla la carga (sin conexión)
 *       error_accion  la carga funciona y las acciones fallan (se revierte y avisa)
 *     El correo `luis.gomez@correo.com` es de un miembro activo (YA_ES_MIEMBRO) y
 *     `invitado1@correo.com` ya tiene una invitación pendiente (INVITACION_PENDIENTE_EXISTENTE).
 *
 * TODO(pendiente: hogarId): aún no existe el estado de sesión/hogar (fila 12). Mientras tanto el
 * hook recibe `hogarId`; sin él (y fuera del modo de ejemplo) devuelve `error.app.no_encontrado`.
 * TODO(pendiente: React Query): la raíz aún no monta QueryClientProvider. Al montarlo, la lista
 * pasa a useQuery(queryKey('listarMiembros', hogarId)) y las acciones a useMutation.
 * TODO(pendiente: ruta de «Invitar miembro»): el mapa asigna crearInvitacion a
 * InviteMemberScreen/useInviteMemberData; mientras esa pantalla no exista, la invitación se
 * hace desde un formulario de esta pantalla con los mismos textos `invitar.*`.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ApiRequestError } from '@/api/client';
import type { Schemas, SuccessBody } from '@/api/client';
import { MOCK_HOGAR_ID, USE_MOCKS } from '@/api/devMocks';
import { toErrorTextKey } from '@/api/errors';
import { getHousehold } from '@/api/households';
import {
  createInvitation,
  leaveHousehold,
  listMembers,
  removeMember,
  revokeInvitation,
  transferAdmin,
  updatePermissions,
} from '@/api/members';

/* ─────────────────────────── Tipos del contrato ─────────────────────────── */

export type MembersData = Schemas['MiembrosHogar'];
export type Member = Schemas['Miembro'];
export type PendingInvitation = Schemas['InvitacionPendiente'];
export type Permissions = Schemas['Permisos'];
export type PermissionKey = keyof Permissions;
export type PermissionsPatch = Schemas['PermisosActualizar'];
export type InvitationBody = Schemas['InvitacionCrear'];
export type HouseholdName = Pick<SuccessBody<'/hogares/{hogar_id}', 'get'>, 'nombre'>;

/** Puerta única de datos: mismas firmas que las funciones de src/api/members.ts. */
export interface MembersSource {
  listMembers: (hogarId: string) => Promise<MembersData>;
  updatePermissions: (hogarId: string, body: PermissionsPatch) => Promise<Permissions>;
  removeMember: (hogarId: string, membresiaId: string) => Promise<void>;
  transferAdmin: (hogarId: string, membresiaId: string) => Promise<MembersData>;
  createInvitation: (hogarId: string, body: InvitationBody) => Promise<PendingInvitation>;
  revokeInvitation: (hogarId: string, invitacionId: string) => Promise<void>;
  leaveHousehold: (hogarId: string) => Promise<void>;
  getHousehold: (hogarId: string) => Promise<HouseholdName>;
}

export type MembersState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'ready'; data: MembersData };

/* ───────────────────────────── Reglas puras ─────────────────────────────── */

/** Máximo de miembros activos más invitaciones pendientes (RN-X-05). */
export const MEMBER_LIMIT = 5;

/** Cupos libres para invitar: 5 menos activos y pendientes (RN-X-05). */
export function freeSlots(data: Pick<MembersData, 'miembros_activos' | 'invitaciones_pendientes'>): number {
  return Math.max(MEMBER_LIMIT - data.miembros_activos - (data.invitaciones_pendientes?.length ?? 0), 0);
}

/** Días enteros que faltan para `expira_en` (0 = vence hoy), con corte en 0 para fechas pasadas. */
export function daysLeft(expiraEn: string, now: number = Date.now()): number {
  return Math.max(Math.ceil((Date.parse(expiraEn) - now) / DAY_MS), 0);
}

/** Las vencidas no se muestran (PendingInvite.md, D7). */
export function visibleInvitations(invitations: PendingInvitation[] | null, now: number = Date.now()): PendingInvitation[] {
  return (invitations ?? []).filter((inv) => Date.parse(inv.expira_en) > now);
}

/** Correo con forma válida para el formulario (el backend vuelve a validar, `422`). */
export function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

/* ───────────────────────────── Fuente real ──────────────────────────────── */

export const apiSource: MembersSource = {
  listMembers,
  updatePermissions,
  removeMember,
  transferAdmin,
  createInvitation,
  revokeInvitation,
  leaveHousehold,
  getHousehold: async (hogarId) => ({ nombre: (await getHousehold(hogarId)).nombre }),
};

/* ─────────────────────────── Fuente de ejemplo ──────────────────────────── */

export const MIEMBROS_MOCK_SCENARIOS = ['admin', 'miembro', 'solo_admin', 'lleno', 'error', 'error_accion'] as const;
export type MiembrosMockScenario = (typeof MIEMBROS_MOCK_SCENARIOS)[number];

const MOCK_LATENCY_MS = 450;
const DAY_MS = 24 * 60 * 60 * 1000;
const MOCK_ID = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export const MOCK_HOUSEHOLD_NAME = 'Casa Pérez';
/** Correo de un miembro activo de ejemplo: invitarlo devuelve `YA_ES_MIEMBRO`. */
export const MOCK_MEMBER_EMAIL = 'luis.gomez@correo.com';
/** Correo con invitación pendiente de ejemplo: invitarlo devuelve `INVITACION_PENDIENTE_EXISTENTE`. */
export const MOCK_PENDING_EMAIL = 'invitado1@correo.com';

function conflict(codigo: 'LIMITE_MIEMBROS' | 'INVITACION_PENDIENTE_EXISTENTE' | 'YA_ES_MIEMBRO' | 'ADMIN_DEBE_TRANSFERIR' | 'ADMIN_UNICO_MIEMBRO'): ApiRequestError {
  return new ApiRequestError('http', 409, { codigo, mensaje: codigo.toLowerCase() });
}

function seedMembers(scenario: MiembrosMockScenario, now: number): Member[] {
  const base: Member[] = [
    { membresia_id: MOCK_ID(0xb1), usuario_id: MOCK_ID(0xa1), nombre_completo: 'Ana Pérez', avatar_url: null, rol: 'administrador', estado: 'activo', fecha_ingreso: new Date(now - 60 * DAY_MS).toISOString() },
    { membresia_id: MOCK_ID(0xb2), usuario_id: MOCK_ID(0xa2), nombre_completo: 'Luis Gómez', avatar_url: null, rol: 'miembro', estado: 'activo', fecha_ingreso: new Date(now - 40 * DAY_MS).toISOString() },
    { membresia_id: MOCK_ID(0xb3), usuario_id: MOCK_ID(0xa3), nombre_completo: 'Marta Rojas', avatar_url: null, rol: 'miembro', estado: 'activo', fecha_ingreso: new Date(now - 12 * DAY_MS).toISOString() },
  ];
  if (scenario === 'solo_admin') return base.slice(0, 1);
  if (scenario === 'lleno') {
    return [
      ...base,
      { membresia_id: MOCK_ID(0xb4), usuario_id: MOCK_ID(0xa4), nombre_completo: 'Camilo Ortiz', avatar_url: null, rol: 'miembro', estado: 'activo', fecha_ingreso: new Date(now - 8 * DAY_MS).toISOString() },
      { membresia_id: MOCK_ID(0xb5), usuario_id: MOCK_ID(0xa5), nombre_completo: 'Sofía Díaz', avatar_url: null, rol: 'miembro', estado: 'activo', fecha_ingreso: new Date(now - 3 * DAY_MS).toISOString() },
    ];
  }
  return base;
}

function seedInvitations(scenario: MiembrosMockScenario, now: number): PendingInvitation[] {
  if (scenario === 'solo_admin' || scenario === 'lleno') return [];
  // Una sola pendiente: con 3 activos queda 1 cupo para probar invitar (RN-X-05).
  return [{ id: MOCK_ID(0xc1), correo_invitado: MOCK_PENDING_EMAIL, estado: 'pendiente', expira_en: new Date(now + 5 * DAY_MS + 3 * 60 * 60 * 1000).toISOString() }];
}

/**
 * Datos de ejemplo de un escenario, con la forma de `MiembrosHogar`. `viewerIsAdmin` decide la
 * vista: el administrador recibe las invitaciones y `puede_gestionar`; los demás, `null` y `false`.
 */
export function buildMockMembers(scenario: MiembrosMockScenario, now: number = Date.now(), viewerIsAdmin: boolean = scenario !== 'miembro'): MembersData {
  const miembros = seedMembers(scenario, now);
  return {
    miembros_activos: miembros.length,
    miembros,
    invitaciones_pendientes: viewerIsAdmin ? seedInvitations(scenario, now) : null,
    permisos: { ver_consumo_actual: true, ver_historial: true, recibir_alertas: true, modificar_metas: false },
    puede_gestionar: viewerIsAdmin,
  };
}

/**
 * Fuente de ejemplo con la misma firma que la real. Guarda todo en memoria y aplica las reglas
 * del backend: solo el administrador gestiona (`403 NO_ES_ADMINISTRADOR`), tope de 5 entre
 * activos y pendientes, correo repetido o ya miembro, y el administrador no se expulsa ni sale
 * con otros miembros (`ADMIN_DEBE_TRANSFERIR`).
 */
export function createMockSource(scenario: MiembrosMockScenario, now: number = Date.now()): MembersSource {
  let data = buildMockMembers(scenario, now);
  /** Los miembros del hogar «mixto»: sus correos para detectar `YA_ES_MIEMBRO`. */
  const memberEmails = new Set([MOCK_MEMBER_EMAIL]);

  const guard = async (write: boolean) => {
    await sleep(MOCK_LATENCY_MS);
    if (scenario === 'error') throw new ApiRequestError('network', null, null);
    if (write && scenario === 'error_accion') throw new ApiRequestError('network', null, null);
    if (write && !data.puede_gestionar) throw new ApiRequestError('http', 403, { codigo: 'NO_ES_ADMINISTRADOR', mensaje: 'no_es_administrador' });
  };
  const snapshot = (): MembersData => ({ ...data, miembros: [...data.miembros], invitaciones_pendientes: data.invitaciones_pendientes ? [...data.invitaciones_pendientes] : null });
  const adminId = () => data.miembros.find((m) => m.rol === 'administrador')?.membresia_id;

  return {
    async listMembers() {
      await guard(false);
      return snapshot();
    },
    async updatePermissions(_hogarId, body) {
      await guard(true);
      data = { ...data, permisos: { ...data.permisos, ...body } };
      return { ...data.permisos };
    },
    async removeMember(_hogarId, membresiaId) {
      await guard(true);
      const target = data.miembros.find((m) => m.membresia_id === membresiaId);
      if (!target) throw new ApiRequestError('http', 404, null);
      // El administrador no puede expulsarse a sí mismo (409).
      if (target.membresia_id === adminId()) throw conflict('ADMIN_DEBE_TRANSFERIR');
      const miembros = data.miembros.filter((m) => m.membresia_id !== membresiaId);
      data = { ...data, miembros, miembros_activos: miembros.length };
    },
    async transferAdmin(_hogarId, membresiaId) {
      await guard(true);
      const target = data.miembros.find((m) => m.membresia_id === membresiaId);
      if (!target) throw new ApiRequestError('http', 404, null);
      // El destinatario no acepta; quien transfiere pasa a `miembro` y deja de gestionar.
      const miembros = data.miembros.map((m): Member => ({ ...m, rol: m.membresia_id === membresiaId ? 'administrador' : 'miembro' }));
      data = { ...data, miembros, puede_gestionar: false, invitaciones_pendientes: null };
      return snapshot();
    },
    async createInvitation(_hogarId, body) {
      await guard(true);
      const correo = body.correo_invitado.trim().toLowerCase();
      const pending = data.invitaciones_pendientes ?? [];
      if (memberEmails.has(correo)) throw conflict('YA_ES_MIEMBRO');
      if (pending.some((inv) => inv.correo_invitado.toLowerCase() === correo)) throw conflict('INVITACION_PENDIENTE_EXISTENTE');
      if (freeSlots(data) === 0) throw conflict('LIMITE_MIEMBROS');
      const created: PendingInvitation = {
        id: MOCK_ID(0xc000 + pending.length + Math.floor(Math.random() * 0xfff)),
        correo_invitado: correo,
        estado: 'pendiente',
        // Vence a los 7 días (RN-X-05); el token no se devuelve.
        expira_en: new Date(Date.now() + 7 * DAY_MS).toISOString(),
      };
      data = { ...data, invitaciones_pendientes: [...pending, created] };
      return created;
    },
    async revokeInvitation(_hogarId, invitacionId) {
      await guard(true);
      const pending = data.invitaciones_pendientes ?? [];
      if (!pending.some((inv) => inv.id === invitacionId)) throw new ApiRequestError('http', 404, null);
      data = { ...data, invitaciones_pendientes: pending.filter((inv) => inv.id !== invitacionId) };
    },
    async leaveHousehold() {
      await sleep(MOCK_LATENCY_MS);
      if (scenario === 'error' || scenario === 'error_accion') throw new ApiRequestError('network', null, null);
      if (data.puede_gestionar) throw conflict(data.miembros.length > 1 ? 'ADMIN_DEBE_TRANSFERIR' : 'ADMIN_UNICO_MIEMBRO');
    },
    async getHousehold() {
      await sleep(MOCK_LATENCY_MS / 3);
      return { nombre: MOCK_HOUSEHOLD_NAME };
    },
  };
}

function isMockScenario(value: string | undefined): value is MiembrosMockScenario {
  return (MIEMBROS_MOCK_SCENARIOS as readonly string[]).includes(value ?? '');
}

/** Escenario de EXPO_PUBLIC_MIEMBROS_MOCK; `admin` si falta o no es válido. */
const ENV_SCENARIO: MiembrosMockScenario = isMockScenario(process.env.EXPO_PUBLIC_MIEMBROS_MOCK)
  ? process.env.EXPO_PUBLIC_MIEMBROS_MOCK
  : 'admin';

/* ─────────────────────────────── El hook ────────────────────────────────── */

export interface UseMiembrosHogarDataOptions {
  /** Solo desarrollo: fuerza un escenario del modo de ejemplo. */
  mockScenario?: MiembrosMockScenario;
  /** Para pruebas: fuente inyectada (tiene prioridad sobre el modo de ejemplo). */
  source?: MembersSource;
}

/** Resultado de invitar: el formulario muestra el aviso de éxito o el error del backend. */
export type InviteResult = { ok: true; correo: string } | { ok: false; errorKey: string };

/** Textos de aviso (`toast.*` del catálogo) tras una acción del administrador. */
export type ToastKey = 'toast.transferida' | 'toast.expulsado' | 'toast.invitacion_cancelada' | 'toast.saliste' | 'miembros.permiso_actualizado';

/**
 * Miembros, invitaciones pendientes y permisos del hogar (cargando, error y datos), con
 * reintento, recarga y las acciones del administrador. Cambiar un permiso es optimista (se
 * revierte con aviso si falla); expulsar, transferir y cancelar esperan al backend y recargan.
 */
export function useMiembrosHogarData(hogarId: string | null, options: UseMiembrosHogarDataOptions = {}) {
  const useMocks = USE_MOCKS || (__DEV__ && options.mockScenario !== undefined);
  const scenario = options.mockScenario ?? ENV_SCENARIO;
  const injected = options.source;
  // Una sola fuente por escenario: la de ejemplo guarda en memoria lo que haces.
  const source = useMemo<MembersSource>(() => injected ?? (useMocks ? createMockSource(scenario) : apiSource), [injected, useMocks, scenario]);
  const effectiveHogarId = hogarId ?? (useMocks ? (MOCK_HOGAR_ID ?? MOCK_ID(1)) : null);

  const [state, setState] = useState<MembersState>({ status: 'loading' });
  const [hogarNombre, setHogarNombre] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [actionErrorKey, setActionErrorKey] = useState<string | null>(null);
  const [toastKey, setToastKey] = useState<ToastKey | null>(null);
  const [left, setLeft] = useState(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!effectiveHogarId) return;
    let cancelled = false;
    source
      .listMembers(effectiveHogarId)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', errorKey: toErrorTextKey(error) });
      })
      .finally(() => {
        if (!cancelled) setRefreshing(false);
      });
    // El nombre es solo para los diálogos: si falla, no estorba a la pantalla.
    source
      .getHousehold(effectiveHogarId)
      .then((h) => {
        if (!cancelled) setHogarNombre(h.nombre);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [effectiveHogarId, source, attempt]);

  useEffect(
    () => () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    },
    [],
  );

  const showToast = useCallback((key: ToastKey) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToastKey(key);
    toastTimer.current = setTimeout(() => setToastKey(null), 3000);
  }, []);

  /** Vuelve a cargar mostrando el esqueleto (tras un error). */
  const retry = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((n) => n + 1);
  }, []);
  /** Recarga sin esqueleto (deslizar hacia abajo). */
  const refresh = useCallback(() => {
    setRefreshing(true);
    setAttempt((n) => n + 1);
  }, []);
  const dismissActionError = useCallback(() => setActionErrorKey(null), []);
  const dismissToast = useCallback(() => setToastKey(null), []);

  /** Ejecuta una acción que espera al backend y luego recarga la lista (sin esqueleto). */
  const runAndReload = useCallback(
    async (action: (hogar: string) => Promise<unknown>, success: ToastKey): Promise<boolean> => {
      if (!effectiveHogarId || busy) return false;
      setBusy(true);
      setActionErrorKey(null);
      try {
        await action(effectiveHogarId);
        const data = await source.listMembers(effectiveHogarId);
        setState({ status: 'ready', data });
        showToast(success);
        return true;
      } catch (error: unknown) {
        setActionErrorKey(toErrorTextKey(error));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [busy, effectiveHogarId, showToast, source],
  );

  /** Cambia un permiso general del hogar (solo administrador, RN-X-08); optimista. */
  const setPermission = useCallback(
    (key: PermissionKey, value: boolean) => {
      if (!effectiveHogarId || state.status !== 'ready' || !state.data.puede_gestionar) return;
      const previous = state.data.permisos;
      const apply = (permisos: Permissions) =>
        setState((prev) => (prev.status === 'ready' ? { status: 'ready', data: { ...prev.data, permisos } } : prev));
      setActionErrorKey(null);
      apply({ ...previous, [key]: value });
      source
        .updatePermissions(effectiveHogarId, { [key]: value })
        .then((permisos) => {
          apply(permisos);
          showToast('miembros.permiso_actualizado');
        })
        .catch((error: unknown) => {
          apply(previous);
          setActionErrorKey(toErrorTextKey(error));
        });
    },
    [effectiveHogarId, showToast, source, state],
  );

  const transfer = useCallback((membresiaId: string) => runAndReload((h) => source.transferAdmin(h, membresiaId), 'toast.transferida'), [runAndReload, source]);
  const remove = useCallback((membresiaId: string) => runAndReload((h) => source.removeMember(h, membresiaId), 'toast.expulsado'), [runAndReload, source]);
  const revoke = useCallback((invitacionId: string) => runAndReload((h) => source.revokeInvitation(h, invitacionId), 'toast.invitacion_cancelada'), [runAndReload, source]);

  /** Invita por correo (RN-X-05). Devuelve el resultado para que el formulario lo muestre. */
  const invite = useCallback(
    async (correo: string): Promise<InviteResult> => {
      if (!effectiveHogarId) return { ok: false, errorKey: 'error.app.no_encontrado' };
      setBusy(true);
      try {
        const created = await source.createInvitation(effectiveHogarId, { correo_invitado: correo.trim() });
        setState((prev) =>
          prev.status === 'ready'
            ? { status: 'ready', data: { ...prev.data, invitaciones_pendientes: [...(prev.data.invitaciones_pendientes ?? []), created] } }
            : prev,
        );
        return { ok: true, correo: created.correo_invitado };
      } catch (error: unknown) {
        return { ok: false, errorKey: toErrorTextKey(error) };
      } finally {
        setBusy(false);
      }
    },
    [effectiveHogarId, source],
  );

  /** Salir del hogar (solo quien no es administrador, RN-X-07). */
  const leave = useCallback(async (): Promise<boolean> => {
    if (!effectiveHogarId || busy) return false;
    setBusy(true);
    setActionErrorKey(null);
    try {
      await source.leaveHousehold(effectiveHogarId);
      setLeft(true);
      showToast('toast.saliste');
      return true;
    } catch (error: unknown) {
      setActionErrorKey(toErrorTextKey(error));
      return false;
    } finally {
      setBusy(false);
    }
  }, [busy, effectiveHogarId, showToast, source]);

  // Sin hogar (y fuera del modo de ejemplo) no hay qué consultar.
  const visibleState: MembersState = effectiveHogarId ? state : { status: 'error', errorKey: 'error.app.no_encontrado' };

  return {
    state: visibleState,
    hogarNombre,
    retry,
    refresh,
    refreshing,
    busy,
    actionErrorKey,
    dismissActionError,
    toastKey,
    dismissToast,
    left,
    setPermission,
    transfer,
    remove,
    revoke,
    invite,
    leave,
  };
}
