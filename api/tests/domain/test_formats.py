"""Formatos del backend (RN-XII-03, RN-X-03, RN-XII-08, RN-XI-09, DC-25).

Nombres de zona y de la fuente principal y meses iguales al catálogo es-CO; números es-CO; horas
HH:00 en Bogotá; clave de evento; textos de `config_files/textos-backend.es-CO.json`.
"""

import copy
import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from app.domain import formats as F
from app.domain.formats import ZONE_NAMES, main_source_name, zone_name
from app.domain.simulator import TIMEZONE
from app.domain.zone_rules import ZONE_TYPES

CATALOG_PATH = Path(__file__).resolve().parents[3] / "docs" / "textos" / "catalogo.es-CO.json"
BACKEND_TEXTS_PATH = Path(__file__).resolve().parents[2] / "app" / "config_files" / (
    "textos-backend.es-CO.json"
)


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


# ------------------------------------------------------------------ meses
def test_month_names_match_the_catalog() -> None:
    catalog = load_catalog()["formato"]["mes"]
    assert {f"{month:02d}": name for month, name in F.MONTH_NAMES.items()} == catalog
    assert tuple(F.MONTH_NAMES) == tuple(range(1, 13))


def test_month_names_cannot_be_modified() -> None:
    with pytest.raises(TypeError):
        F.MONTH_NAMES[1] = "Enero"  # type: ignore[index]


# ------------------------------------------------------------------ números es-CO (RN-XII-08)
@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "0,00"), (1.5, "1,50"), (0.256, "0,26"), (0.2549, "0,25"), (1234.5, "1.234,50"),
     (1234567.891, "1.234.567,89"), (-0.001, "0,00"), (-2.5, "-2,50")],
)
def test_format_kw(value: float, expected: str) -> None:
    assert F.format_kw(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "0,0"), (300.0, "300,0"), (1234.5, "1.234,5"), (12345.67, "12.345,7"),
     (999.96, "1.000,0"), (0.04, "0,0"), (-0.04, "0,0")],
)
def test_format_kwh(value: float, expected: str) -> None:
    assert F.format_kwh(value) == expected


# ------------------------------------------------------------------ horas
@pytest.mark.parametrize(("hour", "expected"), [(0, "00:00"), (7, "07:00"), (19, "19:00"),
                                                (23, "23:00")])
def test_format_hour(hour: int, expected: str) -> None:
    assert F.format_hour(datetime(2026, 11, 3, hour, tzinfo=TIMEZONE)) == expected


def test_format_hour_end_of_23_is_midnight() -> None:
    start = datetime(2026, 11, 3, 23, tzinfo=TIMEZONE)
    assert (F.format_hour(start), F.format_hour(start + timedelta(hours=1))) == ("23:00", "00:00")


def test_format_hour_uses_bogota() -> None:
    assert F.format_hour(datetime(2026, 11, 4, 3, 0, tzinfo=UTC)) == "22:00"  # 22:00 Bogotá


def test_format_hour_rejects_naive() -> None:
    with pytest.raises(ValueError):
        F.format_hour(datetime(2026, 11, 3, 9, tzinfo=TIMEZONE).replace(tzinfo=None))


# ------------------------------------------------------------------ clave de evento (DC-25)
def test_build_event_key_consumption() -> None:
    zona_id = UUID(int=7)
    assert F.build_event_key("consumo_critico", str(zona_id), "2026-11-03") == (
        f"consumo_critico:{zona_id}:2026-11-03")


def test_build_event_key_single_part() -> None:
    assert F.build_event_key("nuevo_consejo", "abc") == "nuevo_consejo:abc"


@pytest.mark.parametrize("parts", [("", "x"), ("regla", ""), ("re:gla", "x"), ("regla", "a:b"),
                                   ("regla",)])
def test_build_event_key_rejects_empty_or_colon(parts: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        F.build_event_key(*parts)


# ------------------------------------------------------------------ textos del backend
@lru_cache(maxsize=1)
def raw_backend_texts() -> dict[str, Any]:
    return json.loads(BACKEND_TEXTS_PATH.read_text(encoding="utf-8"))


def test_parse_backend_texts_from_config_file() -> None:
    texts = F.parse_backend_texts(raw_backend_texts())
    assert set(texts.alerts) >= set(F.REQUIRED_ALERT_RULES)
    elevated = texts.alerts["consumo_elevado"]
    assert (elevated.regla_origen, elevated.categoria, elevated.severidad) == (
        "consumo_elevado", "consumo", "advertencia")
    assert elevated.titulo == "Consumo elevado en {zona}"
    assert len(texts.tips) == 2 * 2 * len(ZONE_TYPES) + 2
    general = [t for t in texts.tips if t.zona is None]
    assert {(t.regla_origen, t.prioridad, t.variante) for t in general} == {
        ("cierre_mes_encima", "baja", 1), ("cierre_mes_encima", "baja", 2)}


def test_parse_backend_texts_every_zone_has_two_variants() -> None:
    texts = F.parse_backend_texts(raw_backend_texts())
    for rule in ("zona_elevada", "zona_critica"):
        for zone in ZONE_TYPES:
            variants = {t.variante for t in texts.tips if (t.regla_origen, t.zona) == (rule, zone)}
            assert variants == {1, 2}, (rule, zone)


def _broken(change) -> dict[str, Any]:
    raw = copy.deepcopy(raw_backend_texts())
    change(raw)
    return raw


@pytest.mark.parametrize(
    "change",
    [
        lambda raw: raw.pop("alertas"),
        lambda raw: raw.pop("consejos"),
        lambda raw: raw["alertas"].pop("consumo_critico"),
        lambda raw: raw["alertas"]["consumo_elevado"].pop("mensaje"),
        lambda raw: raw["alertas"]["consumo_elevado"].update(severidad="alta"),
        lambda raw: raw["alertas"]["consumo_elevado"].update(categoria="otra"),
        lambda raw: raw["alertas"]["consumo_elevado"].update(regla_origen="otra"),
        lambda raw: raw["alertas"]["consumo_elevado"].update(titulo=3),
        lambda raw: raw["consejos"].pop(0),
        lambda raw: raw["consejos"][0].update(variante=True),
        lambda raw: raw["consejos"][0].update(variante=3),
        lambda raw: raw["consejos"][0].update(prioridad="urgente"),
        lambda raw: raw["consejos"][0].update(zona="patio"),
        lambda raw: raw["consejos"][0].update(regla_origen="otra"),
        lambda raw: raw["consejos"][1].update(titulo=raw["consejos"][0]["titulo"]),
        lambda raw: raw["consejos"].append(dict(raw["consejos"][0])),
    ],
)
def test_parse_backend_texts_rejects_incomplete(change) -> None:
    with pytest.raises(ValueError):
        F.parse_backend_texts(_broken(change))


def test_render_backend_text() -> None:
    template = raw_backend_texts()["alertas"]["consumo_critico"]["mensaje"]
    text = F.render_backend_text(template, {"zona": "Cocina", "hora_ini": "19:00",
                                            "hora_fin": "20:00", "kw": "1,23"})
    assert text == ("Entre las 19:00 y las 20:00, Cocina tuvo un promedio de 1,23 kW, muy por "
                    "encima de lo habitual para esa hora.")


def test_render_backend_text_missing_variable() -> None:
    with pytest.raises(KeyError):
        F.render_backend_text("Consumo elevado en {zona}", {"kw": "1,00"})


def test_render_backend_text_keeps_braces_in_values_and_ignores_extras() -> None:
    assert F.render_backend_text("Hola {nombre}", {"nombre": "{hogar}", "otra": 1}) == (
        "Hola {hogar}")
    assert F.render_backend_text("Sin variables", {}) == "Sin variables"


@pytest.mark.parametrize("template", ["{zona.nombre}", "{zona!r}", "{kw:.2f}", "{}", "{0}"])
def test_render_backend_text_rejects_expressions(template: str) -> None:
    with pytest.raises(ValueError):
        F.render_backend_text(template, {"zona": "Cocina", "kw": 1.0, "0": "x"})


def test_backend_texts_use_only_declared_variables() -> None:
    """Cada plantilla se rellena con las variables de `_meta.variables_por_clave`."""
    raw = raw_backend_texts()
    declared = raw["_meta"]["variables_por_clave"]
    texts = F.parse_backend_texts(raw)
    for key, alert in texts.alerts.items():
        variables = dict.fromkeys(declared.get(f"alertas.{key}", {}), "x")
        F.render_backend_text(alert.titulo, variables)
        F.render_backend_text(alert.mensaje, variables)
    for tip in texts.tips:
        variables = dict.fromkeys(declared["consejos.*.descripcion"], "x")
        F.render_backend_text(tip.titulo, {})
        F.render_backend_text(tip.descripcion, variables)
