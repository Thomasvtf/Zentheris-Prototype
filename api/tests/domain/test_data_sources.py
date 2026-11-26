"""Fuentes de datos: estados de sensores, suma de la fuente y valores ocultos (RN-XVI-06, RN-III-03).

`app.domain.data_sources` (fase 10, D5). Los kWh de la última hora completa salen de los promedios
reales de las 5 personalidades (`zone_kwh_for_hour(zona, hora)`). Reglas: `pausado` gana a
`sin_datos`; la fuente suma solo los sensores que cuentan (`counts_for_total`) y es None si a
alguno le falta la lectura o si no cuenta ninguno (nunca un parcial); sin permiso
(RN-XVII-01) todos los kW son None pero los estados se mantienen; orden por nombre visible de la
zona (RN-XII-03) y luego por id.
"""

import math
from uuid import UUID

import pytest

from app.domain.data_sources import (
    DataSourcesView,
    SensorInput,
    SensorView,
    evaluate_data_sources,
    sensor_state,
)
from app.domain.formats import zone_name
from tests.helpers.personalities import PersonalityAverages, load_personalities

HOUR = 19  # hora de la tarde: todas las zonas tienen consumo en las curvas

each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


def sensors_for(
    personality: PersonalityAverages,
    *,
    paused: frozenset[str] = frozenset(),
    inactive: frozenset[str] = frozenset(),
    missing: frozenset[str] = frozenset(),
) -> list[SensorInput]:
    result = []
    for i, zone in enumerate(personality.zone_kwh_per_day):
        result.append(
            SensorInput(
                sensor_id=UUID(int=100 + i),
                zona_id=UUID(int=i + 1),
                zona_tipo=zone,
                zona_estado="inactiva" if zone in inactive else "activa",
                sensor_estado="pausado" if zone in paused else "activo",
                kwh=None if zone in missing else personality.zone_kwh_for_hour(zone, HOUR),
            )
        )
    return result


def by_zone(view: DataSourcesView) -> dict[str, SensorView]:
    return {sensor.zona_nombre: sensor for sensor in view.sensores}


# ------------------------------------------------------------------ sensor_state
@pytest.mark.parametrize(
    ("sensor_estado", "kwh", "expected"),
    [
        ("activo", 0.42, "activo"),
        ("activo", 0.0, "activo"),  # 0 es dato, no «sin datos»
        ("activo", None, "sin_datos"),
        ("pausado", None, "pausado"),  # pausado gana a sin_datos
        ("pausado", 0.42, "pausado"),
    ],
)
def test_sensor_state(sensor_estado: str, kwh: float | None, expected: str) -> None:
    assert sensor_state(sensor_estado, kwh) == expected  # type: ignore[arg-type]


def test_sensor_state_rejects_unknown_state() -> None:
    with pytest.raises(ValueError):
        sensor_state("apagado", 1.0)  # type: ignore[arg-type]


# ------------------------------------------------------------------ evaluate_data_sources
@each_personality
def test_all_active_source_is_the_sum(personality: PersonalityAverages) -> None:
    view = evaluate_data_sources(sensors_for(personality), can_view_values=True)
    assert view.valores_ocultos is False
    assert view.fuente_potencia_kw == pytest.approx(personality.household_kwh_for_hour(HOUR))
    assert len(view.sensores) == len(personality.zone_kwh_per_day)
    for sensor in view.sensores:
        assert sensor.estado == "activo"
        assert sensor.nombre == f"Sensor {sensor.zona_nombre}"


@each_personality
def test_sensor_power_is_the_hour_kwh(personality: PersonalityAverages) -> None:
    view = evaluate_data_sources(sensors_for(personality), can_view_values=True)
    for zone in personality.zone_kwh_per_day:
        sensor = by_zone(view)[zone_name(zone)]
        assert sensor.potencia_kw == personality.zone_kwh_for_hour(zone, HOUR)


@each_personality
def test_paused_sensor_does_not_add(personality: PersonalityAverages) -> None:
    view = evaluate_data_sources(
        sensors_for(personality, paused=frozenset({"cocina"})), can_view_values=True
    )
    others = tuple(z for z in personality.zone_kwh_per_day if z != "cocina")
    assert by_zone(view)["Cocina"].estado == "pausado"
    assert view.fuente_potencia_kw == pytest.approx(personality.household_kwh_for_hour(HOUR, others))


@each_personality
def test_paused_sensor_without_reading_is_paused_and_source_still_adds(
    personality: PersonalityAverages,
) -> None:
    """Pausado gana a sin_datos y, como no cuenta, su falta de lectura no anula la fuente."""
    view = evaluate_data_sources(
        sensors_for(personality, paused=frozenset({"sala"}), missing=frozenset({"sala"})),
        can_view_values=True,
    )
    others = tuple(z for z in personality.zone_kwh_per_day if z != "sala")
    sala = by_zone(view)["Sala"]
    assert sala.estado == "pausado"
    assert sala.potencia_kw is None
    assert view.fuente_potencia_kw == pytest.approx(personality.household_kwh_for_hour(HOUR, others))


@each_personality
def test_inactive_zone_does_not_add(personality: PersonalityAverages) -> None:
    """Zona inactiva con sensor activo y lectura: se muestra, pero no suma a la fuente."""
    view = evaluate_data_sources(
        sensors_for(personality, inactive=frozenset({"dormitorio"})), can_view_values=True
    )
    others = tuple(z for z in personality.zone_kwh_per_day if z != "dormitorio")
    dormitorio = by_zone(view)["Dormitorio"]
    assert dormitorio.estado == "activo"
    assert dormitorio.potencia_kw == personality.zone_kwh_for_hour("dormitorio", HOUR)
    assert view.fuente_potencia_kw == pytest.approx(personality.household_kwh_for_hour(HOUR, others))


@each_personality
def test_inactive_zone_without_reading_does_not_null_the_source(
    personality: PersonalityAverages,
) -> None:
    view = evaluate_data_sources(
        sensors_for(personality, inactive=frozenset({"bano"}), missing=frozenset({"bano"})),
        can_view_values=True,
    )
    assert by_zone(view)["Baño"].estado == "sin_datos"
    assert view.fuente_potencia_kw is not None


@each_personality
def test_counting_sensor_without_reading_nulls_the_source(
    personality: PersonalityAverages,
) -> None:
    """Nunca un total parcial: si a un sensor que cuenta le falta la lectura, la fuente es None."""
    view = evaluate_data_sources(
        sensors_for(personality, missing=frozenset({"cocina"})), can_view_values=True
    )
    assert by_zone(view)["Cocina"].estado == "sin_datos"
    assert by_zone(view)["Cocina"].potencia_kw is None
    assert by_zone(view)["Sala"].potencia_kw is not None
    assert view.fuente_potencia_kw is None


@each_personality
def test_no_counting_sensor_source_is_none(personality: PersonalityAverages) -> None:
    zones = frozenset(personality.zone_kwh_per_day)
    view = evaluate_data_sources(sensors_for(personality, paused=zones), can_view_values=True)
    assert view.fuente_potencia_kw is None
    assert {s.estado for s in view.sensores} == {"pausado"}


def test_without_sensors() -> None:
    view = evaluate_data_sources([], can_view_values=True)
    assert view == DataSourcesView(valores_ocultos=False, fuente_potencia_kw=None, sensores=())


def test_zero_readings_sum_zero_not_none() -> None:
    sensors = [
        SensorInput(UUID(int=10), UUID(int=1), "cocina", "activa", "activo", 0.0),
        SensorInput(UUID(int=11), UUID(int=2), "sala", "activa", "activo", 0.0),
    ]
    view = evaluate_data_sources(sensors, can_view_values=True)
    assert view.fuente_potencia_kw == 0.0
    assert [s.estado for s in view.sensores] == ["activo", "activo"]


@each_personality
def test_without_permission_values_hidden_states_kept(personality: PersonalityAverages) -> None:
    sensors = sensors_for(
        personality, paused=frozenset({"sala"}), missing=frozenset({"cocina"})
    )
    visible = evaluate_data_sources(sensors, can_view_values=True)
    hidden = evaluate_data_sources(sensors, can_view_values=False)
    assert hidden.valores_ocultos is True
    assert hidden.fuente_potencia_kw is None
    assert all(s.potencia_kw is None for s in hidden.sensores)
    assert [(s.sensor_id, s.zona_id, s.nombre, s.zona_nombre, s.estado) for s in hidden.sensores] == [
        (s.sensor_id, s.zona_id, s.nombre, s.zona_nombre, s.estado) for s in visible.sensores
    ]


@each_personality
def test_without_permission_complete_source_is_also_hidden(
    personality: PersonalityAverages,
) -> None:
    view = evaluate_data_sources(sensors_for(personality), can_view_values=False)
    assert view.fuente_potencia_kw is None
    assert view.valores_ocultos is True


@each_personality
def test_sorted_by_visible_zone_name(personality: PersonalityAverages) -> None:
    sensors = list(reversed(sensors_for(personality)))
    view = evaluate_data_sources(sensors, can_view_values=True)
    names = [s.zona_nombre for s in view.sensores]
    assert names == sorted(names)


def test_sort_by_name_not_by_type_nor_id() -> None:
    """«Baño» (tipo `bano`) va antes que «Cocina»; «Cuarto de servicio» antes que «Dormitorio»."""
    sensors = [
        SensorInput(UUID(int=11), UUID(int=1), "dormitorio", "activa", "activo", 0.1),
        SensorInput(UUID(int=12), UUID(int=2), "cuarto_servicio", "activa", "activo", 0.1),
        SensorInput(UUID(int=13), UUID(int=3), "cocina", "activa", "activo", 0.1),
        SensorInput(UUID(int=14), UUID(int=4), "bano", "activa", "activo", 0.1),
        SensorInput(UUID(int=15), UUID(int=5), "lavanderia", "activa", "activo", 0.1),
    ]
    view = evaluate_data_sources(sensors, can_view_values=True)
    assert [s.zona_nombre for s in view.sensores] == [
        "Baño", "Cocina", "Cuarto de servicio", "Dormitorio", "Lavandería",
    ]


def test_same_name_tie_broken_by_zone_id() -> None:
    sensors = [
        SensorInput(UUID(int=21), UUID(int=9), "dormitorio", "activa", "activo", 0.2),
        SensorInput(UUID(int=22), UUID(int=3), "dormitorio", "activa", "activo", 0.3),
    ]
    view = evaluate_data_sources(sensors, can_view_values=True)
    assert [s.zona_id for s in view.sensores] == [UUID(int=3), UUID(int=9)]


def test_view_is_immutable_tuple() -> None:
    view = evaluate_data_sources(
        [SensorInput(UUID(int=1), UUID(int=2), "cocina", "activa", "activo", 0.5)], True
    )
    assert isinstance(view.sensores, tuple)
    with pytest.raises(AttributeError):
        view.fuente_potencia_kw = 1.0  # type: ignore[misc]


def test_unknown_zone_type_raises() -> None:
    with pytest.raises(KeyError):
        evaluate_data_sources(
            [SensorInput(UUID(int=1), UUID(int=2), "patio", "activa", "activo", 0.5)], True
        )


def test_source_uses_exact_sum() -> None:
    values = [0.1, 0.2, 0.3]
    sensors = [
        SensorInput(UUID(int=30 + i), UUID(int=i + 1), zone, "activa", "activo", v)
        for i, (zone, v) in enumerate(zip(("cocina", "sala", "bano"), values, strict=True))
    ]
    view = evaluate_data_sources(sensors, can_view_values=True)
    assert view.fuente_potencia_kw == math.fsum(values)
