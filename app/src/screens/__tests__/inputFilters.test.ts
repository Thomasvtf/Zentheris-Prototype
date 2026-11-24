/** Filtros de entrada de los formularios de Configuración. */
import { describe, expect, it } from '@jest/globals';

import { sanitizeCop, sanitizeDecimal, sanitizeEmail, sanitizeName, sanitizePhone } from '../inputFilters';

describe('sanitizePhone', () => {
  it('deja solo dígitos', () => {
    expect(sanitizePhone('300 123-4567')).toBe('3001234567');
    expect(sanitizePhone('abc3x0y0')).toBe('300');
  });
  it('acepta un «+» solo al inicio y limita a 12 dígitos', () => {
    expect(sanitizePhone('+57 300 123 4567')).toBe('+573001234567');
    expect(sanitizePhone('3+00')).toBe('300');
    expect(sanitizePhone('3001234567890123')).toBe('300123456789');
  });
});

describe('sanitizeEmail', () => {
  it('quita espacios y símbolos inválidos', () => {
    expect(sanitizeEmail(' ana perez@correo.com ')).toBe('anaperez@correo.com');
    expect(sanitizeEmail('ana#$/()@correo.com')).toBe('ana@correo.com');
  });
  it('permite una sola «@» y los símbolos válidos . _ % + -', () => {
    expect(sanitizeEmail('a@b@c.com')).toBe('a@bc.com');
    expect(sanitizeEmail('ana.p_e-r+z%@correo.co')).toBe('ana.p_e-r+z%@correo.co');
  });
  it('limita a 254 caracteres', () => {
    expect(sanitizeEmail('a'.repeat(300))).toHaveLength(254);
  });
});

describe('sanitizeName', () => {
  it('quita dígitos y símbolos, conserva tildes y ñ', () => {
    expect(sanitizeName('Ana 3 Pérez!')).toBe('Ana Pérez');
    expect(sanitizeName('Nuñez-Peña O\'Brien Jr.')).toBe('Nuñez-Peña O\'Brien Jr.');
  });
  it('junta espacios repetidos y no empieza con espacio', () => {
    expect(sanitizeName('  Ana   Pérez')).toBe('Ana Pérez');
  });
});

describe('sanitizeDecimal', () => {
  it('dígitos con una coma y hasta 2 decimales', () => {
    expect(sanitizeDecimal('892,567')).toBe('892,56');
    expect(sanitizeDecimal('8a9b2')).toBe('892');
    expect(sanitizeDecimal('89,2,5')).toBe('89,25');
  });
  it('el punto del teclado cuenta como coma', () => {
    expect(sanitizeDecimal('892.5')).toBe('892,5');
  });
  it('limita la parte entera a 6 dígitos y deja la coma escrita', () => {
    expect(sanitizeDecimal('12345678')).toBe('123456');
    expect(sanitizeDecimal('892,')).toBe('892,');
  });
  it('bloquea letras y signos', () => {
    expect(sanitizeDecimal('-$abc')).toBe('');
  });
});

describe('sanitizeCop', () => {
  it('solo dígitos agrupados con punto de miles es-CO', () => {
    expect(sanitizeCop('12000')).toBe('12.000');
    expect(sanitizeCop('1.234.567')).toBe('1.234.567');
    expect(sanitizeCop('1,5a')).toBe('15');
  });
  it('vacío si no hay dígitos y máximo 9 dígitos', () => {
    expect(sanitizeCop('abc')).toBe('');
    expect(sanitizeCop('1234567890123')).toBe('123.456.789');
  });
});
