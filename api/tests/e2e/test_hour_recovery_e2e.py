"""Recuperación de horas y tarea programada de punta a punta (fase 5, B-04).

El hogar se crea con el onboarding REAL por la API (`POST /api/v1/onboarding` con token de
prueba) sobre el almacén en memoria de `test_onboarding_e2e` (`Store`). Después corren de verdad
`services.hour_recovery.fill_missing_hours`, `services.scheduler.run_hourly_generation`, el
simulador y las funciones de `app.data`; solo se reemplaza lo más bajo, como en el e2e del
onboarding. `RecoveryStore` le enseña al almacén las 4 sentencias nuevas, imitando su SQL:

- `LOCK_HOUSEHOLD_RECOVERY_SQL`: `pg_advisory_xact_lock` por hogar. Si otra transacción abierta
  lo tiene, espera; se suelta al terminar la transacción (commit, rollback o close).
- `HOUSEHOLD_PROFILE_SQL`: el perfil de `hogares.perfil_simulacion_id`, aunque esté inactivo.
- `SENSOR_GAPS_SQL`: por cada sensor 'activo' de una zona 'activa' del hogar, su primera lectura
  (`first_hour`) y las horas sin lectura (`missing_hours`) de hora en hora desde ella hasta
  `:until` inclusive (NULL → sin horas). Se imita el resultado, no las ramas del SQL (atajo
  cuando el sensor no tiene huecos internos).
- `HOUSEHOLDS_WITH_SENSORS_SQL`: hogares con algún sensor 'activo' en una zona 'activa'.

Y en `lecturas` el ON CONFLICT DO NOTHING concurrente de PostgreSQL: un INSERT que choca con
claves que otra transacción abierta ya insertó espera a que termine y luego no las cuenta.

**«La consulta» de B-04.** Las consultas de consumo, historial, fuentes y alertas son de las
fases 6–10 y aún no existen: aquí se representan llamando a `fill_missing_hours(session,
hogar_id, now)`, que es lo que esas fases deben invocar al inicio de su caso de uso, después de
la seguridad. Cuando existan, su e2e debe repetir B-04 llamando al endpoint.

Las alertas aún no se evalúan (fase 8, DC-35): la vigilancia de `test_onboarding_e2e` falla si
alguien llama a alertas o consejos. Cuando la fase 8 enganche las alertas en la recuperación,
esta vigilancia debe cambiar por la comprobación de A-01/A-02 sobre las horas en vivo.

El SQL no se ejecuta: que PostgreSQL haga lo mismo queda pendiente (B-04 sobre Postgres real).

Reglas: RN-IV-05, RN-IV-07, RN-IV-04. Decisiones: DC-34, DC-35, DC-38.
"""

import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, tzinfo
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.data import households as households_data
from app.data import readings as readings_data
from app.data import simulation_profiles as profiles_data
from app.data.database import get_session
from app.domain.simulator import hour_from_index, hour_index
from app.domain.simulator.engine import simulate_household, to_reading_rows
from app.main import create_app
from app.services import onboarding as onboarding_service
from app.services import scheduler as scheduler_service
from app.services.hour_recovery import fill_missing_hours
from app.services.scheduler import GenerationSummary, run_hourly_generation
from tests.data.fake_session import FakeResult
from tests.e2e.test_onboarding_e2e import (
    READINGS_STATEMENT,
    REFERENCE_HOUSEHOLDS,
    WAIT_SECONDS,
    Params,
    Store,
    StoreSession,
    body_of,
    forbid_alerts_and_tips,
    onboard,
    use_household_id,
)
from tests.helpers.auth import install_test_jwks, make_test_settings
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.simulator.support import bogota, final_profiles, stable_id

HOURS_OFF = 5
# Onboarding el sábado a las 22:10; el apagado de 5 h cruza la medianoche.
T = bogota(2026, 11, 21, 22, 10)
LATER = T + timedelta(hours=HOURS_OFF)  # domingo 03:10: última hora completa, la de las 02:00
END = hour_index(T)  # primera hora sin lectura después del backfill (la de las 22:00)
START = END - 720  # primera hora del backfill: la frontera de cada sensor
LOCK_STATEMENT = "LOCK_HOUSEHOLD_RECOVERY_SQL"
READ_STATEMENTS = (LOCK_STATEMENT, "HOUSEHOLD_PROFILE_SQL", "SENSOR_GAPS_SQL")
RECOVERY_STATEMENTS = (*READ_STATEMENTS, READINGS_STATEMENT)
LIST_STATEMENT = "HOUSEHOLDS_WITH_SENSORS_SQL"

Key = tuple[UUID, datetime]

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)


class OnboardingClock(datetime):
    """`datetime.now()` del onboarding congelado en T."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return T.astimezone(tz)


def other_personality(name: str) -> str:
    return PERSONALITY_ORDER[(PERSONALITY_ORDER.index(name) + 1) % len(PERSONALITY_ORDER)]


# --- el almacén con las sentencias de la fase 5 ---------------------------------------------


class RecoverySession(StoreSession):
    """Además: `exec` sin parámetros (lo usa el listado) y `close` (lo usa la tarea)."""

    def __init__(self, db: Store) -> None:
        super().__init__(db)
        self.closed = False

    def exec(self, statement: Any, *, params: Params | None = None) -> FakeResult:
        return self.db.run(self, statement, params or {})

    def close(self) -> None:
        """Como `Session.close`: descarta lo no confirmado."""
        self.closed = True
        self.db.end(self)


class RecoveryStore(Store):
    """`Store` del onboarding más las 4 sentencias de la recuperación (ver el módulo)."""

    def __init__(self) -> None:
        super().__init__()
        self.lock_waiting = threading.Event()  # alguien espera por el candado de un hogar
        for module, name, handler in (
            (readings_data, LOCK_STATEMENT, self._lock_household_recovery),
            (profiles_data, "HOUSEHOLD_PROFILE_SQL", self._household_profile),
            (readings_data, "SENSOR_GAPS_SQL", self._sensor_gaps),
            (households_data, LIST_STATEMENT, self._households_with_sensors),
        ):
            self.handlers[id(getattr(module, name))] = (name, handler)

    def open_session(self) -> RecoverySession:
        session = RecoverySession(self)
        self.sessions.append(session)
        return session

    def _active_sensors(self, session: StoreSession) -> list[tuple[Any, ...]]:
        """(hogar_id, zona tipo, sensor) de cada sensor 'activo' en una zona 'activa'."""
        zones = {
            row["id"]: row
            for row in self.view(session, "zonas").values()
            if row["estado"] == "activa"
        }
        return [
            (zones[row["zona_id"]]["hogar_id"], zones[row["zona_id"]]["tipo"], row["id"])
            for row in self.view(session, "sensores_zona").values()
            if row["estado"] == "activo" and row["zona_id"] in zones
        ]

    def _lock_household_recovery(self, session: StoreSession, params: Params) -> FakeResult:
        """pg_advisory_xact_lock: espera a la otra transacción; `end()` lo suelta."""
        key = ("pg_advisory_xact_lock", params["hogar_id"])

        def is_free() -> bool:
            return not any(
                key in other.unique_keys for other in self.sessions if other is not session
            )

        if not is_free():
            self.lock_waiting.set()
            if not self.lock.wait_for(is_free, timeout=WAIT_SECONDS):
                raise self.unexpected_use("espera sin fin por el candado del hogar")
        session.unique_keys.add(key)
        return FakeResult([{"pg_advisory_xact_lock": ""}])

    def _household_profile(self, session: StoreSession, params: Params) -> FakeResult:
        """JOIN hogares → perfiles_simulacion, sin mirar `activo`."""
        household = self.view(session, "hogares").get(params["hogar_id"])
        if household is None:
            return FakeResult()
        profile = self.view(session, "perfiles_simulacion")[household["perfil_simulacion_id"]]
        return FakeResult([profile])

    def _sensor_gaps(self, session: StoreSession, params: Params) -> FakeResult:
        """min(fecha_hora) y las horas sin lectura de [first_hour, until], de 1 h, por sensor."""
        until = params["until"].astimezone(UTC)
        stored: dict[UUID, set[datetime]] = {}
        for sensor_id, fecha_hora in self.view(session, "lecturas"):
            stored.setdefault(sensor_id, set()).add(fecha_hora)
        rows = []
        for hogar_id, tipo, sensor_id in self._active_sensors(session):
            if hogar_id != params["hogar_id"]:
                continue
            hours = stored.get(sensor_id, set())
            first = min(hours) if hours else None
            missing = []
            moment = first
            while moment is not None and moment <= until:
                if moment not in hours:
                    missing.append(moment)
                moment += timedelta(hours=1)
            rows.append(
                {
                    "sensor_id": sensor_id,
                    "zona_tipo": tipo,
                    "first_hour": first,
                    "missing_hours": missing or None,  # array_agg de cero filas es NULL
                }
            )
        return FakeResult(sorted(rows, key=lambda row: (row["zona_tipo"], row["sensor_id"])))

    def _households_with_sensors(self, session: StoreSession, _params: Params) -> FakeResult:
        ids = sorted({hogar_id for hogar_id, _tipo, _sensor in self._active_sensors(session)})
        return FakeResult([{"hogar_id": hogar_id} for hogar_id in ids])

    def _insert_readings(self, session: StoreSession, params: Params) -> FakeResult:
        """Como PostgreSQL con `lecturas_una_por_sensor_y_hora` y ON CONFLICT DO NOTHING.

        Si otra transacción abierta ya insertó alguna de estas claves, espera a que termine;
        después, lo que ella confirmó ya está en la vista y no se cuenta. Las claves se toman
        todas a la vez (los lotes van ordenados por zona y hora, así que en PostgreSQL tampoco
        se cruzan en un interbloqueo).
        """
        keys = {
            ("lecturas_una_por_sensor_y_hora", UUID(sensor), fecha_hora.astimezone(UTC))
            for sensor, fecha_hora in zip(params["sensor_ids"], params["fechas_hora"], strict=True)
        }

        def is_free() -> bool:
            return not any(
                keys & other.unique_keys for other in self.sessions if other is not session
            )

        if not is_free():
            self.waiting.set()
            if not self.lock.wait_for(is_free, timeout=WAIT_SECONDS):
                raise self.unexpected_use("espera sin fin por lecturas_una_por_sensor_y_hora")
        session.unique_keys |= keys
        return super()._insert_readings(session, params)

    # --- lo que miran las pruebas ------------------------------------------------------

    def sensors_of(self, hogar_id: UUID) -> dict[str, UUID]:
        zones = {
            row["id"]: row["tipo"] for row in self.rows("zonas") if row["hogar_id"] == hogar_id
        }
        return {
            zones[row["zona_id"]]: row["id"]
            for row in self.rows("sensores_zona")
            if row["zona_id"] in zones
        }

    def readings_of(self, hogar_id: UUID) -> dict[Key, Decimal]:
        sensors = set(self.sensors_of(hogar_id).values())
        return {
            (row["sensor_id"], row["fecha_hora"]): row["consumo_kwh"]
            for row in self.rows("lecturas")
            if row["sensor_id"] in sensors
        }

    def by_zone(self, hogar_id: UUID) -> dict[tuple[str, datetime], Decimal]:
        """Lecturas por (zona, hora): comparables entre almacenes con otros ids de sensor."""
        zone_of = {sensor: zone for zone, sensor in self.sensors_of(hogar_id).items()}
        return {
            (zone_of[sensor], hour): value
            for (sensor, hour), value in self.readings_of(hogar_id).items()
        }

    def set_state(self, table: str, key: UUID, estado: str) -> None:
        rows = self.committed[table]
        rows[key] = {**rows[key], "estado": estado}


# --- fixtures y pasos -----------------------------------------------------------------------


@pytest.fixture
def new_store(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[], RecoveryStore]]:
    """Fábrica de almacenes. La vigilancia de alertas anota en el primero (DC-35)."""
    stores: list[RecoveryStore] = []

    def make() -> RecoveryStore:
        store = RecoveryStore()
        if not stores:
            guarded = forbid_alerts_and_tips(monkeypatch, store)
            assert {"evaluate_alert_rules", "build_tips"} <= set(guarded)
        stores.append(store)
        return store

    monkeypatch.setattr(onboarding_service, "datetime", OnboardingClock)
    install_test_jwks(monkeypatch)
    yield make
    # Los servicios capturan cualquier excepción: lo inesperado se comprueba aquí.
    assert [store.unexpected for store in stores] == [[] for _ in stores]


@pytest.fixture
def db(new_store: Callable[[], RecoveryStore]) -> RecoveryStore:
    return new_store()


def client_for(db: RecoveryStore) -> TestClient:
    """La app real con cada petición sobre una sesión del almacén (sin lifespan: sin tarea)."""
    app = create_app(make_test_settings())
    app.dependency_overrides[get_settings] = make_test_settings

    def session_override() -> Iterator[RecoverySession]:
        session = db.open_session()
        try:
            yield session
        finally:
            db.end(session)

    app.dependency_overrides[get_session] = session_override
    return TestClient(app, raise_server_exceptions=False)


def create_household(
    db: RecoveryStore,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    tag: str = "e2e5",
) -> UUID:
    """Onboarding real del hogar de referencia de `name` en T, con un id de hogar fijo."""
    user_id = stable_id("usuario", tag, name)
    hogar_id = stable_id("hogar", tag, name)
    db.seed_user(user_id)
    use_household_id(monkeypatch, hogar_id)

    response = onboard(client, user_id, body_of(*REFERENCE_HOUSEHOLDS[name]))

    assert response.status_code == 201, response.text
    assert response.json()["id"] == str(hogar_id)
    assert db.committed["hogares"][hogar_id]["perfil_simulacion_id"] == db.profile_id(name)
    assert len(db.readings_of(hogar_id)) == 720 * len(REFERENCE_HOUSEHOLDS[name][1])
    return hogar_id


def recover(db: RecoveryStore, hogar_id: UUID, now: datetime = LATER) -> int:
    """«La consulta» de B-04: una sesión nueva, como una petición después del apagado."""
    session = db.open_session()
    try:
        return fill_missing_hours(session, hogar_id, now)
    finally:
        db.end(session)


def continuous(db: RecoveryStore, hogar_id: UUID, name: str, end: int) -> dict[Key, Decimal]:
    """Lo que habría guardado una generación continua desde la primera lectura (START)."""
    sensors = db.sensors_of(hogar_id)
    series = simulate_household(hogar_id, final_profiles()[name], sensors, START, end, START)
    return {
        (row["sensor_id"], row["fecha_hora"].astimezone(UTC)): row["consumo_kwh"]
        for row in to_reading_rows(sensors, series)
    }


def assert_contiguous(db: RecoveryStore, hogar_id: UUID, hours: int) -> None:
    """Cada sensor: `hours` lecturas, una por hora desde START, sin huecos ni duplicados."""
    expected = {hour_from_index(index).astimezone(UTC) for index in range(START, START + hours)}
    per_sensor: dict[UUID, list[datetime]] = {}
    for sensor_id, hour in db.readings_of(hogar_id):
        per_sensor.setdefault(sensor_id, []).append(hour)
    assert set(per_sensor) == set(db.sensors_of(hogar_id).values())
    for sensor_hours in per_sensor.values():
        assert len(sensor_hours) == hours
        assert set(sensor_hours) == expected


# --- 1. B-04: servidor apagado 5 h y luego una consulta -------------------------------------


@each_personality
def test_b04_server_off_five_hours_then_a_query(
    db: RecoveryStore, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """5 × zonas lecturas nuevas, idénticas a la generación continua; repetir no guarda nada.

    RN-IV-05, DC-34: onboarding real en T (sábado 22:10); sin tráfico hasta T+5 h (domingo
    03:10), así que faltan las horas de las 22, 23, 00, 01 y 02. Solo las zonas del hogar
    (RN-IV-07); mismos valores que sin apagado (RN-IV-04).
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = create_household(db, client_for(db), monkeypatch, name)
    backfill = db.readings_of(hogar_id)
    db.events.clear()

    saved = recover(db, hogar_id)

    assert saved == HOURS_OFF * len(zones)
    assert db.events == [*RECOVERY_STATEMENTS, "commit"]
    assert set(db.sensors_of(hogar_id)) == set(zones)
    assert_contiguous(db, hogar_id, 720 + HOURS_OFF)
    stored = db.readings_of(hogar_id)
    assert {key: stored[key] for key in backfill} == backfill  # el backfill no se toca
    new_hours = {hour.astimezone(UTC) for hour in map(hour_from_index, range(END, END + 5))}
    assert {hour for _sensor, hour in set(stored) - set(backfill)} == new_hours
    assert {row["calidad"] for row in db.rows("lecturas")} == {"simulada"}
    assert stored == continuous(db, hogar_id, name, END + HOURS_OFF)

    db.events.clear()
    assert recover(db, hogar_id) == 0
    assert db.events == [*READ_STATEMENTS, "rollback"]  # sin INSERT; rollback suelta el candado
    assert db.readings_of(hogar_id) == stored


@each_personality
def test_b04_follows_the_assigned_profile_even_if_it_is_now_inactive(
    db: RecoveryStore, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Desactivar la personalidad después del onboarding no cambia la serie (RN-IV-04, DC-37)."""
    hogar_id = create_household(db, client_for(db), monkeypatch, name)
    db.deactivate_profile(name)

    assert recover(db, hogar_id) == HOURS_OFF * len(REFERENCE_HOUSEHOLDS[name][1])

    assert db.readings_of(hogar_id) == continuous(db, hogar_id, name, END + HOURS_OFF)


@each_personality
def test_b04_skips_inactive_sensors_and_zones(
    db: RecoveryStore, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """RN-IV-07: un sensor inactivo y una zona inactiva no reciben horas nuevas."""
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = create_household(db, client_for(db), monkeypatch, name)
    sensors = db.sensors_of(hogar_id)
    off_sensor_zone, off_zone = sorted(zones)[:2]
    db.set_state("sensores_zona", sensors[off_sensor_zone], "inactivo")
    (zone_id,) = [
        row["id"]
        for row in db.rows("zonas")
        if row["hogar_id"] == hogar_id and row["tipo"] == off_zone
    ]
    db.set_state("zonas", zone_id, "inactiva")
    before = db.by_zone(hogar_id)

    assert recover(db, hogar_id) == HOURS_OFF * (len(zones) - 2)

    added = {zone for zone, _hour in set(db.by_zone(hogar_id)) - set(before)}
    assert added == set(zones) - {off_sensor_zone, off_zone}


# --- 2. la tarea programada -----------------------------------------------------------------


@each_personality
def test_hourly_job_saves_one_hour_per_zone_of_every_household(
    db: RecoveryStore, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """`run_hourly_generation(T+1h)`: 1 × zonas por hogar, una sesión por hogar, todas cerradas."""
    client = client_for(db)
    households = {
        create_household(db, client, monkeypatch, personality): personality
        for personality in (name, other_personality(name))
    }
    first_session = len(db.sessions)
    db.events.clear()

    summary = run_hourly_generation(T + timedelta(hours=1), session_factory=db.open_session)

    zones = {h: len(REFERENCE_HOUSEHOLDS[p][1]) for h, p in households.items()}
    assert summary == GenerationSummary(len(households), sum(zones.values()), 0)
    per_household = [*RECOVERY_STATEMENTS, "commit"]
    assert db.events == [LIST_STATEMENT, *per_household * len(households)]
    opened = db.sessions[first_session:]
    assert len(opened) == 1 + len(households)  # la del listado y una por hogar
    assert all(session.closed for session in opened)
    for hogar_id, personality in households.items():
        assert_contiguous(db, hogar_id, 721)
        assert db.readings_of(hogar_id) == continuous(db, hogar_id, personality, END + 1)


@each_personality
def test_five_hourly_runs_equal_one_recovery_of_five_hours(
    new_store: Callable[[], RecoveryStore], monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Mismas filas corriendo la tarea hora a hora 5 veces que una sola vez en T+5 h."""
    personalities = (name, other_personality(name))
    hourly, once = new_store(), new_store()
    stores = {}
    for store in (hourly, once):
        client = client_for(store)
        stores[store] = [create_household(store, client, monkeypatch, p) for p in personalities]
    total_zones = sum(len(REFERENCE_HOUSEHOLDS[p][1]) for p in personalities)

    runs = [
        run_hourly_generation(T + timedelta(hours=hour), session_factory=hourly.open_session)
        for hour in range(1, HOURS_OFF + 1)
    ]
    single = run_hourly_generation(LATER, session_factory=once.open_session)

    assert runs == [GenerationSummary(2, total_zones, 0)] * HOURS_OFF
    assert single == GenerationSummary(2, HOURS_OFF * total_zones, 0)
    assert stores[hourly] == stores[once]
    for hogar_id in stores[hourly]:
        assert hourly.by_zone(hogar_id) == once.by_zone(hogar_id)
        assert_contiguous(hourly, hogar_id, 720 + HOURS_OFF)
    assert run_hourly_generation(LATER, session_factory=hourly.open_session).readings == 0


def test_the_job_without_households_saves_nothing(db: RecoveryStore) -> None:
    """Sin hogares: la corrida lista, no abre más sesiones y no guarda nada."""
    summary = scheduler_service.run_hourly_generation(LATER, session_factory=db.open_session)

    assert summary == GenerationSummary(0, 0, 0)
    assert db.events == [LIST_STATEMENT]
    assert [session.closed for session in db.sessions] == [True]


# --- 3. concurrencia ------------------------------------------------------------------------


@each_personality
def test_two_simultaneous_recoveries_save_the_hours_once(
    db: RecoveryStore, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Dos recuperaciones del mismo hogar a la vez se serializan con el candado del hogar.

    La que toma primero el candado espera, antes de leer, a que la otra quede bloqueada en él:
    así el resultado no depende del orden de los hilos. La primera guarda 5 × zonas y confirma;
    la segunda entra después, ve los huecos llenos, no envía INSERT y revierte con 0.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = create_household(db, client_for(db), monkeypatch, name)
    db.events.clear()
    db.after[LOCK_STATEMENT] = lambda: db.lock_waiting.wait(WAIT_SECONDS)

    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = sorted(pool.map(lambda _: recover(db, hogar_id), range(2)))

    assert db.lock_waiting.is_set()
    assert not db.waiting.is_set()  # nadie llegó a chocar en el índice único de lecturas
    assert saved == [0, HOURS_OFF * len(zones)]
    assert (
        db.events
        == [
            LOCK_STATEMENT,  # la primera toma el candado
            LOCK_STATEMENT,  # la segunda queda esperando
            *RECOVERY_STATEMENTS[1:],
            "commit",
            *READ_STATEMENTS[1:],
            "rollback",
        ]
    )
    assert db.events.count(READINGS_STATEMENT) == 1
    assert_contiguous(db, hogar_id, 720 + HOURS_OFF)
    assert db.readings_of(hogar_id) == continuous(db, hogar_id, name, END + HOURS_OFF)


# --- 4. aislamiento -------------------------------------------------------------------------


@each_personality
def test_recovering_one_household_does_not_touch_another(
    db: RecoveryStore, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """RN-IV-07, DC-38: solo los sensores del hogar recuperado reciben lecturas."""
    client = client_for(db)
    hogar_id = create_household(db, client, monkeypatch, name)
    neighbour = create_household(db, client, monkeypatch, other_personality(name))
    neighbour_before = db.readings_of(neighbour)

    saved = recover(db, hogar_id)

    assert saved == HOURS_OFF * len(REFERENCE_HOUSEHOLDS[name][1])
    assert db.readings_of(neighbour) == neighbour_before
    assert len(db.rows("lecturas")) == len(db.readings_of(hogar_id)) + len(neighbour_before)
    assert_contiguous(db, neighbour, 720)
    assert_contiguous(db, hogar_id, 720 + HOURS_OFF)
