"""U-01 · Umbrales: 13 escenarios de `test_escenarios_umbrales.py`.

Esperado: Mismos resultados que la referencia **[ref: 13/13]**. Regla: RN-XI-07.
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

Port a pytest de `docs/datos/test_escenarios_umbrales.py` (4 «Simulado» + 9 «Reglas») con las
funciones de `app.domain.states` y los umbrales de `app/config_files/umbrales-estado.v1.json`.
Los escenarios simulados usan el simulador del repo con el conjunto oficial de *Consumo familiar*
(casa con cocina, sala, dormitorio, baño, oficina y lavandería; día 2026-11-03 y 31 días previos),
como el original. Al final, una prueba diferencial compara el port con `motor_estados_ref.py`.
"""

import importlib.util
import json
import statistics
from datetime import date
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest

from app.domain import states as S
from app.domain.simulator import hour_from_index
from app.domain.simulator.engine import simulate_household
from tests.simulator.support import create_household, final_profiles

API_DIR = Path(__file__).resolve().parents[2]
THRESHOLDS_PATH = API_DIR / "app" / "config_files" / "umbrales-estado.v1.json"
REFERENCE_DIR = API_DIR.parent / "docs" / "datos"
SCENARIO_ZONES = ("cocina", "sala", "dormitorio", "bano", "oficina", "lavanderia")
SCENARIO_DAY = date(2026, 11, 3).toordinal()
PREVIOUS_DAYS = 31


@cache
def raw_thresholds() -> dict:
    return json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))


@cache
def thresholds() -> S.StateThresholds:
    return S.parse_thresholds(raw_thresholds())


def state(value, reference, block: str, *, days: int = 30, excess=None) -> str:
    """Equivalente de `estado_relativo(valor, referencia, bloque, exceso_kwh, dias_con_dato)`."""
    t = thresholds()
    band = {
        "consumo_actual": t.current,
        "acumulado_promedio": t.cumulative_average,
        "zona_estado": t.zone_state,
        "zona_participacion": t.zone_share,
        "dia_completo": t.full_day,
    }[block]
    return S.relative_state(
        value,
        reference,
        band,
        min_days_with_data=t.min_days_with_data,
        days_with_data=days,
        excess_kwh=excess,
    )


# ------------------------------------------------------------------ Simulado (4)
@cache
def simulated() -> dict[str, dict]:
    """Series por zona {inicio de hora: kWh}, como `simular_hogar` del original."""
    household = create_household("escenarios-umbrales", "casa", SCENARIO_ZONES)
    profile = final_profiles()["Consumo familiar"]
    start, end = (SCENARIO_DAY - PREVIOUS_DAYS) * 24, (SCENARIO_DAY + 1) * 24
    series = simulate_household(household.id, profile, SCENARIO_ZONES, start, end)
    return {
        zone: {hour_from_index(reading.index): reading.total for reading in readings}
        for zone, readings in series.items()
    }


def hour_of_day(hour: int):
    return hour_from_index(SCENARIO_DAY * 24 + hour)


def average(zone: str, hour: int) -> float:
    """`prom(z, t)` del original: media de la hora en los 30 días anteriores al día evaluado."""
    value, days = S.same_hour_average(simulated()[zone], hour_of_day(hour), 30)
    assert days == 30
    return value


def test_scenario_household_is_consumo_familiar() -> None:
    household = create_household("escenarios-umbrales", "casa", SCENARIO_ZONES)
    assert household.personality == "Consumo familiar"


def test_average_matches_reference_mean() -> None:
    """`same_hour_average` da la misma media que `statistics.mean` del original."""
    series = simulated()["cocina"]
    for hour in range(24):
        values = [series[hour_from_index(d * 24 + hour)] for d in range(SCENARIO_DAY - 30,
                                                                         SCENARIO_DAY)]
        assert average("cocina", hour) == statistics.mean(values)


def test_escenario_normal() -> None:
    """Sin alteración: la mayoría de horas de hoy son normales para la cocina (>= 20 de 24)."""
    series = simulated()["cocina"]
    states = [
        state(series[hour_of_day(t)], average("cocina", t), "zona_estado") for t in range(24)
    ]
    assert states.count("normal") >= 20


def test_escenario_elevado() -> None:
    """Cocina a las 19:00 con +45 % sobre su promedio -> elevado (exceso >= 0,05 kWh)."""
    reference = average("cocina", 19)
    value = reference * 1.45
    assert value - reference >= 0.05
    assert state(value, reference, "zona_estado") == "elevado"


def test_escenario_critico() -> None:
    """Cocina a las 19:00 con +0,8 kWh (freidora 1.200 W × 40 min aprox.) -> crítico."""
    reference = average("cocina", 19)
    assert state(reference + 0.8, reference, "zona_estado") == "critico"


def test_piso_absoluto_evita_ruido() -> None:
    """Dormitorio a las 03:00 (promedio < 0,05 kWh): triplicar no es crítico si el exceso es
    menor que el piso de 0,05 kWh."""
    reference = average("dormitorio", 3)
    assert reference < 0.05
    expected = "normal" if reference * 2 < 0.05 else "critico"
    assert state(reference * 3, reference, "zona_estado") == expected


# ------------------------------------------------------------------ Reglas (9)
def test_bordes_consumo_actual() -> None:
    """Consumo actual: 1,199/1,00 normal; 1,20 elevado (límite inclusivo); 1,40 crítico."""
    assert state(1.199, 1.0, "consumo_actual") == "normal"
    assert state(1.20, 1.0, "consumo_actual") == "elevado"
    assert state(1.40, 1.0, "consumo_actual") == "critico"


def test_sin_datos_no_es_cero() -> None:
    """None -> sin_datos; 0,0 es un dato (normal)."""
    assert state(None, 1.0, "consumo_actual") == "sin_datos"
    assert state(0.0, 1.0, "consumo_actual") == "normal"


def test_sin_referencia() -> None:
    """6 días con dato o referencia 0 -> sin_referencia."""
    assert state(1.0, 1.0, "consumo_actual", days=6) == "sin_referencia"
    assert state(1.0, 0.0, "consumo_actual") == "sin_referencia"


def test_acumulado_meta() -> None:
    """Meta 300 kWh / 30 días: 7,9 normal; 8,0 elevado (80 %); 10,0 crítico (100 %)."""
    band = thresholds().cumulative_goal
    assert S.cumulative_goal_state(7.9, 300, 30, band)[0] == "normal"
    assert S.cumulative_goal_state(8.0, 300, 30, band)[0] == "elevado"
    assert S.cumulative_goal_state(10.0, 300, 30, band)[0] == "critico"


def test_comparacion() -> None:
    """−6 % menor; −5 % similar; +10 % mayor; +25 % muy mayor; sin anterior."""
    t = thresholds().period_comparison
    assert S.period_comparison(94, 100, t) == ("menor", "normal")
    assert S.period_comparison(95, 100, t) == ("similar", "normal")
    assert S.period_comparison(110, 100, t) == ("mayor", "elevado")
    assert S.period_comparison(125, 100, t) == ("muy_mayor", "critico")
    assert S.period_comparison(10, None, t) == ("sin_anterior", "sin_referencia")


def test_pico() -> None:
    """+9 % no es pico; +10 % sí. +15 %: normal en Día, elevado en Semana."""
    t = thresholds()
    assert not S.is_peak(1.09, 1.0, t.peak_min_pct)
    assert S.is_peak(1.10, 1.0, t.peak_min_pct)
    assert S.peak_state(1.15, 1.0, "dia", t) == "normal"
    assert S.peak_state(1.15, 1.0, "semana", t) == "elevado"


def test_variacion_hora() -> None:
    """+0,4 % igual; +2 % más; sin hora anterior -> sin_dato."""
    equal = thresholds().hour_variation_equal_abs_pct
    assert S.hour_variation(1.004, 1.0, equal) == "igual"
    assert S.hour_variation(1.02, 1.0, equal) == "mas"
    assert S.hour_variation(1.0, None, equal) == "sin_dato"


def test_referencia_meta_hora() -> None:
    """Perfil plano: la hora recibe 1/24 del límite diario (300 / 30 / 24)."""
    assert S.goal_hour_reference(300, 30, [1.0] * 24, 5) == pytest.approx(10 / 24, abs=1e-7)


def test_proyeccion() -> None:
    """10 + 0,5 + 0,5 + 2 × 4 = 19 kWh; COP con cargo fijo solo en Mes."""
    assert S.project_period(10, [0.5, 0.5], 2, 4) == pytest.approx(19, abs=1e-7)
    with_fixed = S.project_cost(1000, 19, 10, 800, fixed_charge=12000, is_month=True)
    without_fixed = S.project_cost(1000, 19, 10, 800, fixed_charge=12000, is_month=False)
    assert with_fixed == pytest.approx(1000 + 7200 + 12000, abs=1e-7)
    assert without_fixed == pytest.approx(1000 + 7200, abs=1e-7)


# ------------------------------------------------------------------ diferencial con la referencia
@cache
def reference_engine() -> ModuleType:
    """`docs/datos/motor_estados_ref.py` cargado desde su ruta, sin modificarlo."""
    spec = importlib.util.spec_from_file_location(
        "motor_estados_ref", REFERENCE_DIR / "motor_estados_ref.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BLOCKS = ("consumo_actual", "acumulado_promedio", "zona_estado", "zona_participacion",
          "dia_completo")
REFERENCES = (None, -1.0, 0.0, 0.01, 0.03, 0.04, 0.1, 0.15, 0.2, 0.37, 1.0, 1.7, 3.0)
FACTORS = (0.0, 0.5, 0.95, 1.0, 1.0999, 1.1, 1.15, 1.1999, 1.2, 1.25, 1.2999, 1.3, 1.4, 1.5,
           1.6, 2.0, 3.0)
OFFSETS = (0.049, 0.0499999, 0.05, 0.0500001, 0.8)
DAYS = (0, 6, 7, 30)
EXCESSES = (None, -0.1, 0.0, 0.049, 0.05, 0.2)


def values_for(reference):
    if reference is None or reference <= 0:
        return (None, 0.0, 0.5, 1.0, 1.2)
    return (None, *(reference * f for f in FACTORS), *(reference + o for o in OFFSETS))


def test_thresholds_file_is_the_reference_copy() -> None:
    """La copia del backend es igual a la de docs/ que lee la referencia."""
    docs = json.loads((REFERENCE_DIR / "umbrales-estado.v1.json").read_text(encoding="utf-8"))
    assert raw_thresholds() == docs == reference_engine().U


@pytest.mark.parametrize("block", BLOCKS)
def test_relative_state_matches_reference(block: str) -> None:
    ref = reference_engine()
    checked = 0
    for reference in REFERENCES:
        for value in values_for(reference):
            assert S.var_pct(value, reference) == ref.var_pct(value, reference)
            for days in DAYS:
                for excess in EXCESSES:
                    expected = ref.estado_relativo(value, reference, block, excess, days)
                    got = state(value, reference, block, days=days, excess=excess)
                    assert got == expected, (value, reference, days, excess)
                    checked += 1
    assert checked > 1000


def test_cumulative_goal_matches_reference() -> None:
    ref, band = reference_engine(), thresholds().cumulative_goal
    for goal, days_in_month in ((300, 30), (310, 31), (280, 28), (123.4, 29)):
        limit = goal / days_in_month
        for factor in (None, 0.0, 0.5, 0.7999, 0.8, 0.95, 0.9999, 1.0, 1.2):
            value = None if factor is None else limit * factor
            assert S.cumulative_goal_state(value, goal, days_in_month, band) == (
                ref.estado_acumulado_meta(value, goal, days_in_month)
            )


def test_goal_hour_reference_matches_reference() -> None:
    ref = reference_engine()
    profiles = ([1.0] * 24, [0.0] * 24, [0.1 * (h % 7) for h in range(24)], [0.0] * 23 + [2.0])
    for averages in profiles:
        for hour in (0, 5, 19, 23):
            assert S.goal_hour_reference(300, 30, averages, hour) == (
                ref.referencia_hora_con_meta(300, 30, averages, hour)
            )


def test_other_functions_match_reference() -> None:
    ref, t = reference_engine(), thresholds()
    for previous in (None, -1.0, 0.0, 100.0):
        for current in (0, 50, 94, 94.99, 95, 109.99, 110, 124.99, 125, 300):
            assert S.period_comparison(current, previous, t.period_comparison) == (
                ref.comparacion_periodo(current, previous)
            )
    for average_value in (None, 0.0, 0.3, 1.0, 2.7):
        for factor in (0.5, 1.0, 1.099, 1.0999999, 1.1, 1.15, 1.2, 1.3, 1.4):
            value = None if average_value is None else average_value * factor
            assert S.is_peak(value, average_value, t.peak_min_pct) == ref.es_pico(
                value, average_value
            )
            if value is not None and average_value > 0:
                for period in ("dia", "semana", "mes"):
                    assert S.peak_state(value, average_value, period, t) == ref.estado_pico(
                        value, average_value, period
                    )
            assert S.hour_variation(value, average_value, t.hour_variation_equal_abs_pct) == (
                ref.variacion_hora(value, average_value)
            )
    assert S.project_period(3.5, [0.2, 0.3, 0.1], 5, 9.8) == ref.proyeccion_cierre(
        3.5, [0.2, 0.3, 0.1], 5, 9.8
    )
    for fixed in (None, 0, 12000.0):
        for is_month in (True, False):
            assert S.project_cost(1500.0, 40.0, 12.5, 812.3, fixed, is_month) == (
                ref.proyeccion_cop(1500.0, 40.0, 12.5, 812.3, fixed, is_month)
            )


# ------------------------------------------------------------------ parse_thresholds
def test_parse_thresholds_values() -> None:
    t = thresholds()
    assert (t.window_days, t.min_days_with_data) == (30, 7)
    assert t.current == S.BandThresholds(20, 40)
    assert t.cumulative_average == S.BandThresholds(15, 30)
    assert t.cumulative_goal == S.BandThresholds(80, 100)
    assert t.zone_state == S.BandThresholds(30, 60, 0.05)
    assert t.zone_share == S.BandThresholds(25, 50, 0.05)
    assert t.full_day == S.BandThresholds(15, 30)
    assert t.peak_min_pct == 10
    assert t.hour_variation_equal_abs_pct == 0.5
    comparison = t.period_comparison
    assert (comparison.lower_if_below_pct, comparison.similar_if_below_pct,
            comparison.much_higher_from_pct) == (-5, 10, 25)
    assert dict(comparison.states) == {
        "menor": "normal", "similar": "normal", "mayor": "elevado", "muy_mayor": "critico"
    }


def _without(path: tuple[str, ...]) -> dict:
    raw = json.loads(json.dumps(raw_thresholds()))
    node = raw
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    return raw


def _with(path: tuple[str, ...], value) -> dict:
    raw = json.loads(json.dumps(raw_thresholds()))
    node = raw
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return raw


@pytest.mark.parametrize(
    "path",
    [
        ("referencia", "ventana_promedio_dias"),
        ("referencia", "minimo_dias_con_dato"),
        ("consumo_actual",),
        ("zona_estado", "critico_desde_pct"),
        ("acumulado_meta", "elevado_desde_pct_del_limite"),
        ("pico", "minimo_pct"),
        ("comparacion_periodo", "estado", "mayor"),
        ("variacion_hora_anterior", "igual_si_abs_menor_que_pct"),
    ],
)
def test_parse_thresholds_missing_key(path) -> None:
    with pytest.raises(ValueError):
        S.parse_thresholds(_without(path))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("consumo_actual", "elevado_desde_pct"), "20"),
        (("consumo_actual", "elevado_desde_pct"), True),
        (("consumo_actual", "elevado_desde_pct"), None),
        (("zona_estado", "exceso_minimo_kwh"), "0.05"),
        (("referencia", "minimo_dias_con_dato"), 7.5),
        (("referencia", "ventana_promedio_dias"), 0),
        (("comparacion_periodo", "estado", "mayor"), "rojo"),
        (("pico", "estado_en_dia"), "dia_completo"),
    ],
)
def test_parse_thresholds_invalid_value(path, value) -> None:
    with pytest.raises(ValueError):
        S.parse_thresholds(_with(path, value))
