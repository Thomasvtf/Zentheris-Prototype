/**
 * Convierte un error de la API en la clave base del catálogo (app/CLAUDE.md: los errores se
 * leen como `error.<codigo en minúsculas>`; los de la app, como `error.app.*`). Quien muestra
 * el error agrega `.titulo` o `.cuerpo` (y `.invitar` o `.aceptar` en LIMITE_MIEMBROS).
 */
import { ApiRequestError } from './client';

export function toErrorTextKey(error: unknown): string {
  if (!(error instanceof ApiRequestError)) return 'error.app.desconocido';
  if (error.kind === 'timeout') return 'error.app.tiempo_agotado';
  if (error.kind === 'network') return 'error.app.sin_conexion';
  if (error.body?.codigo) return `error.${error.body.codigo.toLowerCase()}`;
  if (error.status === 401) return 'error.app.sesion_vencida';
  if (error.status === 404) return 'error.app.no_encontrado';
  return 'error.app.error_servidor';
}
