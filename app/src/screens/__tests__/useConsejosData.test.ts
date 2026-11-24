/** Fuente de ejemplo de Consejos (forma del contrato `Consejo`), orden y vacío (RN-XV-02 a RN-XV-05). */
import { describe, expect, it, jest } from '@jest/globals';

import { ApiRequestError } from '@/api/client';
import { t } from '@/texts';

import { buildMockTips, CONSEJOS_MOCK_SCENARIOS, createMockSource, hasPendingTips, sortTips } from '../useConsejosData';
import type { Tip } from '../useConsejosData';

const NOW = Date.UTC(2026, 10, 18, 20, 30);
const DAY = 24 * 60 * 60 * 1000;
const HOGAR = '00000000-0000-4000-8000-000000000001';

function hasKey(key: string): boolean {
  const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  const found = t(key) !== key;
  warn.mockRestore();
  return found;
}

describe('buildMockTips', () => {
  const tips = buildMockTips('mixto', NOW);

  it('cada consejo trae exactamente los campos del contrato', () => {
    const fields = ['id', 'categoria', 'prioridad', 'titulo', 'descripcion', 'zona_id', 'zona_nombre', 'estado', 'completada_en', 'creado_en'];
    for (const tip of tips) expect(Object.keys(tip).sort()).toEqual([...fields].sort());
  });

  it('categoría zona con zona y general sin zona (RN-XV-07, DC-24)', () => {
    for (const tip of tips) {
      if (tip.categoria === 'zona') expect(tip.zona_id).not.toBeNull();
      else expect([tip.zona_id, tip.zona_nombre]).toEqual([null, null]);
    }
    expect(tips.some((x) => x.categoria === 'general' && x.prioridad === 'baja')).toBe(true);
  });

  it('las tres prioridades; completados con fecha y pendientes sin ella (consejos_usuario)', () => {
    expect(new Set(tips.map((x) => x.prioridad))).toEqual(new Set(['alta', 'media', 'baja']));
    for (const tip of tips) expect(tip.completada_en !== null).toBe(tip.estado === 'completada');
  });

  it('vigencia: pendientes con menos de 7 días y completados hace menos de 7 días', () => {
    for (const tip of tips) {
      if (tip.estado === 'pendiente') expect(NOW - Date.parse(tip.creado_en)).toBeLessThan(7 * DAY);
      else expect(NOW - Date.parse(tip.completada_en as string)).toBeLessThan(7 * DAY);
    }
  });

  it('llega ordenado: pendientes de alta a baja y completados al final', () => {
    const flags = tips.map((x) => x.estado === 'pendiente');
    expect(flags).toEqual([...flags].sort((a, b) => Number(b) - Number(a)));
    expect(tips.filter((x) => x.estado === 'pendiente').map((x) => x.prioridad)).toEqual(['alta', 'alta', 'media', 'media', 'media', 'baja']);
  });

  it('sin_pendientes: todo completado; vacio: sin consejos', () => {
    expect(hasPendingTips(buildMockTips('sin_pendientes', NOW))).toBe(false);
    expect(buildMockTips('sin_pendientes', NOW).length).toBeGreaterThan(0);
    expect(buildMockTips('vacio', NOW)).toEqual([]);
    expect(hasPendingTips(tips)).toBe(true);
  });
});

describe('sortTips', () => {
  const base = { categoria: 'zona', zona_id: null, zona_nombre: null, descripcion: 'd', completada_en: null } as const;
  const tip = (id: string, extra: Partial<Tip>): Tip => ({
    ...base,
    id,
    prioridad: 'media',
    titulo: id,
    estado: 'pendiente',
    creado_en: '2026-11-18T10:00:00.000Z',
    ...extra,
  });

  it('pendientes por prioridad, luego el más reciente; completados al final, el último primero', () => {
    const sorted = sortTips([
      tip('c1', { estado: 'completada', completada_en: '2026-11-17T00:00:00.000Z', prioridad: 'alta' }),
      tip('baja', { prioridad: 'baja' }),
      tip('media-vieja', { creado_en: '2026-11-17T10:00:00.000Z' }),
      tip('alta', { prioridad: 'alta' }),
      tip('c2', { estado: 'completada', completada_en: '2026-11-18T00:00:00.000Z' }),
      tip('media-nueva', {}),
    ]);
    expect(sorted.map((x) => x.id)).toEqual(['alta', 'media-nueva', 'media-vieja', 'baja', 'c2', 'c1']);
  });

  it('no modifica la lista original', () => {
    const list = [tip('b', { prioridad: 'baja' }), tip('a', { prioridad: 'alta' })];
    sortTips(list);
    expect(list.map((x) => x.id)).toEqual(['b', 'a']);
  });
});

describe('createMockSource', () => {
  it('marcar registra completada_en y desmarcar la deja vacía; el cambio persiste al consultar', async () => {
    const source = createMockSource('mixto', NOW);
    const first = (await source.listTips(HOGAR)).consejos.find((x) => x.estado === 'pendiente') as Tip;

    const done = await source.updateTipStatus(HOGAR, first.id, { estado: 'completada' });
    expect(done.estado).toBe('completada');
    expect(done.completada_en).not.toBeNull();
    expect((await source.listTips(HOGAR)).consejos.find((x) => x.id === first.id)?.estado).toBe('completada');

    const back = await source.updateTipStatus(HOGAR, first.id, { estado: 'pendiente' });
    expect([back.estado, back.completada_en]).toEqual(['pendiente', null]);
  });

  it('consejo inexistente: 404 (RN-XV-06)', async () => {
    const source = createMockSource('mixto', NOW);
    await expect(source.updateTipStatus(HOGAR, 'no-existe', { estado: 'completada' })).rejects.toMatchObject({ status: 404 });
  });

  it('error: la carga falla sin conexión; error_marcar: carga bien y marcar falla', async () => {
    await expect(createMockSource('error', NOW).listTips(HOGAR)).rejects.toBeInstanceOf(ApiRequestError);
    const source = createMockSource('error_marcar', NOW);
    const id = (await source.listTips(HOGAR)).consejos[0].id;
    await expect(source.updateTipStatus(HOGAR, id, { estado: 'completada' })).rejects.toBeInstanceOf(ApiRequestError);
  });
});

describe('textos del catálogo y escenarios', () => {
  it.each([
    'consejos.encabezado',
    'consejos.prioridad_alta',
    'consejos.prioridad_media',
    'consejos.prioridad_baja',
    'consejos.completado',
    'consejos.vacio_titulo',
    'consejos.vacio_cuerpo',
    'a11y.consejo_marcar',
    'a11y.consejo_desmarcar',
    'comun.cargando',
    'comun.reintentar',
  ])('existe %s', (key) => expect(hasKey(key)).toBe(true));

  it('hay un escenario por cada estado', () => {
    expect([...CONSEJOS_MOCK_SCENARIOS]).toEqual(['mixto', 'sin_pendientes', 'vacio', 'error', 'error_marcar']);
  });
});
