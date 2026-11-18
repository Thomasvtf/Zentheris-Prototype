# services/

Casos de uso, con los mismos nombres de archivo y de función que `routers/`. Además: `hour_recovery.py` (horas faltantes, RN-IV-05), `scheduler.py` (tareas programadas) y `email.py` (invitaciones por SMTP).

- **Va:** el flujo de cada operación, las transacciones y las llamadas a `domain/` y `data/`.
- **No va:** FastAPI (request, response, decoradores) ni SQL directo.
- **Ejemplo:** `def get_household(user_id: UUID, hogar_id: UUID) -> Hogar`.
