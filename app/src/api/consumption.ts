/** Operaciones de la etiqueta «Consumo» del contrato 0.2.5 (una función por operationId). */
import { apiRequest } from './client';
import type { SuccessBody } from './client';
import type { paths } from './schema';

/**
 * Cards del Panel principal (RN-XI-01, RN-XI-03, RN-XI-04, RN-XI-08).
 * @operationId obtenerConsumoActual
 */
export function getCurrentConsumption(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}/consumo/actual', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/consumo/actual', 'get'>>('GET', `/hogares/${hogarId}/consumo/actual`);
}

/**
 * Participación y estado de cada zona en la última hora completa (RN-XI-05, RN-XII-05, RN-XII-06).
 * @operationId obtenerConsumoZonas
 */
export function getZonesConsumption(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}/consumo/zonas', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/consumo/zonas', 'get'>>('GET', `/hogares/${hogarId}/consumo/zonas`);
}

/**
 * Zona individual (RN-XI-05, RN-XI-06, RN-XII-07).
 * @operationId obtenerConsumoZona
 */
export function getZoneConsumption(hogarId: string, zonaId: string): Promise<SuccessBody<'/hogares/{hogar_id}/consumo/zonas/{zona_id}', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/consumo/zonas/{zona_id}', 'get'>>('GET', `/hogares/${hogarId}/consumo/zonas/${zonaId}`);
}

/**
 * Historial por periodo (RN-XIII-01 a RN-XIII-06).
 * @operationId obtenerHistorial
 */
export function getHistory(hogarId: string, query: NonNullable<paths['/hogares/{hogar_id}/historial']['get']['parameters']['query']>): Promise<SuccessBody<'/hogares/{hogar_id}/historial', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/historial', 'get'>>('GET', `/hogares/${hogarId}/historial`, { query });
}

/**
 * Fuente principal y sensores, solo lectura (RN-III-03, RN-XVI-06).
 * @operationId obtenerFuentesDatos
 */
export function getDataSources(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}/fuentes-datos', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/fuentes-datos', 'get'>>('GET', `/hogares/${hogarId}/fuentes-datos`);
}
