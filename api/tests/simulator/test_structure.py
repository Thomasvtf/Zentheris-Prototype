"""E01 a E16 de la referencia (Avance 03, `pruebas/test_estructura.py`): estructura del perfil."""

import copy
import json

import pytest

from app.domain.simulator.validation import (
    ProfileParameterError,
    load_strict_json,
    validate_or_raise,
    validate_profile,
    validate_profile_set,
)
from tests.simulator.support import (
    Profile,
    contains_credential,
    sample_profile,
    sample_profiles,
)


def codes(profile: object, **options: bool) -> set[str]:
    return {code for code, _ in validate_profile(profile, **options)}


def as_text(profile: Profile) -> str:
    return json.dumps(profile, ensure_ascii=False)


def test_e01_sample_profiles_are_valid():
    """E01 Los cinco conjuntos de prueba pasan el validador (CT01–CT05)."""
    for name, profile in sample_profiles().items():
        assert validate_profile(profile) == [], name


def test_e02_five_names_without_collision():
    """E02 Exactamente cinco nombres exactos; duplicado o faltante se rechaza (CT01)."""
    profiles = list(sample_profiles().values())
    assert validate_profile_set(profiles) == []
    repeated = [*profiles[:4], copy.deepcopy(profiles[0])]
    assert "cinco_nombres" in {code for code, _ in validate_profile_set(repeated)}
    other = copy.deepcopy(profiles[0])
    other["nombre"] = "Consumo Compacto"
    assert "nombre" in codes(other)


def test_e03_duplicated_key():
    """E03 JSON con clave duplicada se rechaza al leer (CT02)."""
    text = as_text(sample_profile()).replace('"activo": true', '"activo": true, "activo": false')
    with pytest.raises(ProfileParameterError):
        load_strict_json(text)


def test_e04_nan_and_infinity():
    """E04 NaN, Infinity y -Infinity se rechazan al leer (CT02)."""
    for literal in ("NaN", "Infinity", "-Infinity"):
        text = as_text(sample_profile()).replace('"humor_min": 0.9', f'"humor_min": {literal}')
        with pytest.raises(ProfileParameterError):
            load_strict_json(text)
    profile = sample_profile()
    profile["humor_min"] = float("nan")
    assert "humor_min_tipo" in codes(profile)


def test_e05_unknown_and_missing_fields():
    """E05 Campo fuera del contrato o faltante se rechaza; sin campos explicativos."""
    profile = sample_profile()
    profile["fuente"] = "narrativa"
    assert "clave_desconocida" in codes(profile)
    profile = sample_profile()
    del profile["base_garaje_kwh_dia"]
    assert "campo_faltante" in codes(profile)
    profile = sample_profile()
    profile["picos_config"]["cocina"]["nota"] = "x"
    assert "pico_clave_desconocida" in codes(profile)


def test_e06_booleans_and_strings_are_not_numbers():
    """E06 true/false o "1.2" no cuentan como números (CT02)."""
    profile = sample_profile()
    profile["base_sala_kwh_dia"] = True
    assert "base_tipo" in codes(profile)
    profile = sample_profile()
    profile["factor_fin_semana"] = "1.1"
    assert "factor_fin_semana_tipo" in codes(profile)
    profile = sample_profile()
    profile["ruido_config"]["memoria"] = False
    assert "ruido_memoria" in codes(profile)
    profile = sample_profile()
    profile["activo"] = 1
    assert "activo" in codes(profile)


def test_e07_bases():
    """E07 Bases >= 0 y con máximo 4 decimales (NUMERIC(10,4))."""
    profile = sample_profile()
    profile["base_bano_kwh_dia"] = -0.0001
    assert "base_negativa" in codes(profile)
    profile["base_bano_kwh_dia"] = 0.12345
    assert "base_precision" in codes(profile)
    profile["base_bano_kwh_dia"] = 0
    assert validate_profile(profile) == []


def test_e08_humor_and_factor():
    """E08 humor ordenado y >= 0; factor > 0; NUMERIC(6,4)."""
    profile = sample_profile()
    profile["humor_min"], profile["humor_max"] = 1.2, 1.1
    assert "humor_invertido" in codes(profile)
    profile = sample_profile()
    profile["humor_min"] = -0.1
    assert "humor_negativo" in codes(profile)
    profile = sample_profile()
    profile["factor_fin_semana"] = 0
    assert "factor_no_positivo" in codes(profile)
    profile = sample_profile()
    profile["humor_max"] = 100.0
    assert "humor_max_precision" in codes(profile)


def test_e09_curves():
    """E09 base obligatoria; 24 valores finitos >= 0; suma 1 ± 1e-10; claves de zona (CT03)."""
    profile = sample_profile()
    del profile["curva_horaria"]["base"]
    assert "curva_base" in codes(profile)
    profile = sample_profile()
    profile["curva_horaria"]["base"] = profile["curva_horaria"]["base"][:23]
    assert "curva_longitud" in codes(profile)
    profile = sample_profile()
    profile["curva_horaria"]["base"][0] = -0.01
    profile["curva_horaria"]["base"][1] = 0.03
    assert "curva_negativa" in codes(profile)
    profile = sample_profile()
    profile["curva_horaria"]["base"][0] += 1e-9
    assert "curva_suma" in codes(profile)
    profile = sample_profile()
    profile["curva_horaria"]["cocinas"] = profile["curva_horaria"]["base"]
    assert "curva_clave" in codes(profile)
    profile = sample_profile()
    profile["curva_horaria"]["sala"] = profile["curva_horaria"]["base"]
    assert validate_profile(profile) == []


def test_e10_noise():
    """E10 ruido solo memoria/intensidad comunes; 0<=φ<1; σ>=0; sin default ni por zona (CT04)."""
    profile = sample_profile()
    profile["ruido_config"]["memoria"] = 1.0
    assert "ruido_memoria" in codes(profile)
    profile = sample_profile()
    profile["ruido_config"]["intensidad"] = -0.01
    assert "ruido_intensidad" in codes(profile)
    profile = sample_profile()
    profile["ruido_config"]["default"] = {"memoria": 0.6, "intensidad": 0.05}
    assert "ruido_clave" in codes(profile)
    profile = sample_profile()
    profile["ruido_config"]["cocina"] = {"memoria": 0.4, "intensidad": 0.1}
    assert "ruido_clave" in codes(profile)


def test_e11_noise_margin():
    """E11 σ/(1−φ) >= 1 se rechaza en conjuntos finales; permitido solo en modo contrato (CT05)."""
    profile = sample_profile()
    profile["ruido_config"] = {"memoria": 0.5, "intensidad": 0.5}
    assert "ruido_margen" in codes(profile)
    assert "ruido_margen" not in codes(profile, require_noise_margin=False)


def test_e12_peak_ranges():
    """E12 rangos [min,max] ordenados; minuto entero 0–59; fracción 0–1; potencia/duración >= 0."""
    cases = [
        ("potencia_w", [1800, 1000], "pico_rango_invertido"),
        ("duracion_min", [-5, 10], "pico_rango_limite"),
        ("minuto_inicio", [0, 60], "pico_rango_limite"),
        ("minuto_inicio", [0.5, 59], "pico_rango_entero"),
        ("fraccion_uso", [0.5, 1.2], "pico_rango_limite"),
        ("potencia_w", [1000], "pico_rango"),
    ]
    for key, value, code in cases:
        profile = sample_profile()
        profile["picos_config"]["cocina"][key] = value
        assert code in codes(profile), (key, value)


def test_e13_probabilities_and_slots():
    """E13 probabilidad en [0,1] antes y después de franja; franjas [desde,hasta) sin solape

    (A05)."""

    def with_kitchen(**changes: object) -> Profile:
        profile = sample_profile()
        profile["picos_config"]["cocina"].update(changes)
        return profile

    def slot(start: int, end: int) -> dict[str, float]:
        return {"desde": start, "hasta": end, "multiplicador": 2}

    assert "pico_probabilidad" in codes(with_kitchen(probabilidad=1.2))
    # 0,6 × 2 en la franja = 1,2
    assert "pico_probabilidad_efectiva" in codes(with_kitchen(probabilidad=0.6))
    assert "franja_limites" in codes(with_kitchen(franjas=[slot(21, 18)]))
    assert "franja_solapada" in codes(with_kitchen(franjas=[slot(18, 21), slot(20, 22)]))
    assert "franja_claves" in codes(with_kitchen(franjas=[{"desde": 18, "hasta": 21}]))
    # 0,5 × 2 = 1, permitido
    assert validate_profile(with_kitchen(probabilidad=0.5)) == []


def test_e14_peak_keys():
    """E14 picos solo por zona del catálogo; sin 'default'; campos completos."""
    profile = sample_profile()
    profile["picos_config"]["default"] = copy.deepcopy(profile["picos_config"]["cocina"])
    assert "pico_clave" in codes(profile)
    profile = sample_profile()
    del profile["picos_config"]["cocina"]["franjas"]
    assert "pico_campo_faltante" in codes(profile)
    profile = sample_profile()
    profile["picos_config"] = {}
    assert validate_profile(profile) == []


def test_e15_database_managed_fields():
    """E15 id/created_at/updated_at opcionales y con formato válido."""
    profile = sample_profile()
    profile["id"] = "no-es-uuid"
    assert "id" in codes(profile)
    profile = sample_profile()
    profile["id"] = "8b6f1c9e-2b1a-4c1e-9a77-0e0f6f1d2c3b"
    profile["created_at"] = "2026-10-28T10:00:00-05:00"
    assert validate_profile(profile) == []


def test_e16_credential_scan():
    """E16 el detector de credenciales marca patrones típicos y no los datos de prueba."""
    assert contains_credential("x eyJhbGciOiJIUzI1NiIsInR5cCI6.abc")
    assert not contains_credential(as_text(sample_profile()))


# ------------------------------------------------ fuera de la referencia
def test_validate_or_raise_returns_the_same_profile_or_lists_the_errors():
    profile = sample_profile()
    assert validate_or_raise(profile) is profile
    profile["humor_min"] = -0.1
    with pytest.raises(ProfileParameterError) as caught:
        validate_or_raise(profile)
    assert [code for code, _ in caught.value.errors] == ["humor_negativo"]


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("curva_horaria", [], "curva_tipo"),
        ("ruido_config", [], "ruido_tipo"),
        ("picos_config", [], "picos_tipo"),
        ("picos_config", {"cocina": []}, "pico_tipo"),
        ("created_at", "ayer", "created_at"),
        ("created_at", None, "created_at"),
        ("id", 7, "id"),
        ("factor_fin_semana", 1.00001, "factor_fin_semana_precision"),
    ],
)
def test_malformed_fields_are_reported(field: str, value: object, code: str):
    profile = sample_profile()
    profile[field] = value
    assert code in codes(profile)


def test_profile_must_be_an_object():
    assert codes([]) == {"tipo"}


@pytest.mark.parametrize(
    ("slots", "code"),
    [
        ("18-21", "franja_tipo"),
        ([{"desde": 1.5, "hasta": 3, "multiplicador": 1}], "franja_valor"),
        ([{"desde": 1, "hasta": 3, "multiplicador": -1}], "franja_multiplicador"),
    ],
)
def test_malformed_slots_are_reported(slots: object, code: str):
    profile = sample_profile()
    profile["picos_config"]["cocina"]["franjas"] = slots
    assert code in codes(profile)


def test_non_numeric_curve_is_reported():
    profile = sample_profile()
    profile["curva_horaria"]["base"][0] = "0.01"
    assert "curva_valor" in codes(profile)


def test_repeated_ids_are_reported():
    profiles = list(sample_profiles().values())
    for profile in profiles:
        profile["id"] = "8b6f1c9e-2b1a-4c1e-9a77-0e0f6f1d2c3b"
    assert [code for code, _ in validate_profile_set(profiles)] == ["id_duplicado"]
