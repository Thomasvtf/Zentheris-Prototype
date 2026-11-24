/** Render de BarChart, LineChart y ZoneDonutChart: etiquetas, píldora del pico y dona en dos columnas. */
import { describe, expect, it, jest } from '@jest/globals';
import { render, screen } from '@testing-library/react-native';

import { BarChart, LineChart } from '../SeriesChart';
import type { SeriesChartProps } from '../SeriesChart';
import { ZoneDonutChart } from '../ZoneDonutChart';

const base: SeriesChartProps = {
  ancho: 320,
  unidad: 'kWh',
  formatTick: (v, d) => v.toFixed(d).replace('.', ','),
  etiquetaPico: 'Pico · Mar · 7,0 kWh',
  resumen: 'Resumen',
  datos: [1, 7, 3, 2, 4, 5, 2].map((valor, i) => ({ valor, pico: i === 1 })),
  xLabels: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'].map((texto, index) => ({ index, texto, posicion: 'centro' as const })),
};

describe('BarChart', () => {
  it('Semana: los 7 días, la unidad y la píldora completa', async () => {
    await render(<BarChart {...base} />);
    for (const d of ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']) expect(screen.getByText(d)).toBeTruthy();
    expect(screen.getByText('kWh')).toBeTruthy();
    expect(screen.getByText('Pico · Mar · 7,0 kWh')).toBeTruthy();
  });

  it('Día: marcas 00h–24h y eje Y con coma decimal', async () => {
    await render(
      <BarChart
        {...base}
        unidad="kW"
        etiquetaPico="Pico · 11h · 0,48 kW"
        datos={Array.from({ length: 24 }, (_, i) => ({ valor: i === 11 ? 0.48 : 0.1, pico: i === 11 }))}
        xLabels={[0, 6, 12, 18, 24].map((index) => ({ index, texto: `${String(index).padStart(2, '0')}h`, posicion: 'borde' as const }))}
      />,
    );
    for (const h of ['00h', '06h', '12h', '18h', '24h']) expect(screen.getByText(h)).toBeTruthy();
    expect(screen.getByText('Pico · 11h · 0,48 kW')).toBeTruthy();
    expect(screen.getByText('0,2')).toBeTruthy();
    expect(screen.queryByText('0.2')).toBeNull();
  });

  it('sin pico: no hay píldora', async () => {
    await render(<BarChart {...base} etiquetaPico={null} datos={base.datos.map((d) => ({ ...d, pico: false }))} />);
    expect(screen.queryByText(/^Pico/)).toBeNull();
  });
});

describe('LineChart', () => {
  it('Mes: fechas completas en el eje X y píldora con el pico en el borde derecho', async () => {
    const datos = Array.from({ length: 22 }, (_, i) => ({ valor: i === 21 ? 9 : 2, pico: i === 21 }));
    await render(
      <LineChart
        {...base}
        datos={datos}
        etiquetaPico="Pico · 22/11 · 8,4 kWh"
        referencia={3}
        xLabels={[0, 7, 14, 21].map((index, n) => ({ index, texto: ['01/11', '08/11', '15/11', '22/11'][n], posicion: 'centro' as const }))}
      />,
    );
    for (const d of ['01/11', '08/11', '15/11', '22/11']) expect(screen.getByText(d)).toBeTruthy();
    expect(screen.getByText('Pico · 22/11 · 8,4 kWh')).toBeTruthy();
  });
});

describe('ZoneDonutChart', () => {
  it('muestra el total, la píldora de la zona principal y la lista', async () => {
    await render(
      <ZoneDonutChart
        ancho={320}
        resumen="Resumen"
        totalValor="2,9"
        totalUnidad="kWh"
        totalEtiqueta="Total hoy"
        otras={{ nombre: 'Otras zonas', valorTexto: '0,3 kWh', pctTexto: '10 %' }}
        destacado="Cocina · 1,0 kWh · 34 %"
        zonas={[
          { id: 'a', nombre: 'Cocina', participacion: 34, valorTexto: '1,0 kWh', pctTexto: '34 %' },
          { id: 'b', nombre: 'Sala', participacion: 26, valorTexto: '0,8 kWh', pctTexto: '26 %' },
          { id: 'c', nombre: 'Baño', participacion: 20, valorTexto: '0,6 kWh', pctTexto: '20 %' },
          { id: 'd', nombre: 'Oficina', participacion: 10, valorTexto: '0,3 kWh', pctTexto: '10 %' },
          { id: 'e', nombre: 'Garaje', participacion: 6, valorTexto: '0,2 kWh', pctTexto: '6 %' },
          { id: 'f', nombre: 'Terraza', participacion: 4, valorTexto: '0,1 kWh', pctTexto: '4 %' },
        ]}
      />,
    );
    expect(screen.getByText('2,9')).toBeTruthy();
    expect(screen.getByText('Total hoy')).toBeTruthy();
    expect(screen.getByText('Cocina · 1,0 kWh · 34 %')).toBeTruthy();
    expect(screen.getByText('Otras zonas')).toBeTruthy();
    expect(screen.getByText('Terraza')).toBeTruthy();
    jest.restoreAllMocks();
  });
});
