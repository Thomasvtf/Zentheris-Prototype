/** Hora de Bogotá (UTC−5) para las etiquetas de hora, intervalo y mes. */
import { describe, expect, it } from '@jest/globals';

import { bogotaHour, bogotaMonth, hourLabel, intervalLabel, pad2, toBogota } from '../bogota';

describe('hora de Bogotá', () => {
  it('pasa de UTC a la hora local (−5 h)', () => {
    expect(bogotaHour('2026-11-11T20:00:00Z')).toBe(15);
    expect(bogotaHour(new Date('2026-11-11T03:00:00Z'))).toBe(22);
  });

  it('cruza la medianoche hacia el día anterior', () => {
    const local = toBogota('2026-11-12T02:30:00Z');
    expect(local.getUTCDate()).toBe(11);
    expect(local.getUTCHours()).toBe(21);
  });

  it('formatea la hora y el intervalo «14:00–15:00»', () => {
    expect(hourLabel('2026-11-11T19:00:00Z')).toBe('14:00');
    expect(hourLabel('2026-11-11T05:00:00Z')).toBe('00:00');
    expect(intervalLabel({ inicio: '2026-11-11T19:00:00Z', fin: '2026-11-11T20:00:00Z' })).toBe('14:00–15:00');
  });

  it('pad2 completa con cero', () => {
    expect(pad2(7)).toBe('07');
    expect(pad2(12)).toBe('12');
  });

  it('mes en curso: año, mes y días (incluye el cambio de mes por la hora local)', () => {
    expect(bogotaMonth(new Date('2026-11-24T15:00:00Z'))).toEqual({ anio: 2026, mm: '11', dias: 30 });
    // 1 de diciembre 03:00 UTC = 30 de noviembre 22:00 en Bogotá.
    expect(bogotaMonth(new Date('2026-12-01T03:00:00Z'))).toEqual({ anio: 2026, mm: '11', dias: 30 });
    expect(bogotaMonth(new Date('2028-02-10T12:00:00Z'))).toEqual({ anio: 2028, mm: '02', dias: 29 });
  });
});
