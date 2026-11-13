/**
 * Cliente de React Query para los datos del servidor (app/CLAUDE.md: React Query para
 * datos del servidor; Supabase solo para Auth y Storage).
 *
 * Con las opciones por defecto de React Query; se ajustan cuando existan las pantallas.
 */
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient();
