"""Reglas de zonas del onboarding según el tipo de vivienda (RN-X-02).

Esqueleto: se implementa en la sesión 4 (pruebas Z-01 a Z-03).
"""

from collections.abc import Sequence


def validate_zones(tipo_vivienda: str, zonas: Sequence[str]) -> None:
    """Valida las zonas elegidas; si no cumplen, indica el `CodigoError` que corresponde

    (`ZONAS_NO_PERMITIDAS`, `ZONAS_BASICAS_FALTANTES`, `CANTIDAD_ZONAS_INVALIDA` o
    `ZONAS_DUPLICADAS`).
    """
    raise NotImplementedError("TODO(sesión 4): reglas de zonas (RN-X-02)")
