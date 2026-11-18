/** Operaciones de la etiqueta «Alertas y consejos» del contrato 0.2.5 (una función por operationId). */
import { apiRequest } from './client';
import type { Schemas, SuccessBody } from './client';
import type { paths } from './schema';

/**
 * Alertas entregadas al usuario (RN-XIV-01, RN-XIV-04, RN-XIV-05).
 * @operationId listarAlertas
 */
export function listAlerts(hogarId: string, query?: NonNullable<paths['/hogares/{hogar_id}/alertas']['get']['parameters']['query']>): Promise<SuccessBody<'/hogares/{hogar_id}/alertas', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/alertas', 'get'>>('GET', `/hogares/${hogarId}/alertas`, { query });
}

/**
 * Indicador de la campana (RN-XII-02).
 * @operationId contarAlertasNoLeidas
 */
export function countUnreadAlerts(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}/alertas/no-leidas', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/alertas/no-leidas', 'get'>>('GET', `/hogares/${hogarId}/alertas/no-leidas`);
}

/**
 * Marcar como leídas las alertas visibles al entrar (RN-XIV-03, RN-VI-05).
 * @operationId marcarAlertasLeidas
 */
export function markAlertsRead(hogarId: string, body: Schemas['AlertasMarcar']): Promise<SuccessBody<'/hogares/{hogar_id}/alertas/marcar-leidas', 'post'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/alertas/marcar-leidas', 'post'>>('POST', `/hogares/${hogarId}/alertas/marcar-leidas`, { body });
}

/**
 * Consejos visibles para el usuario (RN-VI-03, RN-XV-02, RN-XV-03, RN-XV-04, RN-XV-05).
 * @operationId listarConsejos
 */
export function listTips(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}/consejos', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/consejos', 'get'>>('GET', `/hogares/${hogarId}/consejos`);
}

/**
 * Marcar o desmarcar un consejo (RN-XV-03, RN-VI-05).
 * @operationId actualizarEstadoConsejo
 */
export function updateTipStatus(hogarId: string, consejoId: string, body: Schemas['ConsejoEstadoActualizar']): Promise<SuccessBody<'/hogares/{hogar_id}/consejos/{consejo_id}/estado', 'put'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/consejos/{consejo_id}/estado', 'put'>>('PUT', `/hogares/${hogarId}/consejos/${consejoId}/estado`, { body });
}
