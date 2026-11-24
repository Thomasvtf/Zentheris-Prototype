/**
 * Hora de America/Bogota (UTC−5, sin horario de verano) para las etiquetas de la app.
 * La API devuelve instantes ISO en UTC; aquí se pasan a la hora local de Colombia.
 *
 * Truco: `toBogota` devuelve un `Date` desplazado −5 h, de modo que sus campos UTC
 * (`getUTCHours`, `getUTCDate`…) son la hora local de Bogotá en cualquier dispositivo.
 */

export const BOGOTA_OFFSET_MS = -5 * 60 * 60 * 1000;

/** Instante (Date o ISO) con los campos UTC en hora de Bogotá; `shiftMs` lo corre antes. */
export function toBogota(value: Date | string, shiftMs = 0): Date {
  const ms = typeof value === 'string' ? new Date(value).getTime() : value.getTime();
  return new Date(ms + BOGOTA_OFFSET_MS + shiftMs);
}

/** Dos dígitos: 7 → «07». */
export function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

/** Hora del día en Bogotá (0–23). */
export function bogotaHour(value: Date | string): number {
  return toBogota(value).getUTCHours();
}

/** «14:00» (inicio de la hora en Bogotá). */
export function hourLabel(value: Date | string): string {
  return `${pad2(bogotaHour(value))}:00`;
}

/** «14:00–15:00» para un intervalo horario del contrato (`inicio`, `fin`). */
export function intervalLabel(hora: { inicio: string; fin: string }): string {
  return `${hourLabel(hora.inicio)}–${hourLabel(hora.fin)}`;
}

/** Mes en curso en Bogotá: año, mes «01»–«12» y cuántos días tiene. */
export function bogotaMonth(now: Date = new Date()): { anio: number; mm: string; dias: number } {
  const local = toBogota(now);
  const anio = local.getUTCFullYear();
  const mes = local.getUTCMonth() + 1;
  return { anio, mm: pad2(mes), dias: new Date(Date.UTC(anio, mes, 0)).getUTCDate() };
}
