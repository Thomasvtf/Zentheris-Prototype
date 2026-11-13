/** Operaciones de la etiqueta «Usuario» del contrato 0.2.5 (una función por operationId). */
import { apiRequest } from './client';
import type { Schemas, SuccessBody } from './client';

/**
 * Ficha, preferencias y membresía del usuario autenticado.
 * @operationId obtenerUsuarioActual
 */
export function getCurrentUser(): Promise<SuccessBody<'/usuarios/me', 'get'>> {
  return apiRequest<SuccessBody<'/usuarios/me', 'get'>>('GET', '/usuarios/me');
}

/**
 * Crear la ficha y las preferencias por defecto (RN-IX-01).
 * @operationId crearFichaUsuario
 */
export function createUserProfile(body: Schemas['UsuarioCrear']): Promise<SuccessBody<'/usuarios/me', 'post'>> {
  return apiRequest<SuccessBody<'/usuarios/me', 'post'>>('POST', '/usuarios/me', { body });
}

/**
 * Editar nombre completo y teléfono (RN-IX-07).
 * @operationId actualizarPerfil
 */
export function updateProfile(body: Schemas['UsuarioActualizar']): Promise<SuccessBody<'/usuarios/me', 'patch'>> {
  return apiRequest<SuccessBody<'/usuarios/me', 'patch'>>('PATCH', '/usuarios/me', { body });
}

/**
 * Eliminar la cuenta de forma irreversible (RN-IX-09).
 * @operationId eliminarCuenta
 */
export function deleteAccount(): Promise<void> {
  return apiRequest<void>('DELETE', '/usuarios/me');
}

/**
 * Registrar la foto de perfil (RN-I-02).
 * @operationId guardarAvatar
 */
export function saveAvatar(body: Schemas['AvatarGuardar']): Promise<SuccessBody<'/usuarios/me/avatar', 'put'>> {
  return apiRequest<SuccessBody<'/usuarios/me/avatar', 'put'>>('PUT', '/usuarios/me/avatar', { body });
}

/**
 * Eliminar la foto de perfil (RN-I-02).
 * @operationId eliminarAvatar
 */
export function deleteAvatar(): Promise<void> {
  return apiRequest<void>('DELETE', '/usuarios/me/avatar');
}

/**
 * Interruptores de notificación y base de comparación.
 * @operationId obtenerPreferencias
 */
export function getPreferences(): Promise<SuccessBody<'/usuarios/me/preferencias', 'get'>> {
  return apiRequest<SuccessBody<'/usuarios/me/preferencias', 'get'>>('GET', '/usuarios/me/preferencias');
}

/**
 * Cambiar interruptores y base de comparación (RN-VI-04, RN-VII-01, RN-XVI-02, RN-XVI-03).
 * @operationId actualizarPreferencias
 */
export function updatePreferences(body: Schemas['PreferenciasActualizar']): Promise<SuccessBody<'/usuarios/me/preferencias', 'patch'>> {
  return apiRequest<SuccessBody<'/usuarios/me/preferencias', 'patch'>>('PATCH', '/usuarios/me/preferencias', { body });
}

/**
 * Verificar la contraseña actual (RN-IX-05).
 * @operationId verificarContrasenaActual
 */
export function verifyCurrentPassword(body: Schemas['ContrasenaVerificar']): Promise<void> {
  return apiRequest<void>('POST', '/usuarios/me/contrasena/verificar', { body });
}

/**
 * Cambiar la contraseña (RN-IX-02, RN-IX-05).
 * @operationId cambiarContrasena
 */
export function changePassword(body: Schemas['ContrasenaCambiar']): Promise<void> {
  return apiRequest<void>('POST', '/usuarios/me/contrasena', { body });
}
