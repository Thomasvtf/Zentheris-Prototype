"""Reglas del historial: comparación, pico y proyección (RN-XIII, DC-29 a DC-31).

Esqueleto: se implementa en la sesión 6 (pruebas U-02 y U-03).
"""

from collections.abc import Sequence


def compare_periods(actual_kwh: float, anterior_kwh: float | None) -> str:
    """Compara el periodo actual con el anterior y devuelve el estado de la comparación."""
    raise NotImplementedError("TODO(sesión 6): comparación entre periodos (RN-XIII)")


def detect_peak(valores_kwh: Sequence[float], promedio_kwh: float) -> int | None:
    """Devuelve la posición del pico máximo de la serie, o None si no hay pico (U-02)."""
    raise NotImplementedError("TODO(sesión 6): pico (DC-29 a DC-31)")


def project_period(
    acumulado_kwh: float,
    promedios_horas_restantes_hoy: Sequence[float],
    dias_completos_restantes: int,
    promedio_diario_30d: float,
) -> float:
    """Proyecta el consumo al cierre del periodo (U-03)."""
    raise NotImplementedError("TODO(sesión 6): proyección de cierre (U-03)")
