/** Carga del Panel principal (loadDashboard) y fuente de ejemplo (createMockSource). */
import { describe, expect, it, jest } from '@jest/globals';

import { ApiRequestError } from '@/api/client';
import { t } from '@/texts';

import {
  createMockSource,
  DASHBOARD_MOCK_SCENARIOS,
  loadDashboard,
} from '../useDashboardData';
import type { DashboardSource } from '../useDashboardData';

jest.useFakeTimers({ advanceTimers: true });

const HOGAR = '00000000-0000-4000-8000-000000000001';

function hasKey(key: string): boolean {
  const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  const found = t(key) !== key;
  warn.mockRestore();
  return found;
}

describe('createMockSource', () => {
  it.each(['normal', 'elevado', 'critico'] as const)('escenario %s: estados coherentes y COP con tarifa', async (scenario) => {
    const data = await loadDashboard(createMockSource(scenario), HOGAR);
    expect(data.firstName).toBe('Ana');
    expect(data.canSeeConsumption).toBe(true);
    expect(data.current?.actual.estado).toBe(scenario);
    expect(data.current?.acumulado_hoy.estado).toBe(scenario);
    expect(data.current?.tarifa_vigente).toBe(true);
    expect(data.current?.actual.costo_cop).not.toBeNull();
    const shares = data.zones?.zonas.reduce((sum, z) => sum + (z.participacion_pct ?? 0), 0);
    expect(shares).toBe(100);
  });

  it('sin_datos: null (nunca cero) en el consumo actual y sin zonas', async () => {
    const data = await loadDashboard(createMockSource('sin_datos'), HOGAR);
    expect(data.current?.actual.potencia_kw).toBeNull();
    expect(data.current?.actual.estado).toBe('sin_datos');
    expect(data.zones?.total_kw).toBeNull();
    expect(data.zones?.zonas).toHaveLength(0);
  });

  it('sin_tarifa: COP en null y acumulado contra el promedio, sin «Límite»', async () => {
    const data = await loadDashboard(createMockSource('sin_tarifa'), HOGAR);
    expect(data.current?.tarifa_vigente).toBe(false);
    expect(data.current?.actual.costo_cop).toBeNull();
    expect(data.current?.acumulado_hoy.muestra_limite).toBe(false);
    expect(data.current?.acumulado_hoy.referencia_tipo).toBe('promedio');
  });

  it('sin_permiso: no pide consumo ni conteo de alertas', async () => {
    const data = await loadDashboard(createMockSource('sin_permiso'), HOGAR);
    expect(data.canSeeConsumption).toBe(false);
    expect(data.canReceiveAlerts).toBe(false);
    expect(data.current).toBeNull();
    expect(data.zones).toBeNull();
    expect(data.unreadAlerts).toBeNull();
  });

  it('error: rechaza con un error de red', async () => {
    await expect(loadDashboard(createMockSource('error'), HOGAR)).rejects.toBeInstanceOf(ApiRequestError);
  });

  it.each(DASHBOARD_MOCK_SCENARIOS.filter((s) => s !== 'error' && s !== 'sin_permiso'))(
    'escenario %s: cada mensaje_codigo existe en el catálogo',
    async (scenario) => {
      const data = await loadDashboard(createMockSource(scenario), HOGAR);
      const codes = [data.current?.actual.mensaje_codigo, data.current?.acumulado_hoy.mensaje_codigo];
      for (const code of codes) {
        expect(code).toBeTruthy();
        expect(hasKey(`estado.${code}.titulo`)).toBe(true);
      }
    },
  );
});

describe('loadDashboard con la fuente real simulada', () => {
  async function sourceWith(overrides: Partial<DashboardSource>): Promise<DashboardSource> {
    return { ...createMockSource('normal'), ...overrides };
  }

  it('un 403 de consumo se trata como sin permiso', async () => {
    const forbidden = () =>
      Promise.reject(new ApiRequestError('http', 403, { codigo: 'SIN_PERMISO_VER_CONSUMO', mensaje: 'x' }));
    const data = await loadDashboard(await sourceWith({ getCurrentConsumption: forbidden }), HOGAR);
    expect(data.canSeeConsumption).toBe(false);
    expect(data.current).toBeNull();
  });

  it('otro error de consumo se propaga', async () => {
    const failing = () => Promise.reject(new ApiRequestError('http', 500, null));
    await expect(loadDashboard(await sourceWith({ getZonesConsumption: failing }), HOGAR)).rejects.toBeInstanceOf(
      ApiRequestError,
    );
  });

  it('si falla el conteo de alertas, el Panel carga sin indicador', async () => {
    const failing = () => Promise.reject(new ApiRequestError('network', null, null));
    const data = await loadDashboard(await sourceWith({ countUnreadAlerts: failing }), HOGAR);
    expect(data.unreadAlerts).toBeNull();
    expect(data.current).not.toBeNull();
  });
});
