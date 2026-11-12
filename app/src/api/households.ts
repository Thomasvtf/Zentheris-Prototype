/** Operaciones de la etiqueta «Hogares» del contrato 0.2.5 (una función por operationId). */
import { apiRequest } from './client';
import type { SuccessBody } from './client';

/**
 * Hogar de la membresía activa del usuario (RN-II-01).
 * @operationId obtenerHogarActual
 */
export function getCurrentHousehold(): Promise<SuccessBody<'/hogares/actual', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/actual', 'get'>>('GET', '/hogares/actual');
}

/**
 * Datos del hogar, rol del usuario y permisos (RN-II-03).
 * @operationId obtenerHogar
 */
export function getHousehold(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}', 'get'>>('GET', `/hogares/${hogarId}`);
}

/**
 * Zonas del hogar, en orden alfabético por nombre (RN-III-01, RN-XII-03).
 * @operationId listarZonas
 */
export function listZones(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}/zonas', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/zonas', 'get'>>('GET', `/hogares/${hogarId}/zonas`);
}
