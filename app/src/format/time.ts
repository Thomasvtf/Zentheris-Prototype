/**
 * Tiempo relativo para listas (RN-XIV-04: «Hace 10 min», «Ayer»), con las claves
 * formato.tiempo.* del catálogo.
 *
 * Cortes decididos por Nicolás el 11/11/2026 (la regla no los define), en hora de
 * America/Bogota (UTC−5, sin horario de verano):
 * - menos de 1 min → «Ahora»; menos de 60 min → «Hace n min»;
 * - mismo día → «Hace n h»; día anterior → «Ayer»;
 * - de 2 a 6 días → «Hace n días»; 7 días o más → «dd/mm».
 * No se usa «Hoy» (formato.tiempo.dias.zero). Una fecha futura se muestra como «Ahora».
 */
import { plural, t } from '@/texts';

const BOGOTA_OFFSET_MS = -5 * 60 * 60 * 1000;
const MINUTE = 60 * 1000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** Número de día calendario en Bogotá (días desde 1970-01-01, hora local). */
function bogotaDayNumber(date: Date): number {
  return Math.floor((date.getTime() + BOGOTA_OFFSET_MS) / DAY);
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

/** Texto relativo de `fecha` respecto de `ahora` (por defecto, el momento actual). */
export function relativeTime(fecha: Date, ahora: Date = new Date()): string {
  const diff = ahora.getTime() - fecha.getTime();
  if (diff < MINUTE) return t('formato.tiempo.ahora');
  if (diff < HOUR) return t('formato.tiempo.min', { n: Math.floor(diff / MINUTE) });
  const days = bogotaDayNumber(ahora) - bogotaDayNumber(fecha);
  if (days === 0) return t('formato.tiempo.hora', { n: Math.floor(diff / HOUR) });
  if (days === 1) return t('formato.tiempo.ayer');
  if (days < 7) return plural('formato.tiempo.dias', days);
  const local = new Date(fecha.getTime() + BOGOTA_OFFSET_MS);
  return t('formato.tiempo.fecha', { dd: pad2(local.getUTCDate()), mm: pad2(local.getUTCMonth() + 1) });
}
