"""Lecturas de consumo: inserción por lotes del backfill y de las horas recuperadas.

Esqueleto: se implementa en la sesión 4 (onboarding con backfill, B-01 a B-03).
"""

from collections.abc import Sequence
from typing import Any

from sqlmodel import Session


def insert_readings_batch(session: Session, lecturas: Sequence[dict[str, Any]]) -> int:
    """Inserta las lecturas en lote (COPY o INSERT de varias filas); devuelve cuántas guardó."""
    raise NotImplementedError("TODO(sesión 4): inserción por lotes (RN-X-03)")
