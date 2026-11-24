/**
 * Hook de datos del Panel principal (reglas v4.9 §6.4, RN-XI-01 a RN-XI-09, RN-XII-01 a
 * RN-XII-05). Fila de DashboardScreen en docs/MAPA-DE-INTEGRACION.md:
 *   13 · GET /hogares/{hogar_id}                 obtenerHogar          → getHousehold
 *   27 · GET /hogares/{hogar_id}/consumo/actual  obtenerConsumoActual  → getCurrentConsumption
 *   28 · GET /hogares/{hogar_id}/consumo/zonas   obtenerConsumoZonas   → getZonesConsumption
 *   37 · GET /hogares/{hogar_id}/alertas/no-leidas contarAlertasNoLeidas → countUnreadAlerts
 * Además, fila 2 · GET /usuarios/me (obtenerUsuarioActual → getCurrentUser) para el primer
 * nombre del saludo (RN-XII-01): el MAPA no lo asigna al Panel; se avisa en el PR.
 *
 * Fuente de datos: `DashboardSource` es la única puerta de entrada. `apiSource` llama a las
 * funciones del cliente tipado (src/api/); `mockSource` devuelve respuestas con la forma
 * exacta del contrato 0.2.5 (tipos `SuccessBody` de src/api/schema.d.ts). Para pasar a la API
 * real no se toca la pantalla: basta con apagar el modo de ejemplo.
 *
 * Modo de ejemplo (solo `__DEV__`):
 *   - Se enciende con EXPO_PUBLIC_USE_MOCKS=true en app/.env (bandera ya existente).
 *   - El escenario se elige con EXPO_PUBLIC_DASHBOARD_MOCK=<escenario> (por defecto `normal`)
 *     o con la opción `mockScenario` del hook:
 *       normal · elevado (alerta) · critico · sin_datos · sin_permiso · sin_tarifa · error
 *
 * Reglas que aplica:
 *   - Sin «ver consumo actual», no se piden consumo ni zonas: la pantalla muestra el estado
 *     sin permiso (sección 7.3). Un 403 de la API se trata igual.
 *   - Sin «recibir alertas», no se cuenta lo no leído y la campana se oculta (RN-XII-02).
 *     Si el conteo falla, el Panel se muestra igual, sin indicador.
 *   - `null` es «sin dato», nunca cero: el hook no rellena valores.
 *
 * TODO(pendiente: hogarId): aún no existe el estado de sesión/hogar (GET /hogares/actual,
 * fila 12). Mientras tanto el hook recibe `hogarId`; sin él (y fuera del modo de ejemplo)
 * devuelve `error.app.no_encontrado`.
 * TODO(pendiente: React Query): la raíz aún no monta QueryClientProvider. Al montarlo, cada
 * llamada pasa a useQuery(queryKey('<operationId>', hogarId)) con src/state/queryKeys.ts.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { getCurrentConsumption, getZonesConsumption } from '@/api/consumption';
import { countUnreadAlerts } from '@/api/alertsTips';
import { ApiRequestError } from '@/api/client';
import type { SuccessBody } from '@/api/client';
import { MOCK_HOGAR_ID, USE_MOCKS } from '@/api/devMocks';
import { toErrorTextKey } from '@/api/errors';
import { getHousehold } from '@/api/households';
import { getCurrentUser } from '@/api/users';

/* ─────────────────────────── Tipos del contrato ─────────────────────────── */

export type Household = SuccessBody<'/hogares/{hogar_id}', 'get'>;
export type CurrentUser = SuccessBody<'/usuarios/me', 'get'>;
export type CurrentConsumption = SuccessBody<'/hogares/{hogar_id}/consumo/actual', 'get'>;
export type ZonesConsumption = SuccessBody<'/hogares/{hogar_id}/consumo/zonas', 'get'>;
export type UnreadAlerts = SuccessBody<'/hogares/{hogar_id}/alertas/no-leidas', 'get'>;
export type ZoneConsumptionItem = ZonesConsumption['zonas'][number];
export type ConsumptionState = CurrentConsumption['actual']['estado'];

/** Puerta única de datos del Panel: misma firma que las funciones de src/api/. */
export interface DashboardSource {
  getCurrentUser: () => Promise<CurrentUser>;
  getHousehold: (hogarId: string) => Promise<Household>;
  getCurrentConsumption: (hogarId: string) => Promise<CurrentConsumption>;
  getZonesConsumption: (hogarId: string) => Promise<ZonesConsumption>;
  countUnreadAlerts: (hogarId: string) => Promise<UnreadAlerts>;
}

export interface DashboardData {
  household: Household;
  /** Primer nombre de `nombre_completo` (RN-XII-01). */
  firstName: string;
  /** Permiso «ver consumo actual»; sin él, `current` y `zones` son null. */
  canSeeConsumption: boolean;
  /** Permiso «recibir alertas»; sin él, la campana se oculta (RN-XII-02). */
  canReceiveAlerts: boolean;
  current: CurrentConsumption | null;
  zones: ZonesConsumption | null;
  /** null = sin conteo (sin permiso o falló la consulta): sin indicador. */
  unreadAlerts: number | null;
}

export type DashboardState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'ready'; data: DashboardData };

/* ───────────────────────────── Fuente real ──────────────────────────────── */

export const apiSource: DashboardSource = {
  getCurrentUser,
  getHousehold,
  getCurrentConsumption,
  getZonesConsumption,
  countUnreadAlerts,
};

/* ─────────────────────────── Fuente de ejemplo ──────────────────────────── */

export const DASHBOARD_MOCK_SCENARIOS = [
  'normal',
  'elevado',
  'critico',
  'sin_datos',
  'sin_permiso',
  'sin_tarifa',
  'error',
] as const;
export type DashboardMockScenario = (typeof DASHBOARD_MOCK_SCENARIOS)[number];

const MOCK_LATENCY_MS = 600;
/** Precio de ejemplo (el mismo de la tarifa de src/api/devMocks.ts). */
const MOCK_PRICE_COP_KWH = 892;
const MOCK_ID = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Última hora completa, como la devuelve la API. */
function mockLastFullHour(): CurrentConsumption['hora'] {
  const end = new Date();
  end.setUTCMinutes(0, 0, 0);
  const start = new Date(end.getTime() - 60 * 60 * 1000);
  return { inicio: start.toISOString(), fin: end.toISOString() };
}

function cop(kwh: number | null, withTariff: boolean): number | null {
  return withTariff && kwh !== null ? Math.round(kwh * MOCK_PRICE_COP_KWH) : null;
}

/**
 * Valores coherentes con los umbrales v1 (docs/datos/umbrales-estado.v1.json):
 * consumo actual elevado desde +20 % y crítico desde +40 % sobre la referencia; acumulado
 * con meta elevado desde 80 % y crítico desde 100 % del límite diario (RN-XI-04, RN-XI-07).
 */
interface ScenarioValues {
  kw: number | null;
  refKw: number | null;
  variationPct: number | null;
  state: ConsumptionState;
  todayKwh: number;
  refKwh: number | null;
  goal: boolean;
  todayState: ConsumptionState;
  zones: { tipo: ZoneConsumptionItem['tipo']; nombre: string; share: number; state: ConsumptionState }[];
  unread: number;
}

const BASE_ZONES = [
  { tipo: 'bano', nombre: 'Baño' },
  { tipo: 'cocina', nombre: 'Cocina' },
  { tipo: 'dormitorio', nombre: 'Dormitorio' },
  { tipo: 'oficina', nombre: 'Oficina' },
  { tipo: 'sala', nombre: 'Sala' },
] as const;

function zonesWith(
  shares: [number, number, number, number, number],
  states: [ConsumptionState, ConsumptionState, ConsumptionState, ConsumptionState, ConsumptionState],
): ScenarioValues['zones'] {
  return BASE_ZONES.map((zone, i) => ({ ...zone, share: shares[i], state: states[i] }));
}

const SCENARIO_VALUES: Record<Exclude<DashboardMockScenario, 'sin_permiso' | 'error'>, ScenarioValues> = {
  normal: {
    kw: 0.62, refKw: 0.6, variationPct: 2, state: 'normal',
    todayKwh: 6.2, refKwh: 11, goal: true, todayState: 'normal',
    zones: zonesWith([8, 34, 21, 15, 22], ['normal', 'normal', 'normal', 'normal', 'normal']),
    unread: 0,
  },
  elevado: {
    kw: 0.78, refKw: 0.6, variationPct: 18, state: 'elevado',
    todayKwh: 9.4, refKwh: 11, goal: true, todayState: 'elevado',
    zones: zonesWith([7, 46, 17, 12, 18], ['normal', 'elevado', 'normal', 'normal', 'normal']),
    unread: 2,
  },
  critico: {
    kw: 0.95, refKw: 0.6, variationPct: 41, state: 'critico',
    todayKwh: 11.8, refKwh: 11, goal: true, todayState: 'critico',
    zones: zonesWith([6, 52, 14, 9, 19], ['normal', 'critico', 'normal', 'normal', 'elevado']),
    unread: 5,
  },
  // Sección 7.3 «Sin datos»: falta la lectura de la última hora (null, nunca cero).
  sin_datos: {
    kw: null, refKw: 0.6, variationPct: null, state: 'sin_datos',
    todayKwh: 5.1, refKwh: 11, goal: true, todayState: 'sin_datos',
    zones: [],
    unread: 0,
  },
  // Sección 7.3 «Sin tarifa» y «Sin meta»: sin COP y barra contra el promedio.
  sin_tarifa: {
    kw: 0.58, refKw: 0.6, variationPct: -4, state: 'normal',
    todayKwh: 6.4, refKwh: 6.8, goal: false, todayState: 'normal',
    zones: zonesWith([9, 31, 22, 16, 22], ['normal', 'normal', 'normal', 'normal', 'normal']),
    unread: 1,
  },
};

function mockHousehold(hogarId: string, scenario: DashboardMockScenario): Household {
  return {
    id: hogarId,
    nombre: 'Casa Pérez',
    tipo_vivienda: 'apartamento',
    rol_usuario: scenario === 'sin_permiso' ? 'miembro' : 'administrador',
    permisos: {
      ver_consumo_actual: scenario !== 'sin_permiso',
      ver_historial: true,
      recibir_alertas: scenario !== 'sin_permiso',
      modificar_metas: scenario !== 'sin_permiso',
    },
  };
}

function mockUser(hogarId: string): CurrentUser {
  return {
    id: MOCK_ID(0xa1),
    correo: 'ana.perez@correo.com',
    nombre_completo: 'Ana Pérez',
    telefono: null,
    avatar_url: null,
    preferencias: { notif_consumo: true, notif_consejos: true, base_comparacion: 'meta' },
    membresia: { membresia_id: MOCK_ID(0xb1), hogar_id: hogarId, rol: 'administrador' },
  };
}

function mockCurrent(values: ScenarioValues, withTariff: boolean): CurrentConsumption {
  const refType = values.goal ? 'meta' : 'promedio';
  return {
    hora: mockLastFullHour(),
    tarifa_vigente: withTariff,
    actual: {
      potencia_kw: values.kw,
      costo_cop: cop(values.kw, withTariff),
      variacion_hora_anterior_pct: values.variationPct,
      referencia_tipo: refType,
      referencia_kw: values.refKw,
      estado: values.state,
      mensaje_codigo: `consumo_actual.${values.state}`,
    },
    acumulado_hoy: {
      energia_kwh: values.todayKwh,
      costo_cop: cop(values.todayKwh, withTariff),
      referencia_tipo: refType,
      referencia_kwh: values.refKwh,
      muestra_limite: values.goal,
      estado: values.todayState,
      mensaje_codigo: `acumulado.${refType}.${values.todayState}`,
    },
  };
}

function mockZones(values: ScenarioValues, withTariff: boolean): ZonesConsumption {
  const zonas: ZoneConsumptionItem[] = values.zones.map((zone, i) => {
    const kw = values.kw === null ? null : Math.round(values.kw * zone.share) / 100;
    return {
      zona_id: MOCK_ID(0x100 + i),
      tipo: zone.tipo,
      nombre: zone.nombre,
      potencia_kw: kw,
      costo_cop: cop(kw, withTariff),
      participacion_pct: values.kw === null ? null : zone.share,
      estado_participacion: zone.state,
    };
  });
  return { hora: mockLastFullHour(), tarifa_vigente: withTariff, total_kw: values.kw, zonas };
}

function forbidden(): ApiRequestError {
  return new ApiRequestError('http', 403, { codigo: 'SIN_PERMISO_VER_CONSUMO', mensaje: 'sin_permiso' });
}

/** Fuente de ejemplo con la misma firma que la real. */
export function createMockSource(scenario: DashboardMockScenario): DashboardSource {
  const withTariff = scenario !== 'sin_tarifa';
  const values = scenario === 'sin_permiso' || scenario === 'error' ? null : SCENARIO_VALUES[scenario];

  async function respond<T>(build: () => T): Promise<T> {
    await sleep(MOCK_LATENCY_MS);
    if (scenario === 'error') throw new ApiRequestError('network', null, null);
    return build();
  }

  return {
    getCurrentUser: () => respond(() => mockUser(MOCK_HOGAR_ID ?? MOCK_ID(1))),
    getHousehold: (hogarId) => respond(() => mockHousehold(hogarId, scenario)),
    getCurrentConsumption: () =>
      respond(() => {
        if (!values) throw forbidden();
        return mockCurrent(values, withTariff);
      }),
    getZonesConsumption: () =>
      respond(() => {
        if (!values) throw forbidden();
        return mockZones(values, withTariff);
      }),
    countUnreadAlerts: () => respond(() => ({ cantidad: values?.unread ?? 0 })),
  };
}

function isMockScenario(value: string | undefined): value is DashboardMockScenario {
  return (DASHBOARD_MOCK_SCENARIOS as readonly string[]).includes(value ?? '');
}

/** Escenario de EXPO_PUBLIC_DASHBOARD_MOCK; `normal` si falta o no es válido. */
const ENV_SCENARIO: DashboardMockScenario = isMockScenario(process.env.EXPO_PUBLIC_DASHBOARD_MOCK)
  ? process.env.EXPO_PUBLIC_DASHBOARD_MOCK
  : 'normal';

/* ─────────────────────────────── El hook ────────────────────────────────── */

function firstNameOf(fullName: string): string {
  return fullName.trim().split(/\s+/)[0] ?? '';
}

function isForbidden(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 403;
}

/** Carga todo el Panel con la fuente dada. Exportada para las pruebas. */
export async function loadDashboard(source: DashboardSource, hogarId: string): Promise<DashboardData> {
  const [user, household] = await Promise.all([source.getCurrentUser(), source.getHousehold(hogarId)]);
  const canReceiveAlerts = household.permisos.recibir_alertas;
  let canSeeConsumption = household.permisos.ver_consumo_actual;

  const unreadPromise: Promise<number | null> = canReceiveAlerts
    ? source.countUnreadAlerts(hogarId).then((r) => r.cantidad, () => null)
    : Promise.resolve(null);

  let current: CurrentConsumption | null = null;
  let zones: ZonesConsumption | null = null;
  if (canSeeConsumption) {
    try {
      [current, zones] = await Promise.all([
        source.getCurrentConsumption(hogarId),
        source.getZonesConsumption(hogarId),
      ]);
    } catch (error) {
      // El backend comprueba el permiso en cada llamada: un 403 es el estado sin permiso.
      if (!isForbidden(error)) throw error;
      canSeeConsumption = false;
      current = null;
      zones = null;
    }
  }

  return {
    household,
    firstName: firstNameOf(user.nombre_completo),
    canSeeConsumption,
    canReceiveAlerts,
    current,
    zones,
    unreadAlerts: await unreadPromise,
  };
}

export interface UseDashboardDataOptions {
  /** Solo desarrollo: fuerza un escenario del modo de ejemplo. */
  mockScenario?: DashboardMockScenario;
  /** Para pruebas: fuente inyectada (tiene prioridad sobre el modo de ejemplo). */
  source?: DashboardSource;
}

/** Estado del Panel (cargando, error y datos) con reintento y recarga. */
export function useDashboardData(hogarId: string | null, options: UseDashboardDataOptions = {}) {
  const useMocks = USE_MOCKS || (__DEV__ && options.mockScenario !== undefined);
  const scenario = options.mockScenario ?? ENV_SCENARIO;
  const source = options.source ?? (useMocks ? createMockSource(scenario) : apiSource);
  const effectiveHogarId = hogarId ?? (useMocks ? (MOCK_HOGAR_ID ?? MOCK_ID(1)) : null);

  // La fuente más reciente se guarda fuera del render; el efecto de carga la lee al correr.
  const sourceRef = useRef(source);
  useEffect(() => {
    sourceRef.current = source;
  });

  const [state, setState] = useState<DashboardState>({ status: 'loading' });
  const [refreshing, setRefreshing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const silentRef = useRef(false);

  useEffect(() => {
    // Sin hogar no hay nada que pedir; el error se deriva abajo, sin setState aquí.
    if (!effectiveHogarId) return;
    let cancelled = false;
    if (!silentRef.current) setState({ status: 'loading' });
    loadDashboard(sourceRef.current, effectiveHogarId)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', errorKey: toErrorTextKey(error) });
      })
      .finally(() => {
        if (!cancelled) {
          silentRef.current = false;
          setRefreshing(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveHogarId, scenario, attempt]);

  /** Vuelve a cargar mostrando el esqueleto (tras un error). */
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  /** Recarga sin esqueleto (deslizar hacia abajo). */
  const refresh = useCallback(() => {
    silentRef.current = true;
    setRefreshing(true);
    setAttempt((n) => n + 1);
  }, []);

  const visibleState: DashboardState = effectiveHogarId
    ? state
    : { status: 'error', errorKey: 'error.app.no_encontrado' };

  return { state: visibleState, retry, refresh, refreshing };
}
