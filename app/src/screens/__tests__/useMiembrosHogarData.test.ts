/** Reglas de miembros e invitaciones y fuente de ejemplo (forma del contrato `MiembrosHogar`). */
import { describe, expect, it, jest } from '@jest/globals';

import { ApiRequestError } from '@/api/client';
import { t } from '@/texts';

import {
  buildMockMembers,
  createMockSource,
  daysLeft,
  freeSlots,
  isValidEmail,
  MEMBER_LIMIT,
  MIEMBROS_MOCK_SCENARIOS,
  MOCK_MEMBER_EMAIL,
  MOCK_PENDING_EMAIL,
  visibleInvitations,
} from '../useMiembrosHogarData';

const NOW = Date.UTC(2026, 10, 18, 20, 30);
const DAY = 24 * 60 * 60 * 1000;
const HOGAR = '00000000-0000-4000-8000-000000000001';

function hasKey(key: string): boolean {
  const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  const found = t(key) !== key;
  warn.mockRestore();
  return found;
}

describe('buildMockMembers', () => {
  it('admin: la forma exacta de MiembrosHogar con una sola administradora', () => {
    const data = buildMockMembers('admin', NOW);
    expect(Object.keys(data).sort()).toEqual(['invitaciones_pendientes', 'miembros', 'miembros_activos', 'permisos', 'puede_gestionar']);
    expect(data.puede_gestionar).toBe(true);
    expect(data.miembros_activos).toBe(data.miembros.length);
    expect(data.miembros.filter((m) => m.rol === 'administrador')).toHaveLength(1);
    for (const m of data.miembros) {
      expect(Object.keys(m).sort()).toEqual(['avatar_url', 'estado', 'fecha_ingreso', 'membresia_id', 'nombre_completo', 'rol', 'usuario_id']);
      expect(m.estado).toBe('activo');
    }
  });

  it('permisos por defecto: ver consumo, historial y alertas sí; modificar metas no (RN-II-03)', () => {
    expect(buildMockMembers('admin', NOW).permisos).toEqual({ ver_consumo_actual: true, ver_historial: true, recibir_alertas: true, modificar_metas: false });
  });

  it('miembro: solo lectura y sin invitaciones pendientes (null, RN-X-08)', () => {
    const data = buildMockMembers('miembro', NOW);
    expect(data.puede_gestionar).toBe(false);
    expect(data.invitaciones_pendientes).toBeNull();
  });

  it('solo_admin: sin miembros adicionales ni invitaciones; lleno: 5 activos', () => {
    const alone = buildMockMembers('solo_admin', NOW);
    expect([alone.miembros_activos, alone.invitaciones_pendientes]).toEqual([1, []]);
    expect(buildMockMembers('lleno', NOW).miembros_activos).toBe(MEMBER_LIMIT);
  });

  it('las invitaciones de ejemplo están vigentes (vencen dentro de 7 días)', () => {
    for (const inv of buildMockMembers('admin', NOW).invitaciones_pendientes ?? []) {
      expect(inv.estado).toBe('pendiente');
      expect(Date.parse(inv.expira_en) - NOW).toBeLessThanOrEqual(7 * DAY);
    }
  });
});

describe('reglas puras', () => {
  it('cupos = 5 − activos − pendientes, sin bajar de 0 (RN-X-05)', () => {
    expect(freeSlots({ miembros_activos: 3, invitaciones_pendientes: [{ id: 'a', correo_invitado: 'a@a.co', estado: 'pendiente', expira_en: '' }] })).toBe(1);
    expect(freeSlots({ miembros_activos: 5, invitaciones_pendientes: [] })).toBe(0);
    expect(freeSlots({ miembros_activos: 1, invitaciones_pendientes: null })).toBe(4);
    expect(freeSlots({ miembros_activos: 5, invitaciones_pendientes: [{ id: 'a', correo_invitado: 'a@a.co', estado: 'pendiente', expira_en: '' }] })).toBe(0);
  });

  it('días que faltan y las vencidas no se muestran', () => {
    expect(daysLeft(new Date(NOW + 2 * DAY + 3600_000).toISOString(), NOW)).toBe(3);
    expect(daysLeft(new Date(NOW - DAY).toISOString(), NOW)).toBe(0);
    const list = [
      { id: 'vigente', correo_invitado: 'a@a.co', estado: 'pendiente' as const, expira_en: new Date(NOW + DAY).toISOString() },
      { id: 'vencida', correo_invitado: 'b@b.co', estado: 'pendiente' as const, expira_en: new Date(NOW - DAY).toISOString() },
    ];
    expect(visibleInvitations(list, NOW).map((i) => i.id)).toEqual(['vigente']);
    expect(visibleInvitations(null, NOW)).toEqual([]);
  });

  it('correo con forma válida', () => {
    expect(isValidEmail(' ana@correo.com ')).toBe(true);
    for (const bad of ['', 'ana', 'ana@', '@correo.com', 'ana@correo', 'a b@correo.com']) expect(isValidEmail(bad)).toBe(false);
  });
});

describe('createMockSource', () => {
  it('invitar: crea la invitación pendiente a 7 días y el cupo baja', async () => {
    const source = createMockSource('admin', NOW);
    const created = await source.createInvitation(HOGAR, { correo_invitado: 'Nueva@Correo.com ' });
    expect(created).toMatchObject({ correo_invitado: 'nueva@correo.com', estado: 'pendiente' });
    expect(Date.parse(created.expira_en) - Date.now()).toBeGreaterThan(6.9 * DAY);
    const data = await source.listMembers(HOGAR);
    expect(freeSlots(data)).toBe(0); // 3 activos + 2 pendientes = 5 → sin cupos
  });

  it('invitar: 409 por correo repetido, ya miembro y límite de 5', async () => {
    const source = createMockSource('admin', NOW);
    await expect(source.createInvitation(HOGAR, { correo_invitado: MOCK_PENDING_EMAIL })).rejects.toMatchObject({ status: 409, body: { codigo: 'INVITACION_PENDIENTE_EXISTENTE' } });
    await expect(source.createInvitation(HOGAR, { correo_invitado: MOCK_MEMBER_EMAIL })).rejects.toMatchObject({ status: 409, body: { codigo: 'YA_ES_MIEMBRO' } });
    await source.createInvitation(HOGAR, { correo_invitado: 'uno@correo.com' });
    await expect(source.createInvitation(HOGAR, { correo_invitado: 'dos@correo.com' })).rejects.toMatchObject({ status: 409, body: { codigo: 'LIMITE_MIEMBROS' } });
  });

  it('cancelar invitación la quita; una inexistente da 404', async () => {
    const source = createMockSource('admin', NOW);
    const id = (await source.listMembers(HOGAR)).invitaciones_pendientes?.[0].id as string;
    await source.revokeInvitation(HOGAR, id);
    expect((await source.listMembers(HOGAR)).invitaciones_pendientes?.some((i) => i.id === id)).toBe(false);
    await expect(source.revokeInvitation(HOGAR, id)).rejects.toMatchObject({ status: 404 });
  });

  it('expulsar baja el conteo; el administrador no puede expulsarse (409)', async () => {
    const source = createMockSource('admin', NOW);
    const { miembros } = await source.listMembers(HOGAR);
    const admin = miembros.find((m) => m.rol === 'administrador')!;
    const other = miembros.find((m) => m.rol === 'miembro')!;
    await expect(source.removeMember(HOGAR, admin.membresia_id)).rejects.toMatchObject({ status: 409 });
    await source.removeMember(HOGAR, other.membresia_id);
    const after = await source.listMembers(HOGAR);
    expect(after.miembros_activos).toBe(miembros.length - 1);
    expect(after.miembros.some((m) => m.membresia_id === other.membresia_id)).toBe(false);
  });

  it('transferir: el destinatario es administrador, quien transfiere pasa a miembro y deja de gestionar', async () => {
    const source = createMockSource('admin', NOW);
    const { miembros } = await source.listMembers(HOGAR);
    const target = miembros.find((m) => m.rol === 'miembro')!;
    const after = await source.transferAdmin(HOGAR, target.membresia_id);
    expect(after.miembros.filter((m) => m.rol === 'administrador').map((m) => m.membresia_id)).toEqual([target.membresia_id]);
    expect(after.puede_gestionar).toBe(false);
    expect(after.invitaciones_pendientes).toBeNull();
  });

  it('permisos: PATCH parcial y lo cambiado persiste', async () => {
    const source = createMockSource('admin', NOW);
    const permisos = await source.updatePermissions(HOGAR, { modificar_metas: true });
    expect(permisos).toEqual({ ver_consumo_actual: true, ver_historial: true, recibir_alertas: true, modificar_metas: true });
    expect((await source.listMembers(HOGAR)).permisos.modificar_metas).toBe(true);
  });

  it('un miembro no gestiona: 403 NO_ES_ADMINISTRADOR', async () => {
    const source = createMockSource('miembro', NOW);
    await expect(source.updatePermissions(HOGAR, { ver_historial: false })).rejects.toMatchObject({ status: 403, body: { codigo: 'NO_ES_ADMINISTRADOR' } });
    await expect(source.createInvitation(HOGAR, { correo_invitado: 'a@a.co' })).rejects.toMatchObject({ status: 403 });
  });

  it('salir: el miembro sale; el administrador con otros miembros recibe ADMIN_DEBE_TRANSFERIR', async () => {
    await expect(createMockSource('miembro', NOW).leaveHousehold(HOGAR)).resolves.toBeUndefined();
    await expect(createMockSource('admin', NOW).leaveHousehold(HOGAR)).rejects.toMatchObject({ body: { codigo: 'ADMIN_DEBE_TRANSFERIR' } });
    await expect(createMockSource('solo_admin', NOW).leaveHousehold(HOGAR)).rejects.toMatchObject({ body: { codigo: 'ADMIN_UNICO_MIEMBRO' } });
  });

  it('error y error_accion', async () => {
    await expect(createMockSource('error', NOW).listMembers(HOGAR)).rejects.toBeInstanceOf(ApiRequestError);
    const source = createMockSource('error_accion', NOW);
    await expect(source.listMembers(HOGAR)).resolves.toBeTruthy();
    await expect(source.updatePermissions(HOGAR, { ver_historial: false })).rejects.toBeInstanceOf(ApiRequestError);
  });
});

describe('textos del catálogo y escenarios', () => {
  it.each([
    'miembros.encabezado',
    'miembros.subtitulo_admin',
    'miembros.subtitulo_miembro',
    'miembros.estado_activo',
    'miembros.estado_pendiente',
    'miembros.pendientes_titulo',
    'miembros.pendientes_ayuda',
    'miembros.permisos_titulo',
    'miembros.permisos_admin',
    'miembros.permisos_lectura',
    'miembros.perm_consumo',
    'miembros.perm_historial',
    'miembros.perm_alertas',
    'miembros.perm_metas',
    'miembros.perm_si',
    'miembros.perm_no',
    'miembros.invitar',
    'miembros.salir',
    'miembros.menu_miembro',
    'miembros.menu_transferir',
    'miembros.menu_expulsar',
    'miembros.menu_cancelar_inv',
    'miembros.menu_invitacion',
    'miembros.permiso_actualizado',
    'rol.administrador',
    'rol.miembro',
    'invitar.encabezado',
    'invitar.titulo',
    'invitar.cuerpo',
    'invitar.correo',
    'invitar.correo_ph',
    'invitar.boton',
    'invitar.enviada_titulo',
    'invitar.enviada_cuerpo',
    'invitar.otra',
    'dialogo.expulsar.titulo',
    'dialogo.transferir.titulo',
    'dialogo.cancelar_invitacion.titulo',
    'dialogo.salir_hogar.titulo',
    'toast.transferida',
    'toast.expulsado',
    'toast.invitacion_cancelada',
    'toast.saliste',
    'error.campo.correo_invalido',
    'error.invitacion_pendiente_existente.titulo',
    'error.ya_es_miembro.titulo',
    'error.limite_miembros.titulo',
    'error.no_es_administrador.titulo',
    'a11y.menu_acciones',
    'comun.tu',
  ])('existe %s', (key) => expect(hasKey(key)).toBe(true));

  it('hay un escenario por cada estado', () => {
    expect([...MIEMBROS_MOCK_SCENARIOS]).toEqual(['admin', 'miembro', 'solo_admin', 'lleno', 'error', 'error_accion']);
  });
});
