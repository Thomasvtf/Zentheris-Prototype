"""Pruebas de app.services.onboarding con `app.data.*` falso en memoria (sin base ni red).

RN-X-02, RN-X-03, RN-X-04, RN-IV-01, RN-IV-07, RN-II-01, RN-II-03, DC-33, DC-35, DC-37, DC-38.
El simulador y las reglas de zonas son los reales, con los perfiles de `docs/datos/perfiles/`.
Los dobles (`FakeDatabase` y compañía) están en `tests/helpers/onboarding.py`.
"""

import logging
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import count
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.data import alerts as alerts_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import simulation_profiles as profiles_data
from app.data import tips as tips_data
from app.data.households import HouseholdRow
from app.data.memberships import ActiveMembershipExistsError, MembershipSummaryRow
from app.data.simulation_profiles import SimulationProfileRow
from app.domain import alert_rules
from app.domain.formats import ZONE_NAMES
from app.domain.simulator import HOURS_BACKFILL, TIMEZONE
from app.domain.zone_rules import BASIC_ZONES, FALLBACK_PERSONALITY, ZONE_TYPES
from app.errors import ApiError, CodigoError
from app.schemas.common import Rol
from app.schemas.households import Hogar, Permisos
from app.services import onboarding as service
from tests.helpers.onboarding import (
    EMAIL,
    HOUSEHOLD_NAME,
    LAST_HOUR,
    NOW,
    REFERENCE_HOUSEHOLDS,
    STEPS,
    USER_ID,
    FakeDatabase,
    install_fake_database,
    make_payload,
    missing_profile_error,
    run,
    run_error,
)
from tests.helpers.personalities import PERSONALITY_ORDER, load_personalities
from tests.simulator.support import final_profiles


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeDatabase:
    return install_fake_database(monkeypatch)


@pytest.fixture
def stable_uuids(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ids repetibles: las lecturas dependen del id del hogar (RN-IV-04)."""
    numbers = count(1)
    monkeypatch.setattr(service, "uuid4", lambda: UUID(int=next(numbers)))
    yield


each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)


def readings_by_zone(db: FakeDatabase) -> dict[str, list[dict[str, Any]]]:
    zone_types = {row["id"]: row["tipo"] for row in db.saved["zonas"]}
    zone_of_sensor = {row["id"]: zone_types[row["zona_id"]] for row in db.saved["sensores_zona"]}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in db.saved["lecturas"]:
        grouped[zone_of_sensor[row["sensor_id"]]].append(row)
    return dict(grouped)


# ------------------------------------------------------------------ las 5 personalidades
@each_personality
def test_each_personality_is_assigned_and_fills_only_its_zones(db: FakeDatabase, name: str) -> None:
    """RN-X-04, RN-IV-01, RN-IV-07: 720 lecturas por zona elegida, con la personalidad esperada."""
    housing, zones = REFERENCE_HOUSEHOLDS[name]
    assert set(zones) <= set(load_personalities()[name].zone_kwh_per_day)

    run(db, make_payload(housing, zones))

    (household,) = db.saved["hogares"]
    assert household["perfil_simulacion_id"] == db.profiles[name].id
    assert db.requested_profiles == [name, FALLBACK_PERSONALITY]
    assert db.used_profiles == [name]

    by_zone = readings_by_zone(db)
    assert set(by_zone) == set(zones)
    assert len(db.saved["lecturas"]) == HOURS_BACKFILL * len(zones) == 720 * len(zones)
    expected_hours = {LAST_HOUR - timedelta(hours=offset) for offset in range(720)}
    for rows in by_zone.values():
        assert {row["fecha_hora"] for row in rows} == expected_hours
        assert sum(row["consumo_kwh"] for row in rows) > 0
        assert all(isinstance(row["consumo_kwh"], Decimal) for row in rows)
        assert {row["calidad"] for row in rows} == {"simulada"}


@each_personality
def test_response_is_the_household_without_the_personality(db: FakeDatabase, name: str) -> None:
    housing, zones = REFERENCE_HOUSEHOLDS[name]
    hogar = run(db, make_payload(housing, zones))
    assert hogar == Hogar(
        id=db.saved["hogares"][0]["id"],
        nombre=HOUSEHOLD_NAME,
        tipo_vivienda=housing,
        rol_usuario=Rol.ADMINISTRADOR,
        permisos=Permisos(
            ver_consumo_actual=True,
            ver_historial=True,
            recibir_alertas=True,
            modificar_metas=False,
        ),
    )
    text = hogar.model_dump_json()
    assert name not in text
    assert str(db.profiles[name].id) not in text


def test_monthly_consumption_respects_the_order(
    monkeypatch: pytest.MonkeyPatch, stable_uuids: None
) -> None:
    """compacto < eficiente < intermedio < familiar < amplio en los hogares de referencia."""
    totals = []
    for name in PERSONALITY_ORDER:
        with monkeypatch.context() as patch:
            db = install_fake_database(patch)
            run(db, make_payload(*REFERENCE_HOUSEHOLDS[name]))
        totals.append(sum(row["consumo_kwh"] for row in db.saved["lecturas"]))
    assert totals == sorted(totals)
    assert len(set(totals)) == len(PERSONALITY_ORDER)


def test_duplex_with_nine_zones_saves_6480_readings_in_one_batch(db: FakeDatabase) -> None:
    run(db, make_payload("duplex", ZONE_TYPES))
    assert len(db.saved["lecturas"]) == 6480
    assert db.events.count("insert_readings_batch") == 1


# ------------------------------------------------------------------ respaldo de RN-X-04
@pytest.mark.parametrize("name", [n for n in PERSONALITY_ORDER if n != FALLBACK_PERSONALITY])
@pytest.mark.parametrize("how", ["inactiva", "ausente"])
def test_fallback_when_the_assigned_personality_is_not_available(
    db: FakeDatabase, name: str, how: str
) -> None:
    housing, zones = REFERENCE_HOUSEHOLDS[name]
    if how == "inactiva":
        db.set_active(name, False)
    else:
        del db.profiles[name]
    run(db, make_payload(housing, zones))
    assert db.saved["hogares"][0]["perfil_simulacion_id"] == db.profiles[FALLBACK_PERSONALITY].id
    assert db.used_profiles == [FALLBACK_PERSONALITY]
    assert len(db.saved["lecturas"]) == 720 * len(zones)


# ------------------------------------------------------------------ transacción e ids
def test_steps_run_in_order_inside_one_transaction(db: FakeDatabase) -> None:
    run(db)
    assert tuple(db.events) == STEPS
    assert (db.commits, db.rollbacks) == (1, 0)


def test_ids_of_household_zones_source_and_sensors_are_coherent(db: FakeDatabase) -> None:
    """DC-38: zonas, fuente y sensores del mismo hogar; un sensor por zona."""
    hogar = run(db, make_payload("casa", ZONE_TYPES))

    (household,) = db.saved["hogares"]
    (member,) = db.saved["hogar_miembros"]
    (source,) = db.saved["fuentes_principales"]
    assert household["id"] == hogar.id
    assert household["tipo_vivienda"] == "casa"
    assert member == {"hogar_id": hogar.id, "usuario_id": USER_ID, "fecha_ingreso": NOW}
    assert source["hogar_id"] == hogar.id
    assert source["nombre"] == f"Fuente principal {HOUSEHOLD_NAME}"

    zones, sensors = db.saved["zonas"], db.saved["sensores_zona"]
    assert {row["hogar_id"] for row in zones} == {hogar.id}
    assert {row["tipo"]: row["nombre"] for row in zones} == dict(ZONE_NAMES)
    assert {row["zona_id"] for row in sensors} == {row["id"] for row in zones}
    assert {row["fuente_principal_id"] for row in sensors} == {source["id"]}
    assert {row["sensor_id"] for row in db.saved["lecturas"]} == {row["id"] for row in sensors}

    ids = [hogar.id, source["id"], *(row["id"] for row in (*zones, *sensors))]
    assert len(set(ids)) == 2 + 9 + 9
    assert all(value.version == 4 for value in ids)


def test_two_onboardings_do_not_share_ids_nor_readings(db: FakeDatabase) -> None:
    first, second = run(db), run(db)
    assert first.id != second.id
    assert len({row["sensor_id"] for row in db.saved["lecturas"]}) == 2 * len(BASIC_ZONES)


# ------------------------------------------------------------------ reloj inyectado
@pytest.mark.parametrize(
    ("now", "last"),
    [
        (NOW, LAST_HOUR),
        (NOW.astimezone(UTC), LAST_HOUR),
        (datetime(2026, 11, 22, 15, 0, tzinfo=TIMEZONE), LAST_HOUR),
        (
            datetime(2026, 11, 22, 14, 59, 59, tzinfo=TIMEZONE),
            datetime(2026, 11, 22, 13, tzinfo=TIMEZONE),
        ),
        (
            datetime(2026, 11, 22, 0, 10, tzinfo=TIMEZONE),
            datetime(2026, 11, 21, 23, tzinfo=TIMEZONE),
        ),
    ],
)
def test_backfill_ends_at_the_last_complete_hour(
    db: FakeDatabase, now: datetime, last: datetime
) -> None:
    run(db, now=now)
    hours = [row["fecha_hora"] for row in db.saved["lecturas"]]
    assert max(hours) == last
    assert min(hours) == last - timedelta(hours=719)
    assert db.saved["hogar_miembros"][0]["fecha_ingreso"] == now


def test_without_clock_it_uses_the_current_time_in_utc(db: FakeDatabase) -> None:
    before = datetime.now(UTC)
    run(db, now=None)
    joined_at = db.saved["hogar_miembros"][0]["fecha_ingreso"]
    assert joined_at.utcoffset() == timedelta(0)
    assert before <= joined_at <= datetime.now(UTC)
    last = max(row["fecha_hora"] for row in db.saved["lecturas"])
    assert timedelta(hours=1) <= joined_at - last < timedelta(hours=2)


# ------------------------------------------------------------------ sin alertas (DC-35)
@each_personality
def test_backfill_never_creates_alerts_nor_tips(
    db: FakeDatabase, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("el backfill no genera alertas ni consejos (DC-35)")

    for module in (alerts_data, tips_data, alert_rules):
        for attribute, value in list(vars(module).items()):
            if callable(value) and not isinstance(value, type) and not attribute.startswith("_"):
                monkeypatch.setattr(module, attribute, forbidden)
    run(db, make_payload(*REFERENCE_HOUSEHOLDS[name]))
    assert db.commits == 1
    assert not {event for event in db.events if "alert" in event or "tip" in event}


# ------------------------------------------------------------------ zonas inválidas (422)
@pytest.mark.parametrize(
    ("housing", "zones", "code"),
    [
        ("apartaestudio", (*BASIC_ZONES, "terraza"), CodigoError.ZONAS_NO_PERMITIDAS),
        ("apartamento", ("cocina", "sala", "dormitorio"), CodigoError.ZONAS_BASICAS_FALTANTES),
        (
            "apartaestudio",
            ("cocina", "sala", "oficina", "lavanderia"),
            CodigoError.CANTIDAD_ZONAS_INVALIDA,
        ),
        ("casa", (*BASIC_ZONES, "bano"), CodigoError.ZONAS_DUPLICADAS),
    ],
)
def test_invalid_zones_are_422_without_touching_the_database(
    db: FakeDatabase, housing: str, zones: tuple[str, ...], code: CodigoError
) -> None:
    error = run_error(db, make_payload(housing, zones))
    assert (error.status_code, error.codigo) == (422, code)
    assert db.events == []
    db.assert_nothing_saved()


# ------------------------------------------------------------------ membresía activa (409)
def test_active_membership_is_409_before_writing(db: FakeDatabase) -> None:
    db.membership = MembershipSummaryRow(uuid4(), uuid4(), "miembro")
    error = run_error(db)
    assert (error.status_code, error.codigo) == (409, CodigoError.MEMBRESIA_ACTIVA_EXISTENTE)
    assert db.events == ["get_active_membership_of_user"]
    db.assert_nothing_saved()


def test_invalid_zones_are_reported_before_the_membership(db: FakeDatabase) -> None:
    db.membership = MembershipSummaryRow(uuid4(), uuid4(), "administrador")
    assert run_error(db, make_payload("casa", BASIC_ZONES[:3])).status_code == 422


def test_simultaneous_onboarding_is_409_and_reverts_the_household(db: FakeDatabase) -> None:
    """Carrera: el índice único rechaza la segunda membresía activa (RN-II-01)."""
    db.failures["insert_admin_membership"] = ActiveMembershipExistsError("otra membresía")
    error = run_error(db)
    assert (error.status_code, error.codigo) == (409, CodigoError.MEMBRESIA_ACTIVA_EXISTENTE)
    assert db.rollbacks == 1
    assert db.events[-1] == "rollback"
    db.assert_nothing_saved()


def test_conflict_is_409_even_if_the_rollback_fails(db: FakeDatabase) -> None:
    db.failures["insert_admin_membership"] = ActiveMembershipExistsError("otra membresía")
    db.rollback_failure = RuntimeError("conexión perdida")
    assert run_error(db).codigo == CodigoError.MEMBRESIA_ACTIVA_EXISTENTE
    assert db.commits == 0


# ------------------------------------------------------------------ log
def _set_failure(step: str, error: Exception) -> Callable[[FakeDatabase], None]:
    def apply(db: FakeDatabase) -> None:
        db.failures[step] = error

    return apply


def test_success_log_has_counts_and_times_only(
    db: FakeDatabase, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        hogar = run(db, make_payload("duplex", ZONE_TYPES))
    (record,) = [r for r in caplog.records if r.name == "app.services.onboarding"]
    assert record.levelno == logging.INFO
    message = record.getMessage()
    for fragment in ("zonas=9", "lecturas=6480", "generar_ms=", "insertar_ms=", "total_ms="):
        assert fragment in message
    times = [float(part.split("=")[1]) for part in message.split() if "_ms=" in part]
    generate_ms, insert_ms, total_ms = times
    assert 0 <= generate_ms and 0 <= insert_ms
    assert generate_ms + insert_ms <= total_ms + 0.2  # cada valor se redondea a 0,1 ms
    secrets = [HOUSEHOLD_NAME, "Secreto", EMAIL, str(USER_ID), str(hogar.id), "Consumo"]
    secrets += [str(row["id"]) for row in (*db.saved["zonas"], *db.saved["sensores_zona"])]
    assert not [secret for secret in secrets if secret in caplog.text]


def test_success_is_logged_only_after_the_commit(
    db: FakeDatabase, caplog: pytest.LogCaptureFixture
) -> None:
    db.failures["commit"] = RuntimeError("conexión perdida")
    with caplog.at_level(logging.DEBUG):
        run_error(db)
    assert [record.levelno for record in caplog.records] == [logging.ERROR]


@pytest.mark.parametrize(
    "arrange",
    [
        pytest.param(_set_failure("insert_admin_membership", missing_profile_error()), id="23503"),
        pytest.param(
            _set_failure("insert_readings_batch", RuntimeError(f"{USER_ID} {HOUSEHOLD_NAME}")),
            id="otra",
        ),
    ],
)
def test_failure_log_has_no_personal_data(
    db: FakeDatabase,
    caplog: pytest.LogCaptureFixture,
    stable_uuids: None,
    arrange: Callable[[FakeDatabase], None],
) -> None:
    arrange(db)
    db.rollback_failure = RuntimeError(f"rollback {USER_ID} {HOUSEHOLD_NAME}")
    with caplog.at_level(logging.DEBUG):
        error = run_error(db)
    assert error.codigo in (CodigoError.BACKFILL_FALLIDO, CodigoError.FICHA_NO_CREADA)
    assert caplog.records
    for record in caplog.records:
        assert record.exc_info is None and record.stack_info is None
    secrets = [HOUSEHOLD_NAME, "Secreto", EMAIL, str(USER_ID), str(UUID(int=1)), "DETAIL", "insert"]
    logged = caplog.text.replace("insert_readings_batch", "")
    assert not [secret for secret in secrets if secret in logged]


def test_failure_log_has_the_type_and_the_sqlstate(
    db: FakeDatabase, caplog: pytest.LogCaptureFixture
) -> None:
    db.failures["insert_admin_membership"] = missing_profile_error()
    with caplog.at_level(logging.DEBUG):
        run_error(db)
    (record,) = caplog.records
    assert record.levelno == logging.ERROR
    assert "tipo=IntegrityError" in record.getMessage()
    assert "sqlstate=23503" in record.getMessage()
    assert "origen=app.services.onboarding:" in record.getMessage()


def test_failure_without_sqlstate_says_so(
    db: FakeDatabase, caplog: pytest.LogCaptureFixture
) -> None:
    db.failures["insert_zones"] = KeyError(HOUSEHOLD_NAME)
    with caplog.at_level(logging.DEBUG):
        run_error(db)
    assert "tipo=KeyError sqlstate=- " in caplog.records[0].getMessage()


# ------------------------------------------------------------------ reversión rota, motor real
# SQLite en archivo con su pool real (QueuePool) y SIN hide_parameters: el texto de un
# IntegrityError real lleva el SQL y sus parámetros (id del hogar, nombre y usuario).
REAL_TABLES = (
    "create table hogares (id text primary key, nombre text unique)",
    "create table miembros (usuario_id text unique, hogar_id text, nombre_hogar text)",
)


def _real_data(monkeypatch: pytest.MonkeyPatch, variant: str) -> None:
    """`app.data.*` que escriben de verdad en la sesión; cada variante falla en un punto."""

    def get_active_membership_of_user(session: Session, usuario_id: UUID) -> None:
        session.exec(text("select 1"))  # abre la transacción, como la consulta real

    def get_profiles(_session: Session, names: Sequence[str]) -> dict[str, SimulationProfileRow]:
        profiles = final_profiles()
        return {n: SimulationProfileRow(uuid4(), n, True, profiles[n]) for n in names}

    def insert_household(session: Session, *, hogar_id: UUID, nombre: str, **_: Any) -> Any:
        session.exec(
            text("insert into hogares (id, nombre) values (:id, :nombre)"),
            params={"id": str(hogar_id), "nombre": nombre},
        )
        return HouseholdRow(hogar_id, nombre, "apartamento", True, True, True, False)

    def insert_admin_membership(
        session: Session, *, hogar_id: UUID, usuario_id: UUID, joined_at: datetime
    ) -> None:
        if variant == "fk-postgres":
            raise missing_profile_error()
        try:  # como data/memberships.py: el 23505 del índice se traduce `from None`
            session.exec(
                text("insert into miembros values (:usuario_id, :hogar_id, :nombre_hogar)"),
                params={
                    "usuario_id": str(usuario_id),
                    "hogar_id": str(hogar_id),
                    "nombre_hogar": HOUSEHOLD_NAME,
                },
            )
        except IntegrityError:
            raise ActiveMembershipExistsError("El usuario ya tiene un hogar activo.") from None
        raise AssertionError("la variante debía fallar antes")

    monkeypatch.setattr(
        memberships_data, "get_active_membership_of_user", get_active_membership_of_user
    )
    monkeypatch.setattr(memberships_data, "insert_admin_membership", insert_admin_membership)
    monkeypatch.setattr(profiles_data, "get_profiles", get_profiles)
    monkeypatch.setattr(households_data, "insert_household", insert_household)


@pytest.mark.parametrize(
    ("variant", "seed", "status"),
    [
        ("unique-sqlite", "insert into hogares values ('previo', :nombre)", 500),
        ("fk-postgres", None, 404),
        ("carrera", "insert into miembros values (:usuario_id, 'otro', :nombre)", 409),
    ],
)
def test_broken_rollback_with_a_real_engine_logs_no_personal_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    stable_uuids: None,
    variant: str,
    seed: str | None,
    status: int,
) -> None:
    """Ningún logger (tampoco el pool de SQLAlchemy) recibe el DETAIL, los ids ni el nombre."""
    engine = create_engine(f"sqlite:///{tmp_path / 'onboarding.db'}")
    with engine.begin() as connection:
        for statement in REAL_TABLES:
            connection.exec_driver_sql(statement)
        if seed is not None:
            connection.execute(text(seed), {"nombre": HOUSEHOLD_NAME, "usuario_id": str(USER_ID)})
    _real_data(monkeypatch, variant)

    def broken_rollback(_connection: Any) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    working_rollback = engine.dialect.do_rollback
    monkeypatch.setattr(engine.dialect, "do_rollback", broken_rollback)
    with (
        caplog.at_level(logging.DEBUG),
        Session(engine) as session,
        pytest.raises(ApiError) as caught,
    ):
        service.create_household_onboarding(session, USER_ID, make_payload(), NOW)
    monkeypatch.setattr(engine.dialect, "do_rollback", working_rollback)

    assert caught.value.status_code == status
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    names = {record.name for record in caplog.records}
    assert "app.services.onboarding" in names
    assert any(name.startswith("sqlalchemy") for name in names), names  # el pool sí registró
    formatter = logging.Formatter()
    logged = "\n".join(
        record.getMessage()
        + (formatter.formatException(record.exc_info) if record.exc_info else "")
        + (record.stack_info or "")
        for record in caplog.records
    )
    secrets = [HOUSEHOLD_NAME, "Secreto", EMAIL, str(USER_ID), str(UUID(int=1)), "DETAIL"]
    assert not [secret for secret in secrets if secret in logged]

    with engine.connect() as connection:
        rows = connection.execute(text("select count(*) from hogares")).scalar_one()
    assert rows == (1 if variant == "unique-sqlite" else 0)  # el hogar nuevo no quedó
    engine.dispose()
