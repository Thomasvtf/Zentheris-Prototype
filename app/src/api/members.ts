/** Operaciones de la etiqueta «Miembros e invitaciones» del contrato 0.2.5 (una función por operationId). */
import { apiRequest } from './client';
import type { Schemas, SuccessBody } from './client';

/**
 * Miembros activos, invitaciones pendientes y permisos (RN-XVI-07).
 * @operationId listarMiembros
 */
export function listMembers(hogarId: string): Promise<SuccessBody<'/hogares/{hogar_id}/miembros', 'get'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/miembros', 'get'>>('GET', `/hogares/${hogarId}/miembros`);
}

/**
 * Cambiar los permisos generales del hogar (RN-II-03, RN-X-08).
 * @operationId actualizarPermisos
 */
export function updatePermissions(hogarId: string, body: Schemas['PermisosActualizar']): Promise<SuccessBody<'/hogares/{hogar_id}/permisos', 'patch'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/permisos', 'patch'>>('PATCH', `/hogares/${hogarId}/permisos`, { body });
}

/**
 * Expulsar a un miembro (RN-II-04, RN-X-07).
 * @operationId expulsarMiembro
 */
export function removeMember(hogarId: string, membresiaId: string): Promise<void> {
  return apiRequest<void>('DELETE', `/hogares/${hogarId}/miembros/${membresiaId}`);
}

/**
 * Transferir el rol de administrador a otro miembro activo (RN-II-04, RN-X-07).
 * @operationId transferirAdministracion
 */
export function transferAdmin(hogarId: string, membresiaId: string): Promise<SuccessBody<'/hogares/{hogar_id}/miembros/{membresia_id}/transferir-administracion', 'post'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/miembros/{membresia_id}/transferir-administracion', 'post'>>('POST', `/hogares/${hogarId}/miembros/${membresiaId}/transferir-administracion`);
}

/**
 * Salir voluntariamente del hogar (RN-II-04, RN-X-07).
 * @operationId salirDelHogar
 */
export function leaveHousehold(hogarId: string): Promise<void> {
  return apiRequest<void>('POST', `/hogares/${hogarId}/salir`);
}

/**
 * Invitar a una persona por correo (RN-X-05).
 * @operationId crearInvitacion
 */
export function createInvitation(hogarId: string, body: Schemas['InvitacionCrear']): Promise<SuccessBody<'/hogares/{hogar_id}/invitaciones', 'post'>> {
  return apiRequest<SuccessBody<'/hogares/{hogar_id}/invitaciones', 'post'>>('POST', `/hogares/${hogarId}/invitaciones`, { body });
}

/**
 * Cancelar una invitación pendiente (RN-X-06).
 * @operationId revocarInvitacion
 */
export function revokeInvitation(hogarId: string, invitacionId: string): Promise<void> {
  return apiRequest<void>('DELETE', `/hogares/${hogarId}/invitaciones/${invitacionId}`);
}

/**
 * Invitaciones pendientes para el correo del usuario (RN-X-01).
 * @operationId listarInvitacionesRecibidas
 */
export function listReceivedInvitations(): Promise<SuccessBody<'/invitaciones/recibidas', 'get'>> {
  return apiRequest<SuccessBody<'/invitaciones/recibidas', 'get'>>('GET', '/invitaciones/recibidas');
}

/**
 * Obtener la invitación a partir del token del enlace (RN-X-05).
 * @operationId resolverTokenInvitacion
 */
export function resolveInvitationToken(body: Schemas['InvitacionToken']): Promise<SuccessBody<'/invitaciones/resolver', 'post'>> {
  return apiRequest<SuccessBody<'/invitaciones/resolver', 'post'>>('POST', '/invitaciones/resolver', { body });
}

/**
 * Aceptar una invitación (RN-X-05, RN-X-06).
 * @operationId aceptarInvitacion
 */
export function acceptInvitation(invitacionId: string): Promise<SuccessBody<'/invitaciones/{invitacion_id}/aceptar', 'post'>> {
  return apiRequest<SuccessBody<'/invitaciones/{invitacion_id}/aceptar', 'post'>>('POST', `/invitaciones/${invitacionId}/aceptar`);
}

/**
 * Rechazar una invitación (RN-X-06).
 * @operationId rechazarInvitacion
 */
export function rejectInvitation(invitacionId: string): Promise<void> {
  return apiRequest<void>('POST', `/invitaciones/${invitacionId}/rechazar`);
}
