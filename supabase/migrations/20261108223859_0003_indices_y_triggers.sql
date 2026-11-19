-- =============================================================================
-- Zentheris · Migración 03 · Únicos parciales, índices y triggers
-- Fuente: DC-41 (únicos e índices), especificación de Supabase v1 §4,
--         RN-II-01, RN-II-02. Los índices de claves foráneas se añaden para
--         que los borrados en cascada y las uniones no recorran tablas enteras.
-- =============================================================================

-- Únicos parciales de negocio ------------------------------------------------
-- RN-II-01: una membresía activa por usuario.
create unique index uq_miembros_usuario_activo
  on public.hogar_miembros (usuario_id) where estado = 'activo';
-- RN-II-02: un solo administrador activo por hogar.
create unique index uq_miembros_admin_activo
  on public.hogar_miembros (hogar_id) where rol = 'administrador' and estado = 'activo';
-- DC-41: una invitación pendiente por hogar y correo (en minúsculas).
create unique index uq_invitacion_pendiente_hogar_correo
  on public.invitaciones_hogar (hogar_id, lower(correo_invitado)) where estado = 'pendiente';
-- DC-41: una tarifa abierta por hogar.
create unique index uq_tarifa_abierta_por_hogar
  on public.tarifas_hogar (hogar_id) where vigente_hasta is null;
-- DC-41: una meta activa por hogar.
create unique index uq_meta_activa_por_hogar
  on public.metas_consumo (hogar_id) where estado = 'activa';

-- Índices de consulta (especificación §4) ------------------------------------
create index ix_alertas_hogar_fecha        on public.alertas (hogar_id, created_at desc);
create index ix_consejos_hogar_fecha       on public.consejos (hogar_id, created_at desc);
create index ix_alertas_usuario_lectura    on public.alertas_usuario (usuario_id, leida_en);
create index ix_consejos_usuario_estado    on public.consejos_usuario (usuario_id, estado);
create index ix_miembros_hogar_estado      on public.hogar_miembros (hogar_id, estado);
create index ix_zonas_hogar                on public.zonas (hogar_id);
-- lecturas usa el único (sensor_id, fecha_hora) para la consulta horaria.

-- Índices de claves foráneas (decisión de este entorno) ----------------------
create index ix_hogares_perfil             on public.hogares (perfil_simulacion_id);
create index ix_miembros_usuario           on public.hogar_miembros (usuario_id);
create index ix_invitaciones_invitado_por  on public.invitaciones_hogar (invitado_por);
create index ix_sensores_fuente            on public.sensores_zona (fuente_principal_id);
create index ix_tarifas_hogar_desde        on public.tarifas_hogar (hogar_id, vigente_desde);
create index ix_metas_hogar                on public.metas_consumo (hogar_id);
create index ix_alertas_zona               on public.alertas (zona_id);
create index ix_consejos_zona              on public.consejos (zona_id);

-- updated_at automático en las 17 tablas -------------------------------------
do $$
declare
  t text;
begin
  foreach t in array array[
    'perfiles_simulacion', 'usuarios', 'preferencias_usuario', 'hogares',
    'perfil_transicion', 'hogar_miembros', 'invitaciones_hogar', 'zonas',
    'fuentes_principales', 'sensores_zona', 'lecturas', 'tarifas_hogar',
    'metas_consumo', 'alertas', 'alertas_usuario', 'consejos', 'consejos_usuario'
  ]
  loop
    execute format(
      'create trigger trg_%s_updated_at before update on public.%I
         for each row execute function privado.fijar_updated_at();', t, t);
  end loop;
end;
$$;

-- RN-II-02: máximo 5 miembros activos por hogar (segunda defensa; el backend
-- valida primero y responde con su código de error).
create or replace function privado.validar_maximo_miembros()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.estado = 'activo' and (
       select count(*) from public.hogar_miembros m
       where m.hogar_id = new.hogar_id and m.estado = 'activo' and m.id <> new.id
     ) >= 5 then
    raise exception 'RN-II-02: el hogar % ya tiene 5 miembros activos', new.hogar_id
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

create trigger trg_hogar_miembros_maximo
  before insert or update of estado, hogar_id on public.hogar_miembros
  for each row execute function privado.validar_maximo_miembros();
