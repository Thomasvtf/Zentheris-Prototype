/** Renderizado de Consejos con la fuente de ejemplo: estados de §6.8 y marcado individual. */
import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { AccessibilityInfo } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { t } from '@/texts';

import { ConsejosScreen } from '../ConsejosScreen';
import type { ConsejosMockScenario } from '../useConsejosData';

// La configuración de Jest no transforma este paquete ESM; se sustituye por vistas vacías.
jest.mock('lucide-react-native', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return new Proxy({}, { get: () => View });
});

const METRICS = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 0, left: 0, right: 0, bottom: 0 } };
const WAIT = { timeout: 3000 };
const MARCAR = new RegExp(`^${t('a11y.consejo_marcar')}`);
const DESMARCAR = new RegExp(`^${t('a11y.consejo_desmarcar')}`);

beforeEach(() => {
  // «Reducir movimiento»: el esqueleto no anima (sin temporizadores en bucle).
  jest.spyOn(AccessibilityInfo, 'isReduceMotionEnabled').mockResolvedValue(true);
});

async function renderScreen(scenario: ConsejosMockScenario) {
  await render(
    <SafeAreaProvider initialMetrics={METRICS}>
      <ConsejosScreen mockScenario={scenario} />
    </SafeAreaProvider>,
  );
}

async function waitLoaded() {
  await waitFor(() => expect(screen.queryAllByLabelText(t('comun.cargando'))).toHaveLength(0), WAIT);
}

describe('ConsejosScreen', () => {
  it('cargando: esqueletos accesibles antes de los datos', async () => {
    await renderScreen('mixto');
    expect(screen.getAllByLabelText(t('comun.cargando')).length).toBeGreaterThan(0);
    await waitLoaded();
  });

  it('mixto: cabecera, lista con prioridades y sin «Todo bajo control»', async () => {
    await renderScreen('mixto');
    await waitLoaded();
    expect(screen.getByText(t('consejos.encabezado'))).toBeTruthy();
    expect(screen.getAllByText(t('consejos.prioridad_alta'))).toHaveLength(2);
    expect(screen.getAllByText(t('consejos.prioridad_media'))).toHaveLength(3);
    expect(screen.getAllByText(t('consejos.prioridad_baja'))).toHaveLength(1);
    expect(screen.getAllByText(t('consejos.completado'))).toHaveLength(2);
    expect(screen.queryByText(t('consejos.vacio_titulo'))).toBeNull();
    expect(screen.getByText('Apaga el aire acondicionado al salir')).toBeTruthy();
  });

  it('sin_pendientes: «Todo bajo control» y los completados debajo', async () => {
    await renderScreen('sin_pendientes');
    await waitLoaded();
    expect(screen.getByText(t('consejos.vacio_titulo'))).toBeTruthy();
    expect(screen.getByText(t('consejos.vacio_cuerpo'))).toBeTruthy();
    expect(screen.getAllByText(t('consejos.completado')).length).toBeGreaterThan(0);
    expect(screen.queryByText(t('consejos.prioridad_alta'))).toBeNull();
  });

  it('vacio: solo «Todo bajo control»', async () => {
    await renderScreen('vacio');
    await waitLoaded();
    expect(screen.getByText(t('consejos.vacio_titulo'))).toBeTruthy();
    expect(screen.queryByText(t('consejos.completado'))).toBeNull();
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
  });

  it('error: aviso con Reintentar, que vuelve a cargar', async () => {
    await renderScreen('error');
    await waitLoaded();
    expect(screen.getByText(t('error.app.sin_conexion.titulo'))).toBeTruthy();
    fireEvent.press(screen.getByText(t('comun.reintentar')));
    expect((await screen.findAllByLabelText(t('comun.cargando'), {}, WAIT)).length).toBeGreaterThan(0);
    await waitLoaded();
    expect(await screen.findByText(t('error.app.sin_conexion.titulo'), {}, WAIT)).toBeTruthy();
  });

  it('marcar los pendientes muestra «Todo bajo control»; desmarcar uno lo oculta', async () => {
    await renderScreen('mixto');
    await waitLoaded();
    for (let i = 0; i < 6; i++) {
      fireEvent.press(screen.getAllByLabelText(MARCAR)[0]);
      await waitFor(() => expect(screen.getAllByText(t('consejos.completado')).length).toBe(2 + i + 1), WAIT);
    }
    expect(await screen.findByText(t('consejos.vacio_titulo'), {}, WAIT)).toBeTruthy();

    fireEvent.press(screen.getAllByLabelText(DESMARCAR)[0]);
    await waitFor(() => expect(screen.queryByText(t('consejos.vacio_titulo'))).toBeNull(), WAIT);
  });

  it('error_marcar: la casilla vuelve a su estado y se avisa', async () => {
    await renderScreen('error_marcar');
    await waitLoaded();
    const before = screen.getAllByText(t('consejos.completado')).length;
    fireEvent.press(screen.getAllByLabelText(MARCAR)[0]);
    expect(await screen.findByText(t('error.app.sin_conexion.titulo'), {}, WAIT)).toBeTruthy();
    expect(screen.getAllByText(t('consejos.completado')).length).toBe(before);
  });
});
