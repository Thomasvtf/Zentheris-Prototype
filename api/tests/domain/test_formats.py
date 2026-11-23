"""Nombres de zona y de la fuente principal, iguales al catálogo es-CO (RN-XII-03, RN-X-03)."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from app.domain.formats import ZONE_NAMES, main_source_name, zone_name
from app.domain.zone_rules import ZONE_TYPES

CATALOG_PATH = Path(__file__).resolve().parents[3] / "docs" / "textos" / "catalogo.es-CO.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_zone_names_match_the_catalog() -> None:
    assert dict(ZONE_NAMES) == load_catalog()["zona"]


def test_zone_names_cover_the_nine_types() -> None:
    assert tuple(ZONE_NAMES) == ZONE_TYPES


@pytest.mark.parametrize("zone_type", ZONE_TYPES)
def test_zone_name(zone_type: str) -> None:
    assert zone_name(zone_type) == load_catalog()["zona"][zone_type]


def test_zone_name_out_of_catalog() -> None:
    with pytest.raises(KeyError):
        zone_name("patio")


def test_zone_names_cannot_be_modified() -> None:
    with pytest.raises(TypeError):
        ZONE_NAMES["cocina"] = "Otra"  # type: ignore[index]


@pytest.mark.parametrize("household", ["Casa Pérez", "Apto 301", "El {hogar} de Ana", " Mi  casa "])
def test_main_source_name_matches_the_catalog(household: str) -> None:
    """El nombre del hogar se conserva tal cual, aunque traiga llaves o espacios."""
    template = load_catalog()["fuentes"]["principal_nombre"]
    assert main_source_name(household) == template.replace("{hogar}", household, 1)


def test_main_source_name_example() -> None:
    assert main_source_name("Casa Pérez") == "Fuente principal Casa Pérez"
