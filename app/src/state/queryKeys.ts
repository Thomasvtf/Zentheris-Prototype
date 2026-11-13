/**
 * Claves de React Query: la primera parte es el operationId del contrato y después van sus
 * parámetros. Así cada consulta se rastrea hasta su fila de docs/MAPA-DE-INTEGRACION.md.
 */

/** Operaciones GET del contrato 0.2.5 (las que se consultan con React Query). */
export type QueryOperationId =
  | 'obtenerSalud'
  | 'obtenerUsuarioActual'
  | 'obtenerPreferencias'
  | 'obtenerHogarActual'
  | 'obtenerHogar'
  | 'listarZonas'
  | 'listarMiembros'
  | 'listarInvitacionesRecibidas'
  | 'obtenerConsumoActual'
  | 'obtenerConsumoZonas'
  | 'obtenerConsumoZona'
  | 'obtenerHistorial'
  | 'obtenerFuentesDatos'
  | 'obtenerMeta'
  | 'obtenerTarifa'
  | 'listarAlertas'
  | 'contarAlertasNoLeidas'
  | 'listarConsejos';

/** Clave de una consulta: `queryKey('obtenerHogar', hogarId)`. */
export function queryKey<P extends readonly unknown[]>(operationId: QueryOperationId, ...params: P) {
  return [operationId, ...params] as const;
}
