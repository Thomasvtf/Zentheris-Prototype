# services/

Casos de uso, con los mismos nombres de archivo y de función que `routers/`. Además: `hour_recovery.py` (horas faltantes, RN-IV-05), `scheduler.py` (tareas programadas), `email.py` (invitaciones por SMTP) y `supabase_admin.py` (Supabase Auth y Storage con la clave de servicio, para eliminar la cuenta y la foto; nunca registra la clave ni el cuerpo de la respuesta).

- **Va:** el flujo de cada operación, las transacciones y las llamadas a `domain/` y `data/`.
- **No va:** FastAPI (request, response, decoradores) ni SQL directo.
- **Ejemplo:** `def get_household(user_id: UUID, hogar_id: UUID) -> Hogar`.
