"""Recuperación de horas faltantes (RN-IV-05, DC-34).

Antes de responder consumo, historial, fuentes o alertas se completan las horas que
faltan desde la última lectura. Esqueleto: se implementa en la sesión 5.
"""

from uuid import UUID


def fill_missing_hours(hogar_id: UUID) -> int:
    """Genera y guarda las lecturas que faltan del hogar; devuelve cuántas horas completó."""
    raise NotImplementedError("TODO(sesión 5): recuperación de horas (RN-IV-05, DC-34)")
