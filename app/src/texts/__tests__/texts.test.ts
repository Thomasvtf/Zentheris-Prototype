/** t() y plural() sobre el catálogo es-CO. */
import { describe, expect, it, jest } from '@jest/globals';
import { plural, t } from '..';

describe('t', () => {
  it('lee una clave anidada y rellena variables', () => {
    expect(t('formato.saludo.manana', { nombre: 'Ana' })).toBe('Buenos días, Ana');
  });
  it('si falta la clave, devuelve la clave (no inventa texto)', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
    expect(t('no.existe')).toBe('no.existe');
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe('plural (zero / one / other, según _meta.plurales)', () => {
  it('elige la forma por n y rellena {n}', () => {
    expect(plural('formato.vence.dias', 0)).toBe('Vence hoy');
    expect(plural('formato.vence.dias', 1)).toBe('Vence en 1 día');
    expect(plural('formato.vence.dias', 5)).toBe('Vence en 5 días');
  });
});
