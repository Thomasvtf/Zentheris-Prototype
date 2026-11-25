"""Pruebas de app.services.consumption con `app.data.*` falso en memoria (sin base ni red).

Fase 6 · `obtenerConsumoActual`, `obtenerConsumoZonas`, `obtenerConsumoZona`. RN-XI-01 a
RN-XI-09, RN-XII-03, RN-XII-05 a RN-XII-07, RN-V-01, RN-V-02, RN-IV-05, DC-28, DC-34 y la
decisión de Nicolás (23/11/2026): la consulta recupera primero las horas y, si la recuperación
falla, responde con los datos guardados (WARNING sin ids). Los dobles están en
`consumption_fakes.py`; las series salen de `tests/helpers/personalities.py` y del simulador.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from app.data import readings as readings_data
from app.domain import states
from app.domain.simulator import TIMEZONE, hour_from_index
from app.domain.simulator.engine import simulate_household
from app.errors import NOT_FOUND_MESSAGE, ApiError, CodigoError, NotImplementedOperation
from app.schemas.consumption import ConsumoActualHogar, ConsumoZonaDetalle, ConsumoZonas
from app.services import consumption as service
from app.services import thresholds as thresholds_service
from app.services.hour_recovery import RECOVERY_SKIPPED_MESSAGE
from tests.helpers.personalities import PERSONALITY_ORDER, PersonalityAverages, load_personalities
from tests.services.consumption_fakes import (
    FakeConsumptionDatabase,
    FakeSession,
    hourly_series,
    install_fake_consumption_database,
)
from tests.simulator.support import final_profiles, stable_id

HOGAR = stable_id("hogar", "consumo")
OTRO_HOGAR = stable_id("hogar", "consumo", "otro")
USER = stable_id("usuario", "consumo")
NOW = datetime(2026, 11, 23, 15, 20, tzinfo=TIMEZONE)  # lunes; hora evaluada 14:00-15:00
HOUR = datetime(2026, 11, 23, 14, tzinfo=TIMEZONE)
WINDOW_START = datetime(2026, 10, 24, tzinfo=TIMEZONE)  # 30 días antes del 23/11
TODAY = date(2026, 11, 23)
VALUES = {"cocina": 0.5, "bano": 0.25, "sala": 0.25}  # total 1,0 kWh por hora
NAMES = {"cocina": "Cocina", "bano": "Baño", "sala": "Sala"}
PRICE = 800.0

OPERATIONS = ("actual", "zonas", "zona")
each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


# ------------------------------------------------------------------ preparación
@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeConsumptionDatabase:
    return install_fake_consumption_database(monkeypatch)


def seed_household(
    db: FakeConsumptionDatabase, last: datetime = HOUR, hogar_id: UUID = HOGAR
) -> dict[str, UUID]:
    """Cocina, Sala y Baño (insertadas fuera de orden) con 30 días + hoy hasta `last`."""
    ids = {}
    for tipo in ("cocina", "sala", "bano"):
        ids[tipo] = db.add_zone(hogar_id, tipo, NAMES[tipo])
        db.set_series(ids[tipo], hourly_series(lambda _m, v=VALUES[tipo]: v, WINDOW_START, last))
    return ids


def call(operation: str, session: FakeSession, now: datetime = NOW,
         zona_id: UUID | None = None) -> BaseModel:
    if operation == "actual":
        return service.get_current_consumption(session, USER, HOGAR, now)
    if operation == "zonas":
        return service.get_zones_consumption(session, USER, HOGAR, now)
    assert zona_id is not None
    return service.get_zone_consumption(session, USER, HOGAR, zona_id, now)


def roundtrip(result: BaseModel) -> BaseModel:
    """Validación contra el esquema Pydantic del contrato (ida y vuelta por JSON)."""
    return type(result).model_validate_json(result.model_dump_json())


# ------------------------------------------------------------------ umbrales
def test_consumption_uses_the_shared_thresholds_reader() -> None:
    assert service.get_thresholds is thresholds_service.get_thresholds


# ------------------------------------------------------------------ recuperación primero
@pytest.mark.parametrize("operation", OPERATIONS)
def test_recovery_runs_once_first_with_the_same_now(
    db: FakeConsumptionDatabase, operation: str
) -> None:
    ids = seed_household(db)
    session = FakeSession()
    call(operation, session, zona_id=ids["cocina"])

    names = db.names()
    assert names.count("recovery") == 1
    assert names[0] == "recovery"
    assert names.index("recovery") < names.index("readings")
    assert db.calls[0] == ("recovery", HOGAR, NOW)
    readings = [c for c in db.calls if c[0] == "readings"]
    assert len(readings) == 1
    _, _, _, start, end = readings[0]
    assert (start, end) == (WINDOW_START, HOUR)
    assert session.commits == 0  # solo lectura


def test_default_now_is_used_for_recovery_and_evaluation(
    db: FakeConsumptionDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_household(db)
    result = service.get_current_consumption(FakeSession(), USER, HOGAR)
    recovery_now = db.calls[0][2]
    assert recovery_now.utcoffset() == timedelta(0)  # datetime.now(UTC)
    assert result.hora.inicio == states.evaluated_hour(recovery_now)[0]


def _failing_lock(session: object, hogar_id: UUID) -> None:
    raise OperationalError("SELECT", {}, Exception(f"DETAIL: hogar {hogar_id} secreto"))


@pytest.mark.parametrize("operation", OPERATIONS)
def test_recovery_failure_answers_with_saved_data_and_warns_without_ids(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, operation: str
) -> None:
    """Decisión 1: la recuperación real falla (candado); la hora evaluada no está guardada."""
    db = install_fake_consumption_database(monkeypatch, spy_recovery=False)
    monkeypatch.setattr(readings_data, "lock_household_recovery", _failing_lock)
    ids = seed_household(db, last=HOUR - timedelta(hours=1))
    session = FakeSession()

    with caplog.at_level(logging.WARNING):
        result = roundtrip(call(operation, session, zona_id=ids["cocina"]))

    warnings = [r for r in caplog.records if r.getMessage() == RECOVERY_SKIPPED_MESSAGE]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    assert str(HOGAR) not in caplog.text and "secreto" not in caplog.text
    assert session.commits == 0 and session.rollbacks == 1  # revirtió la recuperación
    if operation == "actual":
        assert isinstance(result, ConsumoActualHogar)
        assert result.actual.potencia_kw is None
        assert result.actual.costo_cop is None
        assert result.actual.estado == "sin_datos"
        assert result.actual.mensaje_codigo == "consumo_actual.sin_datos"
        assert result.acumulado_hoy.energia_kwh == pytest.approx(14.0)  # 00:00-13:59
        assert result.acumulado_hoy.estado == "sin_datos"
    elif operation == "zonas":
        assert isinstance(result, ConsumoZonas)
        assert result.total_kw is None
        assert {z.estado_participacion for z in result.zonas} == {"sin_datos"}
        assert all(z.potencia_kw is None for z in result.zonas)
    else:
        assert isinstance(result, ConsumoZonaDetalle)
        assert result.potencia_kw is None
        assert result.estado_consumo.estado == "sin_datos"
        assert result.estado_consumo.mensaje_codigo == "zona_estado.sin_datos"
        assert result.estado_consumo.promedio_misma_hora_kw == pytest.approx(0.5)
        assert result.participacion.estado == "sin_datos"


# ------------------------------------------------------------------ obtenerConsumoActual
def test_current_with_tariff_average_base(db: FakeConsumptionDatabase) -> None:
    seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 11, 1), cargo_fijo=12000.0)
    result = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, NOW))

    assert result.hora.inicio == HOUR and result.hora.fin == HOUR + timedelta(hours=1)
    assert result.hora.inicio.utcoffset() == timedelta(hours=-5)
    assert result.tarifa_vigente is True
    actual = result.actual
    assert actual.potencia_kw == pytest.approx(1.0)
    assert actual.costo_cop == pytest.approx(1.0 * PRICE)  # sin cargo fijo (RN-V-02)
    assert actual.variacion_hora_anterior_pct == 0
    assert actual.referencia_tipo == "promedio" and actual.referencia_kw == pytest.approx(1.0)
    assert (actual.estado, actual.mensaje_codigo) == ("normal", "consumo_actual.normal")
    today = result.acumulado_hoy
    assert today.energia_kwh == pytest.approx(15.0)  # 00:00 a 14:59
    assert today.costo_cop == pytest.approx(15.0 * PRICE)
    assert today.referencia_tipo == "promedio" and today.referencia_kwh == pytest.approx(15.0)
    assert today.muestra_limite is False
    assert (today.estado, today.mensaje_codigo) == ("normal", "acumulado.promedio.normal")
    assert [c for c in db.calls if c[0] == "tariff"] == [("tariff", HOGAR, TODAY)]


def test_current_without_tariff_has_null_costs(db: FakeConsumptionDatabase) -> None:
    seed_household(db)
    # Tarifa vencida ayer ([desde, hasta)) y otra que empieza mañana: ninguna vigente hoy.
    db.add_tariff(HOGAR, PRICE, date(2026, 10, 1), hasta=TODAY)
    db.add_tariff(HOGAR, PRICE, TODAY + timedelta(days=1))
    result = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, NOW))
    assert result.tarifa_vigente is False
    assert result.actual.costo_cop is None and result.acumulado_hoy.costo_cop is None
    assert result.actual.potencia_kw == pytest.approx(1.0)


def test_current_with_goal_applied(db: FakeConsumptionDatabase) -> None:
    seed_household(db)
    db.set_preferences(USER, "meta")
    db.set_goal(HOGAR, 360.0)  # noviembre: 12 kWh/día; cada hora pesa 1/24 → 0,5 kWh
    result = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, NOW))
    actual, today = result.actual, result.acumulado_hoy
    assert actual.referencia_tipo == "meta" and actual.referencia_kw == pytest.approx(0.5)
    assert (actual.estado, actual.mensaje_codigo) == ("critico", "consumo_actual.critico")
    assert today.referencia_tipo == "meta" and today.referencia_kwh == pytest.approx(12.0)
    assert today.muestra_limite is True
    assert (today.estado, today.mensaje_codigo) == ("critico", "acumulado.meta.critico")


def test_goal_preference_without_active_goal_falls_back_to_average(
    db: FakeConsumptionDatabase,
) -> None:
    seed_household(db)
    db.set_preferences(USER, "meta")
    result = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, NOW))
    assert result.actual.referencia_tipo == "promedio"
    assert result.acumulado_hoy.referencia_tipo == "promedio"
    assert result.acumulado_hoy.muestra_limite is False
    assert result.acumulado_hoy.mensaje_codigo == "acumulado.promedio.normal"


@pytest.mark.parametrize("preference", [None, "promedio"])
def test_average_base_ignores_active_goal(
    db: FakeConsumptionDatabase, preference: str | None
) -> None:
    seed_household(db)
    db.set_goal(HOGAR, 360.0)
    if preference is not None:
        db.set_preferences(USER, preference)
    result = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, NOW))
    assert result.actual.referencia_tipo == "promedio"
    assert result.actual.estado == "normal"
    assert result.acumulado_hoy.referencia_tipo == "promedio"
    assert "goal" not in db.names()  # sin base meta no hace falta leer la meta


def test_between_midnight_and_one_cumulative_is_zero_and_without_data(
    db: FakeConsumptionDatabase,
) -> None:
    last = datetime(2026, 11, 22, 23, tzinfo=TIMEZONE)
    seed_household(db, last=last)
    db.add_tariff(HOGAR, PRICE, date(2026, 11, 1))
    now = datetime(2026, 11, 23, 0, 40, tzinfo=TIMEZONE)
    result = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, now))
    assert result.hora.inicio == last  # 23:00 de ayer
    assert result.actual.potencia_kw == pytest.approx(1.0)
    assert result.acumulado_hoy.energia_kwh == 0
    assert result.acumulado_hoy.costo_cop is None  # null = sin dato, nunca 0 COP
    assert result.acumulado_hoy.estado == "sin_datos"
    assert result.acumulado_hoy.mensaje_codigo == "acumulado.promedio.sin_datos"


def test_tariff_is_the_one_in_force_on_the_evaluated_hour_date(
    db: FakeConsumptionDatabase,
) -> None:
    """A las 00:40 la hora evaluada es la de 23:00 de ayer: se cobra con la tarifa de ayer."""
    yesterday = TODAY - timedelta(days=1)
    seed_household(db, last=datetime(2026, 11, 22, 23, tzinfo=TIMEZONE))
    db.add_tariff(HOGAR, PRICE, date(2026, 11, 1), hasta=TODAY)  # vence hoy: [desde, hasta)
    db.add_tariff(HOGAR, 2 * PRICE, TODAY)
    now = datetime(2026, 11, 23, 0, 40, tzinfo=TIMEZONE)
    result = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, now))
    assert result.tarifa_vigente is True
    assert result.actual.costo_cop == pytest.approx(1.0 * PRICE)
    assert [c for c in db.calls if c[0] == "tariff"] == [("tariff", HOGAR, yesterday)]


def test_cumulative_with_a_missing_hour_has_null_cost(db: FakeConsumptionDatabase) -> None:
    ids = seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 11, 1))
    del db.readings[ids["sala"]][HOUR - timedelta(hours=5)]
    result = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, NOW))
    assert result.acumulado_hoy.estado == "sin_datos"
    assert result.acumulado_hoy.energia_kwh == pytest.approx(14.0)  # las horas completas
    assert result.acumulado_hoy.costo_cop is None
    assert result.actual.costo_cop == pytest.approx(1.0 * PRICE)


def test_household_without_zones_is_without_data(db: FakeConsumptionDatabase) -> None:
    result = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, NOW))
    assert result.actual.potencia_kw is None and result.actual.estado == "sin_datos"
    assert result.acumulado_hoy.energia_kwh == 0
    assert result.acumulado_hoy.estado == "sin_datos"
    zones = roundtrip(service.get_zones_consumption(FakeSession(), USER, HOGAR, NOW))
    assert zones.total_kw is None and zones.zonas == []


def test_naive_now_is_rejected_before_touching_data(monkeypatch: pytest.MonkeyPatch) -> None:
    db = install_fake_consumption_database(monkeypatch, spy_recovery=False)
    with pytest.raises(ValueError):
        service.get_current_consumption(FakeSession(), USER, HOGAR, NOW.replace(tzinfo=None))
    assert db.calls == []


# ------------------------------------------------------------------ zonas que cuentan
def seed_with_non_counting(db: FakeConsumptionDatabase) -> dict[str, UUID]:
    """Además de las 3 zonas: oficina inactiva, lavandería con sensor pausado y garaje sin
    sensor, todas con lecturas guardadas hasta la hora evaluada (de antes del cambio)."""
    ids = seed_household(db)
    for tipo, nombre, estado, sensor in (
        ("oficina", "Oficina", "inactiva", "activo"),
        ("lavanderia", "Lavandería", "activa", "pausado"),
        ("garaje", "Garaje", "activa", None),
    ):
        ids[tipo] = db.add_zone(HOGAR, tipo, nombre, estado, sensor)
        db.set_series(ids[tipo], hourly_series(lambda _m: 2.0, WINDOW_START, HOUR))
    return ids


def test_non_counting_zones_do_not_add_to_the_total(db: FakeConsumptionDatabase) -> None:
    ids = seed_with_non_counting(db)
    current = roundtrip(service.get_current_consumption(FakeSession(), USER, HOGAR, NOW))
    assert current.actual.potencia_kw == pytest.approx(1.0)
    assert current.acumulado_hoy.energia_kwh == pytest.approx(15.0)
    zones = roundtrip(service.get_zones_consumption(FakeSession(), USER, HOGAR, NOW))
    assert zones.total_kw == pytest.approx(1.0)
    assert {z.zona_id for z in zones.zonas} == {ids["cocina"], ids["bano"], ids["sala"]}
    # Solo se leen lecturas de las zonas que cuentan.
    read = [c for c in db.calls if c[0] == "readings"]
    assert all(set(c[2]) == {ids["cocina"], ids["bano"], ids["sala"]} for c in read)


@pytest.mark.parametrize("tipo", ["oficina", "lavanderia", "garaje"])
def test_detail_of_non_counting_zone_is_without_data(
    db: FakeConsumptionDatabase, tipo: str
) -> None:
    ids = seed_with_non_counting(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 11, 1))
    result = roundtrip(
        service.get_zone_consumption(FakeSession(), USER, HOGAR, ids[tipo], NOW)
    )
    assert result.zona.id == ids[tipo] and result.zona.tipo == tipo
    assert result.potencia_kw is None and result.costo_cop is None
    assert result.estado_consumo.estado == "sin_datos"
    assert result.estado_consumo.mensaje_codigo == "zona_estado.sin_datos"
    assert result.estado_consumo.variacion_pct is None
    assert result.estado_consumo.promedio_misma_hora_kw is None
    assert result.participacion.participacion_pct is None
    assert result.participacion.estado == "sin_datos"
    assert result.participacion.total_hogar_kw == pytest.approx(1.0)
    read = [c for c in db.calls if c[0] == "readings"]
    assert len(read) == 1
    assert set(read[0][2]) == {ids["cocina"], ids["bano"], ids["sala"]}  # no lee la pedida


# ------------------------------------------------------------------ obtenerConsumoZonas
def test_zones_alphabetical_with_share_and_costs(db: FakeConsumptionDatabase) -> None:
    ids = seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 11, 1))
    result = roundtrip(service.get_zones_consumption(FakeSession(), USER, HOGAR, NOW))
    assert [z.nombre for z in result.zonas] == ["Baño", "Cocina", "Sala"]
    assert result.tarifa_vigente is True and result.total_kw == pytest.approx(1.0)
    by_type = {z.tipo: z for z in result.zonas}
    assert by_type["cocina"].zona_id == ids["cocina"]
    assert by_type["cocina"].participacion_pct == pytest.approx(50.0)
    assert by_type["bano"].participacion_pct == pytest.approx(25.0)
    assert by_type["cocina"].costo_cop == pytest.approx(0.5 * PRICE)
    assert {z.estado_participacion for z in result.zonas} == {"normal"}
    assert result.hora.inicio == HOUR


def test_zones_order_and_name_use_visible_name_not_stored_name(
    db: FakeConsumptionDatabase,
) -> None:
    """RN-XII-03: orden y `nombre` salen del nombre visible del tipo («Baño» < «Cocina»)."""
    cocina = db.add_zone(HOGAR, "cocina", "A cocina")
    db.add_zone(HOGAR, "bano", "Z baño")
    result = roundtrip(service.get_zones_consumption(FakeSession(), USER, HOGAR, NOW))
    assert [z.tipo for z in result.zonas] == ["bano", "cocina"]
    assert [z.nombre for z in result.zonas] == ["Baño", "Cocina"]
    detail = roundtrip(service.get_zone_consumption(FakeSession(), USER, HOGAR, cocina, NOW))
    assert detail.zona.nombre == "Cocina"


def test_zones_without_tariff(db: FakeConsumptionDatabase) -> None:
    seed_household(db)
    result = roundtrip(service.get_zones_consumption(FakeSession(), USER, HOGAR, NOW))
    assert result.tarifa_vigente is False
    assert all(z.costo_cop is None for z in result.zonas)


def test_zones_missing_one_zone_reading_gives_null_total(db: FakeConsumptionDatabase) -> None:
    ids = seed_household(db)
    del db.readings[ids["sala"]][HOUR]
    result = roundtrip(service.get_zones_consumption(FakeSession(), USER, HOGAR, NOW))
    assert result.total_kw is None  # nunca un parcial
    by_type = {z.tipo: z for z in result.zonas}
    assert by_type["sala"].potencia_kw is None
    assert by_type["cocina"].potencia_kw == pytest.approx(0.5)
    assert by_type["cocina"].participacion_pct is None


# ------------------------------------------------------------------ obtenerConsumoZona
def test_zone_detail(db: FakeConsumptionDatabase) -> None:
    ids = seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 11, 1))
    db.readings[ids["cocina"]][HOUR] = 0.5 * 1.7  # +70 % y +0,35 kWh: crítico
    result = roundtrip(
        service.get_zone_consumption(FakeSession(), USER, HOGAR, ids["cocina"], NOW)
    )
    assert result.zona.model_dump() == {
        "id": ids["cocina"], "tipo": "cocina", "nombre": "Cocina", "estado": "activa"
    }
    assert result.tarifa_vigente is True
    assert result.potencia_kw == pytest.approx(0.85)
    assert result.costo_cop == pytest.approx(0.85 * PRICE)
    assert result.estado_consumo.promedio_misma_hora_kw == pytest.approx(0.5)
    assert result.estado_consumo.variacion_pct == pytest.approx(70.0)
    assert result.estado_consumo.estado == "critico"
    assert result.estado_consumo.mensaje_codigo == "zona_estado.critico"
    assert result.participacion.total_hogar_kw == pytest.approx(1.35)
    assert result.participacion.participacion_pct == pytest.approx(0.85 / 1.35 * 100)
    assert result.hora.inicio == HOUR


@pytest.mark.parametrize("which", ["otro_hogar", "inexistente"])
def test_zone_of_another_household_is_404(db: FakeConsumptionDatabase, which: str) -> None:
    seed_household(db)
    other = seed_household(db, hogar_id=OTRO_HOGAR)["cocina"]
    zona_id = other if which == "otro_hogar" else stable_id("zona", "inexistente")
    with pytest.raises(ApiError) as error:
        service.get_zone_consumption(FakeSession(), USER, HOGAR, zona_id, NOW)
    assert error.value.status_code == 404
    assert error.value.codigo == CodigoError.NO_ENCONTRADO
    assert error.value.mensaje == NOT_FOUND_MESSAGE
    assert "readings" not in db.names()  # no lee lecturas de otro hogar
    assert db.names()[0] == "recovery"


# ------------------------------------------------------------------ 501 de fases futuras
def test_data_sources_still_501() -> None:
    """El historial ya está implementado (fase 7, `test_history_service.py`)."""
    with pytest.raises(NotImplementedOperation):
        service.get_data_sources(USER, HOGAR)


# ------------------------------------------------------------------ personalidades (promedios)
def peak_hour(personality: PersonalityAverages) -> int:
    """Hora del día con la mayor referencia de una zona (la hora habitual de más consumo)."""
    return max(
        ((zone, hour) for zone in personality.zone_kwh_per_day for hour in range(24)),
        key=lambda item: personality.zone_kwh_for_hour(*item),
    )[1]


def seed_personality_averages(
    db: FakeConsumptionDatabase, personality: PersonalityAverages, last: datetime
) -> dict[str, UUID]:
    hogar_id = stable_id("hogar", "consumo", personality.name)
    ids = {}
    for zone in personality.zone_kwh_per_day:
        ids[zone] = db.add_zone(hogar_id, zone, zone)
        db.set_series(ids[zone], hourly_series(
            lambda m, z=zone: personality.zone_kwh_for_hour(z, m.hour), WINDOW_START, last
        ))
    return ids


@each_personality
def test_personality_usual_hour_is_normal(
    db: FakeConsumptionDatabase, personality: PersonalityAverages
) -> None:
    hour = peak_hour(personality)
    assert hour < 23
    evaluated = datetime(2026, 11, 23, hour, tzinfo=TIMEZONE)
    now = evaluated + timedelta(hours=1, minutes=20)
    ids = seed_personality_averages(db, personality, evaluated)
    hogar_id = stable_id("hogar", "consumo", personality.name)

    current = roundtrip(service.get_current_consumption(FakeSession(), USER, hogar_id, now))
    assert current.actual.estado == "normal"
    assert current.actual.referencia_kw == pytest.approx(personality.household_kwh_for_hour(hour))
    assert current.acumulado_hoy.estado == "normal"
    zones = roundtrip(service.get_zones_consumption(FakeSession(), USER, hogar_id, now))
    assert len(zones.zonas) == len(personality.zone_kwh_per_day)  # solo sus zonas
    assert sum(z.participacion_pct for z in zones.zonas) == pytest.approx(100.0)
    for zone in zones.zonas:
        # Decisión de Nicolás del 23/11/2026: con 7 o más días con dato, un promedio 0 es
        # referencia válida (crítico si el exceso llega a 0,05 kWh; si no, normal). Una zona sin
        # consumo habitual a esa hora con consumo 0 tiene exceso 0 < 0,05 kWh → "normal", ya no
        # "sin_referencia". Con consumo habitual, también "normal" (igual a su promedio).
        assert zone.estado_participacion == "normal"
        detail = roundtrip(
            service.get_zone_consumption(FakeSession(), USER, hogar_id, ids[zone.tipo], now)
        )
        assert detail.estado_consumo.estado == "normal"


# ------------------------------------------------------------------ personalidades (simulador)
DAY = date(2026, 11, 23)


def seed_simulated(db: FakeConsumptionDatabase, name: str) -> UUID:
    """30 días previos + hoy completo, simulados con el perfil oficial y solo sus zonas."""
    personality = load_personalities()[name]
    hogar_id = stable_id("hogar", "simulado", name)
    zone_ids = {zone: db.add_zone(hogar_id, zone, zone) for zone in personality.zone_kwh_per_day}
    day = DAY.toordinal()
    series = simulate_household(hogar_id, final_profiles()[name], zone_ids, (day - 30) * 24,
                                (day + 1) * 24)
    for zone, readings in series.items():
        db.set_series(zone_ids[zone], {hour_from_index(r.index): r.total for r in readings})
    return hogar_id


def test_simulated_cumulative_reference_follows_personality_order(
    db: FakeConsumptionDatabase,
) -> None:
    """compacto < eficiente < intermedio < familiar < amplio en `acumulado_hoy.referencia_kwh`
    (base promedio) a las 23:xx."""
    now = datetime(2026, 11, 23, 23, 30, tzinfo=TIMEZONE)
    references = []
    for name in PERSONALITY_ORDER:
        hogar_id = seed_simulated(db, name)
        result = roundtrip(service.get_current_consumption(FakeSession(), USER, hogar_id, now))
        assert result.acumulado_hoy.referencia_tipo == "promedio"
        assert result.acumulado_hoy.referencia_kwh is not None
        assert result.actual.estado not in {"sin_datos", "sin_referencia"}
        references.append(result.acumulado_hoy.referencia_kwh)
    assert references == sorted(references) and len(set(references)) == len(references)


# ------------------------------------------------------------------ con la recuperación real
@pytest.mark.parametrize("name", PERSONALITY_ORDER)
def test_query_after_server_off_recovers_and_evaluates_the_new_hour(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """B-04 + fase 6: backfill en NOW, servidor apagado 5 h; la consulta recupera las horas
    (solo de las zonas del hogar) y evalúa la última, que antes no existía."""
    from tests.services.recovery_fakes import (
        HOURS_OFF,
        LATER,
        FakeHousehold,
        install_fake_recovery_database,
    )
    from tests.services.recovery_fakes import NOW as BACKFILL_NOW

    recovery_db = install_fake_recovery_database(monkeypatch)
    household = recovery_db.add_household(FakeHousehold(name, tag="consumo"))
    db = install_fake_consumption_database(monkeypatch, spy_recovery=False)
    zone_of_sensor = {}
    for zone, sensor in household.sensors.items():
        zona_id = db.add_zone(household.id, zone, zone)
        zone_of_sensor[sensor] = zona_id

    def stored() -> dict[UUID, dict[datetime, float]]:
        series: dict[UUID, dict[datetime, float]] = {}
        for (sensor, moment), row in recovery_db.saved.items():
            if sensor in zone_of_sensor:
                series.setdefault(zone_of_sensor[sensor], {})[moment] = float(row["consumo_kwh"])
        return series

    db.extra_readings = stored
    before = len(recovery_db.rows_of(household))
    evaluated = states.evaluated_hour(LATER)[0]
    assert evaluated > states.evaluated_hour(BACKFILL_NOW)[0]

    session = recovery_db.session()
    result = roundtrip(service.get_current_consumption(session, USER, household.id, LATER))

    assert len(recovery_db.rows_of(household)) == before + HOURS_OFF * len(household.sensors)
    expected = sum(
        float(row["consumo_kwh"]) for row in household.off_rows() if row["fecha_hora"] == evaluated
    )
    assert result.actual.potencia_kw == pytest.approx(expected)
    assert result.actual.estado not in {"sin_datos", "sin_referencia"}
    assert result.acumulado_hoy.estado != "sin_datos"  # hoy 00:00-02:59 recuperado
    assert result.hora.inicio == evaluated
    assert evaluated.astimezone(UTC) == LATER.astimezone(UTC).replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=1)
