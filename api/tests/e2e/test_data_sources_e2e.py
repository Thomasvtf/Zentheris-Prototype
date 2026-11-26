"""Fuentes de datos de punta a punta (fase 10): `GET /api/v1/hogares/{hogar_id}/fuentes-datos`.

El hogar se crea con el onboarding REAL por la API (`POST /api/v1/onboarding`) del hogar de
referencia de cada personalidad, sobre el almacén en memoria de los e2e (`ConsumptionStore`, que
extiende el de la recuperación de horas y las alertas, con `GoalsTariffMixin` de
`tests/e2e/goals_tariff_store.py`: `MAIN_SOURCE_SQL` y `ZONE_SENSORS_SQL`). Después se pide
`obtenerFuentesDatos` por HTTP con tokens de prueba. Corren de verdad la guardia, el router,
`services.consumption.get_data_sources`, la recuperación de horas
(`fill_missing_hours_or_continue`), el simulador, `domain.data_sources` y las funciones de
`app.data`; solo se reemplaza lo más bajo.

Lo esperado se lee del almacén (lecturas guardadas de la última hora completa), no del dominio.

Reloj: onboarding en T (sábado 21/11/2026 22:10, Bogotá; la hora evaluada es la de las 21:00, ya
en el backfill) y consultas en T o en LATER (domingo 03:10, tras un apagado de 5 h: la hora
evaluada, las 02:00, la guarda la recuperación de la propia consulta). Al final de cada prueba:
nada inesperado, A-01/A-02 (`assert_live_alert_rules`) y las restricciones de metas y tarifas.

El SQL no se ejecuta: que PostgreSQL haga lo mismo queda pendiente (R-01 sobre Postgres real).

Reglas: RN-XVI-06, RN-III-03, RN-XVII-01, RN-XVII-05, RN-IV-05, RN-I-03. Decisiones: DC-34 y
D1, D5 de la fase 10; decisión de Nicolás (si la recuperación falla, 200 con lo guardado y aviso
en el log). Matriz: P-07 (también en `tests/permissions/test_p07_data_sources_hidden_values.py`).
"""

import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.domain.formats import zone_name
from app.main import API_PREFIX
from app.services import hour_recovery
from app.services import onboarding as onboarding_service
from tests.contract.test_c01_responses_match_schema import assert_matches_contract
from tests.e2e.alerts_store import HOURLY_STATEMENT, use_test_config
from tests.e2e.test_consumption_e2e import (
    FAILURES,
    HOUR_AT_LATER,
    HOUR_AT_T,
    MEMBERSHIP_STATEMENT,
    ConsumptionStore,
    alphabetical,
    query_at,
)
from tests.e2e.test_hour_recovery_e2e import (
    LATER,
    READ_STATEMENTS,
    RECOVERY_STATEMENTS,
    OnboardingClock,
    T,
    assert_contiguous,
    client_for,
    create_household,
    other_personality,
)
from tests.e2e.test_onboarding_e2e import HOUSEHOLD_NAME, INTERNAL_DETAIL, REFERENCE_HOUSEHOLDS
from tests.helpers.auth import auth_header, install_test_jwks, make_token
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.simulator.support import stable_id

TAG = "e2e10f"
OPERATION = "obtenerFuentesDatos"
SOURCES_READS = ["MAIN_SOURCE_SQL", "ZONE_SENSORS_SQL", HOURLY_STATEMENT]
SOURCE_NAME = f"Fuente principal {HOUSEHOLD_NAME}"  # la que guarda el onboarding

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[ConsumptionStore]:
    store = ConsumptionStore()
    monkeypatch.setattr(onboarding_service, "datetime", OnboardingClock)
    use_test_config(monkeypatch)  # umbrales y textos de make_test_settings(), caché propia
    install_test_jwks(monkeypatch)
    yield store
    assert store.unexpected == []
    store.assert_live_alert_rules()
    store.assert_goal_tariff_invariants()


@pytest.fixture
def client(db: ConsumptionStore) -> TestClient:
    return client_for(db)


def user_of(name: str) -> UUID:
    return stable_id("usuario", TAG, name)


def new_household(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> UUID:
    return create_household(db, client, monkeypatch, name, TAG)


def get_sources(client: TestClient, user_id: UUID, hogar_id: UUID) -> httpx.Response:
    """`obtenerFuentesDatos` como `user_id`; 200, 403 y 404 se validan contra el contrato."""
    response = client.get(
        f"{API_PREFIX}/hogares/{hogar_id}/fuentes-datos", headers=auth_header(make_token(user_id))
    )
    if response.status_code in (200, 403, 404):
        assert_matches_contract(OPERATION, response)
    return response


def ok(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    return response.json()


def hour_of(body: dict[str, Any]) -> tuple[datetime, datetime]:
    return datetime.fromisoformat(body["hora"]["inicio"]), datetime.fromisoformat(body["hora"]["fin"])


def expected_sensors(db: ConsumptionStore, hogar_id: UUID) -> list[dict[str, Any]]:
    """Un sensor por zona del hogar, en orden alfabético del nombre visible y luego id de zona."""
    zones = db.zone_ids(hogar_id)
    sensors = db.sensors_of(hogar_id)
    rows = [
        {
            "id": str(sensors[tipo]),
            "nombre": f"Sensor {zone_name(tipo)}",
            "zona_id": str(zones[tipo]),
            "zona_nombre": zone_name(tipo),
        }
        for tipo in zones
    ]
    names = alphabetical(sorted({row["zona_nombre"] for row in rows}))
    return sorted(rows, key=lambda row: (names.index(row["zona_nombre"]), row["zona_id"]))


def assert_sensor_list(body: dict[str, Any], db: ConsumptionStore, hogar_id: UUID) -> None:
    """Todos los sensores del hogar, con nombre, zona y orden de D5 (RN-XVI-06)."""
    keys = ("id", "nombre", "zona_id", "zona_nombre")
    assert [{k: s[k] for k in keys} for s in body["sensores"]] == expected_sensors(db, hogar_id)
    source = body["fuente_principal"]
    (stored,) = [r for r in db.rows("fuentes_principales") if r["hogar_id"] == hogar_id]
    assert (source["id"], source["nombre"], source["estado"]) == (
        str(stored["id"]),
        SOURCE_NAME,
        "activa",
    )


def kw_by_zone(body: dict[str, Any]) -> dict[str, float | None]:
    return {sensor["zona_id"]: sensor["potencia_kw"] for sensor in body["sensores"]}


# --- 1. administrador: kW de cada sensor y la fuente = su suma ------------------------------


@each_personality
def test_admin_sees_each_sensor_and_the_source_is_their_sum(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """200 válido; kW de cada sensor = kWh guardado a las 21:00; fuente = suma (RN-XVI-06, D5).

    En T la hora evaluada ya está en el backfill: la recuperación corre primero (tras la guardia)
    y no guarda nada; después fuente, sensores y lecturas de esa única hora.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    query_at(monkeypatch, T)
    stored = db.zone_kwh(hogar_id, HOUR_AT_T)
    assert set(stored) == set(zones)
    zone_ids = db.zone_ids(hogar_id)

    db.events.clear()
    body = ok(get_sources(client, user_of(name), hogar_id))

    assert db.events == [MEMBERSHIP_STATEMENT, *READ_STATEMENTS, "rollback", *SOURCES_READS]
    assert hour_of(body) == (HOUR_AT_T, HOUR_AT_T + timedelta(hours=1))
    assert body["hora"]["inicio"].endswith("-05:00")
    assert body["valores_ocultos"] is False
    assert_sensor_list(body, db, hogar_id)
    assert {s["estado"] for s in body["sensores"]} == {"activo"}
    expected_kw = {str(zone_ids[tipo]): kwh for tipo, kwh in stored.items()}
    assert kw_by_zone(body) == pytest.approx(expected_kw)
    total = body["fuente_principal"]["potencia_kw"]
    assert total == pytest.approx(sum(stored.values()))
    assert total == pytest.approx(sum(s["potencia_kw"] for s in body["sensores"]))


# --- 2. P-07: miembro sin ver_consumo_actual ------------------------------------------------


@each_personality
def test_p07_member_without_view_consumption_gets_hidden_values(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """P-07: 200, `valores_ocultos=true` y TODOS los kW null; estados y nombres se ven.

    RN-XVI-06, RN-XVII-01: no es un 403. Control: el mismo miembro con el permiso ve los kW; el
    administrador los ve aunque el permiso del hogar esté en false (P-06, RN-XVII-05).
    """
    hogar_id = new_household(db, client, monkeypatch, name)
    member_id = stable_id("miembro", TAG, name)
    db.seed_member(hogar_id, member_id)
    db.set_household_permission(hogar_id, "permiso_ver_consumo_actual", False)
    query_at(monkeypatch, T)
    stored = db.zone_kwh(hogar_id, HOUR_AT_T)

    hidden = ok(get_sources(client, member_id, hogar_id))
    assert hidden["valores_ocultos"] is True
    assert hidden["fuente_principal"]["potencia_kw"] is None
    assert {s["potencia_kw"] for s in hidden["sensores"]} == {None}
    assert {s["estado"] for s in hidden["sensores"]} == {"activo"}  # los estados no se ocultan
    assert_sensor_list(hidden, db, hogar_id)
    assert hour_of(hidden)[0] == HOUR_AT_T

    admin = ok(get_sources(client, user_of(name), hogar_id))
    assert admin["valores_ocultos"] is False
    assert admin["fuente_principal"]["potencia_kw"] == pytest.approx(sum(stored.values()))

    db.set_household_permission(hogar_id, "permiso_ver_consumo_actual", True)
    visible = ok(get_sources(client, member_id, hogar_id))
    assert visible["valores_ocultos"] is False
    assert visible == admin  # la misma vista que el administrador


# --- 3. sensor pausado ---------------------------------------------------------------------


@each_personality
def test_paused_sensor_shows_its_state_and_does_not_add_to_the_source(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Un sensor pausado sale «pausado» y no suma a la fuente (RN-III-03, RN-XVI-06, D5).

    En T su hora ya tiene lectura (del backfill): muestra sus kW pero la fuente suma solo los
    demás. En LATER la recuperación no genera horas para el pausado (solo sensores activos): sale
    «pausado» con kW null y la fuente sigue siendo la suma de los activos (no null).
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    paused_zone = min(zones)
    db.set_state("sensores_zona", db.sensors_of(hogar_id)[paused_zone], "pausado")
    zone_ids = {tipo: str(zona_id) for tipo, zona_id in db.zone_ids(hogar_id).items()}
    states = {zone_ids[t]: ("pausado" if t == paused_zone else "activo") for t in zones}

    query_at(monkeypatch, T)
    stored = db.zone_kwh(hogar_id, HOUR_AT_T)
    body = ok(get_sources(client, user_of(name), hogar_id))
    assert {s["zona_id"]: s["estado"] for s in body["sensores"]} == states
    assert kw_by_zone(body)[zone_ids[paused_zone]] == pytest.approx(stored[paused_zone])
    others = sum(kwh for tipo, kwh in stored.items() if tipo != paused_zone)
    assert body["fuente_principal"]["potencia_kw"] == pytest.approx(others)
    assert_sensor_list(body, db, hogar_id)

    query_at(monkeypatch, LATER)
    later = ok(get_sources(client, user_of(name), hogar_id))
    assert hour_of(later)[0] == HOUR_AT_LATER
    assert {s["zona_id"]: s["estado"] for s in later["sensores"]} == states
    recovered = db.zone_kwh(hogar_id, HOUR_AT_LATER)
    assert set(recovered) == set(zones) - {paused_zone}
    assert kw_by_zone(later)[zone_ids[paused_zone]] is None
    assert later["fuente_principal"]["potencia_kw"] == pytest.approx(sum(recovered.values()))


# --- 4. la recuperación falla: 200 con lo guardado y aviso en el log -------------------------


@pytest.mark.parametrize("failure", sorted(FAILURES))
@each_personality
def test_recovery_failure_answers_200_with_the_saved_data(
    db: ConsumptionStore,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    name: str,
    failure: str,
) -> None:
    """Decisión de Nicolás (D1, RN-IV-05, DC-34): recuperación fallida → 200, nunca 500.

    Apagado de 5 h y la recuperación falla (candado o inserción): no se guarda nada (rollback),
    la respuesta es el objeto completo con lo guardado: la hora evaluada (02:00) falta, así que
    todos los sensores salen `sin_datos` con kW null y la fuente null (nunca una suma parcial).
    El log lleva el WARNING de recuperación omitida, sin el id del hogar ni el detalle interno.
    """
    hogar_id = new_household(db, client, monkeypatch, name)
    backfill = db.readings_of(hogar_id)
    query_at(monkeypatch, LATER)
    caplog.set_level(logging.INFO)
    db.fail_once.add(FAILURES[failure])

    db.events.clear()
    body = ok(get_sources(client, user_of(name), hogar_id))

    assert FAILURES[failure] not in db.fail_once  # la falla sí ocurrió
    assert "rollback" in db.events and "commit" not in db.events
    assert db.events[-len(SOURCES_READS) :] == SOURCES_READS  # y luego leyó lo guardado
    assert db.readings_of(hogar_id) == backfill
    assert_contiguous(db, hogar_id, 720)
    assert hour_of(body)[0] == HOUR_AT_LATER
    assert body["valores_ocultos"] is False
    assert_sensor_list(body, db, hogar_id)
    assert {s["estado"] for s in body["sensores"]} == {"sin_datos"}
    assert {s["potencia_kw"] for s in body["sensores"]} == {None}
    assert body["fuente_principal"]["potencia_kw"] is None

    skipped = [
        record
        for record in caplog.records
        if record.name == hour_recovery.__name__
        and record.levelno == logging.WARNING
        and record.getMessage() == hour_recovery.RECOVERY_SKIPPED_MESSAGE
    ]
    assert len(skipped) == 1
    for record in caplog.records:
        text = record.getMessage()
        assert str(hogar_id) not in text and INTERNAL_DETAIL not in text
        assert record.exc_info is None


def test_recovery_then_live_hour_is_shown(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin fallo, la misma consulta en LATER recupera las 5 h antes de leer (RN-IV-05, DC-34)."""
    name = PERSONALITY_ORDER[2]
    hogar_id = new_household(db, client, monkeypatch, name)
    query_at(monkeypatch, LATER)

    db.events.clear()
    body = ok(get_sources(client, user_of(name), hogar_id))

    assert db.events == [MEMBERSHIP_STATEMENT, *RECOVERY_STATEMENTS, "commit", *SOURCES_READS]
    recovered = db.zone_kwh(hogar_id, HOUR_AT_LATER)
    assert {s["estado"] for s in body["sensores"]} == {"activo"}
    assert body["fuente_principal"]["potencia_kw"] == pytest.approx(sum(recovered.values()))


# --- 5. P-01: otro hogar --------------------------------------------------------------------


def test_another_household_gets_404_and_nothing_is_recovered(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P-01, R-01: sin membresía en el hogar → 404 `NO_ENCONTRADO`, sin recuperar ni leer."""
    name = PERSONALITY_ORDER[0]
    new_household(db, client, monkeypatch, name)
    neighbour = new_household(db, client, monkeypatch, other_personality(name))
    before = db.readings_of(neighbour)
    query_at(monkeypatch, LATER)

    db.events.clear()
    response = get_sources(client, user_of(name), neighbour)

    assert response.status_code == 404, response.text
    assert response.json()["codigo"] == "NO_ENCONTRADO"
    assert db.events == [MEMBERSHIP_STATEMENT]
    assert db.readings_of(neighbour) == before
