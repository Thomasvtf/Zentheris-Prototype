/** Formato numérico es-CO: RN-XII-08 y decisiones del 11/11/2026 (ver numbers.ts). */
import { describe, expect, it } from '@jest/globals';
import { DECIMALES, formatCOP, formatNumber, formatPercent } from '../numbers';

const NBSP = String.fromCharCode(0x00a0);

describe('RN-XII-08: ejemplos de la regla', () => {
  it('kW con 2 decimales y coma decimal: «2,40 kW»', () => {
    expect(formatNumber(2.4, DECIMALES.kW)).toBe('2,40');
  });
  it('kWh con 1 decimal: «145,3 kWh»', () => {
    expect(formatNumber(145.3, DECIMALES.kWh)).toBe('145,3');
  });
  it('COP sin decimales y punto de miles: «$14.400»', () => {
    expect(formatCOP(14400)).toBe('$14.400');
  });
  it('miles abreviados con «k» minúscula: «$6,5k»', () => {
    expect(formatCOP(6500, { abreviar: true })).toBe('$6,5k');
  });
  it('porcentaje con espacio sin ruptura (U+00A0): «34 %»', () => {
    const text = formatPercent(34);
    expect(text).toBe(`34${NBSP}%`);
    expect(text.charCodeAt(2)).toBe(0x00a0);
    expect(text).not.toContain(' %');
  });
  it('DECIMALES por unidad', () => {
    expect(DECIMALES).toEqual({ kW: 2, kWh: 1, COP: 0, '%': 0 });
  });
});

describe('sin datos y cero (index.d.ts, Metric.md)', () => {
  it('null → «—»', () => {
    expect(formatNumber(null)).toBe('—');
    expect(formatCOP(null)).toBe('—');
    expect(formatPercent(null)).toBe('—');
  });
  it('cero se muestra como cero: «0,00 kW»', () => {
    expect(formatNumber(0, DECIMALES.kW)).toBe('0,00');
  });
});

describe('decisiones del 11/11/2026', () => {
  it('«k» sin «,0» final, como Metric.md: «$28k»', () => {
    expect(formatCOP(28000, { abreviar: true })).toBe('$28k');
    expect(formatCOP(6000, { abreviar: true })).toBe('$6k');
  });
  it('millones siguen con «k»: «$1.250k»', () => {
    expect(formatCOP(1250000, { abreviar: true })).toBe('$1.250k');
  });
  it('por debajo de 1.000 no se abrevia', () => {
    expect(formatCOP(950, { abreviar: true })).toBe('$950');
  });
  it('negativos con guion ASCII', () => {
    expect(formatPercent(-12)).toBe(`-12${NBSP}%`);
    expect(formatNumber(-1234.5, 1)).toBe('-1.234,5');
    expect(formatCOP(-6500, { abreviar: true })).toBe('-$6,5k');
  });
  it('redondeo de la mitad alejándose de cero, sin error de coma flotante', () => {
    expect(formatNumber(2.345, 2)).toBe('2,35');
    expect(formatNumber(1.005, 2)).toBe('1,01');
    expect(formatNumber(-2.345, 2)).toBe('-2,35');
    expect(formatNumber(0.5)).toBe('1');
  });
  it('sin decimales por defecto', () => {
    expect(formatNumber(1234.56)).toBe('1.235');
  });
  it('un negativo que redondea a cero no lleva signo', () => {
    expect(formatNumber(-0.004, 2)).toBe('0,00');
  });
});
