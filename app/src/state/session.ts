/**
 * Sesión de Supabase Auth guardada con expo-secure-store, y entrega del token al cliente
 * de la API (src/api/client.ts).
 *
 * TODO(sesión 10): SecureStore limita cada valor a unos 2 KB; si la sesión los supera, se
 * cambia este adaptador antes de implementar el inicio de sesión.
 */
import * as SecureStore from 'expo-secure-store';

import { setAccessTokenProvider } from '@/api/client';

import { getSupabase } from './supabase';

/** Adaptador de almacenamiento para supabase-js (auth.storage). */
export const secureStoreAdapter = {
  getItem: (key: string) => SecureStore.getItemAsync(key),
  setItem: (key: string, value: string) => SecureStore.setItemAsync(key, value),
  removeItem: (key: string) => SecureStore.deleteItemAsync(key),
};

/** Registra el token de la sesión actual como token de las peticiones a la API. */
export function connectSessionToApi(): void {
  setAccessTokenProvider(async () => {
    const { data } = await getSupabase().auth.getSession();
    return data.session?.access_token ?? null;
  });
}
