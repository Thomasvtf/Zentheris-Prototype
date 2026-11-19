/**
 * Hook de datos de Consejos (reglas v4.9 §6.8 y RN-XV-01 a RN-XV-07; RN-VI-05).
 * Filas 39 y 40 de docs/MAPA-DE-INTEGRACION.md:
 *   GET /hogares/{hogar_id}/consejos                       operationId listarConsejos → listTips
 *   PUT /hogares/{hogar_id}/consejos/{consejo_id}/estado   operationId actualizarEstadoConsejo → updateTipStatus
 * El contrato no tiene filtros ni paginación: el backend devuelve los pendientes vigentes
 * (7 días desde `creado_en`, RN-XV-05) por prioridad y los completados de menos de 7 días
 * (RN-XV-03). Tampoco trae ahorro en kWh o COP ni «descartar»: la app no los inventa.
 *
 * Fuente de datos: `TipsSource` es la única puerta. `apiSource` llama a src/api/alertsTips.ts;
 * `createMockSource` responde con la forma exacta del esquema `Consejo` del contrato 0.2.5 y
 * guarda en memoria lo que marcas, así que marcar y desmarcar funciona sin backend. Para pasar
 * a la API real no se toca la pantalla: basta con apagar el modo de ejemplo.
 *
 * Modo de ejemplo (solo `__DEV__`):
 *   - Se enciende con EXPO_PUBLIC_USE_MOCKS=true en app/.env (bandera ya existente).
 *   - Escenario con EXPO_PUBLIC_CONSEJOS_MOCK=<escenario> (por defecto `mixto`) o con la
 *     opción `mockScenario`:
 *       mixto          pendientes de las tres prioridades + completados (la lista completa)
 *       sin_pendientes solo completados → card «¡Todo bajo control!» con ellos debajo
 *       vacio          sin ningún consejo → solo la card «¡Todo bajo control!»
 *       error          falla la carga (sin conexión) → aviso con Reintentar
 *       error_marcar   la carga funciona pero marcar falla → se revierte y avisa
 *
 * TODO(pendiente: hogarId): aún no existe el estado de sesión/hogar (fila 12). Mientras
 * tanto el hook recibe `hogarId`; sin él (y fuera del modo de ejemplo) devuelve
 * `error.app.no_encontrado`.
 * TODO(pendiente: React Query): la raíz aún no monta QueryClientProvider. Al montarlo, la
 * lista pasa a useQuery(queryKey('listarConsejos', hogarId)) y el marcado a useMutation con
 * actualización optimista; la pantalla no cambia.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';

import { listTips, updateTipStatus } from '@/api/alertsTips';
import { ApiRequestError } from '@/api/client';
import type { Schemas, SuccessBody } from '@/api/client';
import { MOCK_HOGAR_ID, USE_MOCKS } from '@/api/devMocks';
import { toErrorTextKey } from '@/api/errors';

/* ─────────────────────────── Tipos del contrato ─────────────────────────── */

export type Tip = Schemas['Consejo'];
export type TipStatus = Tip['estado'];
export type TipPriority = Tip['prioridad'];
export type TipStatusBody = Schemas['ConsejoEstadoActualizar'];
export type TipsResponse = SuccessBody<'/hogares/{hogar_id}/consejos', 'get'>;

/** Puerta única de datos: mismas firmas que listTips y updateTipStatus de src/api/. */
export interface TipsSource {
  listTips: (hogarId: string) => Promise<TipsResponse>;
  updateTipStatus: (hogarId: string, consejoId: string, body: TipStatusBody) => Promise<Tip>;
}

export type TipsState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'ready'; tips: Tip[] };

/* ───────────────────────────── Orden y vacío ────────────────────────────── */

const PRIORITY_RANK: Record<TipPriority, number> = { alta: 0, media: 1, baja: 2 };

/**
 * Orden de la lista (RN-XV-02, RN-XV-04): pendientes de alta a baja prioridad (y, a igual
 * prioridad, el más reciente primero) y, al final, los completados (el último completado antes).
 */
export function sortTips(tips: Tip[]): Tip[] {
  return [...tips].sort((a, b) => {
    const aDone = a.estado === 'completada';
    const bDone = b.estado === 'completada';
    if (aDone !== bDone) return aDone ? 1 : -1;
    if (aDone) return (b.completada_en ?? '').localeCompare(a.completada_en ?? '');
    return PRIORITY_RANK[a.prioridad] - PRIORITY_RANK[b.prioridad] || b.creado_en.localeCompare(a.creado_en);
  });
}

/** `true` si hay al menos un consejo pendiente; si no, la pantalla muestra «¡Todo bajo control!» (RN-XV-02). */
export function hasPendingTips(tips: Tip[]): boolean {
  return tips.some((tip) => tip.estado === 'pendiente');
}

/* ───────────────────────────── Fuente real ──────────────────────────────── */

export const apiSource: TipsSource = { listTips, updateTipStatus };

/* ─────────────────────────── Fuente de ejemplo ──────────────────────────── */

export const CONSEJOS_MOCK_SCENARIOS = ['mixto', 'sin_pendientes', 'vacio', 'error', 'error_marcar'] as const;
export type ConsejosMockScenario = (typeof CONSEJOS_MOCK_SCENARIOS)[number];

const MOCK_LATENCY_MS = 500;
const HOUR_MS = 60 * 60 * 1000;
const MOCK_ID = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Zonas de ejemplo (las mismas del Historial). */
const ZONES = {
  cocina: { zona_id: MOCK_ID(0x202), zona_nombre: 'Cocina' },
  dormitorio: { zona_id: MOCK_ID(0x203), zona_nombre: 'Dormitorio' },
  lavanderia: { zona_id: MOCK_ID(0x204), zona_nombre: 'Lavandería' },
  oficina: { zona_id: MOCK_ID(0x205), zona_nombre: 'Oficina' },
  sala: { zona_id: MOCK_ID(0x206), zona_nombre: 'Sala' },
  bano: { zona_id: MOCK_ID(0x201), zona_nombre: 'Baño' },
} as const;

type MockZone = keyof typeof ZONES | null;

interface MockSeed {
  n: number;
  zona: MockZone;
  prioridad: TipPriority;
  titulo: string;
  descripcion: string;
  /** Horas desde la creación (la vigencia es de 7 días, RN-XV-05). */
  haceHoras: number;
  /** Horas desde que esta persona lo completó (se oculta a los 7 días, RN-XV-03); `null` = pendiente. */
  completadoHaceHoras: number | null;
}

/**
 * Consejos de ejemplo según el catálogo inicial (RN-XV-07): zona crítica → prioridad alta,
 * zona elevada → media, cierre de mes sobre la referencia → baja y general. Son datos como
 * los escribe el backend (RN-XI-09), no textos de la interfaz.
 */
const MOCK_SEEDS: MockSeed[] = [
  {
    n: 1,
    zona: 'cocina',
    prioridad: 'alta',
    titulo: 'Reduce el uso del horno eléctrico',
    descripcion: 'La cocina está muy por encima de su promedio. Descongela los alimentos antes de cocinar y usa tapas en las ollas.',
    haceHoras: 5,
    completadoHaceHoras: null,
  },
  {
    n: 2,
    zona: 'dormitorio',
    prioridad: 'alta',
    titulo: 'Apaga el aire acondicionado al salir',
    descripcion: 'Antes de salir, comprueba que el equipo quede apagado o programa su apagado automático.',
    haceHoras: 20,
    completadoHaceHoras: null,
  },
  {
    n: 3,
    zona: 'lavanderia',
    prioridad: 'media',
    titulo: 'Lava con la carga completa y agua fría',
    descripcion: 'Espera a juntar la ropa para una carga completa y usa el ciclo de agua fría cuando sea posible.',
    haceHoras: 30,
    completadoHaceHoras: null,
  },
  {
    n: 4,
    zona: 'oficina',
    prioridad: 'media',
    titulo: 'Activa el modo de ahorro del computador',
    descripcion: 'Configura la suspensión automática del equipo y la pantalla tras unos minutos sin uso.',
    haceHoras: 52,
    completadoHaceHoras: null,
  },
  {
    n: 5,
    zona: 'sala',
    prioridad: 'media',
    titulo: 'Desconecta el televisor y el decodificador',
    descripcion: 'En espera siguen consumiendo. Usa una regleta con interruptor para apagarlos de una vez.',
    haceHoras: 70,
    completadoHaceHoras: null,
  },
  {
    n: 6,
    zona: null,
    prioridad: 'baja',
    titulo: 'Tu mes cerró por encima de la referencia',
    descripcion: 'Elige un consejo de las zonas con más consumo y aplícalo esta semana para volver a tu referencia.',
    haceHoras: 96,
    completadoHaceHoras: null,
  },
  {
    n: 7,
    zona: 'bano',
    prioridad: 'media',
    titulo: 'Cambia las bombillas del baño por LED',
    descripcion: 'Las bombillas LED gastan hasta una quinta parte y duran mucho más.',
    haceHoras: 120,
    completadoHaceHoras: 48,
  },
  {
    n: 8,
    zona: 'cocina',
    prioridad: 'media',
    titulo: 'Revisa el sello de la nevera',
    descripcion: 'Si la puerta no cierra bien, el motor trabaja más. Comprueba que el sello esté limpio y ajustado.',
    haceHoras: 140,
    completadoHaceHoras: 100,
  },
];

function seedToTip(seed: MockSeed, now: number): Tip {
  const zone = seed.zona ? ZONES[seed.zona] : { zona_id: null, zona_nombre: null };
  const done = seed.completadoHaceHoras !== null;
  return {
    id: MOCK_ID(0x700 + seed.n),
    categoria: seed.zona ? 'zona' : 'general',
    prioridad: seed.prioridad,
    titulo: seed.titulo,
    descripcion: seed.descripcion,
    zona_id: zone.zona_id,
    zona_nombre: zone.zona_nombre,
    estado: done ? 'completada' : 'pendiente',
    completada_en: done ? new Date(now - (seed.completadoHaceHoras ?? 0) * HOUR_MS).toISOString() : null,
    creado_en: new Date(now - seed.haceHoras * HOUR_MS).toISOString(),
  };
}

/** Consejos de ejemplo de un escenario, ya ordenados como los entrega el backend. */
export function buildMockTips(scenario: ConsejosMockScenario, now: number = Date.now()): Tip[] {
  if (scenario === 'vacio') return [];
  const tips = MOCK_SEEDS.map((seed) => seedToTip(seed, now));
  if (scenario === 'sin_pendientes') {
    // Todo completado hace poco (dentro de los 7 días en que aún se ven, RN-XV-03).
    return sortTips(
      tips.map((tip, i) =>
        tip.estado === 'completada'
          ? tip
          : { ...tip, estado: 'completada' as const, completada_en: new Date(now - (i + 1) * 3 * HOUR_MS).toISOString() },
      ),
    );
  }
  return sortTips(tips);
}

/**
 * Fuente de ejemplo con la misma firma que la real. Guarda los consejos en memoria: marcar o
 * desmarcar cambia `estado` y `completada_en` como lo haría el backend (`completada` registra
 * la fecha; `pendiente` la deja vacía) y se ve al volver a consultar.
 */
export function createMockSource(scenario: ConsejosMockScenario, now: number = Date.now()): TipsSource {
  let tips = buildMockTips(scenario, now);
  return {
    async listTips() {
      await sleep(MOCK_LATENCY_MS);
      if (scenario === 'error') throw new ApiRequestError('network', null, null);
      return { consejos: tips };
    },
    async updateTipStatus(_hogarId, consejoId, body) {
      await sleep(MOCK_LATENCY_MS / 2);
      if (scenario === 'error_marcar') throw new ApiRequestError('network', null, null);
      const current = tips.find((tip) => tip.id === consejoId);
      // 404 si la persona no tiene fila en `consejos_usuario` para ese consejo (RN-XV-06).
      if (!current) throw new ApiRequestError('http', 404, null);
      const updated: Tip = {
        ...current,
        estado: body.estado,
        completada_en: body.estado === 'completada' ? new Date().toISOString() : null,
      };
      tips = tips.map((tip) => (tip.id === consejoId ? updated : tip));
      return updated;
    },
  };
}

function isMockScenario(value: string | undefined): value is ConsejosMockScenario {
  return (CONSEJOS_MOCK_SCENARIOS as readonly string[]).includes(value ?? '');
}

/** Escenario de EXPO_PUBLIC_CONSEJOS_MOCK; `mixto` si falta o no es válido. */
const ENV_SCENARIO: ConsejosMockScenario = isMockScenario(process.env.EXPO_PUBLIC_CONSEJOS_MOCK)
  ? process.env.EXPO_PUBLIC_CONSEJOS_MOCK
  : 'mixto';

/* ─────────────────────────────── El hook ────────────────────────────────── */

export interface UseConsejosDataOptions {
  /** Solo desarrollo: fuerza un escenario del modo de ejemplo. */
  mockScenario?: ConsejosMockScenario;
  /** Para pruebas: fuente inyectada (tiene prioridad sobre el modo de ejemplo). */
  source?: TipsSource;
}

/**
 * Consejos de la persona (cargando, error y datos), con reintento, recarga y marcado
 * individual como completado (RN-XV-03, RN-VI-05). Marcar es optimista: la casilla cambia al
 * instante y, si el backend falla, vuelve a su estado y se avisa con `actionErrorKey`.
 */
export function useConsejosData(hogarId: string | null, options: UseConsejosDataOptions = {}) {
  const useMocks = USE_MOCKS || (__DEV__ && options.mockScenario !== undefined);
  const scenario = options.mockScenario ?? ENV_SCENARIO;
  const injected = options.source;
  // Una sola fuente por escenario: la de ejemplo guarda en memoria lo que marcas.
  const source = useMemo<TipsSource>(
    () => injected ?? (useMocks ? createMockSource(scenario) : apiSource),
    [injected, useMocks, scenario],
  );
  const effectiveHogarId = hogarId ?? (useMocks ? (MOCK_HOGAR_ID ?? MOCK_ID(1)) : null);

  const [state, setState] = useState<TipsState>({ status: 'loading' });
  const [refreshing, setRefreshing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [savingIds, setSavingIds] = useState<string[]>([]);
  const [actionErrorKey, setActionErrorKey] = useState<string | null>(null);

  useEffect(() => {
    if (!effectiveHogarId) return;
    let cancelled = false;
    source
      .listTips(effectiveHogarId)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', tips: sortTips(data.consejos) });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', errorKey: toErrorTextKey(error) });
      })
      .finally(() => {
        if (!cancelled) setRefreshing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveHogarId, source, attempt]);

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

  /** Marca el consejo como completado o lo vuelve a pendiente (solo para esta persona). */
  const toggle = useCallback(
    (consejoId: string) => {
      if (!effectiveHogarId || state.status !== 'ready' || savingIds.includes(consejoId)) return;
      const current = state.tips.find((tip) => tip.id === consejoId);
      if (!current) return;
      const next: TipStatus = current.estado === 'pendiente' ? 'completada' : 'pendiente';
      const replace = (tip: Tip) =>
        setState((prev) => (prev.status === 'ready' ? { status: 'ready', tips: sortTips(prev.tips.map((x) => (x.id === tip.id ? tip : x))) } : prev));

      setActionErrorKey(null);
      setSavingIds((ids) => [...ids, consejoId]);
      replace({ ...current, estado: next, completada_en: next === 'completada' ? new Date().toISOString() : null });
      source
        .updateTipStatus(effectiveHogarId, consejoId, { estado: next })
        .then(replace)
        .catch((error: unknown) => {
          replace(current);
          setActionErrorKey(toErrorTextKey(error));
        })
        .finally(() => setSavingIds((ids) => ids.filter((id) => id !== consejoId)));
    },
    [effectiveHogarId, savingIds, source, state],
  );

  // Sin hogar (y fuera del modo de ejemplo) no hay qué consultar.
  const visibleState: TipsState = effectiveHogarId ? state : { status: 'error', errorKey: 'error.app.no_encontrado' };

  return { state: visibleState, retry, refresh, refreshing, toggle, savingIds, actionErrorKey, dismissActionError };
}
