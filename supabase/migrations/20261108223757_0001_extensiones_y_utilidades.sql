-- =============================================================================
-- Zentheris · Migración 01 · Extensiones, esquema privado y utilidades
-- Fuente: reglas v4.9 §3 «Integridad, seguridad y almacenamiento»,
--         especificación de Supabase v1 §4, registro DC-39 y DC-45.
-- Versión definitiva para el proyecto de la organización Zentheris (probada en zentheris-dev).
-- =============================================================================

-- btree_gist: permite la exclusión de tarifas solapadas por hogar (DC-39).
create extension if not exists btree_gist with schema extensions;

-- Esquema privado: funciones auxiliares que NO se exponen por la API REST.
-- (Supabase solo expone «public» y «graphql_public»; «privado» queda fuera.)
create schema if not exists privado;
revoke all on schema privado from public;
grant usage on schema privado to authenticated, service_role;

-- updated_at automático para todas las tablas propias (D-SQL-4 / DC-39).
create or replace function privado.fijar_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

comment on schema privado is
  'Zentheris: funciones auxiliares de RLS y triggers. No expuesto por la API.';
