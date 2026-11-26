"""Detección interna de la restricción violada en una IntegrityError (DC-39, DC-41).

Compartida por los módulos de app.data que traducen una restricción concreta a una excepción
propia (tarifas y metas). Mismo criterio que `invitations._violates_pending_invitation_index`:
el SQLSTATE debe coincidir y el nombre sale de `diag.constraint_name`; si el controlador no lo
trae, del mensaje de Postgres (el nombre entre comillas dobles).
"""

from collections.abc import Mapping

from sqlalchemy.exc import IntegrityError

# SQLSTATE de Postgres por tipo de restricción.
UNIQUE_VIOLATION = "23505"
CHECK_VIOLATION = "23514"
EXCLUSION_VIOLATION = "23P01"


def violated_constraint(exc: IntegrityError, expected: Mapping[str, str]) -> str | None:
    """El nombre de la restricción de `expected` (nombre → SQLSTATE) que violó `exc`, o None.

    None si el SQLSTATE no es el de esa restricción, si no hay SQLSTATE o si el nombre no se
    puede leer. Si `diag.constraint_name` viene, manda sobre el mensaje.
    """
    pgcode = getattr(exc.orig, "pgcode", None)
    if pgcode is None:
        return None
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name is not None:
        return constraint_name if expected.get(constraint_name) == pgcode else None
    message = str(exc.orig)
    for name, sqlstate in expected.items():
        if sqlstate == pgcode and f'"{name}"' in message:
            return name
    return None
