/** Operaciones de la etiqueta «Sistema» del contrato 0.2.5 (una función por operationId). */
import { apiRequest } from './client';
import type { SuccessBody } from './client';

/**
 * Estado del servicio.
 * @operationId obtenerSalud
 */
export function getHealth(): Promise<SuccessBody<'/salud', 'get'>> {
  return apiRequest<SuccessBody<'/salud', 'get'>>('GET', '/salud', { auth: false });
}
