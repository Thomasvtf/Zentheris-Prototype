"""F01 a F10 de la referencia (Avance 03, `pruebas/test_conjuntos_finales.py`).

Se aplican a los conjuntos oficiales de `docs/datos/perfiles/` y a la semilla de la migración 06.
"""

import hashlib
import json
import math
import re

from app.domain.simulator.engine import simulate_backfill, simulate_household
from app.domain.simulator.validation import noise_margin, validate_profile_set
from app.domain.zone_rules import EXTRA_ZONES, PERSONALITIES
from tests.helpers.personalities import PROFILES_PATH, PROFILES_SHA256
from tests.simulator.support import (
    PROFILES_DIR,
    REPO_ROOT,
    bogota,
    contains_credential,
    create_household,
    final_profiles,
    frozen_references,
    idx,
    personality_file_name,
    zones_without_parameters,
)
from tests.zones.selections import enumerate_selections

SEED_MIGRATION = (
    REPO_ROOT / "supabase/migrations/20261108224101_0006_semilla_perfiles_simulacion.sql"
)
RULES = REPO_ROOT / "docs/reglas/reglas-de-negocio.md"


def test_f01_structure():
    """F01 Los cinco JSON finales pasan el validador y tienen los cinco nombres (CT01–CT05)."""
    assert validate_profile_set(list(final_profiles().values())) == []


def test_f02_consolidated_is_identical():
    """F02 El consolidado contiene exactamente los mismos cinco conjuntos."""
    consolidated = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    profiles = final_profiles()
    assert consolidated == [profiles[name] for name in PERSONALITIES]


def test_f03_applicable_zones_are_covered():
    """F03 Toda zona que una personalidad puede recibir (incluido el respaldo) tiene base > 0."""
    assert zones_without_parameters(final_profiles()) == []


def test_f04_justified_zeros():
    """F04 Solo tienen base 0 las zonas que la personalidad nunca recibe."""
    profiles = final_profiles()
    compact = profiles["Consumo compacto"]
    assert [z for z in EXTRA_ZONES if compact[f"base_{z}_kwh_dia"] == 0] == list(EXTRA_ZONES)
    assert profiles["Consumo intermedio"]["base_cuarto_servicio_kwh_dia"] == 0


def test_f05_noise_margin_and_centered_humor():
    """F05 σ/(1−φ) < 1 y humor simétrico alrededor de 1 (E[H] = 1)."""
    for name, profile in final_profiles().items():
        assert noise_margin(profile) < 1, name
        middle = (profile["humor_min"] + profile["humor_max"]) / 2
        assert round(abs(middle - 1.0), 12) == 0, name


def test_f06_sql_comes_from_these_files():
    """F06 La semilla SQL declara el SHA-256 de estos archivos y no contiene DELETE.

    Adaptada: la referencia revisa el SQL del zip (un INSERT por conjunto). Aquí la semilla es la
    migración 06, que declara el SHA-256 del consolidado y lleva su contenido minificado; el de
    cada archivo está en la sección 8.1 de las reglas.
    """
    sql = SEED_MIGRATION.read_text(encoding="utf-8")
    assert hashlib.sha256(PROFILES_PATH.read_bytes()).hexdigest() == PROFILES_SHA256
    assert PROFILES_SHA256 in sql

    (embedded,) = re.findall(r"\$semilla\$(.*?)\$semilla\$", sql, flags=re.DOTALL)
    assert json.loads(embedded) == json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    # Se declara en el comentario y en la comprobación dentro de la base.
    assert sql.count(hashlib.sha256(embedded.encode("utf-8")).hexdigest()) == 2

    rules = RULES.read_text(encoding="utf-8")
    for name in PERSONALITIES:
        file_name = personality_file_name(name)
        digest = hashlib.sha256((PROFILES_DIR / file_name).read_bytes()).hexdigest()
        assert f"| `{file_name}` | {digest} |" in rules

    assert re.search(r"\b(DELETE|TRUNCATE|DROP)\b", sql.upper()) is None
    assert sql.lower().count("on conflict (nombre) do update set") == 1


def test_f07_no_credentials():
    """F07 Ningún archivo final contiene patrones de credenciales."""
    paths = sorted(PROFILES_DIR.glob("*.json"))
    assert len(paths) == 6
    for path in [*paths, SEED_MIGRATION]:
        assert not contains_credential(path.read_text(encoding="utf-8")), path.name


def test_f08_backfill_720_with_final_profiles():
    """F08 Backfill de 720 h con cada conjunto final en su hogar de referencia: finito y >= 0."""
    for name, profile in final_profiles().items():
        reference = frozen_references()[name]
        household = create_household(f"f08|{name}", reference["vivienda"], reference["zonas"])
        now = bogota(2026, 10, 28, 15, 23)
        series = simulate_backfill(household.id, profile, household.zones, now)
        assert set(series) == set(reference["zonas"])
        for readings in series.values():
            assert len(readings) == 720
            assert all(math.isfinite(r.total) and r.total >= 0 for r in readings)


def test_f09_the_147_with_final_profiles():
    """F09 Las 147 combinaciones válidas simulan 2 días con su conjunto, solo con sus zonas."""
    profiles = final_profiles()
    start = idx(2026, 11, 7)
    count = 0
    for housing, zones, valid, personality in enumerate_selections():
        if not valid:
            continue
        household = create_household(f"f09|{count}", housing, zones)
        series = simulate_household(
            household.id, profiles[personality], household.zones, start, start + 48
        )
        assert set(series) == set(zones)
        for zone, readings in series.items():
            assert sum(reading.total for reading in readings) > 0, (housing, zone)
        count += 1
    assert count == 147


def test_f10_no_metadata_in_json():
    """F10 Sin claves explicativas, 'default' ni fuentes dentro de los JSON (solo contrato)."""
    for profile in final_profiles().values():
        text = json.dumps(profile, ensure_ascii=False)
        assert re.search(r'"(default|fuente|nota|descripcion|supuesto)"', text) is None
