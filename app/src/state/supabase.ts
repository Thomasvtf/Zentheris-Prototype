/**
 * Cliente de Supabase, solo para Auth y para subir la foto de perfil (Storage). Todo lo
 * demás pasa por la API (CLAUDE.md, DC-56).
 *
 * Se crea al primer uso, no al importar: así la app arranca aunque falte app/.env.
 * Variables: EXPO_PUBLIC_SUPABASE_URL y EXPO_PUBLIC_SUPABASE_ANON_KEY (la clave anon es
 * pública por diseño; la service_role nunca va en la app).
 */
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

import { secureStoreAdapter } from './session';

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (client) return client;
  const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    throw new Error('Faltan EXPO_PUBLIC_SUPABASE_URL o EXPO_PUBLIC_SUPABASE_ANON_KEY en app/.env.');
  }
  client = createClient(url, anonKey, {
    auth: {
      storage: secureStoreAdapter,
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  });
  return client;
}
