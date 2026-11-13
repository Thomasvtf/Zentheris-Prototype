-- =============================================================================
-- Zentheris · Migración 05 · Storage: bucket privado «avatares»
-- Fuente: RN-I-02, DC-43, especificación de Supabase v1 §3.
-- Ruta: {usuario_id}/avatar.{jpg|png|webp}; máximo 2 MB.
-- Única escritura directa de la app (DC-40). La app muestra la foto con URL firmada.
-- =============================================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('avatares', 'avatares', false, 2097152, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
  set public = excluded.public,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- Leer: el dueño y los miembros activos de su mismo hogar.
create policy avatares_leer on storage.objects
  for select to authenticated
  using (
    bucket_id = 'avatares'
    and (
      (storage.foldername(name))[1] = (select auth.uid())::text
      or privado.comparte_hogar((storage.foldername(name))[1])
    )
  );

-- Subir: solo en su propia carpeta y con el nombre avatar.<ext>.
create policy avatares_subir on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'avatares'
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and storage.filename(name) ~ '^avatar\.(jpg|png|webp)$'
  );

-- Reemplazar: solo el dueño.
create policy avatares_actualizar on storage.objects
  for update to authenticated
  using (bucket_id = 'avatares' and (storage.foldername(name))[1] = (select auth.uid())::text)
  with check (
    bucket_id = 'avatares'
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and storage.filename(name) ~ '^avatar\.(jpg|png|webp)$'
  );

-- Borrar: solo el dueño.
create policy avatares_borrar on storage.objects
  for delete to authenticated
  using (bucket_id = 'avatares' and (storage.foldername(name))[1] = (select auth.uid())::text);
