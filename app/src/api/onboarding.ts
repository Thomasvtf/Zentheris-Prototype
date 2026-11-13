/** Operaciones de la etiqueta «Onboarding» del contrato 0.2.5 (una función por operationId). */
import { apiRequest, ONBOARDING_TIMEOUT_MS } from './client';
import type { Schemas, SuccessBody } from './client';

/**
 * Crear el hogar y generar el backfill (RN-X-02, RN-X-03, RN-X-04, RN-IV-01, RN-IV-07).
 * @operationId crearHogarOnboarding
 */
export function createHouseholdOnboarding(body: Schemas['OnboardingCrear']): Promise<SuccessBody<'/onboarding', 'post'>> {
  return apiRequest<SuccessBody<'/onboarding', 'post'>>('POST', '/onboarding', { body, timeoutMs: ONBOARDING_TIMEOUT_MS });
}
