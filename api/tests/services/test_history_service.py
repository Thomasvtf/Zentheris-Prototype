"""Pruebas de `app.services.consumption.get_history` (`obtenerHistorial`) con `app.data.*` falso.

Fase 7 · RN-XIII-01 a RN-XIII-06, RN-IV-05, RN-V-01, RN-V-02, RN-XII-03, DC-29 a DC-31, DC-34 y
la decisión de Nicolás (23/11/2026): la consulta recupera primero las horas y, si la recuperación
falla, responde con los datos guardados (WARNING sin ids). Los dobles están en
`consumption_fakes.py`; las series salen de `tests/helpers/personalities.py` y del simulador.
Cada respuesta se valida contra el modelo `Historial` (ida y vuelta por JSON).
"""

import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.exc import OperationalError

from app.data import readings as readings_data
from app.domain.simulator import TIMEZONE, hour_from_index
from app.domain.simulator.engine import simulate_household
from app.errors import NOT_FOUND_MESSAGE, ApiError, CodigoError
from app.schemas.consumption import Historial
from app.services import consumption as service
from app.services.hour_recovery import RECOVERY_SKIPPED_MESSAGE
from tests.helpers.personalities import PERSONALITY_ORDER, PersonalityAverages, load_personalities
from tests.services.consumption_fakes import (
    FakeConsumptionDatabase,
    FakeSession,
    hourly_series,
    install_fake_consumption_database,
)
from tests.simulator.support import final_profiles, stable_id

HOGAR = stable_id("hogar", "historial")
OTRO_HOGAR = stable_id("hogar", "historial", "otro")
USER = stable_id("usuario", "historial")
NOW = datetime(2026, 11, 25, 15, 20, tzinfo=TIMEZONE)  # miércoles; última hora completa 14:00
END = datetime(2026, 11, 25, 15, tzinfo=TIMEZONE)  # fin exclusivo del rango
LAST = END - timedelta(hours=1)  # última lectura que se lee
TODAY = date(2026, 11, 25)
SEED_START = datetime(2026, 9, 25, tzinfo=TIMEZONE)  # antes de cualquier read_start
VALUES = {"cocina": 0.5, "bano": 0.25, "sala": 0.25}  # total 1,0 kWh por hora
NAMES = {"cocina": "Cocina", "bano": "Baño", "sala": "Sala"}
PRICE = 800.0
FIXED = 12000.0

PERIODS = ("dia", "semana", "mes")
# Inicio del rango, primera hora que se lee y número de puntos a las 15:20 del 25/11/2026.
RANGE_START = {
    "dia": datetime(2026, 11, 25, tzinfo=TIMEZONE),
    "semana": datetime(2026, 11, 23, tzinfo=TIMEZONE),
    "mes": datetime(2026, 11, 1, tzinfo=TIMEZONE),
}
READ_START = {
    "dia": datetime(2026, 10, 26, tzinfo=TIMEZONE),  # 30 días antes de hoy
    "semana": datetime(2026, 10, 24, tzinfo=TIMEZONE),  # 30 días antes del lunes
    "mes": datetime(2026, 10, 1, tzinfo=TIMEZONE),  # tramo anterior: desde el 1 de octubre
}
POINTS = {"dia": 15, "semana": 3, "mes": 25}
HOURS = {"dia": 15, "semana": 2 * 24 + 15, "mes": 24 * 24 + 15}  # horas del rango actual
# Lo que falta del periodo (DC-30): 9 horas de hoy + días completos restantes.
REMAINING_HOURS = {"dia": 9, "semana": 9 + 4 * 24, "mes": 9 + 5 * 24}

each_period = pytest.mark.parametrize("periodo", PERIODS)
each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


# ------------------------------------------------------------------ preparación
@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeConsumptionDatabase:
    return install_fake_consumption_database(monkeypatch)


def seed_household(
    db: FakeConsumptionDatabase,
    last: datetime = LAST,
    hogar_id: UUID = HOGAR,
    names: dict[str, str] = NAMES,
) -> dict[str, UUID]:
    """Cocina, Sala y Baño (insertadas fuera de orden) con lecturas hasta `last`."""
    ids = {}
    for tipo in ("cocina", "sala", "bano"):
        ids[tipo] = db.add_zone(hogar_id, tipo, names[tipo])
        db.set_series(ids[tipo], hourly_series(lambda _m, v=VALUES[tipo]: v, SEED_START, last))
    return ids


def history(
    periodo: str,
    zona_id: UUID | None = None,
    now: datetime = NOW,
    hogar_id: UUID = HOGAR,
    session: FakeSession | None = None,
) -> Historial:
    result = service.get_history(session or FakeSession(), USER, hogar_id, periodo, zona_id, now)
    assert isinstance(result, Historial)
    return Historial.model_validate_json(result.model_dump_json())


def reading_calls(db: FakeConsumptionDatabase) -> list[tuple]:
    return [call for call in db.calls if call[0] == "readings"]


# ------------------------------------------------------------------ recuperación primero
@each_period
def test_recovery_first_then_reads_the_period_range(
    db: FakeConsumptionDatabase, periodo: str
) -> None:
    ids = seed_household(db)
    session = FakeSession()
    history(periodo, session=session)

    names = db.names()
    assert names[0] == "recovery" and names.count("recovery") == 1
    assert db.calls[0] == ("recovery", HOGAR, NOW)
    reads = reading_calls(db)
    assert len(reads) == 1
    _, hogar_id, zone_ids, start, end = reads[0]
    assert hogar_id == HOGAR
    assert zone_ids == (ids["bano"], ids["cocina"], ids["sala"])  # alfabético
    assert (start, end) == (READ_START[periodo], LAST)  # inclusivo: hasta end − 1 h
    tariffs = [call for call in db.calls if call[0] == "tariffs_between"]
    assert tariffs == [("tariffs_between", HOGAR, RANGE_START[periodo].date(), TODAY)]
    assert session.commits == 0  # solo lectura


def test_default_now_is_used_for_recovery_and_range(db: FakeConsumptionDatabase) -> None:
    seed_household(db)
    result = service.get_history(FakeSession(), USER, HOGAR, "dia", None)
    recovery_now = db.calls[0][2]
    assert recovery_now.utcoffset() == timedelta(0)  # datetime.now(UTC)
    expected_end = recovery_now.astimezone(TIMEZONE).replace(minute=0, second=0, microsecond=0)
    assert result.fin == expected_end


def test_naive_now_is_rejected_before_touching_data(monkeypatch: pytest.MonkeyPatch) -> None:
    db = install_fake_consumption_database(monkeypatch, spy_recovery=False)
    with pytest.raises(ValueError):
        service.get_history(FakeSession(), USER, HOGAR, "dia", None, NOW.replace(tzinfo=None))
    assert db.calls == []


def _failing_lock(session: object, hogar_id: UUID) -> None:
    raise OperationalError("SELECT", {}, Exception(f"DETAIL: hogar {hogar_id} secreto"))


@each_period
def test_recovery_failure_answers_with_saved_data_and_warns_without_ids(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, periodo: str
) -> None:
    """La recuperación real falla (candado): 200 con lo guardado; la hora 14:00 sigue sin dato."""
    db = install_fake_consumption_database(monkeypatch, spy_recovery=False)
    monkeypatch.setattr(readings_data, "lock_household_recovery", _failing_lock)
    seed_household(db, last=LAST - timedelta(hours=1))
    db.add_tariff(HOGAR, PRICE, date(2026, 11, 1))
    session = FakeSession()

    with caplog.at_level(logging.WARNING):
        result = history(periodo, session=session)

    warnings = [r for r in caplog.records if r.getMessage() == RECOVERY_SKIPPED_MESSAGE]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    assert str(HOGAR) not in caplog.text and "secreto" not in caplog.text
    assert session.commits == 0 and session.rollbacks == 1  # revirtió la recuperación
    assert result.total_kwh == pytest.approx(HOURS[periodo] - 1)  # sin la hora 14:00
    assert result.serie[-1].energia_kwh is None  # el punto con la hora que falta: sin dato
    assert result.serie[-1].costo_cop is None
    assert result.comparacion.estado == "sin_datos" and result.comparacion.mensaje_codigo is None
    assert result.costo.costo_cop is None and result.costo.proyeccion_cierre_cop is None
    assert result.tarifa_vigente is True


# ------------------------------------------------------------------ General
@each_period
def test_general_with_tariff(db: FakeConsumptionDatabase, periodo: str) -> None:
    ids = seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 10, 1), cargo_fijo=FIXED)
    result = history(periodo)

    assert result.periodo == periodo and result.zona_id is None
    assert result.inicio == RANGE_START[periodo] and result.fin == END
    assert result.inicio.utcoffset() == timedelta(hours=-5)
    assert result.granularidad == ("hora" if periodo == "dia" else "dia")
    assert result.tarifa_vigente is True
    assert result.total_kwh == pytest.approx(HOURS[periodo])
    assert len(result.serie) == POINTS[periodo]
    assert result.serie[0].inicio == RANGE_START[periodo] and result.serie[-1].fin == END
    point_kwh = 1.0 if periodo == "dia" else 24.0
    for point in result.serie[:-1]:
        assert point.energia_kwh == pytest.approx(point_kwh)
        assert point.costo_cop == pytest.approx(point_kwh * PRICE)  # sin cargo fijo
    assert all(not point.es_pico_maximo for point in result.serie)
    assert result.ultimo_pico is None  # todo igual a su promedio

    shares = result.participacion_zonas
    assert [s.nombre for s in shares] == ["Baño", "Cocina", "Sala"]
    assert [s.zona_id for s in shares] == [ids["bano"], ids["cocina"], ids["sala"]]
    assert [s.participacion_pct for s in shares] == pytest.approx([25.0, 50.0, 25.0])
    assert sum(s.energia_kwh for s in shares) == pytest.approx(result.total_kwh)

    comparison = result.comparacion
    assert comparison.actual_kwh == pytest.approx(HOURS[periodo])
    assert comparison.anterior_kwh == pytest.approx(HOURS[periodo])  # mismo tramo (DC-29)
    assert comparison.variacion_pct == pytest.approx(0.0)
    assert (comparison.estado, comparison.mensaje_codigo) == (
        "normal", "historial_comparacion.similar"
    )

    cost = result.costo
    assert cost.costo_cop == pytest.approx(HOURS[periodo] * PRICE)
    projected = (HOURS[periodo] + REMAINING_HOURS[periodo]) * PRICE
    assert cost.incluye_cargo_fijo is (periodo == "mes")  # cargo fijo solo en Mes General
    assert cost.proyeccion_cierre_cop == pytest.approx(
        projected + (FIXED if periodo == "mes" else 0.0)
    )
    assert (cost.estado, cost.mensaje_codigo) == (comparison.estado, comparison.mensaje_codigo)


def test_zone_order_is_the_visible_name_in_shares_and_in_every_point(
    db: FakeConsumptionDatabase,
) -> None:
    """RN-XII-03: el orden sale del nombre visible, no del guardado, y es el mismo en
    `participacion_zonas` y en `zonas` de cada punto."""
    ids = seed_household(db, names={"sala": "A sala", "cocina": "B cocina", "bano": "C baño"})
    for periodo in PERIODS:
        result = history(periodo)
        order = [s.zona_id for s in result.participacion_zonas]
        assert order == [ids["bano"], ids["cocina"], ids["sala"]]
        assert [s.nombre for s in result.participacion_zonas] == ["Baño", "Cocina", "Sala"]
        for point in result.serie:
            assert [z.zona_id for z in point.zonas] == order
            assert sum(z.energia_kwh for z in point.zonas) == pytest.approx(point.energia_kwh)


@each_period
def test_point_with_one_zone_missing_is_null_never_partial(
    db: FakeConsumptionDatabase, periodo: str
) -> None:
    ids = seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 11, 1))
    missing = datetime(2026, 11, 25, 10, tzinfo=TIMEZONE)
    del db.readings[ids["sala"]][missing]
    result = history(periodo)

    point = next(p for p in result.serie if p.inicio <= missing < p.fin)
    assert point.energia_kwh is None and point.costo_cop is None  # nunca suma parcial
    by_zone = {z.zona_id: z.energia_kwh for z in point.zonas}
    assert by_zone[ids["sala"]] is None
    expected_hours = 1 if periodo == "dia" else 15  # el punto de hoy va de 00:00 a 15:00
    assert by_zone[ids["cocina"]] == pytest.approx(0.5 * expected_hours)
    assert by_zone[ids["bano"]] == pytest.approx(0.25 * expected_hours)
    others = [p for p in result.serie if p is not point]
    assert all(p.energia_kwh is not None for p in others)
    assert result.total_kwh == pytest.approx(HOURS[periodo] - 1)  # solo las horas completas
    assert result.comparacion.estado == "sin_datos"
    assert result.costo.costo_cop is None


def test_peak_is_marked_and_reported(db: FakeConsumptionDatabase) -> None:
    """RN-XIII-03, DC-31: la hora de las 10:00 sube un 50 % frente a su promedio."""
    ids = seed_household(db)
    peak = datetime(2026, 11, 25, 10, tzinfo=TIMEZONE)
    db.readings[ids["cocina"]][peak] = 1.0  # total 1,5 kWh frente a 1,0
    result = history("dia")

    marked = [p for p in result.serie if p.es_pico_maximo]
    assert len(marked) == 1 and marked[0].inicio == peak
    last_peak = result.ultimo_pico
    assert last_peak.inicio == peak and last_peak.fin == peak + timedelta(hours=1)
    assert last_peak.energia_kwh == pytest.approx(1.5)
    assert last_peak.promedio_historico_kwh == pytest.approx(1.0)
    assert last_peak.exceso_pct == pytest.approx(50.0)
    assert last_peak.estado not in {"normal", "sin_datos", "sin_referencia"}


@pytest.mark.parametrize(
    ("now", "periodo"),
    [
        (datetime(2026, 11, 25, 0, 20, tzinfo=TIMEZONE), "dia"),
        (datetime(2026, 11, 23, 0, 20, tzinfo=TIMEZONE), "semana"),  # lunes
        (datetime(2026, 11, 1, 0, 20, tzinfo=TIMEZONE), "mes"),  # día 1
    ],
)
def test_empty_range_between_midnight_and_one(
    db: FakeConsumptionDatabase, now: datetime, periodo: str
) -> None:
    ids = seed_household(db, last=now.replace(minute=0) - timedelta(hours=1))
    db.add_tariff(HOGAR, PRICE, date(2026, 10, 1))
    result = history(periodo, now=now)
    start = now.replace(minute=0)
    assert (result.inicio, result.fin) == (start, start)
    assert result.serie == [] and result.total_kwh == 0
    assert [s.participacion_pct for s in result.participacion_zonas] == [0.0, 0.0, 0.0]
    assert result.comparacion.estado == "sin_datos"
    assert result.costo.costo_cop is None  # null = sin dato, nunca 0 COP
    _, _, zone_ids, _, end = reading_calls(db)[0]
    assert end == start - timedelta(hours=1)
    assert set(zone_ids) == set(ids.values())


# ------------------------------------------------------------------ filtro por zona
@each_period
def test_zone_filter(db: FakeConsumptionDatabase, periodo: str) -> None:
    ids = seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 10, 1), cargo_fijo=FIXED)
    result = history(periodo, zona_id=ids["cocina"])

    assert result.zona_id == ids["cocina"]
    assert result.participacion_zonas is None
    assert all(point.zonas is None for point in result.serie)
    assert result.total_kwh == pytest.approx(0.5 * HOURS[periodo])
    assert result.comparacion.anterior_kwh == pytest.approx(0.5 * HOURS[periodo])
    assert result.costo.costo_cop == pytest.approx(0.5 * HOURS[periodo] * PRICE)
    assert result.costo.incluye_cargo_fijo is False  # nunca con filtro por zona
    projected = 0.5 * (HOURS[periodo] + REMAINING_HOURS[periodo]) * PRICE
    assert result.costo.proyeccion_cierre_cop == pytest.approx(projected)
    (read,) = reading_calls(db)
    assert read[2] == (ids["cocina"],)  # solo lee la zona pedida


@pytest.mark.parametrize("which", ["otro_hogar", "inexistente"])
def test_zone_of_another_household_is_404_without_reading(
    db: FakeConsumptionDatabase, which: str
) -> None:
    seed_household(db)
    other = seed_household(db, hogar_id=OTRO_HOGAR)["cocina"]
    zona_id = other if which == "otro_hogar" else stable_id("zona", "inexistente")
    with pytest.raises(ApiError) as error:
        history("dia", zona_id=zona_id)
    assert error.value.status_code == 404
    assert error.value.codigo == CodigoError.NO_ENCONTRADO
    assert error.value.mensaje == NOT_FOUND_MESSAGE
    assert "readings" not in db.names() and "tariffs_between" not in db.names()
    assert db.names()[0] == "recovery"


def seed_with_non_counting(db: FakeConsumptionDatabase) -> dict[str, UUID]:
    """Además de las 3 zonas: oficina inactiva, lavandería con sensor pausado y garaje sin
    sensor, todas con lecturas guardadas (de antes del cambio)."""
    ids = seed_household(db)
    for tipo, nombre, estado, sensor in (
        ("oficina", "Oficina", "inactiva", "activo"),
        ("lavanderia", "Lavandería", "activa", "pausado"),
        ("garaje", "Garaje", "activa", None),
    ):
        ids[tipo] = db.add_zone(HOGAR, tipo, nombre, estado, sensor)
        db.set_series(ids[tipo], hourly_series(lambda _m: 2.0, SEED_START, LAST))
    return ids


@pytest.mark.parametrize("tipo", ["oficina", "lavanderia", "garaje"])
@each_period
def test_non_counting_zone_is_without_data_and_not_read(
    db: FakeConsumptionDatabase, tipo: str, periodo: str
) -> None:
    ids = seed_with_non_counting(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 10, 1))
    result = history(periodo, zona_id=ids[tipo])

    assert result.zona_id == ids[tipo]
    assert result.total_kwh == 0
    assert len(result.serie) == POINTS[periodo]
    assert all(p.energia_kwh is None and p.costo_cop is None for p in result.serie)
    assert result.ultimo_pico is None
    assert result.comparacion.anterior_kwh is None
    assert result.comparacion.estado == "sin_datos"
    assert result.costo.costo_cop is None and result.costo.proyeccion_cierre_cop is None
    assert all(ids[tipo] not in call[2] for call in reading_calls(db))  # no lee sus lecturas


def test_general_ignores_non_counting_zones(db: FakeConsumptionDatabase) -> None:
    ids = seed_with_non_counting(db)
    result = history("semana")
    assert result.total_kwh == pytest.approx(HOURS["semana"])
    assert [s.zona_id for s in result.participacion_zonas] == [
        ids["bano"], ids["cocina"], ids["sala"]
    ]
    (read,) = reading_calls(db)
    assert set(read[2]) == {ids["bano"], ids["cocina"], ids["sala"]}


# ------------------------------------------------------------------ tarifas
def test_each_date_uses_its_tariff_and_fixed_charge_only_in_month_general(
    db: FakeConsumptionDatabase,
) -> None:
    """RN-V-01, RN-XIII-05: hasta el 23/11 a PRICE; desde el 24/11 a 2 × PRICE ([desde, hasta))."""
    ids = seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 10, 1), hasta=date(2026, 11, 24), cargo_fijo=5000.0)
    db.add_tariff(HOGAR, 2 * PRICE, date(2026, 11, 24), cargo_fijo=FIXED)

    month = history("mes")
    by_day = {p.inicio.date(): p.costo_cop for p in month.serie}
    assert by_day[date(2026, 11, 23)] == pytest.approx(24 * PRICE)
    assert by_day[date(2026, 11, 24)] == pytest.approx(24 * 2 * PRICE)
    assert by_day[date(2026, 11, 25)] == pytest.approx(15 * 2 * PRICE)
    cost = (23 * 24) * PRICE + (24 + 15) * 2 * PRICE
    assert month.costo.costo_cop == pytest.approx(cost)
    assert month.costo.incluye_cargo_fijo is True
    # Lo que falta, al precio de hoy, + el cargo fijo de la tarifa de hoy (DC-30).
    remaining = REMAINING_HOURS["mes"] * 2 * PRICE
    assert month.costo.proyeccion_cierre_cop == pytest.approx(cost + remaining + FIXED)

    week = history("semana")
    assert week.costo.incluye_cargo_fijo is False
    assert week.costo.costo_cop == pytest.approx(24 * PRICE + (24 + 15) * 2 * PRICE)
    zone_month = history("mes", zona_id=ids["cocina"])
    assert zone_month.costo.incluye_cargo_fijo is False
    assert zone_month.costo.costo_cop == pytest.approx(0.5 * cost)


def test_fixed_charge_flag_is_false_when_the_projection_is_null(
    db: FakeConsumptionDatabase,
) -> None:
    """DC-30, RN-V-02: `incluye_cargo_fijo` solo si el cargo fijo entró de verdad en la
    proyección. Mes General con cargo fijo, pero falta una hora: costo y proyección null."""
    ids = seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 10, 1), cargo_fijo=FIXED)
    del db.readings[ids["sala"]][datetime(2026, 11, 25, 10, tzinfo=TIMEZONE)]
    result = history("mes")
    assert result.tarifa_vigente is True
    assert result.costo.costo_cop is None and result.costo.proyeccion_cierre_cop is None
    assert result.costo.incluye_cargo_fijo is False


@each_period
def test_without_tariff_costs_are_null(db: FakeConsumptionDatabase, periodo: str) -> None:
    seed_household(db)
    result = history(periodo)
    assert result.tarifa_vigente is False
    assert all(point.costo_cop is None for point in result.serie)
    assert result.costo.costo_cop is None and result.costo.proyeccion_cierre_cop is None
    assert result.costo.incluye_cargo_fijo is False
    assert result.total_kwh == pytest.approx(HOURS[periodo])  # la energía sí se informa


def test_tariff_expired_yesterday_is_not_in_force(db: FakeConsumptionDatabase) -> None:
    """Vencida hoy ([desde, hasta)): sin tarifa vigente → costo null; los días pasados conservan
    el costo de su punto."""
    seed_household(db)
    db.add_tariff(HOGAR, PRICE, date(2026, 10, 1), hasta=TODAY, cargo_fijo=FIXED)
    result = history("semana")
    assert result.tarifa_vigente is False
    assert result.costo.costo_cop is None and result.costo.incluye_cargo_fijo is False
    assert result.serie[0].costo_cop == pytest.approx(24 * PRICE)
    assert result.serie[-1].costo_cop is None


# ------------------------------------------------------------------ personalidades (promedios)
def seed_personality(
    db: FakeConsumptionDatabase, personality: PersonalityAverages
) -> tuple[UUID, dict[str, UUID]]:
    hogar_id = stable_id("hogar", "historial", personality.name)
    ids = {}
    for zone in personality.zone_kwh_per_day:
        ids[zone] = db.add_zone(hogar_id, zone, zone)
        db.set_series(ids[zone], hourly_series(
            lambda m, z=zone: personality.zone_kwh_for_hour(z, m.hour), SEED_START, LAST
        ))
    db.add_tariff(hogar_id, PRICE, date(2026, 10, 1), cargo_fijo=FIXED)
    return hogar_id, ids


def expected_kwh(personality: PersonalityAverages, periodo: str, zone: str | None = None) -> float:
    """kWh esperados del rango a las 15:20 (días completos + 00:00..14:59 de hoy)."""
    zones = None if zone is None else (zone,)
    today = sum(personality.household_kwh_for_hour(h, zones) for h in range(15))
    full_days = {"dia": 0, "semana": 2, "mes": 24}[periodo]
    day = sum(personality.household_kwh_for_hour(h, zones) for h in range(24))
    return full_days * day + today


@each_personality
@each_period
def test_personality_history_general_and_by_zone(
    db: FakeConsumptionDatabase, personality: PersonalityAverages, periodo: str
) -> None:
    hogar_id, ids = seed_personality(db, personality)
    general = history(periodo, hogar_id=hogar_id)

    assert general.total_kwh == pytest.approx(expected_kwh(personality, periodo))
    assert len(general.serie) == POINTS[periodo]
    shares = general.participacion_zonas
    assert len(shares) == len(personality.zone_kwh_per_day)  # solo sus zonas
    assert sum(s.participacion_pct for s in shares) == pytest.approx(100.0)
    assert [s.nombre for s in shares] == sorted(s.nombre for s in shares)
    order = [s.zona_id for s in shares]
    for point in general.serie:
        assert [z.zona_id for z in point.zonas] == order
    assert general.comparacion.mensaje_codigo == "historial_comparacion.similar"
    assert general.costo.incluye_cargo_fijo is (periodo == "mes")
    assert general.costo.proyeccion_cierre_cop is not None
    assert general.ultimo_pico is None

    share_by_zone = {s.zona_id: s.energia_kwh for s in shares}
    for zone, zona_id in ids.items():
        filtered = history(periodo, zona_id=zona_id, hogar_id=hogar_id)
        assert filtered.zona_id == zona_id
        assert filtered.participacion_zonas is None
        assert all(point.zonas is None for point in filtered.serie)
        assert filtered.total_kwh == pytest.approx(expected_kwh(personality, periodo, zone))
        assert filtered.total_kwh == pytest.approx(share_by_zone[zona_id])
        assert filtered.costo.incluye_cargo_fijo is False


@pytest.mark.parametrize("periodo", ["semana", "mes"])
def test_personality_order_in_total_kwh(db: FakeConsumptionDatabase, periodo: str) -> None:
    """compacto < eficiente < intermedio < familiar < amplio en `total_kwh` (promedios)."""
    personalities = load_personalities()
    totals = []
    for name in PERSONALITY_ORDER:
        hogar_id, _ = seed_personality(db, personalities[name])
        totals.append(history(periodo, hogar_id=hogar_id).total_kwh)
    assert totals == sorted(totals) and len(set(totals)) == len(totals)


# ------------------------------------------------------------------ personalidades (simulador)
def seed_simulated(db: FakeConsumptionDatabase, name: str) -> UUID:
    """Desde el 25/09 hasta la hora 14:00 de hoy, simulado con el perfil oficial y solo sus zonas."""
    personality = load_personalities()[name]
    hogar_id = stable_id("hogar", "historial", "simulado", name)
    zone_ids = {zone: db.add_zone(hogar_id, zone, zone) for zone in personality.zone_kwh_per_day}
    first = SEED_START.date().toordinal() * 24
    last = TODAY.toordinal() * 24 + 15  # exclusivo: hasta las 14:00 inclusive
    series = simulate_household(hogar_id, final_profiles()[name], zone_ids, first, last)
    for zone, readings in series.items():
        db.set_series(zone_ids[zone], {hour_from_index(r.index): r.total for r in readings})
    return hogar_id


def test_simulated_personality_order_in_week_and_month_total(
    db: FakeConsumptionDatabase,
) -> None:
    """compacto < eficiente < intermedio < familiar < amplio en `total_kwh` de Semana y Mes, con
    lecturas del simulador; cada respuesta valida contra `Historial`."""
    totals: dict[str, list[float]] = {"semana": [], "mes": []}
    for name in PERSONALITY_ORDER:
        hogar_id = seed_simulated(db, name)
        for periodo, values in totals.items():
            result = history(periodo, hogar_id=hogar_id)
            assert all(point.energia_kwh is not None for point in result.serie)
            assert result.comparacion.estado != "sin_datos"
            values.append(result.total_kwh)
    for values in totals.values():
        assert values == sorted(values) and len(set(values)) == len(values)


def test_recovery_now_is_utc_aware_default_and_range_in_bogota(
    db: FakeConsumptionDatabase,
) -> None:
    """Un `now` en UTC da el mismo rango que su hora de Bogotá."""
    seed_household(db)
    result = history("dia", now=NOW.astimezone(UTC))
    assert result.inicio == RANGE_START["dia"] and result.fin == END
