import { describe, expect, it } from '@jest/globals';

import { formatNumber } from '@/format';

import {
  RIGHT_PAD,
  X_LABEL_WIDTH,
  Y_LABEL_WIDTH,
  clampBox,
  niceStep,
  plotLayout,
  slotCenter,
  smoothPaths,
  xLabelIndexes,
  yAxisFor,
} from '../chartGeometry';

describe('chartGeometry', () => {
  it('Semana: 7 slots y su etiqueta caben en el ancho de la card (360 px)', () => {
    const layout = plotLayout(360, 7);
    expect(layout.barWidth).toBeLessThanOrEqual(24);
    for (let i = 0; i < 7; i++) {
      const left = clampBox(slotCenter(layout, i), X_LABEL_WIDTH, 360);
      expect(left).toBeGreaterThanOrEqual(0);
      expect(left + X_LABEL_WIDTH).toBeLessThanOrEqual(360);
    }
    const last = layout.plotLeft + layout.plotWidth;
    expect(last).toBe(360 - RIGHT_PAD);
    expect(layout.plotLeft).toBe(Y_LABEL_WIDTH);
  });

  it('Día: 24 barras caben y las marcas van de 0 a 24 cada 6 h', () => {
    const layout = plotLayout(320, 24);
    expect(layout.slot * 24).toBeCloseTo(layout.plotWidth);
    expect(xLabelIndexes('dia', 24)).toEqual([0, 6, 12, 18, 24]);
  });

  it('Mes: una marca cada 7 días', () => {
    expect(xLabelIndexes('mes', 19)).toEqual([0, 7, 14]);
    expect(xLabelIndexes('semana', 7)).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });

  it('clampBox mantiene la caja dentro de [0, ancho] en ambos bordes', () => {
    expect(clampBox(5, 100, 300)).toBe(0);
    expect(clampBox(295, 100, 300)).toBe(200);
    expect(clampBox(150, 100, 300)).toBe(100);
    expect(clampBox(10, 400, 300)).toBe(0);
  });

  it('eje Y: pasos redondos y decimales mínimos con coma («0,2», «0,4», «0,6»)', () => {
    const axis = yAxisFor([0.1, 0.48, null]);
    expect(axis.ticks.map((t) => formatNumber(t, axis.decimals))).toEqual(['0,0', '0,2', '0,4', '0,6']);
    expect(axis.maxValue).toBeGreaterThanOrEqual(0.48);
    expect(yAxisFor([8.4]).maxValue).toBe(9);
    expect(niceStep(0)).toBe(1);
  });

  it('el promedio de referencia entra en la escala del eje Y', () => {
    expect(yAxisFor([1], 5).maxValue).toBeGreaterThanOrEqual(5);
  });

  it('smoothPaths corta la línea en los null (sin dibujar ceros)', () => {
    const paths = smoothPaths([{ x: 0, y: 1 }, { x: 1, y: 2 }, null, { x: 3, y: 4 }, { x: 4, y: 5 }]);
    expect(paths).toHaveLength(2);
  });
});
