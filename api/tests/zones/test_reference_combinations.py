"""K01 a K09 de la referencia (Avance 03, `pruebas/test_combinaciones.py`), RN-X-02 y RN-X-04.

K10 a K12 usan el simulador y viven en tests/simulator/. Los datos de `data/` son copias
exactas de los insumos del zip (su SHA-256 está en el MANIFEST).
"""

import csv
import hashlib
from collections import Counter
from pathlib import Path

import pytest

from app.domain.zone_rules import (
    BASIC_ZONES,
    PERSONALITIES,
    ZONE_TYPES,
    ZoneRuleError,
    assign_personality,
    resolve_active_personality,
    validate_zones,
)
from tests.zones.data.auditar_contrato_avance01 import asignar as assign_avance01
from tests.zones.selections import (
    EXAMPLES_TABLE_12,
    Selection,
    applicable_zones,
    enumerate_selections,
)

CSV_PATH = Path(__file__).parent / "data" / "combinaciones_validas_avance01.csv"
CSV_SHA256 = "be0959e220aa4cdc47e0faee63d96d2c801e97372ff8c6be6b10fed8c9f47cd1"

ALL_ACTIVE = dict.fromkeys(PERSONALITIES, True)


@pytest.fixture(scope="module")
def selections() -> list[Selection]:
    return list(enumerate_selections())


@pytest.fixture(scope="module")
def valid(selections: list[Selection]) -> list[tuple[str, tuple[str, ...], str]]:
    return [(housing, zones, name) for housing, zones, ok, name in selections if ok]


def test_reference_csv_is_an_exact_copy() -> None:
    """El CSV es el del Avance 01. El original usa CRLF; git puede dejarlo en LF (CI en Linux)."""
    content = CSV_PATH.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    assert hashlib.sha256(content).hexdigest() == CSV_SHA256


def test_k01_enumeration(selections, valid) -> None:
    """K01 2.560 selecciones: 147 válidas y 2.413 rechazadas (R02)."""
    assert len(selections) == 2560
    assert len(valid) == 147
    assert len(selections) - len(valid) == 2413


def test_k02_matches_avance01(valid) -> None:
    """K02 Las 147 combinaciones y su personalidad coinciden con el CSV del Avance 01."""
    with CSV_PATH.open(encoding="utf-8", newline="") as file:
        expected = {
            (row["vivienda"], frozenset(row["zonas"].split("|"))): row["personalidad"]
            for row in csv.DictReader(file)
        }
    assert len(expected) == 147
    assert {(housing, frozenset(zones)): name for housing, zones, name in valid} == expected


def test_k03_differential_against_avance01(selections) -> None:
    """K03 Mismas decisiones que la implementación del Avance 01 en las 2.560."""
    for housing, zones, _, name in selections:
        try:
            other = assign_avance01(housing, list(zones))
        except ValueError:
            other = None
        assert name == other, (housing, zones)


def test_k04_examples_of_table_12() -> None:
    """K04 Los 13 ejemplos de la tabla 12 (R03)."""
    for housing, zones, expected in EXAMPLES_TABLE_12:
        assert assign_personality(housing, zones) == expected, (housing, zones)


def test_k05_count_by_personality(valid) -> None:
    """K05 Combinaciones ordinarias por personalidad: 13, 9, 13, 49, 63."""
    count = Counter(name for _, _, name in valid)
    assert [count[name] for name in PERSONALITIES] == [13, 9, 13, 49, 63]


def test_k06_country_house_goes_up_one_level(valid) -> None:
    """K06 Casa campestre = casa + 1 nivel, con tope en amplio (R04)."""
    next_level = {
        "Consumo eficiente": "Consumo intermedio",
        "Consumo intermedio": "Consumo familiar",
        "Consumo familiar": "Consumo amplio",
        "Consumo amplio": "Consumo amplio",
    }
    country = [(zones, name) for housing, zones, name in valid if housing == "casa_campestre"]
    assert len(country) == 32
    for zones, name in country:
        assert name == next_level[assign_personality("casa", zones)], zones


def test_k07_fallback() -> None:
    """K07 Asignada inactiva o ausente => eficiente; si eficiente falta, error (R05, A20)."""
    large, fallback = "Consumo amplio", "Consumo eficiente"
    assert resolve_active_personality(large, ALL_ACTIVE) == large
    assert resolve_active_personality(large, {**ALL_ACTIVE, large: False}) == fallback
    assert resolve_active_personality(large, {fallback: True}) == fallback
    with pytest.raises(LookupError):
        resolve_active_personality(large, {**ALL_ACTIVE, large: False, fallback: False})
    with pytest.raises(LookupError):
        resolve_active_personality(large, {})
    # Eficiente inactiva no afecta a otra personalidad activa.
    assert resolve_active_personality(large, {**ALL_ACTIVE, fallback: False}) == large


@pytest.mark.parametrize("name", PERSONALITIES)
def test_k07_fallback_for_each_personality(name: str) -> None:
    """K07 (por personalidad) activa se conserva; ausente usa el respaldo."""
    assert resolve_active_personality(name, ALL_ACTIVE) == name
    assert resolve_active_personality(name, {"Consumo eficiente": True}) == "Consumo eficiente"


@pytest.mark.parametrize(
    ("housing", "zones", "code"),
    [
        ("apartaestudio", (*BASIC_ZONES, "terraza"), "ZONAS_NO_PERMITIDAS"),
        ("apartaestudio", ("cocina", "sala", "oficina"), "CANTIDAD_ZONAS_INVALIDA"),
        ("apartaestudio", (*BASIC_ZONES, "oficina", "lavanderia"), "CANTIDAD_ZONAS_INVALIDA"),
        ("apartamento", ("cocina", "sala", "bano"), "ZONAS_BASICAS_FALTANTES"),
        ("apartamento", (*BASIC_ZONES, "cocina"), "ZONAS_DUPLICADAS"),
        # Fuera de catálogo: `ValueError` sin código (no hay `CodigoError` para ellos).
        ("apartamento", (*BASIC_ZONES, "patio"), None),
        ("loft", BASIC_ZONES, None),
    ],
)
def test_k08_onboarding_rejections(housing: str, zones: tuple[str, ...], code: str | None) -> None:
    """K08 Rechazos: zona repetida/desconocida, extras en apartaestudio, faltan básicas, vivienda
    desconocida; y el código de cada uno."""
    with pytest.raises(ValueError) as error:
        validate_zones(housing, zones)
    if code is None:
        assert not isinstance(error.value, ZoneRuleError)
    else:
        assert isinstance(error.value, ZoneRuleError)
        assert error.value.code == code


def test_k08_code_of_every_rejected_selection(selections) -> None:
    """K08 (ampliada) código de los 2.413 rechazos, contado con un oráculo independiente."""
    codes: Counter[str] = Counter()
    for housing, zones, ok, _ in selections:
        if ok:
            continue
        with pytest.raises(ZoneRuleError) as error:
            validate_zones(housing, zones)
        codes[error.value.code] += 1
    # Apartaestudio: 2^9 − 2^6 = 448 con alguna extra; 2^6 − 19 válidas = 45 por cantidad.
    # Los otros cuatro tipos: 4 × (2^9 − 2^5) = 1.920 sin las 4 básicas.
    assert codes == {
        "ZONAS_NO_PERMITIDAS": 448,
        "CANTIDAD_ZONAS_INVALIDA": 45,
        "ZONAS_BASICAS_FALTANTES": 1920,
    }


def test_k09_applicable_zones() -> None:
    """K09 Unión de zonas por personalidad (Avance 01) y nueve para eficiente por respaldo (A19)."""
    zones = applicable_zones()
    assert set(zones) == set(PERSONALITIES)
    assert zones["Consumo compacto"] == {*BASIC_ZONES, "oficina", "lavanderia"}
    assert zones["Consumo intermedio"] == {
        *BASIC_ZONES,
        "oficina",
        "lavanderia",
        "terraza",
        "garaje",
    }
    for name in ("Consumo eficiente", "Consumo familiar", "Consumo amplio"):
        assert zones[name] == set(ZONE_TYPES)
