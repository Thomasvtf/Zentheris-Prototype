/**
 * Hook de datos del Historial (reglas v4.9 §6.5 y §7.3; RN-XIII-01 a RN-XIII-07).
 * Fila 30 de docs/MAPA-DE-INTEGRACION.md:
 *   GET /hogares/{hogar_id}/historial?periodo=dia|semana|mes[&zona_id=uuid]
 *   operationId obtenerHistorial → getHistory (src/api/consumption.ts)
 * El contrato no tiene paginación ni rangos libres (RN-XIII-02): solo `periodo` y `zona_id`.
 *
 * Fuente de datos: `HistorySource` es la única puerta. `apiSource` llama a getHistory;
 * `createMockSource` devuelve respuestas con la forma exacta del esquema `Historial` del
 * contrato 0.2.5 y aplica en local los mismos filtros (periodo y zona). Para pasar a la API
 * real no se toca la pantalla: basta con apagar el modo de ejemplo.
 *
 * Modo de ejemplo (solo `__DEV__`):
 *   - Se enciende con EXPO_PUBLIC_USE_MOCKS=true en app/.env (bandera ya existente).
 *   - Escenario con EXPO_PUBLIC_HISTORIAL_MOCK=<escenario> (por defecto `mixto`) o con la
 *     opción `mockScenario`:
 *       mixto (Día normal · Semana elevado · Mes crítico, como Figma A5.1–A5.3)
 *       normal · elevado (alerta) · critico · sin_anterior · sin_tarifa · faltan_horas
 *       sin_picos · vacio · sin_permiso · error
 *
 * Lista de zonas del filtro: sale de `participacion_zonas` de la respuesta General (trae
 * `zona_id` y `nombre`), que se guarda mientras se filtra por una zona. Así no se usa un
 * endpoint que la fila 30 del MAPA no lista.
 *
 * TODO(pendiente: hogarId): aún no existe el estado de sesión/hogar (fila 12). Mientras
 * tanto el hook recibe `hogarId`; sin él (y fuera del modo de ejemplo) devuelve
 * `error.app.no_encontrado`.
 * TODO(pendiente: React Query): la raíz aún no monta QueryClientProvider. Al montarlo, la
 * consulta pasa a useQuery(queryKey('obtenerHistorial', hogarId, periodo, zonaId)).
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiRequestError } from '@/api/client';
import type { SuccessBody } from '@/api/client';
import { getHistory } from '@/api/consumption';
import { MOCK_HOGAR_ID, USE_MOCKS } from '@/api/devMocks';
import { toErrorTextKey } from '@/api/errors';
import type { paths } from '@/api/schema';

/* ─────────────────────────── Tipos del contrato ─────────────────────────── */

export type History = SuccessBody<'/hogares/{hogar_id}/historial', 'get'>;
export type HistoryQuery = NonNullable<paths['/hogares/{hogar_id}/historial']['get']['parameters']['query']>;
export type Period = History['periodo'];
export type SeriesPoint = History['serie'][number];
export type ZoneShare = NonNullable<History['participacion_zonas']>[number];
export type HistoryPeak = NonNullable<History['ultimo_pico']>;
export type ConsumptionState = History['comparacion']['estado'];

/** Zona del filtro (de `participacion_zonas` del filtro General). */
export interface ZoneOption {
  zona_id: string;
  nombre: string;
}

/** Puerta única de datos: misma firma que getHistory de src/api/. */
export interface HistorySource {
  getHistory: (hogarId: string, query: HistoryQuery) => Promise<History>;
}

export type HistoryState =
  | { status: 'loading' }
  | { status: 'error'; errorKey: string }
  | { status: 'forbidden' }
  | { status: 'ready'; data: History };

/** `true` si el periodo no tiene ninguna lectura (estado vacío). */
export function isEmptyHistory(data: History): boolean {
  return data.serie.every((p) => p.energia_kwh === null);
}

/** `true` si falta la lectura de la última hora del Día (§7.3, aviso «Falta la lectura»). */
export function isMissingLastHour(data: History): boolean {
  const last = data.serie[data.serie.length - 1];
  return data.periodo === 'dia' && last !== undefined && last.energia_kwh === null && !isEmptyHistory(data);
}

/* ───────────────────────────── Fuente real ──────────────────────────────── */

export const apiSource: HistorySource = { getHistory };

/* ─────────────────────────── Fuente de ejemplo ──────────────────────────── */

export const HISTORIAL_MOCK_SCENARIOS = [
  'mixto',
  'normal',
  'elevado',
  'critico',
  'sin_anterior',
  'sin_tarifa',
  'faltan_horas',
  'sin_picos',
  'vacio',
  'sin_permiso',
  'error',
] as const;
export type HistorialMockScenario = (typeof HISTORIAL_MOCK_SCENARIOS)[number];

type Severity = 'normal' | 'elevado' | 'critico';

const MOCK_LATENCY_MS = 500;
/** Precio y cargo fijo de ejemplo (los mismos de la tarifa de src/api/devMocks.ts). */
const MOCK_PRICE_COP_KWH = 892;
const MOCK_FIXED_CHARGE_COP = 12000;
const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;
const BOGOTA_OFFSET_MS = -5 * HOUR_MS;

const MOCK_ID = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;

/** Seis zonas (más de 4, para ver «Otras zonas» en el anillo, RN-XIII-04); suman 100 %. */
const MOCK_ZONES: { zona_id: string; nombre: string; share: number }[] = [
  { zona_id: MOCK_ID(0x201), nombre: 'Baño', share: 5 },
  { zona_id: MOCK_ID(0x202), nombre: 'Cocina', share: 34 },
  { zona_id: MOCK_ID(0x203), nombre: 'Dormitorio', share: 10 },
  { zona_id: MOCK_ID(0x204), nombre: 'Lavandería', share: 4 },
  { zona_id: MOCK_ID(0x205), nombre: 'Oficina', share: 28 },
  { zona_id: MOCK_ID(0x206), nombre: 'Sala', share: 19 },
];

/** Perfil horario de un día (kW promedio, General). */
const HOURLY_KW = [
  0.1, 0.08, 0.07, 0.06, 0.08, 0.11, 0.17, 0.24, 0.3, 0.36, 0.4, 0.48, 0.45, 0.42, 0.37, 0.36,
  0.4, 0.43, 0.38, 0.31, 0.27, 0.22, 0.17, 0.12,
];
/** Variación diaria (factor sobre el total de un día típico). */
const DAILY_FACTOR = [1, 1.1, 0.96, 1.2, 1.12, 1.32, 0.86, 1.04, 0.92, 1.15, 1.25, 0.98, 1.08, 1.18];
const TYPICAL_DAY_KWH = HOURLY_KW.reduce((a, b) => a + b, 0);

/** Exceso del último pico y variación de la comparación por estado (umbrales v1). */
const BY_SEVERITY: Record<Severity, { peakDay: number; peakPeriod: number; variation: number; code: 'similar' | 'mayor' | 'muy_mayor' }> = {
  // Día usa los umbrales del consumo actual (+20 % / +40 %); Semana y Mes, los del día
  // completo (+15 % / +30 %) (RN-XIII-03, DC-31). Comparación: similar < +10 %, mayor
  // < +25 %, muy mayor ≥ +25 % (RN-XIII-01, DC-29).
  normal: { peakDay: 14, peakPeriod: 12, variation: 3, code: 'similar' },
  elevado: { peakDay: 28, peakPeriod: 22, variation: 18, code: 'mayor' },
  critico: { peakDay: 52, peakPeriod: 41, variation: 32, code: 'muy_mayor' },
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function round(value: number, decimals: number): number {
  const f = 10 ** decimals;
  return Math.round(value * f) / f;
}

/** Inicio del día de Bogotá que contiene `t` (en milisegundos UTC). */
function bogotaMidnight(t: number): number {
  const local = t + BOGOTA_OFFSET_MS;
  return local - (local % DAY_MS) - BOGOTA_OFFSET_MS;
}

/** Límites del periodo según RN-XIII-01 (Bogotá) hasta la última hora completa. */
function periodBounds(periodo: Period, now: number): { start: number; end: number } {
  const end = Math.floor(now / HOUR_MS) * HOUR_MS;
  const today = bogotaMidnight(end - 1);
  if (periodo === 'dia') return { start: today, end };
  const local = new Date(today + BOGOTA_OFFSET_MS);
  if (periodo === 'semana') {
    const sinceMonday = (local.getUTCDay() + 6) % 7;
    return { start: today - sinceMonday * DAY_MS, end };
  }
  return { start: today - (local.getUTCDate() - 1) * DAY_MS, end };
}

function severityFor(scenario: HistorialMockScenario, periodo: Period): Severity {
  if (scenario === 'elevado' || scenario === 'critico') return scenario;
  if (scenario === 'mixto') return periodo === 'dia' ? 'normal' : periodo === 'semana' ? 'elevado' : 'critico';
  return 'normal';
}

function cost(kwh: number | null, withTariff: boolean): number | null {
  return withTariff && kwh !== null ? Math.round(kwh * MOCK_PRICE_COP_KWH) : null;
}

/** Respuesta del contrato `Historial` para un periodo, una zona y un escenario. */
export function buildMockHistory(
  scenario: HistorialMockScenario,
  query: HistoryQuery,
  now: number = Date.now(),
): History {
  const { periodo } = query;
  const zone = query.zona_id ? MOCK_ZONES.find((z) => z.zona_id === query.zona_id) : undefined;
  const factor = zone ? zone.share / 100 : 1;
  const withTariff = scenario !== 'sin_tarifa';
  const severity = severityFor(scenario, periodo);
  const params = BY_SEVERITY[severity];
  const { start, end } = periodBounds(periodo, now);
  const hourly = periodo === 'dia';
  const step = hourly ? HOUR_MS : DAY_MS;

  // Serie: una hora en Día y un día en Semana y Mes (el último día, parcial hasta `end`).
  const serie: SeriesPoint[] = [];
  for (let t = start; t < end; t += step) {
    const pointEnd = Math.min(t + step, end);
    const i = serie.length;
    let kwh: number | null;
    if (hourly) {
      kwh = HOURLY_KW[new Date(t + BOGOTA_OFFSET_MS).getUTCHours()] * factor;
    } else {
      const hours = (pointEnd - t) / HOUR_MS;
      kwh = TYPICAL_DAY_KWH * DAILY_FACTOR[i % DAILY_FACTOR.length] * (hours / 24) * factor;
    }
    if (scenario === 'vacio') kwh = null;
    if (scenario === 'faltan_horas' && hourly && pointEnd === end) kwh = null;
    const energy = kwh === null ? null : round(kwh, 2);
    serie.push({
      inicio: new Date(t).toISOString(),
      fin: new Date(pointEnd).toISOString(),
      energia_kwh: energy,
      costo_cop: cost(energy, withTariff),
      es_pico_maximo: false,
    });
  }

  // Pico más alto del periodo (lo marca el backend; la app solo lo dibuja).
  const valued = serie.filter((p) => p.energia_kwh !== null);
  const highest = valued.reduce<SeriesPoint | null>(
    (best, p) => (best === null || (p.energia_kwh ?? 0) > (best.energia_kwh ?? 0) ? p : best),
    null,
  );
  const hasPeaks = scenario !== 'sin_picos' && scenario !== 'vacio' && highest !== null;
  if (hasPeaks && highest) highest.es_pico_maximo = true;

  const total = round(valued.reduce((sum, p) => sum + (p.energia_kwh ?? 0), 0), 1);
  const excess = hourly ? params.peakDay : params.peakPeriod;
  const lastPeak = hasPeaks && highest ? highest : null;
  const ultimo_pico: History['ultimo_pico'] = lastPeak
    ? {
        inicio: lastPeak.inicio,
        fin: lastPeak.fin,
        energia_kwh: lastPeak.energia_kwh ?? 0,
        promedio_historico_kwh: round((lastPeak.energia_kwh ?? 0) / (1 + excess / 100), 2),
        exceso_pct: excess,
        estado: severity,
      }
    : null;

  const noPrevious = scenario === 'sin_anterior' || scenario === 'vacio';
  const previous = noPrevious ? null : round(total / (1 + params.variation / 100), 1);
  const comparisonState: ConsumptionState = noPrevious ? 'sin_datos' : severity;
  const comparisonCode = noPrevious ? 'sin_anterior' : params.code;

  const fixed = periodo === 'mes' ? MOCK_FIXED_CHARGE_COP : 0;
  const elapsed = (end - start) / HOUR_MS;
  const periodHours = hourly ? 24 : periodo === 'semana' ? 7 * 24 : 30 * 24;
  const projectedKwh = elapsed > 0 ? (total * periodHours) / elapsed : total;
  const costNow = cost(total, withTariff);

  return {
    periodo,
    zona_id: zone ? zone.zona_id : null,
    inicio: new Date(start).toISOString(),
    fin: new Date(end).toISOString(),
    granularidad: hourly ? 'hora' : 'dia',
    tarifa_vigente: withTariff,
    total_kwh: total,
    serie,
    participacion_zonas: zone
      ? null
      : MOCK_ZONES.map((z) => ({
          zona_id: z.zona_id,
          nombre: z.nombre,
          energia_kwh: round((total * z.share) / 100, 1),
          participacion_pct: z.share,
        })),
    ultimo_pico,
    comparacion: {
      actual_kwh: total,
      anterior_kwh: previous,
      variacion_pct: noPrevious ? null : params.variation,
      estado: comparisonState,
      mensaje_codigo: `historial_comparacion.${comparisonCode}`,
    },
    costo: {
      costo_cop: costNow === null ? null : costNow + fixed,
      proyeccion_cierre_cop: costNow === null ? null : Math.round(projectedKwh * MOCK_PRICE_COP_KWH) + fixed,
      incluye_cargo_fijo: periodo === 'mes',
      estado: comparisonState,
      mensaje_codigo: `historial_comparacion.${comparisonCode}`,
    },
  };
}

/** Fuente de ejemplo con la misma firma que la real. */
export function createMockSource(scenario: HistorialMockScenario): HistorySource {
  return {
    async getHistory(_hogarId, query) {
      await sleep(MOCK_LATENCY_MS);
      if (scenario === 'error') throw new ApiRequestError('network', null, null);
      if (scenario === 'sin_permiso') {
        throw new ApiRequestError('http', 403, { codigo: 'SIN_PERMISO_VER_HISTORIAL', mensaje: 'sin_permiso' });
      }
      return buildMockHistory(scenario, query);
    },
  };
}

function isMockScenario(value: string | undefined): value is HistorialMockScenario {
  return (HISTORIAL_MOCK_SCENARIOS as readonly string[]).includes(value ?? '');
}

/** Escenario de EXPO_PUBLIC_HISTORIAL_MOCK; `mixto` si falta o no es válido. */
const ENV_SCENARIO: HistorialMockScenario = isMockScenario(process.env.EXPO_PUBLIC_HISTORIAL_MOCK)
  ? process.env.EXPO_PUBLIC_HISTORIAL_MOCK
  : 'mixto';

/* ─────────────────────────────── El hook ────────────────────────────────── */

function isForbidden(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 403;
}

export interface UseHistorialDataOptions {
  /** Solo desarrollo: fuerza un escenario del modo de ejemplo. */
  mockScenario?: HistorialMockScenario;
  /** Para pruebas: fuente inyectada (tiene prioridad sobre el modo de ejemplo). */
  source?: HistorySource;
}

/**
 * Historial del periodo y la zona elegidos (cargando, error, sin permiso y datos), con
 * reintento, recarga y la lista de zonas del filtro.
 */
export function useHistorialData(
  hogarId: string | null,
  periodo: Period,
  zonaId: string | null,
  options: UseHistorialDataOptions = {},
) {
  const useMocks = USE_MOCKS || (__DEV__ && options.mockScenario !== undefined);
  const scenario = options.mockScenario ?? ENV_SCENARIO;
  const source = options.source ?? (useMocks ? createMockSource(scenario) : apiSource);
  const effectiveHogarId = hogarId ?? (useMocks ? (MOCK_HOGAR_ID ?? MOCK_ID(1)) : null);

  // La fuente más reciente se guarda fuera del render; el efecto de carga la lee al correr.
  const sourceRef = useRef(source);
  useEffect(() => {
    sourceRef.current = source;
  });

  const [state, setState] = useState<HistoryState>({ status: 'loading' });
  const [zones, setZones] = useState<ZoneOption[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const silentRef = useRef(false);

  useEffect(() => {
    // Sin hogar no hay nada que pedir; el error se deriva abajo, sin setState aquí.
    if (!effectiveHogarId) return;
    let cancelled = false;
    if (!silentRef.current) setState({ status: 'loading' });
    const query: HistoryQuery = zonaId ? { periodo, zona_id: zonaId } : { periodo };
    sourceRef.current
      .getHistory(effectiveHogarId, query)
      .then((data) => {
        if (cancelled) return;
        if (data.participacion_zonas) {
          setZones(data.participacion_zonas.map(({ zona_id, nombre }) => ({ zona_id, nombre })));
        }
        setState({ status: 'ready', data });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        // El backend comprueba el permiso en cada llamada (SIN_PERMISO_VER_HISTORIAL).
        setState(isForbidden(error) ? { status: 'forbidden' } : { status: 'error', errorKey: toErrorTextKey(error) });
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
  }, [effectiveHogarId, periodo, zonaId, scenario, attempt]);

  /** Vuelve a cargar mostrando el esqueleto (tras un error). */
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  /** Recarga sin esqueleto (deslizar hacia abajo). */
  const refresh = useCallback(() => {
    silentRef.current = true;
    setRefreshing(true);
    setAttempt((n) => n + 1);
  }, []);

  const visibleState: HistoryState = effectiveHogarId
    ? state
    : { status: 'error', errorKey: 'error.app.no_encontrado' };

  return { state: visibleState, zones, retry, refresh, refreshing };
}
