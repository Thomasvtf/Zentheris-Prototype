/** Renderizado de Miembros del hogar con la fuente de ejemplo: estados, roles y acciones (§6.17, §7.3). */
import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { plural, t } from '@/texts';

import { MiembrosHogarScreen } from '../MiembrosHogarScreen';
import type { MiembrosMockScenario } from '../useMiembrosHogarData';

jest.mock('expo-router', () => ({ useRouter: () => ({ back: jest.fn(), push: jest.fn() }) }));
// La configuración de Jest no transforma este paquete ESM; se sustituye por vistas vacías.
jest.mock('lucide-react-native', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return new Proxy({}, { get: () => View });
});

const METRICS = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 0, left: 0, right: 0, bottom: 0 } };
const WAIT = { timeout: 3000 };

async function renderScenario(scenario: MiembrosMockScenario) {
  await render(
    <SafeAreaProvider initialMetrics={METRICS}>
      <MiembrosHogarScreen mockScenario={scenario} />
    </SafeAreaProvider>,
  );
}

async function waitLoaded() {
  await waitFor(() => expect(screen.queryAllByLabelText(t('comun.cargando'))).toHaveLength(0), WAIT);
}

async function load(scenario: MiembrosMockScenario) {
  await renderScenario(scenario);
  await waitLoaded();
}

const menuOf = (nombre: string) => screen.getByLabelText(t('a11y.menu_acciones', { nombre }));

beforeEach(() => {
  jest.useRealTimers();
});

describe('MiembrosHogarScreen · administrador', () => {
  it('cargando: esqueleto accesible antes de los datos', async () => {
    await renderScenario('admin');
    expect(screen.getAllByLabelText(t('comun.cargando')).length).toBeGreaterThan(0);
    await waitLoaded();
  });

  it('resumen, lista con rol y estado, invitaciones aparte, permisos e invitar', async () => {
    await load('admin');
    expect(screen.getByText(t('miembros.encabezado'))).toBeTruthy();
    expect(screen.getByText(plural('miembros.resumen', 3))).toBeTruthy();
    expect(screen.getByText(`Ana Pérez ${t('comun.tu')}`)).toBeTruthy();
    expect(screen.getByText(`${t('rol.administrador')} · ${t('miembros.estado_activo')}`)).toBeTruthy();
    expect(screen.getAllByText(`${t('rol.miembro')} · ${t('miembros.estado_activo')}`)).toHaveLength(2);
    expect(screen.getByText(t('miembros.pendientes_titulo'))).toBeTruthy();
    expect(screen.getByText('invitado1@correo.com')).toBeTruthy();
    expect(screen.getAllByText(t('miembros.estado_pendiente'))).toHaveLength(1);
    expect(screen.getByText(plural('formato.vence.dias', 6))).toBeTruthy();
    expect(screen.getByText(t('miembros.permisos_titulo'))).toBeTruthy();
    expect(screen.getAllByRole('switch')).toHaveLength(4);
    expect(screen.getByText(t('miembros.invitar'))).toBeTruthy();
    expect(screen.getByText(plural('miembros.cupos', 1))).toBeTruthy(); // 3 activos + 1 pendiente
    expect(screen.queryByText(t('miembros.salir'))).toBeNull();
  });

  it('el administrador no tiene menú sobre sí mismo', async () => {
    await load('admin');
    expect(screen.queryByLabelText(t('a11y.menu_acciones', { nombre: 'Ana Pérez' }))).toBeNull();
    expect(menuOf('Luis Gómez')).toBeTruthy();
  });

  it('expulsar: menú → confirmación con el nombre del hogar → aviso y el conteo baja', async () => {
    await load('admin');
    fireEvent.press(menuOf('Luis Gómez'));
    fireEvent.press(await screen.findByText(t('miembros.menu_expulsar')));
    expect(await screen.findByText(t('dialogo.expulsar.titulo', { nombre: 'Luis Gómez' }))).toBeTruthy();
    expect(await screen.findByText(t('dialogo.expulsar.cuerpo', { hogar: 'Casa Pérez' }), {}, WAIT)).toBeTruthy();
    fireEvent.press(screen.getByText(t('dialogo.expulsar.confirmar')));
    expect(await screen.findByText(t('toast.expulsado'), {}, WAIT)).toBeTruthy();
    expect(screen.getByText(plural('miembros.resumen', 2))).toBeTruthy();
    expect(screen.queryByText('Luis Gómez')).toBeNull();
  });

  it('transferir: Marta queda como administradora y la vista pasa a solo lectura', async () => {
    await load('admin');
    fireEvent.press(menuOf('Marta Rojas'));
    fireEvent.press(await screen.findByText(t('miembros.menu_transferir')));
    expect(await screen.findByText(t('dialogo.transferir.titulo', { nombre: 'Marta Rojas' }))).toBeTruthy();
    fireEvent.press(screen.getByText(t('dialogo.transferir.confirmar')));
    expect(await screen.findByText(t('toast.transferida'), {}, WAIT)).toBeTruthy();
    await waitFor(() => expect(screen.queryAllByRole('switch')).toHaveLength(0), WAIT);
    expect(screen.queryByText(t('miembros.pendientes_titulo'))).toBeNull();
    expect(screen.getByText(t('miembros.salir'))).toBeTruthy();
  });

  it('cancelar invitación: menú → confirmación con el correo → desaparece', async () => {
    await load('admin');
    fireEvent.press(menuOf('invitado1@correo.com'));
    fireEvent.press(await screen.findByText(t('miembros.menu_cancelar_inv')));
    expect(await screen.findByText(t('dialogo.cancelar_invitacion.cuerpo', { correo: 'invitado1@correo.com' }))).toBeTruthy();
    fireEvent.press(screen.getByText(t('dialogo.cancelar_invitacion.confirmar')));
    expect(await screen.findByText(t('toast.invitacion_cancelada'), {}, WAIT)).toBeTruthy();
    await waitFor(() => expect(screen.queryByText('invitado1@correo.com')).toBeNull(), WAIT);
  });

  it('cambiar un permiso lo guarda y avisa', async () => {
    await load('admin');
    fireEvent(screen.getAllByRole('switch')[3], 'valueChange', true);
    expect(await screen.findByText(t('miembros.permiso_actualizado'), {}, WAIT)).toBeTruthy();
    expect(screen.getAllByRole('switch')[3].props.value).toBe(true);
  });

  it('error_accion: el permiso vuelve a su valor y se avisa', async () => {
    await load('error_accion');
    fireEvent(screen.getAllByRole('switch')[3], 'valueChange', true);
    expect(await screen.findByText(t('error.app.sin_conexion.titulo'), {}, WAIT)).toBeTruthy();
    expect(screen.getAllByRole('switch')[3].props.value).toBe(false);
  });
});

describe('MiembrosHogarScreen · invitar', () => {
  it('solo_admin: estado vacío con la invitación y 4 cupos', async () => {
    await load('solo_admin');
    expect(screen.getByText(plural('miembros.resumen', 1))).toBeTruthy();
    expect(screen.getByText(t('invitar.titulo'))).toBeTruthy();
    expect(screen.queryByText(t('miembros.pendientes_titulo'))).toBeNull();
    expect(screen.getByText(plural('miembros.cupos', 4))).toBeTruthy();
  });

  it('enviar una invitación válida muestra el éxito y suma una pendiente', async () => {
    await load('solo_admin');
    await fireEvent.press(screen.getByText(t('miembros.invitar')));
    await fireEvent.changeText(await screen.findByPlaceholderText(t('invitar.correo_ph')), 'nueva@correo.com');
    await fireEvent.press(screen.getByText(t('invitar.boton')));
    expect(await screen.findByText(t('invitar.enviada_titulo'), {}, WAIT)).toBeTruthy();
    expect(screen.getByText(t('invitar.enviada_cuerpo', { correo: 'nueva@correo.com' }))).toBeTruthy();
    fireEvent.press(screen.getByText(t('comun.cerrar')));
    expect(await screen.findByText(t('miembros.pendientes_titulo'))).toBeTruthy();
    expect(screen.getByText('nueva@correo.com')).toBeTruthy();
  });

  it('correo con formato inválido: error en el campo, sin llamar al backend', async () => {
    await load('solo_admin');
    await fireEvent.press(screen.getByText(t('miembros.invitar')));
    await fireEvent.changeText(await screen.findByPlaceholderText(t('invitar.correo_ph')), 'esto-no-es-un-correo');
    await fireEvent.press(screen.getByText(t('invitar.boton')));
    expect(await screen.findByText(t('error.campo.correo_invalido'))).toBeTruthy();
  });

  it('YA_ES_MIEMBRO: el error del contrato se muestra en el formulario', async () => {
    await load('solo_admin');
    await fireEvent.press(screen.getByText(t('miembros.invitar')));
    await fireEvent.changeText(await screen.findByPlaceholderText(t('invitar.correo_ph')), 'luis.gomez@correo.com');
    await fireEvent.press(screen.getByText(t('invitar.boton')));
    expect(await screen.findByText(t('error.ya_es_miembro.titulo'), {}, WAIT)).toBeTruthy();
  });

  it('INVITACION_PENDIENTE_EXISTENTE: el correo ya invitado', async () => {
    await load('admin');
    await fireEvent.press(screen.getByText(t('miembros.invitar')));
    await fireEvent.changeText(await screen.findByPlaceholderText(t('invitar.correo_ph')), 'invitado1@correo.com');
    await fireEvent.press(screen.getByText(t('invitar.boton')));
    expect(await screen.findByText(t('error.invitacion_pendiente_existente.titulo'), {}, WAIT)).toBeTruthy();
  });

  it('lleno: sin cupos, el botón Invitar está desactivado', async () => {
    await load('lleno');
    expect(screen.getByText(plural('miembros.cupos', 0))).toBeTruthy();
    expect(screen.getByRole('button', { name: t('miembros.invitar') }).props.accessibilityState.disabled).toBe(true);
  });
});

describe('MiembrosHogarScreen · miembro y errores', () => {
  it('miembro: solo lectura, sin menús, sin invitaciones y con Salir del hogar', async () => {
    await load('miembro');
    expect(screen.getByText(t('miembros.subtitulo_miembro'))).toBeTruthy();
    expect(screen.getByText(t('miembros.permisos_lectura'))).toBeTruthy();
    expect(screen.queryAllByRole('switch')).toHaveLength(0);
    expect(screen.getAllByText(t('miembros.perm_si'))).toHaveLength(3);
    expect(screen.getAllByText(t('miembros.perm_no'))).toHaveLength(1);
    expect(screen.queryByText(t('miembros.pendientes_titulo'))).toBeNull();
    expect(screen.queryByText(t('miembros.invitar'))).toBeNull();
    expect(screen.queryByLabelText(t('a11y.menu_acciones', { nombre: 'Luis Gómez' }))).toBeNull();
  });

  it('salir del hogar pide confirmación y avisa', async () => {
    await load('miembro');
    fireEvent.press(screen.getByText(t('miembros.salir')));
    expect(await screen.findByText(t('dialogo.salir_hogar.titulo', { hogar: 'Casa Pérez' }), {}, WAIT)).toBeTruthy();
    fireEvent.press(screen.getAllByText(t('dialogo.salir_hogar.confirmar')).slice(-1)[0]);
    expect((await screen.findAllByText(t('toast.saliste'), {}, WAIT)).length).toBeGreaterThan(0);
  });

  it('error: aviso con Reintentar que vuelve a cargar', async () => {
    await load('error');
    expect(screen.getByText(t('error.app.sin_conexion.titulo'))).toBeTruthy();
    fireEvent.press(screen.getByText(t('comun.reintentar')));
    expect((await screen.findAllByLabelText(t('comun.cargando'), {}, WAIT)).length).toBeGreaterThan(0);
    await waitLoaded();
    expect(await screen.findByText(t('error.app.sin_conexion.titulo'), {}, WAIT)).toBeTruthy();
  });
});
