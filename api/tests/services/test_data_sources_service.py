"""Pruebas de `app.services.consumption.get_data_sources` (`obtenerFuentesDatos`, fase 10).

Con `app.data.*` falso en memoria (sin base ni red): `consumption_fakes.py` para zonas, lecturas
y el espía de la recuperación, más la fuente principal y los sensores de esta prueba. Reglas:
RN-XVI-06, RN-III-03, RN-XVII-01, RN-IV-05, DC-34 y las decisiones D1 y D5 de la fase 10:

- D1 (decisión de Nicolás): primero la recuperación de horas; si falla (`HourRecoveryError`
  dentro de `fill_missing_hours`), la consulta responde el objeto completo con lo guardado, no
  un 500, y el aviso queda en el log sin datos del hogar.
- D5: todos los sensores, orden por nombre visible de la zona y luego id; pausado gana a
  sin_datos; la fuente principal suma solo los sensores que cuentan y es null si a alguno le
  falta la lectura; sin permiso, `valores_ocultos` y todos los kW null.
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.data import households as households_data
from app.data import readings as readings_data
from app.data.households import MainSourceRow, ZoneSensorRow
from app.domain.simulator import TIMEZONE
from app.schemas.consumption import FuentesDatos
from app.services import consumption as service
from app.services import hour_recovery
from app.services.hour_recovery import RECOVERY_SKIPPED_MESSAGE, HourRecoveryError
from tests.helpers.personalities import PERSONALITY_ORDER, PersonalityAverages, load_personalities
from tests.services.consumption_fakes import (
    FakeConsumptionDatabase,
    FakeSession,
    install_fake_consumption_database,
)
from tests.simulator.support import stable_id

HOGAR = stable_id("hogar", "fuentes")
OTRO_HOGAR = stable_id("hogar", "fuentes", "otro")
USER = stable_id("usuario", "fuentes")
NOW = datetime(2026, 11, 23, 15, 20, tzinfo=TIMEZONE)  # hora evaluada 14:00-15:00
HOUR = datetime(2026, 11, 23, 14, tzinfo=TIMEZONE)
SOURCE_NAME = "Fuente principal Casa Pérez"

each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


class SourcesDatabase:
    """Fuente principal y sensores en memoria, derivados de las zonas de `FakeConsumptionDatabase`."""

    def __init__(self, db: FakeConsumptionDatabase) -> None:
        self.db = db
        self.sources: dict[UUID, MainSourceRow] = {}

    def add_source(self, hogar_id: UUID, nombre: str = SOURCE_NAME, estado: str = "activa") -> UUID:
        source_id = stable_id("fuente", str(hogar_id))
        self.sources[hogar_id] = MainSourceRow(id=source_id, nombre=nombre, estado=estado)
        return source_id

    def get_main_source(self, session: Any, hogar_id: UUID) -> MainSourceRow | None:
        self.db.calls.append(("main_source", hogar_id))
        return self.sources.get(hogar_id)

    def list_zone_sensors(self, session: Any, hogar_id: UUID) -> list[ZoneSensorRow]:
        """Como la consulta: solo zonas del hogar con sensor, ordenadas por id de zona."""
        self.db.calls.append(("zone_sensors", hogar_id))
        rows = [
            ZoneSensorRow(
                sensor_id=sensor_id(zone.id),
                zona_id=zone.id,
                zona_tipo=zone.tipo,
                zona_estado=zone.estado,
                sensor_estado=zone.sensor_estado,
            )
            for zone in self.db.zones.get(hogar_id, [])
            if zone.sensor_estado is not None
        ]
        return sorted(rows, key=lambda row: str(row.zona_id))


def sensor_id(zona_id: UUID) -> UUID:
    return stable_id("sensor", str(zona_id))


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeConsumptionDatabase:
    return install_fake_consumption_database(monkeypatch)


def install_sources(monkeypatch: pytest.MonkeyPatch, db: FakeConsumptionDatabase) -> SourcesDatabase:
    sources = SourcesDatabase(db)
    monkeypatch.setattr(households_data, "get_main_source", sources.get_main_source)
    monkeypatch.setattr(households_data, "list_zone_sensors", sources.list_zone_sensors)
    return sources


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch, db: FakeConsumptionDatabase) -> SourcesDatabase:
    return install_sources(monkeypatch, db)


def seed(
    db: FakeConsumptionDatabase,
    sources: SourcesDatabase,
    values: dict[str, float | None],
    *,
    hogar_id: UUID = HOGAR,
    estados: dict[str, tuple[str, str]] | None = None,
) -> dict[str, UUID]:
    """Zonas con su lectura en HOUR (None = sin lectura) y la hora anterior siempre guardada."""
    sources.add_source(hogar_id)
    ids = {}
    for tipo, kwh in values.items():
        zona_estado, sensor_estado = (estados or {}).get(tipo, ("activa", "activo"))
        ids[tipo] = db.add_zone(hogar_id, tipo, tipo, zona_estado, sensor_estado)
        series = {HOUR - timedelta(hours=1): 9.9}  # fuera del rango: no debe leerse
        if kwh is not None:
            series[HOUR] = kwh
        db.set_series(ids[tipo], series)
    return ids


def call(
    session: FakeSession, can_view_values: bool = True, now: datetime = NOW, hogar_id: UUID = HOGAR
) -> FuentesDatos:
    result = service.get_data_sources(session, USER, hogar_id, can_view_values, now)
    return FuentesDatos.model_validate_json(result.model_dump_json())  # ida y vuelta (contrato)


def by_zone(result: FuentesDatos, ids: dict[str, UUID]) -> dict[str, Any]:
    reverse = {zona_id: tipo for tipo, zona_id in ids.items()}
    return {reverse[sensor.zona_id]: sensor for sensor in result.sensores}


# ------------------------------------------------------------------ recuperación primero (D1)
def test_recovery_runs_first_with_the_same_now_and_reads_only_the_evaluated_hour(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    seed(db, sources, {"cocina": 0.5, "sala": 0.25})
    session = FakeSession()

    result = call(session)

    assert db.calls[0] == ("recovery", HOGAR, NOW)
    assert db.names().count("recovery") == 1
    (readings,) = [c for c in db.calls if c[0] == "readings"]
    assert readings[3:] == (HOUR, HOUR)  # solo la última hora completa
    assert result.hora.inicio == HOUR and result.hora.fin == HOUR + timedelta(hours=1)
    assert session.commits == 0 and session.rollbacks == 0  # solo lectura


def test_default_now_is_utc_and_drives_the_evaluated_hour(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    seed(db, sources, {"cocina": 0.5})
    result = service.get_data_sources(FakeSession(), USER, HOGAR, True)
    recovery_now = db.calls[0][2]
    assert recovery_now.utcoffset() == timedelta(0)
    assert result.hora.fin <= recovery_now


def test_recovery_error_answers_200_with_saved_data_and_logs_a_warning(
    db: FakeConsumptionDatabase,
    sources: SourcesDatabase,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Decisión de Nicolás: `fill_missing_hours` lanza HourRecoveryError → objeto completo con
    lo guardado (la cocina tiene su lectura; a la sala le faltaba y sale sin_datos), WARNING sin
    datos del hogar, nunca un 500."""
    ids = seed(db, sources, {"cocina": 0.5, "sala": None})

    def failing_recovery(session: Any, hogar_id: UUID, now: datetime | None = None) -> int:
        db.calls.append(("recovery", hogar_id, now))
        raise HourRecoveryError()

    monkeypatch.setattr(hour_recovery, "fill_missing_hours", failing_recovery)

    with caplog.at_level(logging.WARNING):
        result = call(FakeSession())

    assert isinstance(result, FuentesDatos)
    warnings = [r for r in caplog.records if r.getMessage() == RECOVERY_SKIPPED_MESSAGE]
    assert len(warnings) == 1 and warnings[0].levelno == logging.WARNING
    assert str(HOGAR) not in caplog.text and str(USER) not in caplog.text
    assert result.fuente_principal.nombre == SOURCE_NAME
    assert result.fuente_principal.potencia_kw is None  # a un sensor que cuenta le falta la hora
    sensors = by_zone(result, ids)
    assert sensors["cocina"].estado == "activo"
    assert sensors["cocina"].potencia_kw == pytest.approx(0.5)
    assert sensors["sala"].estado == "sin_datos"
    assert sensors["sala"].potencia_kw is None


def test_real_recovery_failure_also_answers_with_saved_data(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """La recuperación real falla al pedir el candado (OperationalError → HourRecoveryError)."""
    from sqlalchemy.exc import OperationalError

    db = install_fake_consumption_database(monkeypatch, spy_recovery=False)
    sources = install_sources(monkeypatch, db)

    def failing_lock(session: object, hogar_id: UUID) -> None:
        raise OperationalError("SELECT", {}, Exception(f"DETAIL: hogar {hogar_id} secreto"))

    monkeypatch.setattr(readings_data, "lock_household_recovery", failing_lock)
    seed(db, sources, {"cocina": 0.5, "bano": 0.25})
    session = FakeSession()

    with caplog.at_level(logging.WARNING):
        result = call(session)

    assert [r.getMessage() for r in caplog.records].count(RECOVERY_SKIPPED_MESSAGE) == 1
    assert "secreto" not in caplog.text and str(HOGAR) not in caplog.text
    assert session.commits == 0 and session.rollbacks == 1
    assert result.fuente_principal.potencia_kw == pytest.approx(0.75)


# ------------------------------------------------------------------ valores, estados y suma (D5)
def test_sensors_names_values_and_source_sum(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    ids = seed(db, sources, {"cocina": 0.5, "sala": 0.25, "bano": 0.125})

    result = call(FakeSession())

    assert result.valores_ocultos is False
    assert result.fuente_principal.id == stable_id("fuente", str(HOGAR))
    assert result.fuente_principal.estado == "activa"
    assert result.fuente_principal.potencia_kw == pytest.approx(0.875)
    sensors = by_zone(result, ids)
    assert sensors["cocina"].nombre == "Sensor Cocina"
    assert sensors["cocina"].zona_nombre == "Cocina"
    assert sensors["bano"].nombre == "Sensor Baño"
    assert sensors["cocina"].id == sensor_id(ids["cocina"])
    assert {tipo: s.potencia_kw for tipo, s in sensors.items()} == {
        "cocina": pytest.approx(0.5),
        "sala": pytest.approx(0.25),
        "bano": pytest.approx(0.125),
    }
    assert {s.estado for s in result.sensores} == {"activo"}


def test_sensor_without_reading_is_sin_datos_and_source_is_null(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    ids = seed(db, sources, {"cocina": 0.5, "sala": None})

    result = call(FakeSession())

    sensors = by_zone(result, ids)
    assert sensors["sala"].estado == "sin_datos"
    assert sensors["sala"].potencia_kw is None  # null = sin dato, nunca 0
    assert sensors["cocina"].potencia_kw == pytest.approx(0.5)
    assert result.fuente_principal.potencia_kw is None  # nunca un total parcial


def test_paused_and_inactive_sensors_show_their_state_but_do_not_sum(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    """Pausado con lectura: muestra sus kW y estado «pausado», no suma. Zona inactiva con
    sensor activo: estado «activo», no suma. Uno de ellos sin lectura no anula la fuente."""
    ids = seed(
        db,
        sources,
        {"cocina": 0.5, "sala": 0.25, "oficina": 0.3, "terraza": None},
        estados={
            "sala": ("activa", "pausado"),
            "oficina": ("inactiva", "activo"),
            "terraza": ("activa", "pausado"),
        },
    )

    result = call(FakeSession())

    sensors = by_zone(result, ids)
    assert sensors["sala"].estado == "pausado"
    assert sensors["sala"].potencia_kw == pytest.approx(0.25)
    assert sensors["terraza"].estado == "pausado"  # pausado gana a sin_datos
    assert sensors["terraza"].potencia_kw is None
    assert sensors["oficina"].estado == "activo"
    assert result.fuente_principal.potencia_kw == pytest.approx(0.5)  # solo la cocina cuenta


def test_no_counting_sensor_gives_null_source(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    seed(db, sources, {"cocina": 0.5}, estados={"cocina": ("activa", "pausado")})

    result = call(FakeSession())

    assert result.fuente_principal.potencia_kw is None
    assert result.sensores[0].potencia_kw == pytest.approx(0.5)


def test_without_permission_values_are_hidden_but_states_are_shown(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    """RN-XVII-01: sin ver consumo actual (ni administrador), nombres y estados sin kW."""
    ids = seed(
        db, sources, {"cocina": 0.5, "sala": None, "bano": 0.2},
        estados={"bano": ("activa", "pausado")},
    )

    result = call(FakeSession(), can_view_values=False)

    assert result.valores_ocultos is True
    assert result.fuente_principal.potencia_kw is None
    assert result.fuente_principal.nombre == SOURCE_NAME
    assert all(sensor.potencia_kw is None for sensor in result.sensores)
    sensors = by_zone(result, ids)
    assert {tipo: s.estado for tipo, s in sensors.items()} == {
        "cocina": "activo",
        "sala": "sin_datos",
        "bano": "pausado",
    }
    assert sensors["cocina"].nombre == "Sensor Cocina"


def test_sensors_are_sorted_by_visible_zone_name(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    seed(
        db,
        sources,
        {tipo: 0.1 for tipo in ("terraza", "sala", "cuarto_servicio", "bano", "cocina", "garaje")},
    )

    result = call(FakeSession())

    assert [s.zona_nombre for s in result.sensores] == [
        "Baño",
        "Cocina",
        "Cuarto de servicio",
        "Garaje",
        "Sala",
        "Terraza",
    ]


def test_only_the_household_sensors_and_readings_are_used(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    ids = seed(db, sources, {"cocina": 0.5})
    seed(db, sources, {"cocina": 7.0, "sala": 3.0}, hogar_id=OTRO_HOGAR)

    result = call(FakeSession())

    assert [s.zona_id for s in result.sensores] == [ids["cocina"]]
    assert result.fuente_principal.potencia_kw == pytest.approx(0.5)


def test_missing_main_source_is_an_internal_error(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    """Estado imposible tras el onboarding (RN-X-03): RuntimeError → 500 ERROR_INTERNO."""
    db.add_zone(HOGAR, "cocina", "cocina")

    with pytest.raises(RuntimeError):
        service.get_data_sources(FakeSession(), USER, HOGAR, True, NOW)
    assert "readings" not in db.names()


def test_naive_now_is_rejected_before_touching_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = install_fake_consumption_database(monkeypatch, spy_recovery=False)
    sources = install_sources(monkeypatch, db)
    seed(db, sources, {"cocina": 0.5})

    with pytest.raises(ValueError):
        service.get_data_sources(FakeSession(), USER, HOGAR, True, NOW.replace(tzinfo=None))
    assert db.calls == []


# ------------------------------------------------------------------ personalidades (promedios)
def seed_personality(
    db: FakeConsumptionDatabase, sources: SourcesDatabase, personality: PersonalityAverages,
    hour: int,
) -> UUID:
    hogar_id = stable_id("hogar", "fuentes", personality.name)
    sources.add_source(hogar_id, f"Fuente principal {personality.name}")
    moment = HOUR.replace(hour=hour)
    for zone in personality.zone_kwh_per_day:
        zona_id = db.add_zone(hogar_id, zone, zone)
        db.set_series(zona_id, {moment: personality.zone_kwh_for_hour(zone, hour)})
    return hogar_id


@each_personality
@pytest.mark.parametrize("hour", [3, 14, 20])
def test_personality_sensors_are_only_its_zones_and_the_source_is_their_sum(
    db: FakeConsumptionDatabase,
    sources: SourcesDatabase,
    personality: PersonalityAverages,
    hour: int,
) -> None:
    hogar_id = seed_personality(db, sources, personality, hour)
    now = HOUR.replace(hour=hour) + timedelta(hours=1, minutes=5)

    result = call(FakeSession(), now=now, hogar_id=hogar_id)

    assert len(result.sensores) == len(personality.zone_kwh_per_day)
    assert {s.estado for s in result.sensores} == {"activo"}
    assert result.fuente_principal.potencia_kw == pytest.approx(
        personality.household_kwh_for_hour(hour)
    )
    for sensor in result.sensores:
        assert sensor.potencia_kw is not None and sensor.potencia_kw >= 0
    names = [s.zona_nombre for s in result.sensores]
    assert names == sorted(names)


def test_personality_daily_source_totals_follow_the_order(
    db: FakeConsumptionDatabase, sources: SourcesDatabase
) -> None:
    """La suma de la fuente principal en las 24 horas de un día sigue el orden compacto <
    eficiente < intermedio < familiar < amplio (promedios de los perfiles)."""
    totals = []
    for name in PERSONALITY_ORDER:
        personality = load_personalities()[name]
        hogar_id = stable_id("hogar", "fuentes", "dia", name)
        sources.add_source(hogar_id)
        zone_ids = {zone: db.add_zone(hogar_id, zone, zone) for zone in personality.zone_kwh_per_day}
        for zone, zona_id in zone_ids.items():
            db.set_series(
                zona_id,
                {
                    HOUR.replace(hour=h): personality.zone_kwh_for_hour(zone, h)
                    for h in range(24)
                },
            )
        day_total = 0.0
        for h in range(24):
            now = HOUR.replace(hour=h) + timedelta(hours=1, minutes=1)
            result = call(FakeSession(), now=now, hogar_id=hogar_id)
            assert result.fuente_principal.potencia_kw is not None
            day_total += result.fuente_principal.potencia_kw
        assert day_total == pytest.approx(personality.kwh_per_day)
        totals.append(day_total)
    assert totals == sorted(totals) and len(set(totals)) == len(totals)
