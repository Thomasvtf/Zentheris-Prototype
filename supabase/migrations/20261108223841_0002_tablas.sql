-- =============================================================================
-- Zentheris · Migración 02 · 17 tablas propias (auth.users ya existe)
-- Fuente: reglas v4.9 §3 (diccionario de 18 tablas) y especificación de
--         Supabase v1 §4 (orden de creación). Decisiones DC-36 a DC-41.
-- Convención: todas tienen created_at y updated_at (TIMESTAMPTZ).
-- =============================================================================

-- 1. perfiles_simulacion (tabla 12 del diccionario) ---------------------------
create table public.perfiles_simulacion (
  id                            uuid primary key default gen_random_uuid(),
  nombre                        text not null unique,
  activo                        boolean not null default true,
  base_cocina_kwh_dia           numeric(10,4) not null check (base_cocina_kwh_dia >= 0),
  base_sala_kwh_dia             numeric(10,4) not null check (base_sala_kwh_dia >= 0),
  base_dormitorio_kwh_dia       numeric(10,4) not null check (base_dormitorio_kwh_dia >= 0),
  base_bano_kwh_dia             numeric(10,4) not null check (base_bano_kwh_dia >= 0),
  base_lavanderia_kwh_dia       numeric(10,4) not null check (base_lavanderia_kwh_dia >= 0),
  base_oficina_kwh_dia          numeric(10,4) not null check (base_oficina_kwh_dia >= 0),
  base_terraza_kwh_dia          numeric(10,4) not null check (base_terraza_kwh_dia >= 0),
  base_garaje_kwh_dia           numeric(10,4) not null check (base_garaje_kwh_dia >= 0),
  base_cuarto_servicio_kwh_dia  numeric(10,4) not null check (base_cuarto_servicio_kwh_dia >= 0),
  curva_horaria                 jsonb not null,
  humor_min                     numeric(6,4) not null,
  humor_max                     numeric(6,4) not null,
  ruido_config                  jsonb not null,
  picos_config                  jsonb not null,
  factor_fin_semana             numeric(6,4) not null check (factor_fin_semana > 0),
  created_at                    timestamptz not null default now(),
  updated_at                    timestamptz not null default now(),
  constraint perfiles_humor_rango check (humor_min <= humor_max)
);
comment on table public.perfiles_simulacion is
  'Tabla 12. Personalidades del simulador (5). Solo la lee el backend (RLS sin políticas).';

-- 2. usuarios -----------------------------------------------------------------
create table public.usuarios (
  id               uuid primary key references auth.users(id) on delete cascade,
  nombre_completo  text not null,
  telefono         text,
  avatar_url       text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
comment on table public.usuarios is
  'Tabla 2. Ficha personal 1:1 con auth.users. Se borra en cascada con la cuenta (DC-36).';

-- 3. preferencias_usuario -----------------------------------------------------
create table public.preferencias_usuario (
  usuario_id        uuid primary key references public.usuarios(id) on delete cascade,
  notif_consumo     boolean not null default true,
  notif_consejos    boolean not null default true,
  base_comparacion  text not null default 'promedio'
                    check (base_comparacion in ('meta', 'promedio')),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);
comment on table public.preferencias_usuario is
  'Tabla 3. Ajustes individuales (interruptores y base de comparación).';

-- 4. hogares ------------------------------------------------------------------
create table public.hogares (
  id                          uuid primary key default gen_random_uuid(),
  nombre                      text not null,
  estrato                     smallint check (estrato between 1 and 6),
  ciudad                      text,
  numero_personas             integer check (numero_personas >= 1),
  trabajo_estudio_casa        boolean,
  tipo_vivienda               text not null
                              check (tipo_vivienda in ('apartamento', 'casa', 'apartaestudio', 'duplex', 'casa_campestre')),
  perfil_simulacion_id        uuid not null references public.perfiles_simulacion(id),
  permiso_ver_consumo_actual  boolean not null default true,
  permiso_ver_historial       boolean not null default true,
  permiso_recibir_alertas     boolean not null default true,
  permiso_modificar_metas     boolean not null default false,
  created_at                  timestamptz not null default now(),
  updated_at                  timestamptz not null default now()
);
comment on table public.hogares is
  'Tabla 4. Entidad central. Personalidad obligatoria (D-SQL-2 / DC-37). 4 permisos generales (RN-II-03).';

-- 5. perfil_transicion (Fase 2: la tabla existe, el MVP no la llena) ---------
create table public.perfil_transicion (
  id                    uuid primary key default gen_random_uuid(),
  hogar_id              uuid not null unique references public.hogares(id) on delete cascade,
  area_techo_m2         numeric(8,2) check (area_techo_m2 >= 0),
  factura_promedio_cop  numeric(12,2),
  vehiculo_electrico    boolean,
  presupuesto_cop       numeric(14,2),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
comment on table public.perfil_transicion is
  'Tabla 5. Datos opcionales para transición energética (Fase 2, DC-01).';

-- 6. hogar_miembros -----------------------------------------------------------
create table public.hogar_miembros (
  id             uuid primary key default gen_random_uuid(),
  hogar_id       uuid not null references public.hogares(id) on delete cascade,
  usuario_id     uuid references public.usuarios(id) on delete set null,
  rol            text not null check (rol in ('administrador', 'miembro')),
  estado         text not null check (estado in ('activo', 'inactivo')),
  fecha_ingreso  timestamptz not null,
  fecha_salida   timestamptz,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  -- Una membresía activa siempre tiene usuario (DC-36).
  constraint miembros_activo_con_usuario check (estado <> 'activo' or usuario_id is not null)
);
comment on table public.hogar_miembros is
  'Tabla 6. Relación M:N usuarios-hogares con rol y estado. usuario_id nulo solo en membresías cerradas de cuentas eliminadas.';

-- 7. invitaciones_hogar -------------------------------------------------------
create table public.invitaciones_hogar (
  id               uuid primary key default gen_random_uuid(),
  hogar_id         uuid not null references public.hogares(id) on delete cascade,
  correo_invitado  text not null,
  invitado_por     uuid references public.usuarios(id) on delete set null,
  token_hash       text not null unique,
  estado           text not null
                   check (estado in ('pendiente', 'aceptada', 'rechazada', 'expirada', 'revocada')),
  expira_en        timestamptz not null,
  respondida_en    timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
comment on table public.invitaciones_hogar is
  'Tabla 7. Invitaciones por correo (7 días). Solo se guarda el hash del token (RN-X-05).';

-- 8. zonas --------------------------------------------------------------------
create table public.zonas (
  id          uuid primary key default gen_random_uuid(),
  hogar_id    uuid not null references public.hogares(id) on delete cascade,
  nombre      text not null,
  tipo        text not null
              check (tipo in ('cocina', 'sala', 'dormitorio', 'bano', 'lavanderia',
                              'oficina', 'terraza', 'garaje', 'cuarto_servicio')),
  estado      text not null check (estado in ('activa', 'inactiva')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint zonas_nombre_unico_por_hogar unique (hogar_id, nombre)
);
comment on table public.zonas is
  'Tabla 8. Catálogo de 9 tipos. Se eligen solo en el onboarding (RN-III-01).';

-- 9. fuentes_principales ------------------------------------------------------
create table public.fuentes_principales (
  id          uuid primary key default gen_random_uuid(),
  hogar_id    uuid not null unique references public.hogares(id) on delete cascade,
  nombre      text not null,
  estado      text not null check (estado in ('activa', 'inactiva')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
comment on table public.fuentes_principales is
  'Tabla 9. Medidor virtual general. Una por hogar en el MVP.';

-- 10. sensores_zona -----------------------------------------------------------
create table public.sensores_zona (
  id                   uuid primary key default gen_random_uuid(),
  zona_id              uuid not null unique references public.zonas(id) on delete cascade,
  fuente_principal_id  uuid not null references public.fuentes_principales(id) on delete cascade,
  estado               text not null check (estado in ('activo', 'pausado')),
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);
comment on table public.sensores_zona is
  'Tabla 10. Sensor virtual: une una zona con la fuente principal (1 por zona).';

-- 11. lecturas ----------------------------------------------------------------
create table public.lecturas (
  id           uuid primary key default gen_random_uuid(),
  sensor_id    uuid not null references public.sensores_zona(id) on delete cascade,
  fecha_hora   timestamptz not null,
  consumo_kwh  numeric(12,4) not null check (consumo_kwh >= 0),
  calidad      text not null check (calidad in ('simulada', 'estimada', 'real')),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint lecturas_una_por_sensor_y_hora unique (sensor_id, fecha_hora)
);
comment on table public.lecturas is
  'Tabla 11. kWh por sensor y hora (America/Bogota). El total del hogar se deriva sumando zonas.';

-- 13. tarifas_hogar -----------------------------------------------------------
create table public.tarifas_hogar (
  id                  uuid primary key default gen_random_uuid(),
  hogar_id            uuid not null references public.hogares(id) on delete cascade,
  operador            text,
  precio_kwh          numeric(12,2) not null check (precio_kwh >= 0),
  cargo_fijo_mensual  numeric(12,2) check (cargo_fijo_mensual >= 0),
  vigente_desde       date not null,
  vigente_hasta       date,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  constraint tarifas_rango_valido check (vigente_hasta is null or vigente_hasta > vigente_desde),
  -- Vigencias [desde, hasta) sin solapamiento dentro del mismo hogar (DC-39).
  constraint tarifas_sin_solapamiento exclude using gist (
    hogar_id with =,
    daterange(vigente_desde, vigente_hasta, '[)') with &&
  )
);
comment on table public.tarifas_hogar is
  'Tabla 13. Precio COP/kWh con vigencia [desde, hasta). Sin solapes y una sola abierta por hogar.';

-- 14. metas_consumo -----------------------------------------------------------
create table public.metas_consumo (
  id                 uuid primary key default gen_random_uuid(),
  hogar_id           uuid not null references public.hogares(id) on delete cascade,
  tipo               text not null check (tipo in ('ahorro', 'eficiencia', 'presupuesto')),
  valor_kwh_mensual  numeric not null check (valor_kwh_mensual > 0),
  estado             text not null check (estado in ('activa', 'inactiva')),
  fecha_inicio       date not null,
  fecha_fin          date,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  constraint metas_rango_valido check (fecha_fin is null or fecha_fin > fecha_inicio)
);
comment on table public.metas_consumo is
  'Tabla 14. Límite mensual en kWh. Una sola meta activa por hogar.';

-- 15. alertas -----------------------------------------------------------------
create table public.alertas (
  id            uuid primary key default gen_random_uuid(),
  hogar_id      uuid not null references public.hogares(id) on delete cascade,
  categoria     text not null check (categoria in ('consumo', 'consejo', 'informacion')),
  severidad     text not null check (severidad in ('informativa', 'advertencia', 'critica')),
  titulo        text not null,
  mensaje       text not null,
  zona_id       uuid references public.zonas(id) on delete cascade,
  regla_origen  text not null,
  clave_evento  text not null unique,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
comment on table public.alertas is
  'Tabla 15. Avisos del hogar. clave_evento evita duplicados (DC-25, RN-XIV-08).';

-- 16. alertas_usuario ---------------------------------------------------------
create table public.alertas_usuario (
  alerta_id   uuid not null references public.alertas(id) on delete cascade,
  usuario_id  uuid not null references public.usuarios(id) on delete cascade,
  leida_en    timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  primary key (alerta_id, usuario_id)
);
comment on table public.alertas_usuario is
  'Tabla 16. Entrega y lectura individual de cada alerta (M:N alertas-usuarios).';

-- 17. consejos ----------------------------------------------------------------
create table public.consejos (
  id            uuid primary key default gen_random_uuid(),
  hogar_id      uuid not null references public.hogares(id) on delete cascade,
  categoria     text not null check (categoria in ('zona', 'general')),
  prioridad     text not null check (prioridad in ('baja', 'media', 'alta')),
  zona_id       uuid references public.zonas(id) on delete cascade,
  titulo        text not null,
  descripcion   text not null,
  regla_origen  text not null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  -- DC-24: «zona» lleva zona_id; «general» va sin zona.
  constraint consejos_categoria_coherente check (
    (categoria = 'zona' and zona_id is not null) or
    (categoria = 'general' and zona_id is null)
  )
);
comment on table public.consejos is
  'Tabla 17. Recomendaciones del hogar. categoria zona (con zona_id) o general (DC-24).';

-- 18. consejos_usuario --------------------------------------------------------
create table public.consejos_usuario (
  id             uuid primary key default gen_random_uuid(),
  consejo_id     uuid not null references public.consejos(id) on delete cascade,
  usuario_id     uuid not null references public.usuarios(id) on delete cascade,
  estado         text not null check (estado in ('pendiente', 'completada')),
  completada_en  timestamptz,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  constraint consejos_usuario_unico unique (consejo_id, usuario_id),
  constraint consejos_usuario_estado_coherente check (
    (estado = 'pendiente'  and completada_en is null) or
    (estado = 'completada' and completada_en is not null)
  )
);
comment on table public.consejos_usuario is
  'Tabla 18. Seguimiento individual de cada consejo (M:N consejos-usuarios).';
