/** Hoja «Vigente desde» (BottomSheet.md + Select.md): año, cuadrícula de meses y «Aplicar». */
import { describe, expect, it, jest } from '@jest/globals';
import { fireEvent, render, screen } from '@testing-library/react-native';

import { t } from '@/texts';

import { SinceSheet } from '../ConfigurarTarifaScreen';

// La configuración de Jest no transforma este paquete ESM; se sustituye por vistas vacías.
jest.mock('@expo/vector-icons', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return new Proxy({}, { get: () => View });
});
jest.mock('expo-router', () => ({ useRouter: () => ({ back: jest.fn(), push: jest.fn() }) }));

/** Meses elegibles de 2026 (de más reciente a más antiguo): octubre a noviembre; hubo tarifa en septiembre. */
const MONTHS = ['2026-11', '2026-10'];

async function open(extra: Partial<React.ComponentProps<typeof SinceSheet>> = {}) {
  const onApply = jest.fn();
  const onClose = jest.fn();
  await render(<SinceSheet months={MONTHS} selected={null} support="ayuda" onApply={onApply} onClose={onClose} {...extra} />);
  return { onApply, onClose };
}

describe('SinceSheet', () => {
  it('título, ayuda, año y los 12 meses con la etiqueta de cierre', async () => {
    await open();
    expect(screen.getByText(t('tarifa.hoja_vigencia_titulo'))).toBeTruthy();
    expect(screen.getByText('ayuda')).toBeTruthy();
    expect(screen.getByText(t('tarifa.hoja_vigencia_anio'))).toBeTruthy();
    expect(screen.getByText(t('tarifa.hoja_vigencia_mes'))).toBeTruthy();
    expect(screen.getByText('2026')).toBeTruthy();
    for (let m = 1; m <= 12; m++) expect(screen.getByText(t(`formato.mes_corto.${String(m).padStart(2, '0')}`))).toBeTruthy();
    expect(screen.getByLabelText(t('comun.cerrar'))).toBeTruthy();
  });

  it('solo los meses elegibles están habilitados (posteriores a la tarifa y no futuros)', async () => {
    await open();
    const enabled = (label: string) => screen.getByRole('radio', { name: label }).props.accessibilityState.disabled === false;
    expect(enabled(t('formato.mes_corto.10'))).toBe(true);
    expect(enabled(t('formato.mes_corto.11'))).toBe(true);
    for (const m of ['01', '09', '12']) expect(enabled(t(`formato.mes_corto.${m}`))).toBe(false);
  });

  it('preselecciona el mes más reciente y «Aplicar · mes de año» lo confirma', async () => {
    const { onApply } = await open();
    expect(screen.getByRole('radio', { name: t('formato.mes_corto.11') }).props.accessibilityState.checked).toBe(true);
    const label = t('tarifa.hoja_vigencia_aplicar', { mes_anio: t('formato.mes_anio', { mes: t('formato.mes.11'), anio: '2026' }) });
    await fireEvent.press(screen.getByText(label));
    expect(onApply).toHaveBeenCalledWith('2026-11');
  });

  it('elegir otro mes cambia lo que se aplica', async () => {
    const { onApply } = await open();
    await fireEvent.press(screen.getByRole('radio', { name: t('formato.mes_corto.10') }));
    await fireEvent.press(screen.getByText(t('tarifa.hoja_vigencia_aplicar', { mes_anio: t('formato.mes_anio', { mes: t('formato.mes.10'), anio: '2026' }) })));
    expect(onApply).toHaveBeenCalledWith('2026-10');
  });

  it('un mes no elegible no se puede elegir', async () => {
    const { onApply } = await open();
    await fireEvent.press(screen.getByRole('radio', { name: t('formato.mes_corto.01') }));
    await fireEvent.press(screen.getByText(t('tarifa.hoja_vigencia_aplicar', { mes_anio: t('formato.mes_anio', { mes: t('formato.mes.11'), anio: '2026' }) })));
    expect(onApply).toHaveBeenCalledWith('2026-11');
  });

  it('sin meses elegibles: «Aplicar» desactivado', async () => {
    const { onApply } = await open({ months: [] });
    await fireEvent.press(screen.getByText(t('tarifa.vigencia_ph')));
    expect(onApply).not.toHaveBeenCalled();
  });

  it('cerrar con el botón de la hoja', async () => {
    const { onClose } = await open();
    await fireEvent.press(screen.getByLabelText(t('comun.cerrar')));
    expect(onClose).toHaveBeenCalled();
  });
});
