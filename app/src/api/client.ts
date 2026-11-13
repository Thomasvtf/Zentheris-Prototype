/**
 * Cliente HTTP de la API de Zentheris (contrato docs/api/zentheris-api-v0.2.5.yaml).
 *
 * - Base: EXPO_PUBLIC_API_URL + /api/v1 (servers del contrato).
 * - Token: el JWT de Supabase Auth, que entrega state/session.ts con setAccessTokenProvider.
 * - Tiempos de espera: 15 s; 60 s en POST /onboarding (app/CLAUDE.md).
 * - Los errores llegan como ApiRequestError; errors.ts los convierte en claves del catálogo.
 */
import type { components, paths } from './schema';

export type Schemas = components['schemas'];
export type ApiError = Schemas['Error'];

type JsonContent<R> = R extends { content: { 'application/json': infer T } } ? T : never;
/** Cuerpo de la respuesta 2xx de una operación del contrato. */
export type SuccessBody<
  P extends keyof paths,
  M extends 'get' | 'post' | 'put' | 'patch' | 'delete',
> = paths[P][M] extends { responses: infer R }
  ? JsonContent<R[Extract<keyof R, 200 | 201>]>
  : never;

export const DEFAULT_TIMEOUT_MS = 15_000;
export const ONBOARDING_TIMEOUT_MS = 60_000;
const API_PREFIX = '/api/v1';

/** Error de una petición: HTTP con cuerpo del contrato, tiempo agotado o sin conexión. */
export class ApiRequestError extends Error {
  constructor(
    readonly kind: 'http' | 'timeout' | 'network',
    readonly status: number | null,
    readonly body: ApiError | null,
  ) {
    super(body?.mensaje ?? kind);
    this.name = 'ApiRequestError';
  }
}

let accessTokenProvider: () => Promise<string | null> = async () => null;

/** state/session.ts registra aquí cómo obtener el token de la sesión de Supabase. */
export function setAccessTokenProvider(provider: () => Promise<string | null>): void {
  accessTokenProvider = provider;
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
type Query = Record<string, string | number | boolean | null | undefined>;

export interface RequestOptions {
  body?: unknown;
  query?: Query;
  timeoutMs?: number;
  auth?: boolean;
}

function buildUrl(path: string, query?: Query): string {
  const base = (process.env.EXPO_PUBLIC_API_URL ?? '').replace(/\/$/, '');
  const params = Object.entries(query ?? {})
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&');
  return `${base}${API_PREFIX}${path}${params ? `?${params}` : ''}`;
}

function isApiError(value: unknown): value is ApiError {
  return value !== null && typeof value === 'object' && 'codigo' in value && 'mensaje' in value;
}

/** Hace una petición a la API y devuelve el cuerpo JSON (o `undefined` si es 204). */
export async function apiRequest<T>(
  method: Method,
  path: string,
  { body, query, timeoutMs = DEFAULT_TIMEOUT_MS, auth = true }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth) {
    const token = await accessTokenProvider();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (error) {
    const aborted = error instanceof Error && error.name === 'AbortError';
    throw new ApiRequestError(aborted ? 'timeout' : 'network', null, null);
  } finally {
    clearTimeout(timer);
  }
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiRequestError('http', response.status, isApiError(data) ? data : null);
  }
  return data as T;
}
