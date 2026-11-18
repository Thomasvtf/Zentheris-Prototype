/** Fuente de ejemplo del Historial (forma del contrato `Historial`) y reglas de vacío. */
import { describe, expect, it, jest } from '@jest/globals';

import { ApiRequestError } from '@/api/client';
import { t } from '@/texts';

import {
  buildMockHistory,
  createMockSource,
  HISTORIAL_MOCK_SCENARIOS,
  isEmptyHistory,
  isMissingLastHour,
} from '../useHistorialData';

/** Miércoles 18/11/2026 15:30 en Bogotá (20:30 UTC). */
const NOW = Date.UTC(2026, 10, 18, 20, 30);
const HOUR = 60 * 60 * 1000;

function hasKey(key: string): boolean {
  const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  const found = t(key) !== key;
  warn.mockRestore();
  return found;
}

describe('buildMockHistory · periodos (RN-XIII-01)', () => {
  it('Día: de 00:00 a la última hora completa, por hora', () => {
    const h = buildMockHistory('normal', { periodo: 'dia' }, NOW);
    expect(h.granularidad).toBe('hora');
    expect(h.inicio).toBe('2026-11-18T05:00:00.000Z'); // 00:00 Bogotá
    expect(h.fin).toBe('2026-11-18T20:00:00.000Z'); // 15:00 Bogotá
    expect(h.serie).toHaveLength(15);
  });

  it('Semana: de lunes a hoy, por día (el último, parcial)', () => {
    const h = buildMockHistory('normal', { periodo: 'semana' }, NOW);
    expect(h.granularidad).toBe('dia');
    expect(h.inicio).toBe('2026-11-16T05:00:00.000Z'); // lunes 16/11
    expect(h.serie).toHaveLength(3);
    expect(h.serie[2].fin).toBe(h.fin);
  });

  it('Mes: del día 1 a hoy, con cargo fijo solo en Mes', () => {
    const mes = buildMockHistory('normal', { periodo: 'mes' }, NOW);
    expect(mes.inicio).toBe('2026-11-01T05:00:00.000Z');
    expect(mes.serie).toHaveLength(18);
    expect(mes.costo.incluye_cargo_fijo).toBe(true);
    expect(buildMockHistory('normal', { periodo: 'semana' }, NOW).costo.incluye_cargo_fijo).toBe(false);
  });
});

describe('buildMockHistory · escenarios', () => {
  it('mixto: Día normal, Semana elevado y Mes crítico (como Figma A5.1–A5.3)', () => {
    expect(buildMockHistory('mixto', { periodo: 'dia' }, NOW).comparacion.estado).toBe('normal');
    expect(buildMockHistory('mixto', { periodo: 'semana' }, NOW).comparacion.estado).toBe('elevado');
    expect(buildMockHistory('mixto', { periodo: 'mes' }, NOW).comparacion.estado).toBe('critico');
  });

  it.each(['normal', 'elevado', 'critico'] as const)('%s: pico, comparación y costo con el mismo estado', (s) => {
    const h = buildMockHistory(s, { periodo: 'semana' }, NOW);
    expect(h.ultimo_pico?.estado).toBe(s);
    expect(h.comparacion.estado).toBe(s);
    expect(h.costo.estado).toBe(h.comparacion.estado);
    expect(h.serie.filter((p) => p.es_pico_maximo)).toHaveLength(1);
  });

  it('participación por zona solo con General y suma 100', () => {
    const general = buildMockHistory('normal', { periodo: 'dia' }, NOW);
    const sum = general.participacion_zonas?.reduce((a, z) => a + z.participacion_pct, 0);
    expect(sum).toBe(100);
    expect(general.zona_id).toBeNull();

    const zona = general.participacion_zonas![1];
    const filtered = buildMockHistory('normal', { periodo: 'dia', zona_id: zona.zona_id }, NOW);
    expect(filtered.zona_id).toBe(zona.zona_id);
    expect(filtered.participacion_zonas).toBeNull();
    expect(filtered.total_kwh).toBeLessThan(general.total_kwh);
  });

  it('sin_anterior: anterior y variación en null, estado sin severidad', () => {
    const h = buildMockHistory('sin_anterior', { periodo: 'mes' }, NOW);
    expect(h.comparacion.anterior_kwh).toBeNull();
    expect(h.comparacion.variacion_pct).toBeNull();
    expect(h.comparacion.estado).toBe('sin_datos');
    expect(h.comparacion.mensaje_codigo).toBe('historial_comparacion.sin_anterior');
  });

  it('sin_tarifa: todo el COP en null', () => {
    const h = buildMockHistory('sin_tarifa', { periodo: 'dia' }, NOW);
    expect(h.tarifa_vigente).toBe(false);
    expect(h.costo.costo_cop).toBeNull();
    expect(h.costo.proyeccion_cierre_cop).toBeNull();
    expect(h.serie.every((p) => p.costo_cop === null)).toBe(true);
  });

  it('faltan_horas: la última hora del Día en null (nunca cero) y aviso', () => {
    const h = buildMockHistory('faltan_horas', { periodo: 'dia' }, NOW);
    expect(h.serie[h.serie.length - 1].energia_kwh).toBeNull();
    expect(isMissingLastHour(h)).toBe(true);
    expect(isEmptyHistory(h)).toBe(false);
  });

  it('sin_picos: ultimo_pico null y ningún pico máximo', () => {
    const h = buildMockHistory('sin_picos', { periodo: 'dia' }, NOW);
    expect(h.ultimo_pico).toBeNull();
    expect(h.serie.some((p) => p.es_pico_maximo)).toBe(false);
  });

  it('vacio: sin lecturas en el periodo → estado vacío', () => {
    const h = buildMockHistory('vacio', { periodo: 'semana' }, NOW);
    expect(isEmptyHistory(h)).toBe(true);
    expect(isMissingLastHour(h)).toBe(false);
  });

  it.each(HISTORIAL_MOCK_SCENARIOS.filter((s) => s !== 'error' && s !== 'sin_permiso'))(
    '%s: los textos de comparación y costo existen en el catálogo',
    (s) => {
      const h = buildMockHistory(s, { periodo: 'mes' }, NOW);
      expect(hasKey(`estado.${h.comparacion.mensaje_codigo}.titulo`)).toBe(true);
      const suffix = h.costo.mensaje_codigo?.split('.').pop();
      expect(hasKey(`estado.historial_costo.${suffix}.titulo`)).toBe(true);
    },
  );
});

describe('createMockSource', () => {
  it('sin_permiso responde 403 SIN_PERMISO_VER_HISTORIAL', async () => {
    jest.useFakeTimers();
    const promise = createMockSource('sin_permiso').getHistory('h', { periodo: 'dia' });
    jest.advanceTimersByTime(HOUR);
    await expect(promise).rejects.toMatchObject({ status: 403, body: { codigo: 'SIN_PERMISO_VER_HISTORIAL' } });
    jest.useRealTimers();
  });

  it('error responde un error de red', async () => {
    jest.useFakeTimers();
    const promise = createMockSource('error').getHistory('h', { periodo: 'dia' });
    jest.advanceTimersByTime(HOUR);
    await expect(promise).rejects.toBeInstanceOf(ApiRequestError);
    jest.useRealTimers();
  });
});
