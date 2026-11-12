-- =============================================================================
-- Zentheris · Migración 04 · Seguridad por fila (RLS) y privilegios
-- Fuente: DC-40 (D-SQL-5), reglas v4.9 RN-I-03 y RN-XVII, especificación de
--         Supabase v1 §5 (matriz de lectura).
-- Principio: RLS es la SEGUNDA defensa. La primera es el backend (FastAPI con
-- conexión de servicio, que salta RLS). El cliente (app con clave anon + JWT)
-- solo LEE; no escribe ninguna tabla.
-- =============================================================================

-- 1. Funciones auxiliares (SECURITY DEFINER para evitar recursión de RLS) -----
-- Todas viven en «privado», que la API no expone.

create or replace function privado.es_miembro_activo(p_hogar uuid)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.hogar_miembros m
    where m.hogar_id = p_hogar
      and m.usuario_id = (select auth.uid())
      and m.estado = 'activo'
  );
$$;

create or replace function privado.es_administrador(p_hogar uuid)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.hogar_miembros m
    where m.hogar_id = p_hogar
      and m.usuario_id = (select auth.uid())
      and m.estado = 'activo'
      and m.rol = 'administrador'
  );
$$;

-- Permiso general del hogar (RN-II-03, RN-XVII). El administrador siempre pasa.
-- p_permiso: 'ver_consumo_actual' | 'ver_historial' | 'recibir_alertas' | 'modificar_metas'
create or replace function privado.tiene_permiso(p_hogar uuid, p_permiso text)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.hogar_miembros m
    join public.hogares h on h.id = m.hogar_id
    where m.hogar_id = p_hogar
      and m.usuario_id = (select auth.uid())
      and m.estado = 'activo'
      and (
        m.rol = 'administrador'
        or case p_permiso
             when 'ver_consumo_actual' then h.permiso_ver_consumo_actual
             when 'ver_historial'      then h.permiso_ver_historial
             when 'recibir_alertas'    then h.permiso_recibir_alertas
             when 'modificar_metas'    then h.permiso_modificar_metas
             else false
           end
      )
  );
$$;

-- ¿El usuario autenticado comparte hogar activo con otro usuario?
-- Recibe texto para poder usarse con nombres de carpeta de Storage.
create or replace function privado.comparte_hogar(p_usuario text)
returns boolean
language sql stable security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.hogar_miembros yo
    join public.hogar_miembros otro on otro.hogar_id = yo.hogar_id
    where yo.usuario_id = (select auth.uid())
      and yo.estado = 'activo'
      and otro.usuario_id::text = p_usuario
      and otro.estado = 'activo'
  );
$$;

revoke all on function privado.es_miembro_activo(uuid)      from public, anon;
revoke all on function privado.es_administrador(uuid)       from public, anon;
revoke all on function privado.tiene_permiso(uuid, text)    from public, anon;
revoke all on function privado.comparte_hogar(text)         from public, anon;
grant execute on function privado.es_miembro_activo(uuid)   to authenticated, service_role;
grant execute on function privado.es_administrador(uuid)    to authenticated, service_role;
grant execute on function privado.tiene_permiso(uuid, text) to authenticated, service_role;
grant execute on function privado.comparte_hogar(text)      to authenticated, service_role;

-- 2. Activar RLS en las 17 tablas ---------------------------------------------
alter table public.perfiles_simulacion   enable row level security;
alter table public.usuarios              enable row level security;
alter table public.preferencias_usuario  enable row level security;
alter table public.hogares               enable row level security;
alter table public.perfil_transicion     enable row level security;
alter table public.hogar_miembros        enable row level security;
alter table public.invitaciones_hogar    enable row level security;
alter table public.zonas                 enable row level security;
alter table public.fuentes_principales   enable row level security;
alter table public.sensores_zona         enable row level security;
alter table public.lecturas              enable row level security;
alter table public.tarifas_hogar         enable row level security;
alter table public.metas_consumo         enable row level security;
alter table public.alertas               enable row level security;
alter table public.alertas_usuario       enable row level security;
alter table public.consejos              enable row level security;
alter table public.consejos_usuario      enable row level security;

-- 3. Privilegios: la app no escribe; anon no lee nada (DC-40) -----------------
revoke insert, update, delete, truncate, references, trigger
  on all tables in schema public from anon, authenticated;
revoke all on all tables in schema public from anon;
revoke all on public.perfiles_simulacion from authenticated;

-- 4. Políticas de LECTURA (matriz de la especificación §5) --------------------

-- usuarios: su fila y la de miembros activos de su hogar.
create policy usuarios_leer on public.usuarios
  for select to authenticated
  using (id = (select auth.uid()) or privado.comparte_hogar(id::text));

-- Filas personales: solo las propias.
create policy preferencias_leer_propias on public.preferencias_usuario
  for select to authenticated
  using (usuario_id = (select auth.uid()));

create policy alertas_usuario_leer_propias on public.alertas_usuario
  for select to authenticated
  using (usuario_id = (select auth.uid()));

create policy consejos_usuario_leer_propias on public.consejos_usuario
  for select to authenticated
  using (usuario_id = (select auth.uid()));

-- Datos del hogar: miembros activos.
create policy hogares_leer on public.hogares
  for select to authenticated using (privado.es_miembro_activo(id));

create policy hogar_miembros_leer on public.hogar_miembros
  for select to authenticated using (privado.es_miembro_activo(hogar_id));

create policy zonas_leer on public.zonas
  for select to authenticated using (privado.es_miembro_activo(hogar_id));

create policy fuentes_leer on public.fuentes_principales
  for select to authenticated using (privado.es_miembro_activo(hogar_id));

create policy tarifas_leer on public.tarifas_hogar
  for select to authenticated using (privado.es_miembro_activo(hogar_id));

create policy metas_leer on public.metas_consumo
  for select to authenticated using (privado.es_miembro_activo(hogar_id));

create policy consejos_leer on public.consejos
  for select to authenticated using (privado.es_miembro_activo(hogar_id));

create policy perfil_transicion_leer on public.perfil_transicion
  for select to authenticated using (privado.es_miembro_activo(hogar_id));

create policy sensores_leer on public.sensores_zona
  for select to authenticated
  using (zona_id in (
    select z.id from public.zonas z where privado.es_miembro_activo(z.hogar_id)
  ));

-- Invitaciones: el administrador del hogar; el invitado, solo las de su correo.
create policy invitaciones_leer on public.invitaciones_hogar
  for select to authenticated
  using (
    privado.es_administrador(hogar_id)
    or lower(correo_invitado) = lower((select auth.jwt()) ->> 'email')
  );
-- Nota: esta es la forma final (incluye los ajustes 07 y 08 de zentheris-dev,
-- lint 0003 auth_rls_initplan). En el proyecto definitivo no se aplican 07 ni 08.

-- Lecturas: permiso de ver consumo actual o historial (o administrador).
create policy lecturas_leer on public.lecturas
  for select to authenticated
  using (sensor_id in (
    select s.id
    from public.sensores_zona s
    join public.zonas z on z.id = s.zona_id
    where privado.tiene_permiso(z.hogar_id, 'ver_consumo_actual')
       or privado.tiene_permiso(z.hogar_id, 'ver_historial')
  ));

-- Alertas: permiso de recibir alertas (o administrador).
create policy alertas_leer on public.alertas
  for select to authenticated
  using (privado.tiene_permiso(hogar_id, 'recibir_alertas'));

-- perfiles_simulacion: SIN políticas a propósito. Solo el backend la lee.
