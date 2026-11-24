/** Componentes del sistema de diseño: textos del catálogo, accesibilidad y reglas de cada ficha. */
import { describe, expect, it, jest } from '@jest/globals';
import { fireEvent, render, screen } from '@testing-library/react-native';

import { plural, t } from '@/texts';

import { Button, Chip, ConfirmDialog, InlineNotice, ProgressBar, ScreenHeader, StateMessage, StatusBadge } from '..';

// La configuración de Jest no transforma este paquete ESM; se sustituye por vistas vacías.
jest.mock('lucide-react-native', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return new Proxy({}, { get: () => View });
});

describe('StatusBadge', () => {
  it('muestra la palabra del estado («Crítico», nunca «sobreconsumo»)', async () => {
    await render(<StatusBadge estado="critico" />);
    expect(screen.getByText(t('estado.palabra.critico'))).toBeTruthy();
    expect(screen.queryByText(/sobreconsumo/i)).toBeNull();
  });
});

describe('Chip', () => {
  it('es un radio con su estado y avisa al tocarlo', async () => {
    const onClick = jest.fn();
    await render(
      <Chip activo onClick={onClick}>
        kW
      </Chip>,
    );
    const chip = screen.getByRole('radio');
    expect(chip.props.accessibilityState).toMatchObject({ checked: true, disabled: false });
    await fireEvent.press(chip);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('deshabilitado no responde', async () => {
    const onClick = jest.fn();
    await render(
      <Chip deshabilitado onClick={onClick}>
        COP
      </Chip>,
    );
    await fireEvent.press(screen.getByRole('radio'));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe('ProgressBar', () => {
  it('muestra el porcentaje es-CO y lo limita a 0–100', async () => {
    await render(<ProgressBar porcentaje={130} estado="normal" etiqueta="Normal" />);
    const bar = screen.getByRole('progressbar');
    expect(bar.props.accessibilityValue).toMatchObject({ now: 100 });
    expect(screen.getByText('130 %')).toBeTruthy();
  });

  it('null es «sin dato»: «—» y pista vacía, nunca cero', async () => {
    await render(<ProgressBar porcentaje={null} etiqueta="Participación" />);
    expect(screen.getByText('—')).toBeTruthy();
    expect(screen.getByRole('progressbar').props.accessibilityValue).toMatchObject({ now: 0 });
  });
});

describe('InlineNotice', () => {
  it('«Reintentar» solo en error y con función', async () => {
    const onReintentar = jest.fn();
    await render(<InlineNotice tono="error" titulo="Sin conexión" onReintentar={onReintentar} />);
    await fireEvent.press(screen.getByText(t('comun.reintentar')));
    expect(onReintentar).toHaveBeenCalledTimes(1);
  });

  it('en información no ofrece reintentar', async () => {
    await render(<InlineNotice tono="informacion" titulo="Faltan lecturas" onReintentar={jest.fn()} />);
    expect(screen.queryByText(t('comun.reintentar'))).toBeNull();
  });
});

describe('StateMessage', () => {
  it('muestra título, descripción y la acción', async () => {
    const onAccion = jest.fn();
    await render(<StateMessage tipo="sin_tarifa" titulo="Configura tu tarifa" descripcion="Los kWh se siguen mostrando." accion="Configurar tarifa" onAccion={onAccion} />);
    expect(screen.getByText('Configura tu tarifa')).toBeTruthy();
    await fireEvent.press(screen.getByRole('link'));
    expect(onAccion).toHaveBeenCalledTimes(1);
  });
});

describe('ScreenHeader', () => {
  it('título como encabezado, atrás y campana con no leídas', async () => {
    const onAtras = jest.fn();
    const onCampana = jest.fn();
    await render(<ScreenHeader titulo="Panel principal" onAtras={onAtras} campana noLeidas={3} onCampana={onCampana} />);
    expect(screen.getByRole('header')).toBeTruthy();
    await fireEvent.press(screen.getByLabelText(t('a11y.volver')));
    await fireEvent.press(screen.getByLabelText(plural('a11y.campana_no_leidas', 3)));
    expect(onAtras).toHaveBeenCalledTimes(1);
    expect(onCampana).toHaveBeenCalledTimes(1);
  });

  it('sin onAtras ni campana no muestra botones', async () => {
    await render(<ScreenHeader titulo="Consejos" onAtras={false} />);
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('Button', () => {
  it('cargando bloquea el toque', async () => {
    const onClick = jest.fn();
    await render(
      <Button estado="cargando" onClick={onClick}>
        Guardar
      </Button>,
    );
    // El toque llega al Pressable deshabilitado y no avisa.
    await fireEvent.press(screen.getByText('Guardar'));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe('ConfirmDialog', () => {
  it('principal arriba y «Cancelar» abajo', async () => {
    const onConfirmar = jest.fn();
    const onCancelar = jest.fn();
    await render(<ConfirmDialog titulo="¿Expulsar a María?" descripcion="Dejará de ver la casa." tono="destructivo" confirmar="Expulsar" cancelar="Cancelar" onConfirmar={onConfirmar} onCancelar={onCancelar} />);
    const [primero, segundo] = screen.getAllByText(/^(Expulsar|Cancelar)$/);
    expect(primero.props.children).toBe('Expulsar');
    expect(segundo.props.children).toBe('Cancelar');
    await fireEvent.press(primero);
    await fireEvent.press(segundo);
    expect(onConfirmar).toHaveBeenCalledTimes(1);
    expect(onCancelar).toHaveBeenCalledTimes(1);
  });

  it('ocupado bloquea los dos botones', async () => {
    const onConfirmar = jest.fn();
    const onCancelar = jest.fn();
    await render(<ConfirmDialog titulo="¿Salir del hogar?" confirmar="Salir" cancelar="Cancelar" ocupado onConfirmar={onConfirmar} onCancelar={onCancelar} />);
    await fireEvent.press(screen.getByText('Salir'));
    await fireEvent.press(screen.getByText('Cancelar'));
    expect(onConfirmar).not.toHaveBeenCalled();
    expect(onCancelar).not.toHaveBeenCalled();
  });
});
