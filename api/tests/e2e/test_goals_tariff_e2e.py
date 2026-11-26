"""Meta y tarifa de punta a punta (fase 10): `obtenerMeta`, `crearMeta`, `obtenerTarifa`, `crearTarifa`.

El hogar se crea con el onboarding REAL por la API (`POST /api/v1/onboarding`) del hogar de
referencia de cada personalidad, sobre el almacén en memoria de los e2e (`ConsumptionStore`, con
`GoalsTariffMixin` de `tests/e2e/goals_tariff_store.py`: las filas de `metas_consumo` y
`tarifas_hogar` con una meta activa por hogar, una tarifa abierta por hogar, vigencias
[desde, hasta) sin solapes, `fecha_fin > fecha_inicio` y `vigente_hasta > vigente_desde`).
Después todo pasa por HTTP con tokens de prueba: guardia → router → `services.goals_tariff` →
dominio → `app.data` → almacén. Para el costo se piden además `obtenerConsumoActual` y
`obtenerHistorial` (fases 6 y 7), que leen la tarifa guardada por `crearTarifa`.

Lo esperado se recalcula desde lo guardado en el almacén (promedio diario de 30 días: media de
los totales de los días completos anteriores a hoy en Bogotá, D6), no con el dominio.

Reloj: onboarding en T (sábado 21/11/2026 22:10, Bogotá). `datetime.now()` de
`services.goals_tariff` y de `services.consumption` sigue a `Clock.moment` (T y minutos o días
después). Al final de cada prueba: nada inesperado, A-01/A-02 y las restricciones de metas y
tarifas sobre lo confirmado (`assert_goal_tariff_invariants`).

El SQL no se ejecuta y `lock_household` no espera de verdad: que PostgreSQL haga lo mismo (I-02,
las carreras y R-01) queda pendiente.

Reglas: RN-V-01, RN-V-02, RN-V-03, RN-XVI-04, RN-XVI-05, RN-XVII-04, RN-XVII-05, RN-XI-08,
RN-XIII-05, RN-IV-05, RN-I-03. Decisiones: DC-39, DC-41 y D3, D4, D6, D7 de la fase 10; aviso del
coordinador (contrato 0.2.10): `crearTarifa` con un mes posterior al mes actual de Bogotá → 422
`VALIDACION`. Matriz: P-04, P-05, P-06.
"""

import statistics
from collections import defaultdict
from collections.abc import Iterator
from datetime import date, datetime, timedelta, tzinfo
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.domain.simulator import TIMEZONE
from app.main import API_PREFIX
from app.services import consumption as consumption_service
from app.services import goals_tariff as goals_tariff_service
from app.services import onboarding as onboarding_service
from tests.contract.test_c01_responses_match_schema import (
    OPERATIONS,
    assert_matches_contract,
    assert_matches_error_schema,
)
from tests.e2e.alerts_store import use_test_config
from tests.e2e.test_consumption_e2e import ConsumptionStore, every_cost
from tests.e2e.test_consumption_e2e import get as get_consumption
from tests.e2e.test_history_e2e import get_history
from tests.e2e.test_hour_recovery_e2e import OnboardingClock, T, client_for, create_household
from tests.helpers.auth import auth_header, install_test_jwks, make_token
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.simulator.support import stable_id

TAG = "e2e10m"
TODAY = date(2026, 11, 21)  # fecha de Bogotá de T
NOVEMBER_DAYS = 30
WINDOW_DAYS = 30  # umbrales-estado.v1.json: ventana_promedio_dias
MIN_DAYS = 7  # umbrales-estado.v1.json: minimo_dias_con_dato
NO_BODY = object()

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)


class Clock:
    moment = T


class ServiceClock(datetime):
    """`datetime.now()` de metas y tarifa y de consumo en `Clock.moment`."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return Clock.moment.astimezone(tz)


def at(*, minutes: int = 0, days: int = 0) -> datetime:
    Clock.moment = T + timedelta(days=days, minutes=minutes)
    return Clock.moment


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[ConsumptionStore]:
    store = ConsumptionStore()
    Clock.moment = T
    monkeypatch.setattr(onboarding_service, "datetime", OnboardingClock)
    monkeypatch.setattr(goals_tariff_service, "datetime", ServiceClock)
    monkeypatch.setattr(consumption_service, "datetime", ServiceClock)
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


def household(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> tuple[UUID, UUID, UUID]:
    """Onboarding real en T; (administrador, miembro sin `modificar_metas`, hogar)."""
    hogar_id = create_household(db, client, monkeypatch, name, TAG)
    member_id = stable_id("miembro", TAG, name)
    db.seed_member(hogar_id, member_id)
    return user_of(name), member_id, hogar_id


def call(
    client: TestClient, operation_id: str, user_id: UUID, hogar_id: UUID, body: Any = NO_BODY
) -> httpx.Response:
    """Llama la operación; un estado declarado se valida con su esquema, un 500 con `Error`."""
    method, path, op = OPERATIONS[operation_id]
    kwargs: dict[str, Any] = {"headers": auth_header(make_token(user_id))}
    if body is not NO_BODY:
        kwargs["json"] = body
    url = API_PREFIX + path.format(hogar_id=str(hogar_id))
    response = client.request(method.upper(), url, **kwargs)
    if str(response.status_code) in op["responses"]:
        assert_matches_contract(operation_id, response)
    elif response.status_code == 500:
        assert_matches_error_schema(response)
    else:
        pytest.fail(f"{operation_id} respondió {response.status_code}, que el contrato no declara")
    return response


def ok(response: httpx.Response, status: int = 200) -> dict[str, Any]:
    assert response.status_code == status, response.text
    return response.json()


def error(response: httpx.Response, status: int, codigo: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"codigo", "mensaje", "detalles"}
    assert body["codigo"] == codigo, body
    return body


def expected_daily_average(db: ConsumptionStore, hogar_id: UUID, today: date) -> float:
    """D6 desde lo guardado: media de los totales del hogar en los días completos (24 h de
    todas sus zonas, que cuentan todas) de los `WINDOW_DAYS` días anteriores a `today`."""
    zones = set(db.zone_ids(hogar_id))
    totals: dict[date, float] = defaultdict(float)
    hours: dict[date, set[tuple[str, datetime]]] = defaultdict(set)
    for (zone, hour), kwh in db.by_zone(hogar_id).items():
        day = hour.astimezone(TIMEZONE).date()
        if today - timedelta(days=WINDOW_DAYS) <= day < today:
            totals[day] += float(kwh)
            hours[day].add((zone, hour))
    complete = [day for day in totals if len(hours[day]) == 24 * len(zones)]
    assert len(complete) >= MIN_DAYS
    return statistics.fmean(totals[day] for day in complete)


def goal_rows(db: ConsumptionStore, hogar_id: UUID) -> list[tuple[Any, ...]]:
    return [
        (row["tipo"], float(row["valor_kwh_mensual"]), row["estado"], row["fecha_inicio"],
         row["fecha_fin"])
        for row in db.goals_of(hogar_id)
    ]


# --- 1. obtenerMeta: promedio de 30 días y orden de las personalidades -----------------------


def test_goal_view_without_goal_has_the_30_day_average_in_personality_order(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin meta: `meta` y `limite_diario_kwh` null; `promedio_diario_30d_kwh` con valor tras el
    onboarding (29 días completos de backfill, ≥ 7) y en el orden compacto < eficiente <
    intermedio < familiar < amplio (RN-XVI-04, D6). Igual a lo recalculado desde lo guardado."""
    averages = []
    for name in PERSONALITY_ORDER:
        admin, _member, hogar_id = household(db, client, monkeypatch, name)
        body = ok(call(client, "obtenerMeta", admin, hogar_id))
        assert (body["meta"], body["limite_diario_kwh"], body["puede_editar"]) == (None, None, True)
        expected = expected_daily_average(db, hogar_id, TODAY)
        assert body["promedio_diario_30d_kwh"] == pytest.approx(expected), name
        averages.append(body["promedio_diario_30d_kwh"])
        assert db.goals_of(hogar_id) == []  # consultar no escribe
    assert averages == sorted(averages)
    assert len(set(averages)) == len(PERSONALITY_ORDER)


# --- 2. crearMeta: permisos, D3 y puede_editar -----------------------------------------------


@each_personality
def test_goal_flow_permissions_and_replacement(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """crearMeta de punta a punta (RN-V-03, RN-XVI-04, RN-XVII-04, P-04, D3, D7).

    - Miembro sin `modificar_metas`: GET con `puede_editar` false; POST → 403
      `SIN_PERMISO_MODIFICAR_METAS` sin fila nueva (P-04).
    - Administrador POST → 201 'activa' desde hoy (Bogotá) y abierta; GET la muestra con
      `limite_diario_kwh` = meta ÷ 30 (noviembre).
    - El mismo día, el miembro CON el permiso POST → 201; la anterior queda 'inactiva' con
      `fecha_fin` null (D3: `metas_rango_valido` exige fin > inicio); GET del miembro con
      `puede_editar` true muestra la nueva.
    - Otro día, el administrador POST → la anterior 'inactiva' con `fecha_fin` = inicio nueva.
    - Siempre una sola activa; zonas, sensores y lecturas del backfill intactos.
    """
    admin, member, hogar_id = household(db, client, monkeypatch, name)
    backfill = db.readings_of(hogar_id)

    member_view = ok(call(client, "obtenerMeta", member, hogar_id))
    assert (member_view["meta"], member_view["puede_editar"]) == (None, False)
    before = db.snapshot()
    error(
        call(client, "crearMeta", member, hogar_id, {"tipo": "ahorro", "valor_kwh_mensual": 250}),
        403,
        "SIN_PERMISO_MODIFICAR_METAS",
    )
    assert db.snapshot() == before

    # Administrador: primera meta (hoy, Bogotá).
    first = ok(
        call(client, "crearMeta", admin, hogar_id, {"tipo": "ahorro", "valor_kwh_mensual": 300}),
        201,
    )
    assert {k: v for k, v in first.items() if k != "id"} == {
        "tipo": "ahorro",
        "valor_kwh_mensual": 300,
        "estado": "activa",
        "fecha_inicio": TODAY.isoformat(),
        "fecha_fin": None,
    }
    assert goal_rows(db, hogar_id) == [("ahorro", 300.0, "activa", TODAY, None)]
    view = ok(call(client, "obtenerMeta", admin, hogar_id))
    assert view["meta"] == first
    assert view["limite_diario_kwh"] == pytest.approx(300 / NOVEMBER_DAYS)
    assert view["promedio_diario_30d_kwh"] == pytest.approx(
        expected_daily_average(db, hogar_id, TODAY)
    )

    # Mismo día: el miembro con el permiso la reemplaza (D3: fecha_fin null).
    db.set_household_permission(hogar_id, "permiso_modificar_metas", True)
    at(minutes=5)
    second = ok(
        call(
            client, "crearMeta", member, hogar_id, {"tipo": "eficiencia", "valor_kwh_mensual": 250.5}
        ),
        201,
    )
    assert (second["estado"], second["fecha_inicio"], second["fecha_fin"]) == (
        "activa",
        TODAY.isoformat(),
        None,
    )
    assert goal_rows(db, hogar_id) == [
        ("ahorro", 300.0, "inactiva", TODAY, None),
        ("eficiencia", 250.5, "activa", TODAY, None),
    ]
    member_view = ok(call(client, "obtenerMeta", member, hogar_id))
    assert (member_view["meta"], member_view["puede_editar"]) == (second, True)
    assert member_view["limite_diario_kwh"] == pytest.approx(250.5 / NOVEMBER_DAYS)

    # Otro día: la anterior se cierra con la fecha de inicio de la nueva.
    next_day = at(days=1, minutes=-720)  # domingo 22/11 10:10
    tomorrow = next_day.astimezone(TIMEZONE).date()
    assert tomorrow == date(2026, 11, 22)
    third = ok(
        call(
            client, "crearMeta", admin, hogar_id, {"tipo": "presupuesto", "valor_kwh_mensual": 200}
        ),
        201,
    )
    assert third["fecha_inicio"] == tomorrow.isoformat()
    assert goal_rows(db, hogar_id) == [
        ("ahorro", 300.0, "inactiva", TODAY, None),
        ("eficiencia", 250.5, "inactiva", TODAY, tomorrow),
        ("presupuesto", 200.0, "activa", tomorrow, None),
    ]
    view = ok(call(client, "obtenerMeta", admin, hogar_id))  # recupera las horas de la noche
    assert view["meta"] == third
    assert view["limite_diario_kwh"] == pytest.approx(200 / NOVEMBER_DAYS)
    stored = db.readings_of(hogar_id)
    assert {key: stored[key] for key in backfill} == backfill


def test_goal_with_invalid_value_is_422_and_saves_nothing(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`valor_kwh_mensual` > 0 y `tipo` del catálogo (contrato `MetaCrear`) → 422 `VALIDACION`."""
    admin, _member, hogar_id = household(db, client, monkeypatch, PERSONALITY_ORDER[2])
    before = db.snapshot()
    for body in (
        {"tipo": "ahorro", "valor_kwh_mensual": 0},
        {"tipo": "otro", "valor_kwh_mensual": 100},
        {"tipo": "ahorro"},
    ):
        error(call(client, "crearMeta", admin, hogar_id, body), 422, "VALIDACION")
    assert db.snapshot() == before


def test_goal_of_another_household_is_404(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P-01, R-01: sin membresía en ese hogar → 404 en las 4 operaciones, sin escribir."""
    admin, _member, _own = household(db, client, monkeypatch, PERSONALITY_ORDER[0])
    _other_admin, _other_member, other = household(db, client, monkeypatch, PERSONALITY_ORDER[1])
    before = db.snapshot()
    for operation_id, body in (
        ("obtenerMeta", NO_BODY),
        ("crearMeta", {"tipo": "ahorro", "valor_kwh_mensual": 100}),
        ("obtenerTarifa", NO_BODY),
        ("crearTarifa", {"precio_kwh": 800, "vigente_desde": "2026-11"}),
    ):
        error(call(client, operation_id, admin, other, body), 404, "NO_ENCONTRADO")
    assert db.snapshot() == before


# --- 3. tarifa: permisos, cierre de la vigente y conexión con el costo -----------------------


@each_personality
def test_tariff_flow_closes_the_previous_and_the_cost_appears(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """crearTarifa de punta a punta (RN-V-01, RN-V-02, RN-XVI-05, DC-39, DC-41, P-05, D4, D7).

    - Sin tarifa: GET → `tarifa` null (`puede_editar` true para el administrador, false para el
      miembro); consumo actual e historial con todo `costo_cop` null (RN-XI-08, RN-XIII-05).
    - Mes futuro respecto a hoy (Bogotá) → 422 `VALIDACION` (contrato 0.2.10).
    - Miembro POST → 403 `NO_ES_ADMINISTRADOR` (P-05).
    - Administrador POST octubre (mes pasado) → 201 desde el día 1, abierta; POST noviembre (mes
      actual) → 201 y la de octubre queda cerrada con `vigente_hasta` = 2026-11-01 (fin
      excluido). GET → la de noviembre (la que aplica hoy).
    - Igual o anterior a la abierta → 422 `VIGENCIA_NO_POSTERIOR` con `detalles.vigente_desde` de
      la abierta; futuro → 422 `VALIDACION`. Nada cambia.
    - Con la tarifa, el costo del consumo actual y del historial del mes deja de ser null:
      kWh × precio de noviembre (sin cargo fijo en la hora; RN-V-02).
    """
    admin, member, hogar_id = household(db, client, monkeypatch, name)

    assert ok(call(client, "obtenerTarifa", admin, hogar_id)) == {
        "tarifa": None,
        "puede_editar": True,
    }
    assert ok(call(client, "obtenerTarifa", member, hogar_id)) == {
        "tarifa": None,
        "puede_editar": False,
    }
    actual = ok(get_consumption(client, "actual", admin, hogar_id))
    assert actual["tarifa_vigente"] is False and set(every_cost(actual)) == {None}
    month = ok(get_history(client, admin, hogar_id, "mes"))
    assert month["costo"]["costo_cop"] is None
    assert {point["costo_cop"] for point in month["serie"]} <= {None}

    before = db.snapshot()
    error(
        call(client, "crearTarifa", admin, hogar_id, {"precio_kwh": 800, "vigente_desde": "2026-12"}),
        422,
        "VALIDACION",
    )
    error(
        call(client, "crearTarifa", member, hogar_id, {"precio_kwh": 800, "vigente_desde": "2026-11"}),
        403,
        "NO_ES_ADMINISTRADOR",
    )
    assert db.snapshot() == before

    october = ok(
        call(
            client,
            "crearTarifa",
            admin,
            hogar_id,
            {
                "operador": "EPM",
                "precio_kwh": 700,
                "cargo_fijo_mensual": 15000,
                "vigente_desde": "2026-10",
            },
        ),
        201,
    )
    assert {k: v for k, v in october.items() if k != "id"} == {
        "operador": "EPM",
        "precio_kwh": 700,
        "cargo_fijo_mensual": 15000,
        "vigente_desde": "2026-10-01",
        "vigente_hasta": None,
    }
    at(minutes=3)
    november = ok(
        call(
            client, "crearTarifa", admin, hogar_id, {"precio_kwh": 812.5, "vigente_desde": "2026-11"}
        ),
        201,
    )
    assert {k: v for k, v in november.items() if k != "id"} == {
        "operador": None,
        "precio_kwh": 812.5,
        "cargo_fijo_mensual": None,
        "vigente_desde": "2026-11-01",
        "vigente_hasta": None,
    }
    rows = [
        (str(r["id"]), r["vigente_desde"], r["vigente_hasta"], float(r["precio_kwh"]))
        for r in db.tariffs_of(hogar_id)
    ]
    assert rows == [
        (october["id"], date(2026, 10, 1), date(2026, 11, 1), 700.0),
        (november["id"], date(2026, 11, 1), None, 812.5),
    ]
    assert ok(call(client, "obtenerTarifa", admin, hogar_id)) == {
        "tarifa": november,
        "puede_editar": True,
    }
    assert ok(call(client, "obtenerTarifa", member, hogar_id))["tarifa"] == november

    before = db.snapshot()
    for since in ("2026-11", "2026-09"):
        body = error(
            call(client, "crearTarifa", admin, hogar_id, {"precio_kwh": 900, "vigente_desde": since}),
            422,
            "VIGENCIA_NO_POSTERIOR",
        )
        assert body["detalles"] == {"vigente_desde": "2026-11-01"}
    error(
        call(client, "crearTarifa", admin, hogar_id, {"precio_kwh": 900, "vigente_desde": "2026-12"}),
        422,
        "VALIDACION",
    )
    assert db.snapshot() == before

    # Conexión con las fases 6 y 7: el costo ya no es null.
    price = 812.5
    actual = ok(get_consumption(client, "actual", admin, hogar_id))
    assert actual["tarifa_vigente"] is True
    assert actual["actual"]["costo_cop"] == pytest.approx(actual["actual"]["potencia_kw"] * price)
    today = actual["acumulado_hoy"]
    assert today["costo_cop"] == pytest.approx(today["energia_kwh"] * price)
    month = ok(get_history(client, admin, hogar_id, "mes"))
    assert month["costo"]["costo_cop"] == pytest.approx(month["total_kwh"] * price)
    assert month["costo"]["incluye_cargo_fijo"] is False  # la de noviembre no tiene cargo fijo
    assert None not in [point["costo_cop"] for point in month["serie"]]


def test_first_tariff_of_the_current_month_and_invalid_bodies(
    db: ConsumptionStore, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Primera tarifa del mes actual → 201 el día 1 (RN-XVI-05). Cuerpos fuera del contrato
    (`precio_kwh` < 0, mes 13, sin `vigente_desde`) → 422 `VALIDACION` sin escribir."""
    admin, _member, hogar_id = household(db, client, monkeypatch, PERSONALITY_ORDER[4])
    before = db.snapshot()
    for body in (
        {"precio_kwh": -1, "vigente_desde": "2026-11"},
        {"precio_kwh": 800, "vigente_desde": "2026-13"},
        {"precio_kwh": 800},
    ):
        error(call(client, "crearTarifa", admin, hogar_id, body), 422, "VALIDACION")
    assert db.snapshot() == before

    created = ok(
        call(client, "crearTarifa", admin, hogar_id, {"precio_kwh": 0, "vigente_desde": "2026-11"}),
        201,
    )
    assert (created["vigente_desde"], created["vigente_hasta"], created["precio_kwh"]) == (
        "2026-11-01",
        None,
        0,
    )
    (row,) = db.tariffs_of(hogar_id)
    assert row["precio_kwh"] == Decimal("0.00")
