/** Operaciones de la etiqueta «Metas y tarifa» del contrato 0.2.5 (una función por operationId). */
import { apiRequest } from './client';
import type { Schemas, SuccessBody } from './client';

/**
 * Meta activa del hogar y promedio de referencia (RN-V-03, RN-XVI-04).
 * @operationId obtenerMeta
 */
export function getGoal(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}/meta', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/meta', 'get'>>('GET', `/hogares/${hogarId}/meta`);
}

/**
 * Guardar una meta nueva (RN-V-03, RN-XVI-04, RN-XVII-04).
 * @operationId crearMeta
 */
export function createGoal(hogarId: string, body: Schemas['MetaCrear']): Promise<SuccessBody<'/hogares/{hogar_id}/metas', 'post'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/metas', 'post'>>('POST', `/hogares/${hogarId}/metas`, { body });
}

/**
 * Tarifa vigente del hogar (RN-XVI-05).
 * @operationId obtenerTarifa
 */
export function getTariff(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}/tarifa', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/tarifa', 'get'>>('GET', `/hogares/${hogarId}/tarifa`);
}

/**
 * Guardar una tarifa nueva (RN-V-01, RN-V-02, RN-XVI-05).
 * @operationId crearTarifa
 */
export function createTariff(hogarId: string, body: Schemas['TarifaCrear']): Promise<SuccessBody<'/hogares/{hogar_id}/tarifas', 'post'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/tarifas', 'post'>>('POST', `/hogares/${hogarId}/tarifas`, { body });
}
