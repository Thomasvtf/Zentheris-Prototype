/** Renderizado del Historial con la fuente de ejemplo: estados de §6.5 y §7.3. */
import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { AccessibilityInfo } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { t } from '@/texts';

import { HistorialScreen } from '../HistorialScreen';
import type { HistorialMockScenario } from '../useHistorialData';

jest.mock('expo-router', () => ({ useRouter: () => ({ push: jest.fn() }) }));
// La configuración de Jest no transforma estos paquetes ESM; se sustituyen por vistas vacías
// (aquí se prueban estados y textos, no el dibujo de íconos ni gráficos).
jest.mock('lucide-react-native', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return new Proxy({}, { get: () => View });
});
jest.mock('react-native-gifted-charts', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { BarChart: View, LineChart: View, PieChart: View };
});

const METRICS = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 0, left: 0, right: 0, bottom: 0 } };
const WAIT = { timeout: 3000 };

beforeEach(() => {
  // «Reducir movimiento»: el esqueleto no anima (sin temporizadores en bucle).
  jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(true);
});

async function waitLoaded() {
  await waitFor(() => expect(screen.queryAllByLabelText(t('comun.cargando'))).toHaveLength(0), WAIT);
}

async function renderScenario(scenario: HistorialMockScenario) {
  render(
    <SafeAreaProvider initialMetrics={METRICS}>
      <HistorialScreen mockScenario={scenario} />
    </SafeAreaProvider>,
  );
  await waitLoaded();
}

describe('HistorialScreen', () => {
  it('mixto: cards del Día y filtro por zona', async () => {
    await renderScenario('mixto');
    expect(screen.getByText(t('historial.pico_dia'))).toBeTruthy();
    expect(screen.getByText(t('historial.filtrar_zona'))).toBeTruthy();
    expect(screen.getByText(t('historial.costo_dia'))).toBeTruthy();
    expect(screen.getByText(t('estado.historial_comparacion.similar.titulo'))).toBeTruthy();
  });

  it('cambiar a Mes recarga todas las cards (RN-XIII-02)', async () => {
    await renderScenario('mixto');
    fireEvent.press(screen.getByText(t('formato.periodo.mes')));
    expect(await screen.findByText(t('historial.pico_mes'), {}, WAIT)).toBeTruthy();
    expect(screen.getByText(t('estado.historial_comparacion.muy_mayor.titulo'))).toBeTruthy();
  });

  it('filtrar por zona mantiene la lista de zonas', async () => {
    await renderScenario('normal');
    fireEvent.press(screen.getByText('Cocina'));
    await waitLoaded();
    expect(await screen.findByText('Cocina', {}, WAIT)).toBeTruthy();
    expect(screen.getByText(t('comun.general'))).toBeTruthy();
  });

  it('sin_tarifa: card «Configura tu tarifa» y sin COP', async () => {
    await renderScenario('sin_tarifa');
    expect(screen.getByText(t('estado.historial_costo.sin_tarifa.titulo'))).toBeTruthy();
    expect(screen.queryByText(t('comun.cop'))).toBeNull();
  });

  it('faltan_horas: aviso de la última hora', async () => {
    await renderScenario('faltan_horas');
    expect(screen.getByText(t('historial.faltan_titulo'))).toBeTruthy();
  });

  it('sin_picos: «Sin picos en este periodo»', async () => {
    await renderScenario('sin_picos');
    expect(screen.getByText(t('estado.historial_pico.ninguno.titulo'))).toBeTruthy();
  });

  it('vacio: sin cards de pico, comparación ni costo', async () => {
    await renderScenario('vacio');
    expect(screen.getByText(t('estado.palabra.sin_datos'))).toBeTruthy();
    expect(screen.queryByText(t('historial.pico_dia'))).toBeNull();
  });

  it('sin_permiso: mensaje con selector visible', async () => {
    await renderScenario('sin_permiso');
    expect(screen.getByText(t('error.sin_permiso_ver_historial.titulo'))).toBeTruthy();
    expect(screen.getByText(t('formato.periodo.semana'))).toBeTruthy();
  });

  it('error: aviso con Reintentar', async () => {
    await renderScenario('error');
    expect(screen.getByText(t('error.app.sin_conexion.titulo'))).toBeTruthy();
    expect(screen.getByText(t('comun.reintentar'))).toBeTruthy();
  });
});
