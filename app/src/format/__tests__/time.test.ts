/** Tiempo relativo (RN-XIV-04) con los cortes decididos el 11/11/2026 (ver time.ts). */
import { describe, expect, it } from '@jest/globals';
import { relativeTime } from '../time';

// 11/11/2026 15:00 en Bogotá = 20:00 UTC.
const NOW = new Date('2026-11-11T20:00:00Z');
const ago = (ms: number) => new Date(NOW.getTime() - ms);
const MIN = 60 * 1000;
const HOUR = 60 * MIN;

describe('relativeTime', () => {
  it('menos de 1 min → «Ahora» (también una fecha futura)', () => {
    expect(relativeTime(ago(30 * 1000), NOW)).toBe('Ahora');
    expect(relativeTime(ago(-5 * MIN), NOW)).toBe('Ahora');
  });
  it('menos de 60 min → «Hace n min» (RN-XIV-04: «Hace 10 min»)', () => {
    expect(relativeTime(ago(10 * MIN), NOW)).toBe('Hace 10 min');
  });
  it('mismo día en Bogotá → «Hace n h»', () => {
    expect(relativeTime(ago(3 * HOUR), NOW)).toBe('Hace 3 h');
  });
  it('día anterior en Bogotá → «Ayer», aunque hayan pasado menos de 24 h', () => {
    expect(relativeTime(ago(16 * HOUR), NOW)).toBe('Ayer');
  });
  it('de 2 a 6 días → «Hace n días»', () => {
    expect(relativeTime(ago(2 * 24 * HOUR), NOW)).toBe('Hace 2 días');
    expect(relativeTime(ago(6 * 24 * HOUR), NOW)).toBe('Hace 6 días');
  });
  it('7 días o más → «dd/mm» en hora de Bogotá', () => {
    expect(relativeTime(new Date('2026-11-01T03:00:00Z'), NOW)).toBe('31/10');
  });
});
