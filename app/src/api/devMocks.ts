/**
 * MODO DE DESARROLLO con datos de ejemplo (sin API ni Supabase) para ver las pantallas
 * cargadas. Solo se activa con `__DEV__` y EXPO_PUBLIC_USE_MOCKS=true en app/.env; en
 * producción `USE_MOCKS` es siempre false y este archivo no responde nada.
 *
 * - Los datos viven en memoria: guardar un cambio lo refleja al volver a consultar, y se
 *   pierden al recargar la app.
 * - Las respuestas siguen la forma del contrato (src/api/schema.d.ts); los errores usan los
 *   códigos del contrato para ver también esos estados:
 *     · contraseña actual correcta en el modo de ejemplo: `Mock1234`
 *       (otra cosa → CONTRASENA_ACTUAL_INCORRECTA; nueva igual a la actual →
 *       CONTRASENA_IGUAL_A_ACTUAL).
 *     · tarifa con «vigente desde» no posterior a la vigente → VIGENCIA_NO_POSTERIOR.
 * - Es un dato de ejemplo, no una fuente de verdad: no sustituye a la API real.
 */
import { ApiRequestError } from './client';
import type { Schemas } from './client';

/** true solo en desarrollo y con la bandera encendida. */
export const USE_MOCKS: boolean = __DEV__ && process.env.EXPO_PUBLIC_USE_MOCKS === 'true';

/** `hogarId` de ejemplo para las rutas; null cuando el modo está apagado. */
export const MOCK_HOGAR_ID: string | null = USE_MOCKS ? '00000000-0000-4000-8000-000000000001' : null;

/** Correo de ejemplo de la sesión simulada (Gestionar correo). */
export const MOCK_EMAIL = 'ana.perez@correo.com';

const MOCK_PASSWORD = 'Mock1234';
const LATENCY_MS = 450;

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

let user: Schemas['UsuarioActual'] = {
  id: '00000000-0000-4000-8000-0000000000a1',
  correo: MOCK_EMAIL,
  nombre_completo: 'Ana Pérez',
  telefono: '300 123 4567',
  avatar_url: null,
  preferencias: { notif_consumo: true, notif_consejos: true, base_comparacion: 'meta' },
  membresia: {
    membresia_id: '00000000-0000-4000-8000-0000000000b1',
    hogar_id: MOCK_HOGAR_ID ?? '00000000-0000-4000-8000-000000000001',
    rol: 'administrador',
  },
};

let goal: Schemas['Meta'] | null = {
  id: '00000000-0000-4000-8000-0000000000c1',
  tipo: 'ahorro',
  valor_kwh_mensual: 330,
  estado: 'activa',
  fecha_inicio: '2026-11-01',
  fecha_fin: null,
};

let tariff: Schemas['Tarifa'] | null = {
  id: '00000000-0000-4000-8000-0000000000d1',
  operador: 'Enel Colombia',
  precio_kwh: 892,
  cargo_fijo_mensual: 12000,
  vigente_desde: '2026-09-01',
  vigente_hasta: null,
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function apiError(status: number, codigo: Schemas['Error']['codigo'], mensaje: string): ApiRequestError {
  return new ApiRequestError('http', status, { codigo, mensaje });
}

/** Última hora completa (UTC, redondeada), como la devolvería la API. */
function lastFullHour(): Schemas['IntervaloHora'] {
  const end = new Date();
  end.setUTCMinutes(0, 0, 0);
  const start = new Date(end.getTime() - 60 * 60 * 1000);
  return { inicio: start.toISOString(), fin: end.toISOString() };
}

function dataSources(): Schemas['FuentesDatos'] {
  return {
    valores_ocultos: false,
    hora: lastFullHour(),
    fuente_principal: {
      id: '00000000-0000-4000-8000-0000000000e0',
      nombre: 'Fuente principal Apto 502',
      estado: 'activa',
      potencia_kw: 0.52,
    },
    sensores: [
      { id: '00000000-0000-4000-8000-0000000000e1', nombre: 'Sensor Cocina', zona_id: '00000000-0000-4000-8000-0000000000f1', zona_nombre: 'Cocina', potencia_kw: 0.21, estado: 'activo' },
      { id: '00000000-0000-4000-8000-0000000000e2', nombre: 'Sensor Dormitorio', zona_id: '00000000-0000-4000-8000-0000000000f2', zona_nombre: 'Dormitorio', potencia_kw: 0.19, estado: 'activo' },
      { id: '00000000-0000-4000-8000-0000000000e3', nombre: 'Sensor Oficina', zona_id: '00000000-0000-4000-8000-0000000000f3', zona_nombre: 'Oficina', potencia_kw: null, estado: 'pausado' },
      { id: '00000000-0000-4000-8000-0000000000e4', nombre: 'Sensor Sala', zona_id: '00000000-0000-4000-8000-0000000000f4', zona_nombre: 'Sala', potencia_kw: 0.12, estado: 'activo' },
    ],
  };
}

function goalView(): Schemas['MetaVista'] {
  const now = new Date();
  const daysInMonth = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0)).getUTCDate();
  return {
    meta: goal,
    limite_diario_kwh: goal ? Math.round((goal.valor_kwh_mensual / daysInMonth) * 10) / 10 : null,
    promedio_diario_30d_kwh: 14.2,
    puede_editar: true,
  };
}

/** Responde como lo haría la API; devuelve `undefined` si la ruta no está simulada. */
async function route(method: Method, path: string, body: unknown): Promise<{ handled: boolean; value?: unknown }> {
  const payload = (body ?? {}) as Record<string, unknown>;

  if (method === 'GET' && path === '/usuarios/me') return { handled: true, value: user };

  if (method === 'PATCH' && path === '/usuarios/me') {
    const changes = payload as Schemas['UsuarioActualizar'];
    user = {
      ...user,
      ...(changes.nombre_completo !== undefined ? { nombre_completo: changes.nombre_completo } : {}),
      ...(changes.telefono !== undefined ? { telefono: changes.telefono } : {}),
    };
    return { handled: true, value: user };
  }

  if (method === 'DELETE' && path === '/usuarios/me') return { handled: true, value: undefined };
  if (method === 'DELETE' && path === '/usuarios/me/avatar') {
    user = { ...user, avatar_url: null };
    return { handled: true, value: undefined };
  }

  if (method === 'GET' && path === '/usuarios/me/preferencias') return { handled: true, value: user.preferencias };
  if (method === 'PATCH' && path === '/usuarios/me/preferencias') {
    user = { ...user, preferencias: { ...user.preferencias, ...(payload as Partial<Schemas['Preferencias']>) } };
    return { handled: true, value: user.preferencias };
  }

  if (method === 'POST' && path === '/usuarios/me/contrasena/verificar') {
    if (payload.contrasena_actual !== MOCK_PASSWORD) {
      throw apiError(422, 'CONTRASENA_ACTUAL_INCORRECTA', 'Contraseña actual incorrecta (modo de ejemplo).');
    }
    return { handled: true, value: undefined };
  }
  if (method === 'POST' && path === '/usuarios/me/contrasena') {
    if (payload.contrasena_actual !== MOCK_PASSWORD) {
      throw apiError(422, 'CONTRASENA_ACTUAL_INCORRECTA', 'Contraseña actual incorrecta (modo de ejemplo).');
    }
    if (payload.contrasena_nueva === payload.contrasena_actual) {
      throw apiError(422, 'CONTRASENA_IGUAL_A_ACTUAL', 'La nueva contraseña es igual a la actual.');
    }
    return { handled: true, value: undefined };
  }

  if (method === 'GET' && /^\/hogares\/[^/]+\/fuentes-datos$/.test(path)) return { handled: true, value: dataSources() };
  if (method === 'GET' && /^\/hogares\/[^/]+\/meta$/.test(path)) return { handled: true, value: goalView() };
  if (method === 'POST' && /^\/hogares\/[^/]+\/metas$/.test(path)) {
    const input = payload as Schemas['MetaCrear'];
    const today = new Date().toISOString().slice(0, 10);
    goal = {
      id: `00000000-0000-4000-8000-${String(Date.now()).padStart(12, '0').slice(-12)}`,
      tipo: input.tipo,
      valor_kwh_mensual: input.valor_kwh_mensual,
      estado: 'activa',
      fecha_inicio: today,
      fecha_fin: null,
    };
    return { handled: true, value: goal };
  }

  if (method === 'GET' && /^\/hogares\/[^/]+\/tarifa$/.test(path)) {
    return { handled: true, value: { tarifa: tariff, puede_editar: true } satisfies Schemas['TarifaVista'] };
  }
  if (method === 'POST' && /^\/hogares\/[^/]+\/tarifas$/.test(path)) {
    const input = payload as Schemas['TarifaCrear'];
    if (tariff && `${input.vigente_desde}-01` <= tariff.vigente_desde) {
      throw apiError(422, 'VIGENCIA_NO_POSTERIOR', 'La vigencia debe ser posterior a la tarifa vigente.');
    }
    tariff = {
      id: `00000000-0000-4000-8000-${String(Date.now()).padStart(12, '0').slice(-12)}`,
      operador: input.operador ?? null,
      precio_kwh: input.precio_kwh,
      cargo_fijo_mensual: input.cargo_fijo_mensual ?? null,
      vigente_desde: `${input.vigente_desde}-01`,
      vigente_hasta: null,
    };
    return { handled: true, value: tariff };
  }

  return { handled: false };
}

/**
 * Atiende una petición en modo de ejemplo. Rutas sin simular → error de red (como si la API
 * no respondiera), para que se note qué falta en vez de fallar en silencio.
 */
export async function handleMockRequest<T>(method: Method, path: string, body?: unknown): Promise<T> {
  await sleep(LATENCY_MS);
  const result = await route(method, path, body);
  if (!result.handled) throw new ApiRequestError('network', null, null);
  return result.value as T;
}
