"""Alertas y consejos de punta a punta (fase 8): las 5 operaciones por HTTP y la evaluación en vivo.

El hogar se crea con el onboarding REAL por la API (`POST /api/v1/onboarding`) sobre el almacén en
memoria de `test_consumption_e2e` (`ConsumptionStore` → `RecoveryStore` + `LiveAlertsMixin` de
`tests/e2e/alerts_store.py`), y después se llaman por HTTP `listarAlertas`,
`contarAlertasNoLeidas`, `marcarAlertasLeidas`, `listarConsejos` y `actualizarEstadoConsejo`.
Corren de verdad la guardia, el router, `services.alerts_tips`, la recuperación de horas
(`fill_missing_hours_or_continue`; decisión de Nicolás del 23/11/2026: si la recuperación falla,
la consulta responde con lo guardado, RN-IV-05, DC-34) con su evaluación en vivo
(`services.live_alerts.evaluate_live_hours`; DC-35: alertas solo sobre horas en vivo; se evalúan
en un SAVEPOINT para que un fallo no impida guardar las lecturas), el motor de estados,
`domain.alert_rules`, los textos de `textos-backend.es-CO.json` y las funciones de `app.data`;
solo se reemplaza lo más bajo.

Línea de tiempo (Bogotá; reloj fijo en el onboarding y en `alerts_tips`):

- T0 = lunes 30/11/2026 12:10 → onboarding; backfill del 31/10 12:00 al 30/11 11:00.
- T1 = 15:10 → la consulta recupera 12:00–14:00 (en vivo) con un pico crítico en la cocina a las
  13:00.
- T2 = 18:10 → recupera 15:00–17:00 con OTRO pico crítico en la cocina a las 16:00 (A-01).
- T3 = martes 01/12 00:10 → recupera 18:00–23:00 con un pico elevado en otra zona y cruza las
  23:00 del último día de noviembre: cierre de mes (A-04).

**Lo que la prueba fija a propósito** (entrada controlada, no esperados ajustados):

- Las horas en vivo de un «hogar habitual»: cada lectura generada por la recuperación se cambia por
  el promedio de su misma hora en los 30 días anteriores (estado normal, RN-XI-06) y en las horas
  del pico se pone `promedio + max(0,8 kWh; promedio)` (crítico: ≥ +100 % y exceso ≥ 0,05 kWh) o
  el punto medio de la banda elevada de `zona_estado` (desde `promedio + max(30 %; 0,05 kWh)`
  hasta antes de +60 %). Esa banda solo existe si el promedio pasa de 0,05 / 0,6 ≈ 0,083 kWh: en
  los hogares pequeños pocas horas lo cumplen, así que se elige la (zona, hora) de 18:00 a 22:00
  con la banda más ancha (puede ser la cocina: la regla elevada es otra clave). Se reemplaza
  `hour_recovery.generate_readings_for_gaps` envolviendo al simulador real; la continuidad del
  simulador ya la prueban `test_hour_recovery_e2e` y B-04. En la prueba del orden de
  personalidades las horas son las del simulador, sin tocar.
- Un segundo miembro y una meta se insertan directo en el almacén: invitaciones y metas (crear)
  son de la fase 9 y aún no hay operación que los cree. El consejo de otro hogar (para el 404)
  sí nace del flujo real: onboarding y recuperación en vivo con un pico crítico del vecino.

El SQL no se ejecuta: que PostgreSQL haga lo mismo queda pendiente (A-01…A-05 y R-01 sobre
Postgres real).

Reglas: RN-VI-02…05, RN-XIV-01…08, RN-XV-02…06, RN-XVII-03, RN-IV-05. Decisiones: DC-24, DC-25,
DC-32, DC-34, DC-35; decisión de Nicolás del 23/11/2026 (recuperación fallida → 200 con lo
guardado). created_at = momento del evento (fin de la hora; cierre: 00:00 del día 1).
"""

import json
import logging
import math
import re
import statistics
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.domain import alert_rules
from app.domain.formats import zone_name
from app.domain.simulator import TIMEZONE
from app.main import API_PREFIX
from app.services import alerts_tips, hour_recovery
from app.services import onboarding as onboarding_service
from tests.contract.test_c01_responses_match_schema import assert_matches_contract
from tests.e2e.alerts_store import (
    EVALUATION_ONLY,
    SAVEPOINT_RELEASED,
    SAVEPOINT_REVERTED,
    use_test_config,
)
from tests.e2e.test_consumption_e2e import MEMBERSHIP_STATEMENT, ConsumptionStore
from tests.e2e.test_hour_recovery_e2e import (
    LOCK_STATEMENT,
    READ_STATEMENTS,
    RECOVERY_STATEMENTS,
    client_for,
    create_household,
)
from tests.e2e.test_onboarding_e2e import INTERNAL_DETAIL, REFERENCE_HOUSEHOLDS
from tests.helpers.auth import auth_header, install_test_jwks, make_token
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.simulator.support import stable_id

TAG = "e2e8"
T0 = datetime(2026, 11, 30, 12, 10, tzinfo=TIMEZONE)
T1 = datetime(2026, 11, 30, 15, 10, tzinfo=TIMEZONE)
T2 = datetime(2026, 11, 30, 18, 10, tzinfo=TIMEZONE)
T3 = datetime(2026, 12, 1, 0, 10, tzinfo=TIMEZONE)
CRITICAL_ZONE = "cocina"  # zona básica: la tienen las 5 personalidades
CRITICAL_HOUR = datetime(2026, 11, 30, 13, tzinfo=TIMEZONE)
SECOND_CRITICAL_HOUR = datetime(2026, 11, 30, 16, tzinfo=TIMEZONE)
ELEVATED_HOURS = [datetime(2026, 11, 30, hour, tzinfo=TIMEZONE) for hour in range(18, 23)]
NOVEMBER = date(2026, 11, 1)
MONTH_END = datetime(2026, 12, 1, tzinfo=TIMEZONE)  # created_at del cierre: 00:00 del día 1
GOAL_KWH = Decimal("10.00")  # por debajo del mes de cualquier personalidad (≥ 34 kWh)
CRITICAL_EXTRA_KWH = 0.8  # el +0,8 kWh de U-01
ELEVATED_FROM, CRITICAL_FROM = 0.30, 0.60  # zona_estado: elevado desde +30 %, crítico +60 %
ZONE_MIN_EXCESS_KWH = 0.05  # zona_estado.exceso_minimo_kwh
WINDOW_DAYS = 30  # referencia.ventana_promedio_dias
ONE_HOUR = timedelta(hours=1)
USER_ALERTS = "USER_ALERTS_SQL"
FORBIDDEN_CODE = "SIN_PERMISO_RECIBIR_ALERTAS"
TEXTS_PATH = Path(__file__).resolve().parents[3] / "docs/textos/textos-backend.es-CO.json"
TEXTS: dict[str, Any] = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))
OPERATIONS = {
    "listarAlertas": ("GET", "/hogares/{hogar_id}/alertas"),
    "contarAlertasNoLeidas": ("GET", "/hogares/{hogar_id}/alertas/no-leidas"),
    "marcarAlertasLeidas": ("POST", "/hogares/{hogar_id}/alertas/marcar-leidas"),
    "listarConsejos": ("GET", "/hogares/{hogar_id}/consejos"),
    "actualizarEstadoConsejo": ("PUT", "/hogares/{hogar_id}/consejos/{consejo_id}/estado"),
}

# El generador real, tomado una vez: cada paso lo envuelve de nuevo sin encadenar envolturas.
REAL_GENERATE = hour_recovery.generate_readings_for_gaps

Spikes = dict[tuple[str, datetime], str]  # (zona, inicio de hora) → "critico" | "elevado"

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)


# --- reloj, almacén y fixtures --------------------------------------------------------------


class Clock:
    moment = T0


class AlertsClock(datetime):
    """`datetime.now()` del onboarding y de `alerts_tips` en `Clock.moment`."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return Clock.moment.astimezone(tz)


class AlertsStore(ConsumptionStore):
    """`ConsumptionStore` con lo que la prueba siembra directo (fase 9 aún sin operación)."""

    def seed_goal(self, hogar_id: UUID, kwh: Decimal = GOAL_KWH) -> None:
        """Meta activa desde el 1 de noviembre (la crea `crearMeta`, fase 9)."""
        meta_id = stable_id("meta", TAG, str(hogar_id))
        self.committed["metas_consumo"][meta_id] = {
            "id": meta_id,
            "hogar_id": hogar_id,
            "tipo": "ahorro",
            "valor_kwh_mensual": kwh,
            "estado": "activa",
            "fecha_inicio": NOVEMBER,
            "fecha_fin": None,
            "created_at": T0,
        }

    def seed_member_with_switches(
        self, hogar_id: UUID, usuario_id: UUID, notif_consumo: bool, notif_consejos: bool
    ) -> None:
        """Miembro activo (rol miembro) con sus interruptores (lo crea una invitación, fase 9)."""
        self.seed_member(hogar_id, usuario_id)
        prefs = self.committed["preferencias_usuario"]
        prefs[usuario_id] = {
            **prefs[usuario_id],
            "notif_consumo": notif_consumo,
            "notif_consejos": notif_consejos,
        }

    def seed_member_joined_at(self, hogar_id: UUID, usuario_id: UUID, joined_at: datetime) -> None:
        """Miembro activo con los interruptores encendidos que ingresó en `joined_at`."""
        self.seed_member_with_switches(hogar_id, usuario_id, True, True)
        members = self.committed["hogar_miembros"]
        (key,) = [
            key
            for key, row in members.items()
            if (row["hogar_id"], row["usuario_id"]) == (hogar_id, usuario_id)
        ]
        members[key] = {**members[key], "fecha_ingreso": joined_at.astimezone(UTC)}

    def household_alerts(self, hogar_id: UUID) -> list[dict[str, Any]]:
        return [row for row in self.rows("alertas") if row["hogar_id"] == hogar_id]

    def household_tips(self, hogar_id: UUID) -> list[dict[str, Any]]:
        return [row for row in self.rows("consejos") if row["hogar_id"] == hogar_id]


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[AlertsStore]:
    store = AlertsStore()
    Clock.moment = T0
    monkeypatch.setattr(onboarding_service, "datetime", AlertsClock)
    monkeypatch.setattr(alerts_tips, "datetime", AlertsClock)
    use_test_config(monkeypatch)
    install_test_jwks(monkeypatch)
    yield store
    # Los servicios capturan cualquier excepción: lo inesperado se comprueba aquí.
    assert store.unexpected == []
    store.assert_live_alert_rules()  # A-01 y A-02 sobre todo lo confirmado


@pytest.fixture
def client(db: AlertsStore) -> TestClient:
    return client_for(db)


# --- pasos ----------------------------------------------------------------------------------


def admin_of(name: str) -> UUID:
    return stable_id("usuario", TAG, name)


def member_of(name: str) -> UUID:
    return stable_id("miembro", TAG, name)


def call(
    client: TestClient,
    operation_id: str,
    user_id: UUID,
    hogar_id: UUID,
    *,
    params: Mapping[str, Any] | None = None,
    body: Any = None,
    consejo_id: UUID | None = None,
) -> httpx.Response:
    """Una de las 5 operaciones como `user_id`; 200/403/404 se validan contra el contrato."""
    method, path = OPERATIONS[operation_id]
    url = API_PREFIX + path.format(hogar_id=hogar_id, consejo_id=consejo_id)
    response = client.request(
        method,
        url,
        params=dict(params or {}),
        json=body,
        headers=auth_header(make_token(user_id)),
    )
    if response.status_code in (200, 403, 404):
        assert_matches_contract(operation_id, response)
    return response


def ok(response: httpx.Response) -> Any:
    assert response.status_code == 200, response.text
    return response.json()


def alerts_of(client: TestClient, user_id: UUID, hogar_id: UUID, **params: Any) -> list[dict]:
    return ok(call(client, "listarAlertas", user_id, hogar_id, params=params))["alertas"]


def unread_of(client: TestClient, user_id: UUID, hogar_id: UUID) -> int:
    return ok(call(client, "contarAlertasNoLeidas", user_id, hogar_id))["cantidad"]


def tips_of(client: TestClient, user_id: UUID, hogar_id: UUID) -> list[dict]:
    return ok(call(client, "listarConsejos", user_id, hogar_id))["consejos"]


def moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


def same_hour_average(db: AlertsStore, hogar_id: UUID, zone: str, hour: datetime) -> float:
    """Promedio de la zona a la misma hora en las 30 fechas anteriores con dato (DC-28)."""
    by_zone = db.by_zone(hogar_id)
    values = []
    for back in range(1, WINDOW_DAYS + 1):
        key = (zone, (hour - timedelta(days=back)).astimezone(UTC))
        if key in by_zone:
            values.append(float(by_zone[key]))
    assert len(values) >= 7, (zone, hour)  # hay referencia (minimo_dias_con_dato)
    return statistics.mean(values)


def elevated_band(average: float) -> tuple[float, float]:
    """[desde, hasta) del kWh que deja la zona en elevado: +30 % y exceso ≥ 0,05; antes de +60 %."""
    low = average + max(ELEVATED_FROM * average, ZONE_MIN_EXCESS_KWH)
    return low, average * (1 + CRITICAL_FROM)


def spike_value(average: float, kind: str) -> float:
    if kind == "critico":
        return average + max(CRITICAL_EXTRA_KWH, average)
    assert kind == "elevado"
    low, high = elevated_band(average)
    value = round((low + high) / 2, 4)
    assert low <= value < high, (average, low, high)  # la banda existe para este promedio
    return value


def control_live_hours(
    monkeypatch: pytest.MonkeyPatch, db: AlertsStore, hogar_id: UUID, spikes: Spikes
) -> dict[tuple[str, datetime], float]:
    """Horas en vivo de un hogar habitual con los picos pedidos (ver el módulo).

    Devuelve, al terminar la recuperación, el kWh guardado de cada pico.
    """
    zone_of = {sensor: zone for zone, sensor in db.sensors_of(hogar_id).items()}
    saved: dict[tuple[str, datetime], float] = {}

    def generate(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        rows = []
        for row in REAL_GENERATE(*args, **kwargs):
            zone = zone_of.get(row["sensor_id"])
            if zone is None:  # otro hogar
                rows.append(row)
                continue
            hour = row["fecha_hora"].astimezone(TIMEZONE)
            value = same_hour_average(db, hogar_id, zone, hour)
            if (zone, hour) in spikes:
                value = spike_value(value, spikes[zone, hour])
            kwh = Decimal(str(round(value, 4)))
            if (zone, hour) in spikes:
                saved[zone, hour] = float(kwh)
            rows.append({**row, "consumo_kwh": kwh})
        return rows

    monkeypatch.setattr(hour_recovery, "generate_readings_for_gaps", generate)
    return saved


def at(moment_: datetime) -> None:
    Clock.moment = moment_


def es_co(value: float, decimals: int) -> str:
    """Número es-CO: coma decimal y punto de miles (RN-XII-08, `_meta` de textos-backend)."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def hour_text(start: datetime) -> str:
    return start.astimezone(TIMEZONE).strftime("%H:00")


def render(template: str, **variables: str) -> str:
    return template.format(**variables)


def catalog_tip(regla: str, zona: str | None, variante: int) -> dict[str, Any]:
    (tip,) = [
        t
        for t in TEXTS["consejos"]
        if (t["regla_origen"], t["zona"], t["variante"]) == (regla, zona, variante)
    ]
    return tip


def november_total(db: AlertsStore, hogar_id: UUID, name: str) -> float:
    """Suma de noviembre (Bogotá) de las horas con TODAS las zonas, leída del almacén (DC-32)."""
    zones = set(REFERENCE_HOUSEHOLDS[name][1])
    per_hour: dict[datetime, dict[str, float]] = {}
    for (zone, hour), value in db.by_zone(hogar_id).items():
        local = hour.astimezone(TIMEZONE)
        if (local.year, local.month) == (2026, 11):
            per_hour.setdefault(hour, {})[zone] = float(value)
    return math.fsum(
        math.fsum(values.values()) for values in per_hour.values() if set(values) == zones
    )


def new_household(
    db: AlertsStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> UUID:
    """Onboarding real por la API del hogar de referencia de `name` (en `Clock.moment`)."""
    return create_household(db, client, monkeypatch, name, TAG)


@dataclass(frozen=True)
class Timeline:
    hogar_id: UUID
    admin: UUID
    member: UUID
    elevated_zone: str
    elevated_hour: datetime
    peaks: dict[tuple[str, datetime], float]


def run_timeline(
    db: AlertsStore,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    *,
    member_switches: tuple[bool, bool] = (False, True),
) -> Timeline:
    """Onboarding en T0, un miembro con `notif_consumo` apagado, meta y las 3 recuperaciones.

    Cada recuperación la dispara `GET /alertas` del administrador (RN-IV-05, DC-34: la
    consulta recupera primero). En T3 el pico elevado va en la (zona, hora) de 18:00 a 22:00
    con la banda elevada más ancha (ver el módulo).
    """
    at(T0)
    hogar_id = new_household(db, client, monkeypatch, name)
    admin, member = admin_of(name), member_of(name)
    db.seed_member_with_switches(hogar_id, member, *member_switches)
    db.seed_goal(hogar_id)
    peaks: dict[tuple[str, datetime], float] = {}

    at(T1)
    peaks |= control_live_hours(
        monkeypatch, db, hogar_id, {(CRITICAL_ZONE, CRITICAL_HOUR): "critico"}
    )
    alerts_of(client, admin, hogar_id)
    at(T2)
    peaks |= control_live_hours(
        monkeypatch, db, hogar_id, {(CRITICAL_ZONE, SECOND_CRITICAL_HOUR): "critico"}
    )
    alerts_of(client, admin, hogar_id)

    candidates = []
    for zone in REFERENCE_HOUSEHOLDS[name][1]:
        for hour in ELEVATED_HOURS:
            low, high = elevated_band(same_hour_average(db, hogar_id, zone, hour))
            candidates.append((high - low, zone, hour))
    width, zone, hour = max(candidates)
    assert width > 0.0002, (name, width)  # hay una banda elevada utilizable
    at(T3)
    saved = control_live_hours(monkeypatch, db, hogar_id, {(zone, hour): "elevado"})
    alerts_of(client, admin, hogar_id)
    return Timeline(hogar_id, admin, member, zone, hour, peaks | saved)


def assert_newest_first(alerts: list[dict[str, Any]]) -> None:
    """RN-XIV-04: created_at desc y, a igual momento, id desc."""
    keys = [(moment(a["creada_en"]), a["id"]) for a in alerts]
    assert keys == sorted(keys, reverse=True)


def by_rule(db: AlertsStore, hogar_id: UUID) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in db.household_alerts(hogar_id):
        result.setdefault(row["regla_origen"], []).append(row)
    return result


# --- 1. A-02 y A-01 paso a paso -------------------------------------------------------------


@each_personality
def test_backfill_creates_nothing_and_a_live_peak_creates_one_alert_per_day(
    db: AlertsStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """A-02: tras el onboarding no hay alertas ni consejos. Pico crítico en vivo: 1 alerta
    `consumo_critico`, su consejo de prioridad alta y el aviso «Nuevo consejo». A-01: otro pico
    crítico de la misma zona el mismo día no crea otra alerta ni otro consejo.

    Textos resueltos del archivo (RN-XII-08 y textos-backend `_meta`: formato de las variables),
    created_at = fin de la hora, variante 1 (DC-24: variante alterna; la anterior se reconoce por
    su título).
    """
    at(T0)
    hogar_id = new_household(db, client, monkeypatch, name)
    admin = admin_of(name)

    db.events.clear()
    assert alerts_of(client, admin, hogar_id) == []
    assert unread_of(client, admin, hogar_id) == 0
    assert tips_of(client, admin, hogar_id) == []
    assert db.household_alerts(hogar_id) == [] and db.household_tips(hogar_id) == []
    assert db.live_evaluations == []  # T0: la última hora completa ya es del backfill
    assert db.events[:5] == [MEMBERSHIP_STATEMENT, *READ_STATEMENTS, "rollback"]

    at(T1)
    peaks = control_live_hours(
        monkeypatch, db, hogar_id, {(CRITICAL_ZONE, CRITICAL_HOUR): "critico"}
    )
    db.events.clear()
    alerts = alerts_of(client, admin, hogar_id)

    assert db.events == [MEMBERSHIP_STATEMENT, *RECOVERY_STATEMENTS, "commit", USER_ALERTS]
    ((outcome, statements),) = db.live_evaluations
    assert outcome == SAVEPOINT_RELEASED
    assert {"INSERT_ALERT_SQL", "INSERT_TIP_SQL", "INSERT_TIP_ASSIGNMENTS_SQL"} <= set(statements)
    zona_id = db.zone_ids(hogar_id)[CRITICAL_ZONE]
    created = (CRITICAL_HOUR + ONE_HOUR).astimezone(UTC)
    kw = peaks[CRITICAL_ZONE, CRITICAL_HOUR]
    templates = TEXTS["alertas"]
    zone = zone_name(CRITICAL_ZONE)
    assert len(alerts) == 2
    assert_newest_first(alerts)
    assert {moment(a["creada_en"]) for a in alerts} == {created}  # created_at: fin de la hora
    without_ids = [
        {k: v for k, v in a.items() if k not in ("id", "creada_en")}
        for a in sorted(alerts, key=lambda a: a["categoria"])
    ]
    assert without_ids == [
        {  # aviso «Nuevo consejo» de la zona (categoría consejo)
            "categoria": "consejo",
            "severidad": "informativa",
            "titulo": templates["nuevo_consejo_zona"]["titulo"],
            "mensaje": render(templates["nuevo_consejo_zona"]["mensaje"], zona=zone),
            "zona_id": str(zona_id),
            "zona_nombre": zone,
            "leida_en": None,
        },
        {  # la alerta de consumo crítico, con el texto resuelto (RN-XII-08)
            "categoria": "consumo",
            "severidad": "critica",
            "titulo": render(templates["consumo_critico"]["titulo"], zona=zone),
            "mensaje": render(
                templates["consumo_critico"]["mensaje"],
                zona=zone,
                hora_ini=hour_text(CRITICAL_HOUR),
                hora_fin=hour_text(CRITICAL_HOUR + ONE_HOUR),
                kw=es_co(kw, 2),
            ),
            "zona_id": str(zona_id),
            "zona_nombre": zone,
            "leida_en": None,
        },
    ]
    rules = by_rule(db, hogar_id)
    (critical,) = rules["consumo_critico"]
    assert critical["clave_evento"] == f"consumo_critico:{zona_id}:2026-11-30"  # DC-25
    (notice,) = rules["nuevo_consejo_zona"]
    (tip,) = db.household_tips(hogar_id)
    assert notice["clave_evento"] == f"nuevo_consejo:{tip['id']}"  # DC-25, DC-35

    expected_tip = catalog_tip("zona_critica", CRITICAL_ZONE, 1)
    (listed,) = tips_of(client, admin, hogar_id)
    assert moment(listed.pop("creado_en")) == created
    assert listed == {
        "id": str(tip["id"]),
        "categoria": "zona",
        "prioridad": "alta",
        "titulo": expected_tip["titulo"],
        "descripcion": expected_tip["descripcion"],
        "zona_id": str(zona_id),
        "zona_nombre": zone,
        "estado": "pendiente",
        "completada_en": None,
    }
    assert unread_of(client, admin, hogar_id) == 2

    # A-01: otro pico crítico en la cocina, el mismo día.
    at(T2)
    control_live_hours(
        monkeypatch, db, hogar_id, {(CRITICAL_ZONE, SECOND_CRITICAL_HOUR): "critico"}
    )
    again = alerts_of(client, admin, hogar_id)

    assert again == alerts
    assert len(db.live_evaluations) == 2
    outcome, statements = db.live_evaluations[-1]
    assert outcome == SAVEPOINT_RELEASED
    assert "EXISTING_EVENT_KEYS_SQL" in statements  # la clave del día ya existía
    assert "INSERT_ALERT_SQL" not in statements and "INSERT_TIP_SQL" not in statements
    assert len(db.household_alerts(hogar_id)) == 2 and len(db.household_tips(hogar_id)) == 1
    stored = db.zone_kwh(hogar_id, SECOND_CRITICAL_HOUR)[CRITICAL_ZONE]
    average = same_hour_average(db, hogar_id, CRITICAL_ZONE, SECOND_CRITICAL_HOUR)
    assert stored >= average + CRITICAL_EXTRA_KWH - 1e-4  # el pico sí se guardó


def alerts_by(alerts: list[dict[str, Any]], categoria: str) -> dict[str, Any]:
    (alert,) = [a for a in alerts if a["categoria"] == categoria]
    return alert


# --- 2. listar, filtrar, limitar y marcar ---------------------------------------------------


@each_personality
def test_list_filter_limit_and_mark_read(
    db: AlertsStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """RN-XIV-04, RN-XIV-05, RN-VI-05: orden, filtro de categoría, límite y marcar leídas.

    Al terminar la línea de tiempo el administrador tiene 6 alertas: crítico de la cocina,
    elevado de otra zona, cierre de noviembre y los 3 avisos «Nuevo consejo». Marcar solo
    cambia las entregas propias y sin leer; `no-leidas` baja en consecuencia.
    """
    timeline = run_timeline(db, client, monkeypatch, name)
    hogar_id, admin, member = timeline.hogar_id, timeline.admin, timeline.member

    every = alerts_of(client, admin, hogar_id)
    assert len(every) == 6
    assert_newest_first(every)
    # El cierre y su aviso general nacen el 01/12 a las 00:00 (momento del evento); entre ellos
    # decide el id.
    assert {a["categoria"] for a in every[:2]} == {"informacion", "consejo"}
    assert {moment(a["creada_en"]) for a in every[:2]} == {MONTH_END}

    consumption = alerts_of(client, admin, hogar_id, categoria="consumo")
    assert [a["severidad"] for a in consumption] == ["advertencia", "critica"]
    assert [a["zona_nombre"] for a in consumption] == [
        zone_name(timeline.elevated_zone),
        zone_name(CRITICAL_ZONE),
    ]
    notices = alerts_of(client, admin, hogar_id, categoria="consejo")
    assert len(notices) == 3 and {a["titulo"] for a in notices} == {"Nuevo consejo disponible"}
    (closing,) = alerts_of(client, admin, hogar_id, categoria="informacion")
    assert closing["severidad"] == "advertencia"
    assert sorted(a["id"] for a in consumption + notices + [closing]) == sorted(
        a["id"] for a in every
    )
    assert alerts_of(client, admin, hogar_id, limite=2) == every[:2]
    assert alerts_of(client, admin, hogar_id, limite=1) == every[:1]
    response = call(client, "listarAlertas", admin, hogar_id, params={"limite": 0})
    assert response.status_code == 422 and response.json()["codigo"] == "VALIDACION"

    # El miembro marca una alerta suya y otra que no le llegó (el crítico): solo cuenta la suya.
    assert unread_of(client, member, hogar_id) == 3
    member_alerts = alerts_of(client, member, hogar_id)
    critical = consumption[1]
    body = {"alerta_ids": [critical["id"], member_alerts[0]["id"]]}
    marked = ok(call(client, "marcarAlertasLeidas", member, hogar_id, body=body))
    assert marked == {"marcadas": 1}
    assert unread_of(client, member, hogar_id) == 2
    assert unread_of(client, admin, hogar_id) == 6  # solo afecta a esa persona
    seen = alerts_of(client, member, hogar_id)
    assert moment(seen[0]["leida_en"]) == T3  # leída hace menos de 7 días: sigue visible
    assert [a["leida_en"] for a in seen[1:]] == [None, None]
    again = ok(call(client, "marcarAlertasLeidas", member, hogar_id, body=body))
    assert again == {"marcadas": 0}  # ya estaba leída

    every_id = {"alerta_ids": [a["id"] for a in every]}
    assert ok(call(client, "marcarAlertasLeidas", admin, hogar_id, body=every_id)) == {
        "marcadas": 6
    }
    assert unread_of(client, admin, hogar_id) == 0
    assert len(alerts_of(client, admin, hogar_id)) == 6


# --- 3. consejos: orden y estado ------------------------------------------------------------


@each_personality
def test_tips_order_and_status(
    db: AlertsStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """RN-XV-02, RN-XV-03: alta, media, baja; completada al final; solo para esa persona.

    `actualizarEstadoConsejo` registra `completada_en` = ahora y vuelve a pendiente con null.
    Un consejo de otro hogar responde 404 `NO_ENCONTRADO` (RN-XV-06, R-01).
    """
    timeline = run_timeline(db, client, monkeypatch, name)
    hogar_id, admin, member = timeline.hogar_id, timeline.admin, timeline.member

    tips = tips_of(client, admin, hogar_id)
    assert [t["prioridad"] for t in tips] == ["alta", "media", "baja"]
    assert [t["zona_nombre"] for t in tips] == [
        zone_name(CRITICAL_ZONE),
        zone_name(timeline.elevated_zone),
        None,
    ]
    elevated_tip = catalog_tip("zona_elevada", timeline.elevated_zone, 1)
    closing_tip = catalog_tip("cierre_mes_encima", None, 1)
    assert (tips[1]["titulo"], tips[1]["categoria"]) == (elevated_tip["titulo"], "zona")
    assert tips[2]["categoria"] == "general"
    assert tips[2]["titulo"] == closing_tip["titulo"]
    assert tips[2]["descripcion"] == render(closing_tip["descripcion"], mes="noviembre")
    assert moment(tips[2]["creado_en"]) == MONTH_END

    high = tips[0]["id"]
    done = ok(
        call(
            client,
            "actualizarEstadoConsejo",
            admin,
            hogar_id,
            body={"estado": "completada"},
            consejo_id=UUID(high),
        )
    )
    assert done == {**tips[0], "estado": "completada", "completada_en": done["completada_en"]}
    assert moment(done["completada_en"]) == T3
    after = tips_of(client, admin, hogar_id)
    assert [t["id"] for t in after] == [tips[1]["id"], tips[2]["id"], high]
    assert after[-1]["estado"] == "completada"
    assert tips_of(client, member, hogar_id)[0] == tips[0]  # el miembro no cambia

    back = ok(
        call(
            client,
            "actualizarEstadoConsejo",
            admin,
            hogar_id,
            body={"estado": "pendiente"},
            consejo_id=UUID(high),
        )
    )
    assert back == tips[0]
    assert tips_of(client, admin, hogar_id) == tips

    # Consejo de otro hogar (y uno inexistente): 404 con el cuerpo de siempre. El del vecino
    # nace de su propio onboarding y de un pico crítico en vivo.
    neighbour_name = PERSONALITY_ORDER[(PERSONALITY_ORDER.index(name) + 1) % 5]
    neighbour_admin = stable_id("usuario", TAG + "-vecino", neighbour_name)
    at(T0)
    neighbour = create_household(db, client, monkeypatch, neighbour_name, TAG + "-vecino")
    at(T1)
    control_live_hours(monkeypatch, db, neighbour, {(CRITICAL_ZONE, CRITICAL_HOUR): "critico"})
    (foreign_tip,) = tips_of(client, neighbour_admin, neighbour)
    foreign = UUID(foreign_tip["id"])
    at(T3)
    for consejo_id in (foreign, uuid4()):
        response = call(
            client,
            "actualizarEstadoConsejo",
            admin,
            hogar_id,
            body={"estado": "completada"},
            consejo_id=consejo_id,
        )
        assert response.status_code == 404, response.text
        assert response.json()["codigo"] == "NO_ENCONTRADO"
    assert tips_of(client, neighbour_admin, neighbour) == [foreign_tip]  # el vecino, intacto


# --- 4. A-03 y A-05: segundo miembro --------------------------------------------------------


@each_personality
def test_member_with_consumption_switch_off(
    db: AlertsStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """A-03: con `notif_consumo` apagado el miembro no recibe las alertas de consumo ni el cierre
    (categoría información); con `notif_consejos` encendido sí recibe los avisos «Nuevo consejo».
    A-05: tiene su fila `pendiente` de cada consejo (RN-VI-03, RN-XV-06), sin mirar interruptores.

    El miembro se inserta directo en el almacén: las invitaciones son de la fase 9.
    """
    timeline = run_timeline(db, client, monkeypatch, name)
    hogar_id, admin, member = timeline.hogar_id, timeline.admin, timeline.member

    member_alerts = alerts_of(client, member, hogar_id)
    assert {a["categoria"] for a in member_alerts} == {"consejo"}
    assert len(member_alerts) == 3
    assert alerts_of(client, member, hogar_id, categoria="consumo") == []
    assert alerts_of(client, member, hogar_id, categoria="informacion") == []
    admin_ids = {a["id"] for a in alerts_of(client, admin, hogar_id)}
    assert {a["id"] for a in member_alerts} < admin_ids

    tips = db.household_tips(hogar_id)
    assert len(tips) == 3
    for tip in tips:
        rows = {
            usuario: row
            for (consejo_id, usuario), row in db.committed["consejos_usuario"].items()
            if consejo_id == tip["id"]
        }
        assert set(rows) == {admin, member}
        assert {(r["estado"], r["completada_en"]) for r in rows.values()} == {("pendiente", None)}
    assert [t["id"] for t in tips_of(client, member, hogar_id)] == [
        t["id"] for t in tips_of(client, admin, hogar_id)
    ]


@each_personality
def test_without_receive_permission_the_member_gets_nothing_but_keeps_tips(
    db: AlertsStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """RN-VI-02, RN-XIV-06, RN-XVII-03: sin `permiso_recibir_alertas` el miembro no recibe ninguna
    entrega (ni avisos) aunque tenga los interruptores encendidos, y las 3 operaciones de alertas
    le responden 403 sin recuperar nada; los consejos sí (RN-VI-03): solo exigen membresía. El
    administrador pasa igual (P-06). Sin membresía: 404 en las 5 (P-01).
    """
    at(T0)
    hogar_id = new_household(db, client, monkeypatch, name)
    admin, member = admin_of(name), member_of(name)
    db.seed_member_with_switches(hogar_id, member, True, True)
    db.set_household_permission(hogar_id, "permiso_recibir_alertas", False)
    at(T1)
    control_live_hours(monkeypatch, db, hogar_id, {(CRITICAL_ZONE, CRITICAL_HOUR): "critico"})

    assert len(alerts_of(client, admin, hogar_id)) == 2  # P-06: el administrador recibe
    deliveries = {user for (_a, user) in db.committed["alertas_usuario"]}
    assert deliveries == {admin}
    for operation_id, body in (
        ("listarAlertas", None),
        ("contarAlertasNoLeidas", None),
        ("marcarAlertasLeidas", {"alerta_ids": [str(uuid4())]}),
    ):
        db.events.clear()
        response = call(client, operation_id, member, hogar_id, body=body)
        assert response.status_code == 403, response.text
        assert response.json()["codigo"] == FORBIDDEN_CODE
        assert db.events == [MEMBERSHIP_STATEMENT]  # ni candado ni lecturas
    (tip,) = tips_of(client, member, hogar_id)
    assert tip["prioridad"] == "alta"

    stranger = stable_id("usuario", TAG, "sin-hogar")
    db.seed_user(stranger)
    (consejo_id,) = [t["id"] for t in db.household_tips(hogar_id)]
    bodies = {
        "marcarAlertasLeidas": {"alerta_ids": [str(uuid4())]},
        "actualizarEstadoConsejo": {"estado": "completada"},
    }
    for operation_id in OPERATIONS:
        db.events.clear()
        response = call(
            client,
            operation_id,
            stranger,
            hogar_id,
            body=bodies.get(operation_id),
            consejo_id=consejo_id,
        )
        assert response.status_code == 404, (operation_id, response.text)
        assert response.json()["codigo"] == "NO_ENCONTRADO"
        assert db.events == [MEMBERSHIP_STATEMENT]


@each_personality
def test_member_who_joined_after_the_event_gets_neither_alert_nor_tip(
    db: AlertsStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """RN-VI-02 (sin efecto retroactivo) y RN-XV-06 (un miembro que ingresa después no recibe
    consejos anteriores): la recuperación de T1 genera el pico crítico de las 13:00, cuyo evento
    nace a las 14:00. Un miembro que ingresó a las 14:30 (después del evento y antes de la
    recuperación) no recibe la alerta, ni la fila del consejo, ni el aviso «Nuevo consejo»; el
    que ya estaba (y el que ingresó justo a las 14:00: `fecha_ingreso <= created_at`) sí.

    Los eventos posteriores a su ingreso sí le llegan: el cierre de noviembre (01/12 00:00),
    su consejo general y su aviso. Los miembros se insertan directo en el almacén: las
    invitaciones son de la fase 9.
    """
    event_at = CRITICAL_HOUR + ONE_HOUR  # created_at del pico crítico
    at(T0)
    hogar_id = new_household(db, client, monkeypatch, name)
    admin = admin_of(name)
    before = member_of(name)  # fecha_ingreso: 21/11 (antes del evento)
    on_time = stable_id("miembro-a-tiempo", TAG, name)
    late = stable_id("miembro-tarde", TAG, name)
    db.seed_member_with_switches(hogar_id, before, True, True)
    db.seed_member_joined_at(hogar_id, on_time, event_at)
    db.seed_member_joined_at(hogar_id, late, event_at + timedelta(minutes=30))
    db.seed_goal(hogar_id)
    assert event_at + timedelta(minutes=30) < T1  # ingresó antes de la recuperación

    at(T1)
    control_live_hours(monkeypatch, db, hogar_id, {(CRITICAL_ZONE, CRITICAL_HOUR): "critico"})
    admin_alerts = alerts_of(client, admin, hogar_id)
    assert len(admin_alerts) == 2  # el crítico y su aviso
    (tip,) = db.household_tips(hogar_id)
    for user in (before, on_time):
        assert alerts_of(client, user, hogar_id) == admin_alerts
        assert unread_of(client, user, hogar_id) == 2
        assert [t["id"] for t in tips_of(client, user, hogar_id)] == [str(tip["id"])]
    assert alerts_of(client, late, hogar_id) == []
    assert unread_of(client, late, hogar_id) == 0
    assert tips_of(client, late, hogar_id) == []
    alert_ids = {row["id"] for row in db.household_alerts(hogar_id)}
    deliveries = db.committed["alertas_usuario"]
    assert not any(user == late and alerta_id in alert_ids for alerta_id, user in deliveries)
    assert {user for _consejo_id, user in db.committed["consejos_usuario"]} == {
        admin,
        before,
        on_time,
    }

    # El cierre de noviembre nace después de su ingreso: ese sí le llega.
    at(T3)
    alerts_of(client, admin, hogar_id)
    late_alerts = alerts_of(client, late, hogar_id)
    assert {moment(a["creada_en"]) for a in late_alerts} == {MONTH_END}
    assert sorted(a["categoria"] for a in late_alerts) == ["consejo", "informacion"]
    (closing_tip,) = [
        t for t in db.household_tips(hogar_id) if t["regla_origen"] == "cierre_mes_encima"
    ]
    assert [t["id"] for t in tips_of(client, late, hogar_id)] == [str(closing_tip["id"])]


# --- 5. A-04: cierre de mes -----------------------------------------------------------------


@each_personality
def test_month_close_above_the_goal(
    db: AlertsStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """A-04, DC-32, RN-XIV-07: la recuperación que cruza las 23:00 del 30/11 cierra noviembre.

    Total de noviembre (horas con todas las zonas) por encima de la meta vigente el último día:
    `cierre_mes_encima` (información, advertencia) con «tu meta de 10,0 kWh», created_at =
    01/12 00:00, consejo general de prioridad baja con {mes} y su aviso general. Se entrega al
    administrador (y no al miembro con `notif_consumo` apagado). Repetir no crea otro cierre.
    """
    timeline = run_timeline(db, client, monkeypatch, name)
    hogar_id, admin = timeline.hogar_id, timeline.admin

    (closing,) = alerts_of(client, admin, hogar_id, categoria="informacion")
    templates = TEXTS["alertas"]["cierre_mes_encima"]
    assert closing["titulo"] == render(templates["titulo"], mes="noviembre")
    total = november_total(db, hogar_id, name)
    found = re.search(r"con ([0-9.]+,[0-9]) kWh", closing["mensaje"])
    assert found, closing["mensaje"]
    shown = float(found[1].replace(".", "").replace(",", "."))
    assert abs(shown - total) <= 0.05 + 1e-9, (shown, total)  # redondeo a 1 decimal (RN-XII-08)
    assert closing["mensaje"] == render(
        templates["mensaje"],
        mes="noviembre",
        kwh=found[1],
        referencia=f"tu meta de {es_co(float(GOAL_KWH), 1)} kWh",
    )
    assert total > float(GOAL_KWH)
    assert (closing["severidad"], closing["zona_id"], closing["zona_nombre"]) == (
        "advertencia",
        None,
        None,
    )
    assert moment(closing["creada_en"]) == MONTH_END
    rules = by_rule(db, hogar_id)
    (stored,) = rules["cierre_mes_encima"]
    assert stored["clave_evento"] == alert_rules.month_close_keys(hogar_id, NOVEMBER)[1]
    assert "cierre_mes_dentro" not in rules
    (general_notice,) = rules["nuevo_consejo_general"]
    assert general_notice["created_at"] == MONTH_END.astimezone(UTC)

    # Una consulta más tarde (sin horas nuevas que crucen otro fin de mes) no repite el cierre.
    at(T3 + timedelta(hours=2))
    alerts_of(client, admin, hogar_id)
    assert len(by_rule(db, hogar_id)["cierre_mes_encima"]) == 1


def test_month_close_total_follows_the_personality_order(
    db: AlertsStore, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """compacto < eficiente < intermedio < familiar < amplio en el kWh del cierre de noviembre.

    Horas en vivo del simulador real (sin controlar): el total que publica la alerta (por la API,
    `GET /alertas?categoria=informacion`) sigue el orden de las personalidades y coincide con lo
    guardado (±0,05 por el redondeo a 1 decimal).
    """
    at(T0)
    households = {name: new_household(db, client, monkeypatch, name) for name in PERSONALITY_ORDER}
    for hogar_id in households.values():
        db.seed_goal(hogar_id)
    at(T3)

    shown = {}
    for name, hogar_id in households.items():
        (closing,) = alerts_of(client, admin_of(name), hogar_id, categoria="informacion")
        found = re.search(r"con ([0-9.]+,[0-9]) kWh", closing["mensaje"])
        assert found, closing["mensaje"]
        shown[name] = float(found[1].replace(".", "").replace(",", "."))
        assert abs(shown[name] - november_total(db, hogar_id, name)) <= 0.05 + 1e-9

    values = [shown[name] for name in PERSONALITY_ORDER]
    assert values == sorted(values), shown
    assert len(set(values)) == len(values), shown


# --- 6. si la recuperación o la evaluación fallan, se responde con lo guardado --------------


@each_personality
def test_failed_recovery_answers_200_with_the_stored_alerts(
    db: AlertsStore,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    name: str,
) -> None:
    """Decisión de Nicolás del 23/11/2026 (RN-IV-05, DC-34): si la recuperación falla, las
    consultas de alertas y consejos responden 200 con lo guardado y queda un WARNING sin datos.

    DC-35: si falla una sentencia de la evaluación en vivo (alta de la alerta), se revierte solo el
    SAVEPOINT, queda un ERROR sin datos y las lecturas se guardan igual.
    """
    at(T0)
    hogar_id = new_household(db, client, monkeypatch, name)
    admin = admin_of(name)
    at(T1)
    control_live_hours(monkeypatch, db, hogar_id, {(CRITICAL_ZONE, CRITICAL_HOUR): "critico"})
    stored_alerts = alerts_of(client, admin, hogar_id)
    stored_tips = tips_of(client, admin, hogar_id)
    readings = db.readings_of(hogar_id)

    at(T2)
    caplog.set_level(logging.INFO)
    for operation_id in ("listarAlertas", "contarAlertasNoLeidas", "listarConsejos"):
        db.fail_once.add(LOCK_STATEMENT)
        db.events.clear()
        body = ok(call(client, operation_id, admin, hogar_id))
        assert LOCK_STATEMENT not in db.fail_once  # la falla sí ocurrió
        assert "rollback" in db.events and "commit" not in db.events
        assert body == {
            "listarAlertas": {"alertas": stored_alerts},
            "contarAlertasNoLeidas": {"cantidad": 2},
            "listarConsejos": {"consejos": stored_tips},
        }[operation_id]
    assert db.readings_of(hogar_id) == readings  # nada nuevo
    skipped = [
        r
        for r in caplog.records
        if r.name == hour_recovery.__name__
        and r.levelno == logging.WARNING
        and r.getMessage() == hour_recovery.RECOVERY_SKIPPED_MESSAGE
    ]
    assert len(skipped) == 3

    # Falla la evaluación: otro pico crítico (en otra zona) cuya alta falla.
    other_zone = next(z for z in REFERENCE_HOUSEHOLDS[name][1] if z != CRITICAL_ZONE)
    control_live_hours(monkeypatch, db, hogar_id, {(other_zone, SECOND_CRITICAL_HOUR): "critico"})
    db.fail_once.add("INSERT_ALERT_SQL")
    db.events.clear()
    assert alerts_of(client, admin, hogar_id) == stored_alerts
    assert db.fail_once == set()
    assert db.events == [
        MEMBERSHIP_STATEMENT,
        *READ_STATEMENTS,
        "INSERT_READINGS_BATCH_SQL",
        SAVEPOINT_REVERTED,
        "commit",
        USER_ALERTS,
    ]
    assert db.live_evaluations[-1][0] == SAVEPOINT_REVERTED
    assert not EVALUATION_ONLY & set(db.events)
    zones = REFERENCE_HOUSEHOLDS[name][1]
    assert len(db.readings_of(hogar_id)) == len(readings) + 3 * len(zones)  # 15:00–17:00
    assert len(db.household_alerts(hogar_id)) == 2
    assert "Evaluación de alertas fallida" in caplog.text
    for record in caplog.records:
        text = record.getMessage()
        assert str(hogar_id) not in text and INTERNAL_DETAIL not in text
        assert record.exc_info is None
