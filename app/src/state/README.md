# state/

- `queryClient.ts` y `queryKeys.ts`: React Query para los datos del servidor. La clave empieza por el operationId: `queryKey('obtenerHogar', hogarId)`.
- `supabase.ts`: cliente de Supabase **solo para Auth y Storage** (todo lo demás va por la API). Se crea al primer uso.
- `session.ts`: guarda la sesión con `expo-secure-store` y entrega el token al cliente de la API (`connectSessionToApi`).
- **No va:** datos del servidor guardados a mano ni llamadas a tablas de Supabase.
