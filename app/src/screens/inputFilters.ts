/**
 * Filtros de entrada de los formularios de Configuración: cada campo acepta solo los
 * caracteres de su tipo mientras se escribe (la validación final y los mensajes siguen en
 * cada pantalla y en el backend).
 *
 * - Teléfono: celular colombiano opcional, 10 dígitos con o sin +57 (RN-IX-01, EditarPerfil).
 * - Correo: sin espacios ni caracteres que no existen en un correo, una sola «@» (RN-IX-06).
 * - Nombre: letras (con tildes y ñ), espacios, apóstrofo, punto y guion (RN-IX-07).
 * - Valor por kWh: dígitos con coma decimal es-CO y hasta 2 decimales (RN-XVI-05, RN-XII-08).
 * - Cargo fijo: solo dígitos, agrupados con punto de miles es-CO, sin decimales (COP).
 */
import { formatNumber } from '@/format';

/** Máximos de cada campo (límites de entrada, no reglas de negocio). */
export const INPUT_LIMITS = {
  nameLength: 80,
  emailLength: 254,
  phoneDigits: 12, // 57 + 10 dígitos
  priceIntDigits: 6,
  priceDecimals: 2,
  fixedChargeDigits: 9,
} as const;

/** Nombre completo: quita dígitos y símbolos y junta los espacios repetidos. */
export function sanitizeName(value: string): string {
  return value
    .replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]/g, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/^\s+/, '')
    .slice(0, INPUT_LIMITS.nameLength);
}

/** Teléfono: solo dígitos y, si va, un «+» al inicio. */
export function sanitizePhone(value: string): string {
  const plus = value.startsWith('+') ? '+' : '';
  return plus + value.replace(/\D/g, '').slice(0, INPUT_LIMITS.phoneDigits);
}

/** Correo: sin espacios ni símbolos ajenos a un correo; una sola «@». */
export function sanitizeEmail(value: string): string {
  const clean = value.replace(/[^A-Za-z0-9._%+@-]/g, '');
  const at = clean.indexOf('@');
  const joined = at === -1 ? clean : clean.slice(0, at + 1) + clean.slice(at + 1).replace(/@/g, '');
  return joined.slice(0, INPUT_LIMITS.emailLength);
}

/** Valor por kWh: dígitos y una coma decimal (el punto del teclado cuenta como coma). */
export function sanitizeDecimal(value: string): string {
  const text = value.replace(/\./g, ',').replace(/[^\d,]/g, '');
  const [int, ...rest] = text.split(',');
  const intPart = int.slice(0, INPUT_LIMITS.priceIntDigits);
  if (rest.length === 0) return intPart;
  return `${intPart},${rest.join('').slice(0, INPUT_LIMITS.priceDecimals)}`;
}

/** Cargo fijo en COP: solo dígitos, mostrados con punto de miles («12.000»). */
export function sanitizeCop(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, INPUT_LIMITS.fixedChargeDigits);
  return digits === '' ? '' : formatNumber(Number(digits));
}
