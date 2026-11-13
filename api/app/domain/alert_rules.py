"""Reglas de alertas y consejos (RN-XIV-07, RN-XV-07).

Solo sobre horas en vivo, nunca sobre el backfill (A-02). Esqueleto: se implementa en la
sesión de alertas (pruebas A-01 a A-05).
"""

from collections.abc import Mapping, Sequence
from typing import Any


def evaluate_alert_rules(contexto: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    """Evalúa las reglas de alerta del catálogo (`regla_origen`, DC-25) para una hora."""
    raise NotImplementedError("TODO(sesión de alertas): reglas de alerta (RN-XIV-07)")


def build_tips(contexto: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    """Construye los consejos de zona y generales que correspondan (RN-XV-07)."""
    raise NotImplementedError("TODO(sesión de alertas): consejos (RN-XV-07)")
