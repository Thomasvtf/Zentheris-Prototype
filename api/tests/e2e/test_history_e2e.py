"""Historial de punta a punta (fase 7): `GET /api/v1/hogares/{hogar_id}/historial`.

El hogar se crea con el onboarding REAL por la API (`POST /api/v1/onboarding`) sobre el almacén
en memoria de `test_consumption_e2e` (`ConsumptionStore`, que a su vez extiende el de la
recuperación de horas), y después se pide `obtenerHistorial` por HTTP con `periodo` = dia,
semana o mes, en General y con `zona_id`. Corren de verdad la guardia (`app.security`), el
router, `services.consumption.get_history`, la recuperación de horas
(`fill_missing_hours_or_continue`), el simulador, `domain.history` y las funciones de `app.data`;
solo se reemplaza lo más bajo. `HistoryStore` le enseña al almacén la sentencia nueva de la
fase 7, imitando su resultado (no las ramas del SQL):

- `TARIFFS_BETWEEN_SQL`: tarifas del hogar cuya vigencia [desde, hasta) toca alguna fecha de
  [start, end] (ambas inclusive), por `vigente_desde`. Las tarifas se siembran ya confirmadas:
  `crearTarifa` sigue en 501 (fase 9).

Lo esperado se recalcula aquí, desde las lecturas guardadas en el almacén y con las reglas
escritas (no con el dominio): serie, total, participación, pico (DC-31), tramo anterior
(DC-29) y costo por fecha (RN-XIII-05). Así la prueba no repite el código que vigila.

Reloj: el onboarding corre en T (sábado 21/11/2026 22:10, Bogotá; backfill del 22/10 22:00 al
21/11 21:00) y `datetime.now()` del servicio se fija por prueba (`query_at`). Umbrales de
`make_test_settings()` (no se lee `.env`). Las alertas y los consejos siguen vigilados (DC-35).

El SQL no se ejecuta: que PostgreSQL haga lo mismo queda pendiente (B-04 y R-01 sobre Postgres
real).

Reglas: RN-XIII-01…06, RN-XVII-02, RN-IV-05, RN-V-01, RN-V-02, RN-XII-03.
Decisiones: DC-29, DC-30, DC-31, DC-34, DC-35, DC-39; decisión de Nicolás del 23/11/2026 (si la
recuperación falla, la consulta responde con los datos guardados).
"""

import logging
import math
import statistics
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import cache
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.data import tariffs as tariffs_data
from app.domain.formats import zone_name
from app.domain.simulator import TIMEZONE
from app.main import API_PREFIX
from app.services import consumption as consumption_service
from app.services import hour_recovery
from app.services import onboarding as onboarding_service
from app.services import thresholds as thresholds_service
from tests.contract.test_c01_responses_match_schema import assert_matches_contract
from tests.data.fake_session import FakeResult
from tests.e2e.test_consumption_e2e import (
    FAILURES,
    HOURLY_STATEMENT,
    MEMBERSHIP_STATEMENT,
    ZONES_STATEMENT,
    ConsumptionStore,
    alphabetical,
    query_at,
)
from tests.e2e.test_hour_recovery_e2e import (
    HOURS_OFF,
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
from tests.e2e.test_onboarding_e2e import (
    INTERNAL_DETAIL,
    READINGS_STATEMENT,
    REFERENCE_HOUSEHOLDS,
    ROUNDING_KWH,
    Params,
    StoreSession,
    forbid_alerts_and_tips,
)
from tests.helpers.auth import auth_header, install_test_jwks, make_test_settings, make_token
from tests.helpers.personalities import PERSONALITY_ORDER, load_personalities
from tests.simulator.support import final_profiles, stable_id

TAG = "e2e7"
TARIFFS_STATEMENT = "TARIFFS_BETWEEN_SQL"
READS_GENERAL = [ZONES_STATEMENT, HOURLY_STATEMENT, TARIFFS_STATEMENT]
PERIODS = ("dia", "semana", "mes")
ONE_HOUR = timedelta(hours=1)
ONE_DAY = timedelta(days=1)
WINDOW_DAYS = 30  # ventana_promedio_dias de umbrales-estado.v1.json
MIN_DAYS = 7  # minimo_dias_con_dato
PEAK_MIN_PCT = 10  # pico.minimo_pct (DC-31)
COUNTED_STATES = {"normal", "elevado", "critico"}
FORBIDDEN_CODE = "SIN_PERMISO_VER_HISTORIAL"
OLD_PRICE, NEW_PRICE = Decimal("700.0000"), Decimal("812.5000")
FIXED_CHARGE = Decimal("15000.00")
# En T (sábado 21/11 22:10) el periodo termina en el inicio de la hora en curso.
END_AT_T = datetime(2026, 11, 21, 22, tzinfo=TIMEZONE)
STARTS_AT_T = {
    "dia": datetime(2026, 11, 21, tzinfo=TIMEZONE),
    "semana": datetime(2026, 11, 16, tzinfo=TIMEZONE),  # lunes
    "mes": datetime(2026, 11, 1, tzinfo=TIMEZONE),
}
# En LATER (domingo 22/11 03:10): hoy domingo, la semana sigue empezando el lunes 16.
END_AT_LATER = datetime(2026, 11, 22, 3, tzinfo=TIMEZONE)
STARTS_AT_LATER = {
    "dia": datetime(2026, 11, 22, tzinfo=TIMEZONE),
    "semana": datetime(2026, 11, 16, tzinfo=TIMEZONE),
    "mes": datetime(2026, 11, 1, tzinfo=TIMEZONE),
}

Stored = dict[str, dict[datetime, float]]  # tipo de zona → {inicio de hora (UTC): kWh}

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)
each_period = pytest.mark.parametrize("periodo", PERIODS)


# --- el almacén con la sentencia de la fase 7 -----------------------------------------------


class HistoryStore(ConsumptionStore):
    """`ConsumptionStore` más las tarifas por rango de fechas del historial."""

    def __init__(self) -> None:
        super().__init__()
        self.handlers[id(tariffs_data.TARIFFS_BETWEEN_SQL)] = (
            TARIFFS_STATEMENT,
            self._tariffs_between,
        )

    def _tariffs_between(self, _session: StoreSession, params: Params) -> FakeResult:
        """tarifas_hogar del hogar con vigencia [desde, hasta) que toca [start, end]."""
        rows = [
            row
            for row in self.tariffs.get(params["hogar_id"], [])
            if row["vigente_desde"] <= params["end"]
            and (row["vigente_hasta"] is None or row["vigente_hasta"] > params["start"])
        ]
        return FakeResult(sorted(rows, key=lambda row: row["vigente_desde"]))

    def seed_tariff(
        self,
        hogar_id: UUID,
        price: Decimal,
        since: date,
        until: date | None = None,
        fixed: Decimal | None = None,
    ) -> None:
        self.tariffs.setdefault(hogar_id, []).append(
            {
                "id": stable_id("tarifa", TAG, str(hogar_id), since.isoformat()),
                "precio_kwh": price,
                "cargo_fijo_mensual": fixed,
                "vigente_desde": since,
                "vigente_hasta": until,
            }
        )

    def stored(self, hogar_id: UUID) -> Stored:
        """Lecturas guardadas del hogar por zona, como float."""
        result: Stored = {}
        for (zone, hour), value in self.by_zone(hogar_id).items():
            result.setdefault(zone, {})[hour.astimezone(UTC)] = float(value)
        return result


# --- fixtures y pasos -----------------------------------------------------------------------


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[HistoryStore]:
    store = HistoryStore()
    guarded = forbid_alerts_and_tips(monkeypatch, store)  # DC-35: nadie llama alertas/consejos
    assert {"evaluate_alert_rules", "build_tips"} <= set(guarded)
    monkeypatch.setattr(onboarding_service, "datetime", OnboardingClock)
    monkeypatch.setattr(thresholds_service, "get_settings", make_test_settings)
    fresh = cache(thresholds_service.get_thresholds.__wrapped__)
    monkeypatch.setattr(thresholds_service, "get_thresholds", fresh)
    monkeypatch.setattr(consumption_service, "get_thresholds", fresh)
    install_test_jwks(monkeypatch)
    yield store
    assert store.unexpected == []


@pytest.fixture
def client(db: HistoryStore) -> TestClient:
    return client_for(db)


def user_of(name: str) -> UUID:
    return stable_id("usuario", TAG, name)


def new_household(
    db: HistoryStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> UUID:
    return create_household(db, client, monkeypatch, name, TAG)


def get_history(
    client: TestClient,
    user_id: UUID,
    hogar_id: UUID,
    periodo: str,
    zona_id: UUID | None = None,
) -> httpx.Response:
    """GET del historial como `user_id`; un 200/403/404 se valida contra el contrato."""
    params = {"periodo": periodo}
    if zona_id is not None:
        params["zona_id"] = str(zona_id)
    response = client.get(
        f"{API_PREFIX}/hogares/{hogar_id}/historial",
        params=params,
        headers=auth_header(make_token(user_id)),
    )
    if response.status_code in (200, 403, 404):
        assert_matches_contract("obtenerHistorial", response)
    return response


def ok(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    return response.json()


def moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


# --- lo esperado, recalculado desde lo guardado ---------------------------------------------


def hours_of(start: datetime, end: datetime) -> list[datetime]:
    """Inicios de hora (UTC) de [start, end)."""
    result, current = [], start.astimezone(UTC)
    while current < end:
        result.append(current)
        current += ONE_HOUR
    return result


def zone_sum(series: dict[datetime, float], start: datetime, end: datetime) -> float | None:
    """Suma de la zona en [start, end) si tiene TODAS esas horas; si no, None (nunca parcial)."""
    hours = hours_of(start, end)
    if not hours or any(hour not in series for hour in hours):
        return None
    return math.fsum(series[hour] for hour in hours)


def household_totals(stored: Stored) -> dict[datetime, float]:
    """Total por hora, solo en las horas en que TODAS las zonas tienen lectura (nunca una suma parcial)."""
    common = set.intersection(*(set(series) for series in stored.values()))
    return {hour: math.fsum(series[hour] for series in stored.values()) for hour in common}


def range_total(totals: dict[datetime, float], start: datetime, end: datetime) -> float:
    return math.fsum(totals[hour] for hour in hours_of(start, end) if hour in totals)


def complete_total(totals: dict[datetime, float], start: datetime, end: datetime) -> float | None:
    hours = hours_of(start, end)
    if not hours or any(hour not in totals for hour in hours):
        return None
    return math.fsum(totals[hour] for hour in hours)


def expected_points(periodo: str, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """dia: una hora por punto; semana y mes: un día por punto, el de hoy termina en `end`."""
    step = ONE_HOUR if periodo == "dia" else ONE_DAY
    points, current = [], start
    while current < end:
        following = min(current + step, end)
        points.append((current, following))
        current = following
    return points


def previous_range(periodo: str, start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Mismo tramo del periodo anterior (DC-29). En mes vale para días que existen en octubre."""
    if periodo == "dia":
        return start - ONE_DAY, end - ONE_DAY
    if periodo == "semana":
        return start - 7 * ONE_DAY, end - 7 * ONE_DAY
    month = start.month - 1 or 12
    year = start.year - (start.month == 1)
    return start.replace(year=year, month=month), end.replace(year=year, month=month)


def point_reference(
    totals: dict[datetime, float], periodo: str, start: datetime, end: datetime
) -> float | None:
    """Promedio histórico del punto (RN-XIII-03, DC-31), con ≥ 7 días y > 0.

    dia: la misma hora en los 30 días anteriores. semana/mes: lo acumulado de 00:00 a la última
    hora del punto en los 30 días anteriores a su fecha, solo días con todas esas horas.
    """
    values = []
    for days_back in range(1, WINDOW_DAYS + 1):
        shift = days_back * ONE_DAY
        if periodo == "dia":
            hour = (start - shift).astimezone(UTC)
            if hour in totals:
                values.append(totals[hour])
        else:
            value = complete_total(totals, start - shift, end - shift)
            if value is not None:
                values.append(value)
    if len(values) < MIN_DAYS:
        return None
    average = statistics.mean(values)
    return average if average > 0 else None


def expected_peaks(
    totals: dict[datetime, float],
    periodo: str,
    points: list[tuple[datetime, datetime]],
    energies: list[float | None],
) -> list[tuple[int, float, float]]:
    """(posición, energía, promedio) de cada pico: supera su promedio en ≥ 10 % (DC-31)."""
    found = []
    for position, ((start, end), energy) in enumerate(zip(points, energies, strict=True)):
        if energy is None:
            continue
        reference = point_reference(totals, periodo, start, end)
        if reference is not None and (energy - reference) / reference * 100 >= PEAK_MIN_PCT:
            found.append((position, energy, reference))
    return found


def comparison_variant(current: float, previous: float | None) -> str:
    """Variante del mensaje del contrato: menor < −5 % <= similar < +10 % <= mayor < +25 %."""
    if previous is None:
        return "sin_anterior"
    if previous <= 0:
        return "sin_referencia"
    pct = (current - previous) / previous * 100
    if pct < -5:
        return "menor"
    if pct < 10:
        return "similar"
    if pct < 25:
        return "mayor"
    return "muy_mayor"


# --- comprobaciones comunes -----------------------------------------------------------------


def assert_history_matches_store(
    body: dict[str, Any],
    stored: Stored,
    zone_ids: dict[str, UUID],
    periodo: str,
    start: datetime,
    end: datetime,
    zone: str | None = None,
) -> None:
    """La respuesta coincide con lo recalculado desde lo guardado (General o una zona).

    RN-XIII-01 (periodo y tramo anterior), RN-XIII-02 (serie, null nunca cero ni suma parcial),
    RN-XIII-03 (pico ≥ 10 %, a lo sumo un `es_pico_maximo`), RN-XIII-04 (participación).
    """
    general = zone is None
    used = stored if general else {zone: stored[zone]}
    totals = household_totals(used)
    assert body["periodo"] == periodo
    assert body["granularidad"] == ("hora" if periodo == "dia" else "dia")
    assert body["zona_id"] == (None if general else str(zone_ids[zone]))
    assert (moment(body["inicio"]), moment(body["fin"])) == (start, end)
    assert body["inicio"].endswith("-05:00") and body["fin"].endswith("-05:00")

    # Serie: un punto por hora (dia) o por día (semana/mes), contiguos, de inicio a fin.
    points = expected_points(periodo, start, end)
    serie = body["serie"]
    assert [(moment(p["inicio"]), moment(p["fin"])) for p in serie] == points
    order = alphabetical([zone_name(tipo) for tipo in used])
    ordered_ids = [
        str(zone_ids[tipo]) for tipo in sorted(used, key=lambda tipo: order.index(zone_name(tipo)))
    ]
    energies: list[float | None] = []
    for point, (point_start, point_end) in zip(serie, points, strict=True):
        by_zone = {tipo: zone_sum(used[tipo], point_start, point_end) for tipo in used}
        expected = (
            None
            if any(value is None for value in by_zone.values())
            else math.fsum(by_zone.values())
        )
        energies.append(expected)
        if expected is None:
            assert point["energia_kwh"] is None, point  # nunca suma parcial ni cero
        else:
            assert point["energia_kwh"] == pytest.approx(expected)
        if not general:
            assert point["zonas"] is None
            continue
        # Mismos zona_id y mismo orden que participacion_zonas; energía = suma de zonas o null.
        assert [item["zona_id"] for item in point["zonas"]] == ordered_ids
        tipo_of = {str(zone_ids[tipo]): tipo for tipo in used}
        for item in point["zonas"]:
            value = by_zone[tipo_of[item["zona_id"]]]
            if value is None:
                assert item["energia_kwh"] is None
            else:
                assert item["energia_kwh"] == pytest.approx(value)
        zone_values = [item["energia_kwh"] for item in point["zonas"]]
        if None in zone_values:
            assert point["energia_kwh"] is None
        else:
            assert point["energia_kwh"] == pytest.approx(math.fsum(zone_values))

    # Total: suma de las horas con total en [inicio, fin).
    total = range_total(totals, start, end)
    assert body["total_kwh"] == pytest.approx(total)

    # Participación (solo General): por zona, en orden alfabético, suma 100 y Σ = total.
    shares = body["participacion_zonas"]
    if general:
        assert [item["zona_id"] for item in shares] == ordered_ids
        assert [item["nombre"] for item in shares] == order
        hours_with_total = [hour for hour in hours_of(start, end) if hour in totals]
        for item in shares:
            tipo = next(t for t in used if str(zone_ids[t]) == item["zona_id"])
            energy = math.fsum(used[tipo][hour] for hour in hours_with_total)
            assert item["energia_kwh"] == pytest.approx(energy)
            assert item["nombre"] == zone_name(tipo)  # RN-XII-03
        assert math.fsum(item["energia_kwh"] for item in shares) == pytest.approx(total)
        pct = math.fsum(item["participacion_pct"] for item in shares)
        assert pct == pytest.approx(100 if total > 0 else 0)
    else:
        assert shares is None

    # Pico: el más reciente en ultimo_pico; es_pico_maximo en el de mayor energía (empate → el
    # más reciente); a lo sumo uno.
    peaks = expected_peaks(totals, periodo, points, energies)
    flags = [point["es_pico_maximo"] for point in serie]
    assert sum(flags) <= 1
    last = body["ultimo_pico"]
    if not peaks:
        assert last is None and not any(flags)
    else:
        best = max(peaks, key=lambda peak: (peak[1], peak[0]))
        assert flags.index(True) == best[0]
        position, energy, reference = peaks[-1]
        assert (moment(last["inicio"]), moment(last["fin"])) == points[position]
        assert last["energia_kwh"] == pytest.approx(energy)
        assert last["promedio_historico_kwh"] == pytest.approx(reference)
        assert last["exceso_pct"] == pytest.approx((energy - reference) / reference * 100)
        assert last["exceso_pct"] >= PEAK_MIN_PCT - 1e-6
        assert last["estado"] in COUNTED_STATES
        assert serie[best[0]]["energia_kwh"] >= last["energia_kwh"] - 1e-9

    # Comparación con el mismo tramo del periodo anterior (DC-29).
    comparison = body["comparacion"]
    previous_start, previous_end = previous_range(periodo, start, end)
    previous = complete_total(totals, previous_start, previous_end)
    if previous is None:
        assert comparison["anterior_kwh"] is None
    else:
        assert comparison["anterior_kwh"] == pytest.approx(previous)
    assert comparison["actual_kwh"] == pytest.approx(total)
    complete = complete_total(totals, start, end) is not None
    if not complete:
        assert (comparison["estado"], comparison["mensaje_codigo"]) == ("sin_datos", None)
        assert comparison["variacion_pct"] is None
    else:
        variant = comparison_variant(total, previous)
        thresholds = consumption_service.get_thresholds()
        expected_state = (
            "sin_referencia"
            if variant in ("sin_anterior", "sin_referencia")
            else thresholds.period_comparison.states[variant]
        )
        assert comparison["mensaje_codigo"] == f"historial_comparacion.{variant}"
        assert comparison["estado"] == expected_state
        if previous is None or previous <= 0:
            assert comparison["variacion_pct"] is None
        else:
            assert comparison["variacion_pct"] == pytest.approx(
                (total - previous) / previous * 100, abs=1e-5
            )
    # El estado del costo sigue a la comparación (contrato, opción A).
    assert body["costo"]["estado"] == comparison["estado"]
    assert body["costo"]["mensaje_codigo"] == comparison["mensaje_codigo"]


def assert_without_tariff(body: dict[str, Any]) -> None:
    """Sin tarifa: tarifa_vigente false y todo costo null (RN-XIII-05)."""
    assert body["tarifa_vigente"] is False
    assert {point["costo_cop"] for point in body["serie"]} <= {None}
    assert body["costo"]["costo_cop"] is None
    assert body["costo"]["proyeccion_cierre_cop"] is None
    assert body["costo"]["incluye_cargo_fijo"] is False


# --- 1. los 3 periodos, General y por zona, para las 5 personalidades ------------------------


@each_period
@each_personality
def test_history_general_and_by_zone_matches_the_stored_readings(
    db: HistoryStore,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    periodo: str,
) -> None:
    """200 válido contra el contrato; todo coincide con lo recalculado desde lo guardado.

    Onboarding real en T: el periodo termina a las 22:00 del sábado y todas sus horas están en
    el backfill, así que la recuperación corre (después de la guardia) y no guarda nada.
    General: serie con zonas en el orden de `participacion_zonas`, energía = suma de zonas,
    participación que suma 100. Con `zona_id`: `zonas` y `participacion_zonas` null y
    `total_kwh` = la energía de esa zona en General. Sin tarifa: costos null.
    RN-XIII-01…05, RN-XII-03, DC-29, DC-31.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    zone_ids = db.zone_ids(hogar_id)
    stored = db.stored(hogar_id)
    assert set(stored) == set(zones)
    start = STARTS_AT_T[periodo]
    query_at(monkeypatch, T)
    before = db.readings_of(hogar_id)

    db.events.clear()
    general = ok(get_history(client, user_id, hogar_id, periodo))
    assert db.events == [MEMBERSHIP_STATEMENT, *READ_STATEMENTS, "rollback", *READS_GENERAL]
    assert_history_matches_store(general, stored, zone_ids, periodo, start, END_AT_T)
    assert_without_tariff(general)
    # En T todo el periodo está guardado: ningún punto sin dato.
    assert None not in [point["energia_kwh"] for point in general["serie"]]
    shares = {item["zona_id"]: item["energia_kwh"] for item in general["participacion_zonas"]}

    for zone in zones:
        db.events.clear()
        filtered = ok(get_history(client, user_id, hogar_id, periodo, zone_ids[zone]))
        assert db.events == [MEMBERSHIP_STATEMENT, *READ_STATEMENTS, "rollback", *READS_GENERAL]
        assert db.hourly_requests[-1] == {zone_ids[zone]}  # lee solo esa zona
        assert_history_matches_store(
            filtered, stored, zone_ids, periodo, start, END_AT_T, zone=zone
        )
        assert_without_tariff(filtered)
        assert filtered["total_kwh"] == pytest.approx(shares[str(zone_ids[zone])])
        # La serie de la zona es la misma columna de la serie General.
        for own, whole in zip(filtered["serie"], general["serie"], strict=True):
            (item,) = [i for i in whole["zonas"] if i["zona_id"] == str(zone_ids[zone])]
            assert own["energia_kwh"] == pytest.approx(item["energia_kwh"])

    assert db.readings_of(hogar_id) == before  # consultar no escribe
    assert "commit" not in db.events


@pytest.mark.parametrize("periodo", ["semana", "mes"])
@each_personality
def test_daily_points_stay_in_the_band_of_the_personality_averages(
    db: HistoryStore,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    periodo: str,
) -> None:
    """Cada día completo de la serie, por zona: promedio × fin de semana × [humor mín., máx.].

    Los promedios salen de `tests/helpers/personalities.py` (los mismos del simulador). Los
    picos del simulador solo suman: el techo se comprueba en las zonas sin picos.
    """
    personality = load_personalities()[name]
    zones_with_peaks = set(final_profiles()[name]["picos_config"])
    hogar_id = new_household(db, client, monkeypatch, name)
    tipo_of = {str(zona_id): tipo for tipo, zona_id in db.zone_ids(hogar_id).items()}
    query_at(monkeypatch, T)

    body = ok(get_history(client, user_of(name), hogar_id, periodo))

    tolerance = 24 * float(ROUNDING_KWH)
    complete_days = [p for p in body["serie"] if moment(p["fin"]) - moment(p["inicio"]) == ONE_DAY]
    assert len(complete_days) == len(body["serie"]) - 1  # el de hoy es parcial
    for point in complete_days:
        day = moment(point["inicio"]).date()
        factor = personality.weekend_factor if day.weekday() >= 5 else 1.0
        for item in point["zonas"]:
            zone = tipo_of[item["zona_id"]]
            expected = personality.zone_kwh_per_day[zone] * factor
            assert item["energia_kwh"] >= expected * personality.humor_min - tolerance, (zone, day)
            if zone not in zones_with_peaks:
                assert item["energia_kwh"] <= expected * personality.humor_max + tolerance


@pytest.mark.parametrize("periodo", ["semana", "mes"])
def test_period_totals_follow_the_personality_order(
    db: HistoryStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, periodo: str
) -> None:
    """compacto < eficiente < intermedio < familiar < amplio en `total_kwh`, por la API.

    Semana (lunes 16 a sábado 21 a las 22:00) y mes (1 al 21 a las 22:00), en General, del
    hogar de referencia de cada personalidad. Si el ruido invirtiera el orden, el mensaje de
    la aserción lleva los números.
    """
    households = {name: new_household(db, client, monkeypatch, name) for name in PERSONALITY_ORDER}
    query_at(monkeypatch, T)

    totals = {
        name: ok(get_history(client, user_of(name), hogar_id, periodo))["total_kwh"]
        for name, hogar_id in households.items()
    }

    values = [totals[name] for name in PERSONALITY_ORDER]
    assert values == sorted(values), totals
    assert len(set(values)) == len(values), totals


# --- 2. tarifa por fecha y cargo fijo solo en Mes General -----------------------------------


@each_personality
def test_tariff_by_date_and_fixed_charge_only_in_month_general(
    db: HistoryStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Cada fecha con la tarifa vigente en ella; cargo fijo solo en la proyección de Mes General.

    RN-V-01, RN-V-02, RN-XIII-05, DC-30, DC-39. Tarifa vieja (700) hasta el 18/11 (exclusivo)
    y nueva (812,5 con cargo fijo 15.000) desde el 18/11. Luego la misma tarifa nueva sin cargo
    fijo: la proyección de Mes General baja exactamente el cargo fijo y las demás no cambian.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    zona_id = db.zone_ids(hogar_id)[min(zones)]
    change = date(2026, 11, 18)
    db.seed_tariff(hogar_id, OLD_PRICE, date(2026, 10, 1), change)
    db.seed_tariff(hogar_id, NEW_PRICE, change, None, FIXED_CHARGE)
    query_at(monkeypatch, T)

    def price_of(point: dict[str, Any]) -> float:
        day = moment(point["inicio"]).date()
        return float(OLD_PRICE if day < change else NEW_PRICE)

    views = [(periodo, zone) for periodo in PERIODS for zone in (None, zona_id)]
    with_fixed = {}
    for periodo, zone in views:
        db.events.clear()
        body = ok(get_history(client, user_id, hogar_id, periodo, zone))
        assert db.events[-1] == TARIFFS_STATEMENT
        assert body["tarifa_vigente"] is True
        for point in body["serie"]:
            assert point["costo_cop"] == pytest.approx(point["energia_kwh"] * price_of(point))
        # Todo el periodo con total: costo = Σ kWh de cada hora × precio de su fecha (aquí, por
        # día, la misma suma).
        assert body["costo"]["costo_cop"] == pytest.approx(
            math.fsum(point["costo_cop"] for point in body["serie"])
        )
        projection = body["costo"]["proyeccion_cierre_cop"]
        assert projection is not None and projection >= body["costo"]["costo_cop"]
        assert body["costo"]["incluye_cargo_fijo"] is (periodo == "mes" and zone is None)
        with_fixed[periodo, zone] = projection

    # La misma tarifa nueva, sin cargo fijo.
    db.tariffs[hogar_id] = []
    db.seed_tariff(hogar_id, OLD_PRICE, date(2026, 10, 1), change)
    db.seed_tariff(hogar_id, NEW_PRICE, change, None, None)
    for periodo, zone in views:
        body = ok(get_history(client, user_id, hogar_id, periodo, zone))
        assert body["costo"]["incluye_cargo_fijo"] is False
        fixed = float(FIXED_CHARGE) if (periodo, zone) == ("mes", None) else 0.0
        assert with_fixed[periodo, zone] - body["costo"]["proyeccion_cierre_cop"] == pytest.approx(
            fixed
        )


@each_personality
def test_a_date_without_tariff_leaves_the_period_cost_null(
    db: HistoryStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Tarifa solo desde el jueves 19/11: en Semana los días 16–18 no tienen costo.

    RN-XIII-05: el punto sin tarifa en su fecha va en null y el costo del periodo también
    (falta el precio de alguna fecha); `tarifa_vigente` es true porque hoy sí hay tarifa. En
    Día (solo el 21/11) el costo existe.
    """
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    since = date(2026, 11, 19)
    db.seed_tariff(hogar_id, NEW_PRICE, since)
    query_at(monkeypatch, T)

    week = ok(get_history(client, user_id, hogar_id, "semana"))
    assert week["tarifa_vigente"] is True
    for point in week["serie"]:
        if moment(point["inicio"]).date() < since:
            assert point["costo_cop"] is None
        else:
            assert point["costo_cop"] == pytest.approx(point["energia_kwh"] * float(NEW_PRICE))
    assert week["costo"]["costo_cop"] is None
    assert week["costo"]["proyeccion_cierre_cop"] is None

    day = ok(get_history(client, user_id, hogar_id, "dia"))
    assert day["costo"]["costo_cop"] == pytest.approx(day["total_kwh"] * float(NEW_PRICE))


# --- 3. B-04 con el historial ----------------------------------------------------------------


@each_personality
def test_b04_the_history_query_recovers_the_missing_hours(
    db: HistoryStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Servidor apagado 5 h (cruza medianoche) y luego `GET /historial?periodo=dia`.

    RN-IV-05, DC-34: la consulta, después de la guardia y antes de leer, guarda las 5 horas de
    cada sensor y las usa: el día del domingo trae sus 3 horas (00, 01 y 02) con dato.
    Repetirla no guarda nada más.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    query_at(monkeypatch, LATER)

    db.events.clear()
    body = ok(get_history(client, user_id, hogar_id, "dia"))

    assert db.events == [MEMBERSHIP_STATEMENT, *RECOVERY_STATEMENTS, "commit", *READS_GENERAL]
    assert_contiguous(db, hogar_id, 720 + HOURS_OFF)
    assert len(db.readings_of(hogar_id)) == (720 + HOURS_OFF) * len(zones)
    stored = db.stored(hogar_id)
    assert_history_matches_store(
        body, stored, db.zone_ids(hogar_id), "dia", STARTS_AT_LATER["dia"], END_AT_LATER
    )
    assert len(body["serie"]) == 3
    assert None not in [point["energia_kwh"] for point in body["serie"]]

    db.events.clear()
    again = ok(get_history(client, user_id, hogar_id, "dia"))
    assert db.events == [MEMBERSHIP_STATEMENT, *READ_STATEMENTS, "rollback", *READS_GENERAL]
    assert READINGS_STATEMENT not in db.events
    assert again == body


# --- 4. si la recuperación falla, se responde con lo guardado -------------------------------


@pytest.mark.parametrize("failure", sorted(FAILURES))
@each_personality
def test_failed_recovery_answers_200_with_the_stored_data(
    db: HistoryStore,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    name: str,
    failure: str,
) -> None:
    """Decisión de Nicolás (23/11/2026): recuperación fallida → 200 con los datos guardados.

    Apagado de 5 h y la recuperación falla (candado o inserción) en cada consulta: nada se
    guarda, los 3 periodos responden 200 (no 500) y las horas que faltan (sábado 22:00 a domingo
    02:00) dejan en null sus puntos, nunca en cero ni con suma parcial. El periodo queda
    incompleto: comparación `sin_datos` y costo null aunque haya tarifa. El log lleva el WARNING
    de recuperación omitida, sin el id del hogar ni el detalle interno de la base; la respuesta
    tampoco lo trae.
    """
    hogar_id = new_household(db, client, monkeypatch, name)
    user_id = user_of(name)
    backfill = db.readings_of(hogar_id)
    stored = db.stored(hogar_id)
    zone_ids = db.zone_ids(hogar_id)
    db.seed_tariff(hogar_id, NEW_PRICE, date(2026, 11, 1))
    query_at(monkeypatch, LATER)
    caplog.set_level(logging.INFO)

    for periodo in PERIODS:
        db.fail_once.add(FAILURES[failure])
        db.events.clear()
        response = get_history(client, user_id, hogar_id, periodo)
        body = ok(response)
        assert FAILURES[failure] not in db.fail_once  # la falla sí ocurrió
        assert "rollback" in db.events and "commit" not in db.events
        assert db.events[-len(READS_GENERAL) :] == READS_GENERAL  # y luego leyó lo guardado
        assert INTERNAL_DETAIL not in response.text

        assert_history_matches_store(
            body, stored, zone_ids, periodo, STARTS_AT_LATER[periodo], END_AT_LATER
        )
        energies = [point["energia_kwh"] for point in body["serie"]]
        if periodo == "dia":
            assert energies == [None, None, None]
            assert body["total_kwh"] == 0
            assert {item["participacion_pct"] for item in body["participacion_zonas"]} == {0}
        else:
            # El sábado 21 (le faltan 22:00 y 23:00) y el domingo 22 van en null; el resto no.
            assert energies[-2:] == [None, None]
            assert None not in energies[:-2]
            assert body["total_kwh"] > 0
        for point in body["serie"]:
            if point["energia_kwh"] is None:
                assert point["costo_cop"] is None
            else:
                assert point["costo_cop"] == pytest.approx(
                    point["energia_kwh"] * float(NEW_PRICE)
                )
        assert body["comparacion"]["estado"] == "sin_datos"
        assert body["tarifa_vigente"] is True
        assert body["costo"]["costo_cop"] is None
        assert body["costo"]["proyeccion_cierre_cop"] is None

    assert db.readings_of(hogar_id) == backfill  # nada nuevo
    skipped = [
        record
        for record in caplog.records
        if record.name == hour_recovery.__name__
        and record.levelno == logging.WARNING
        and record.getMessage() == hour_recovery.RECOVERY_SKIPPED_MESSAGE
    ]
    assert len(skipped) == len(PERIODS)
    for record in caplog.records:
        text = record.getMessage()
        assert str(hogar_id) not in text and INTERNAL_DETAIL not in text
        assert record.exc_info is None


# --- 5. seguridad y zonas -------------------------------------------------------------------


@each_personality
def test_member_without_view_history_gets_403_and_nothing_is_recovered(
    db: HistoryStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """P-03 de punta a punta: 403 `SIN_PERMISO_VER_HISTORIAL` y la recuperación NO corre.

    RN-XVII-02, RN-IV-05: la guardia va antes. El administrador pasa aunque el permiso del hogar
    esté en false (P-06, RN-XVII-05). Con `ver_historial` y sin `ver_consumo_actual`, el
    miembro sí ve el historial: cada permiso vigila lo suyo.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    member_id = stable_id("miembro", TAG, name)
    db.seed_member(hogar_id, member_id)
    db.set_household_permission(hogar_id, "permiso_ver_historial", False)
    zona_id = db.zone_ids(hogar_id)[min(zones)]
    backfill = db.readings_of(hogar_id)
    query_at(monkeypatch, LATER)

    for periodo in PERIODS:
        for zone in (None, zona_id):
            db.events.clear()
            response = get_history(client, member_id, hogar_id, periodo, zone)
            assert response.status_code == 403, response.text
            assert response.json()["codigo"] == FORBIDDEN_CODE
            assert db.events == [MEMBERSHIP_STATEMENT]  # ni candado ni lecturas
    assert db.readings_of(hogar_id) == backfill

    db.events.clear()
    admin = ok(get_history(client, user_of(name), hogar_id, "dia"))
    assert db.events[:2] == [MEMBERSHIP_STATEMENT, READ_STATEMENTS[0]]
    assert moment(admin["fin"]) == END_AT_LATER

    db.set_household_permission(hogar_id, "permiso_ver_historial", True)
    db.set_household_permission(hogar_id, "permiso_ver_consumo_actual", False)
    assert ok(get_history(client, member_id, hogar_id, "semana"))["total_kwh"] > 0


@each_personality
def test_other_household_404_and_zones_that_do_not_count(
    db: HistoryStore, client: TestClient, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """P-01 y R-01: sin membresía → 404 sin recuperar; zona de otro hogar → 404 sin leer.

    RN-XI-05 (`counts_for_total`): una zona con sensor pausado no entra en General y, pedida por
    filtro, responde 200 con todo sin dato (sin leer sus lecturas, total 0). Periodo fuera del
    enum → 422 `VALIDACION`.
    """
    zones = REFERENCE_HOUSEHOLDS[name][1]
    hogar_id = new_household(db, client, monkeypatch, name)
    neighbour = new_household(db, client, monkeypatch, other_personality(name))
    neighbour_zone = next(iter(db.zone_ids(neighbour).values()))
    user_id = user_of(name)
    query_at(monkeypatch, T)

    db.events.clear()
    response = get_history(client, user_id, neighbour, "dia")
    assert response.status_code == 404, response.text
    assert response.json()["codigo"] == "NO_ENCONTRADO"
    assert db.events == [MEMBERSHIP_STATEMENT]

    db.events.clear()
    response = get_history(client, user_id, hogar_id, "mes", neighbour_zone)
    assert response.status_code == 404, response.text
    assert response.json()["codigo"] == "NO_ENCONTRADO"
    assert HOURLY_STATEMENT not in db.events and TARIFFS_STATEMENT not in db.events

    paused = min(zones)
    db.set_state("sensores_zona", db.sensors_of(hogar_id)[paused], "pausado")
    zone_ids = db.zone_ids(hogar_id)
    stored = {zone: series for zone, series in db.stored(hogar_id).items() if zone != paused}
    general = ok(get_history(client, user_id, hogar_id, "semana"))
    assert str(zone_ids[paused]) not in {i["zona_id"] for i in general["participacion_zonas"]}
    assert_history_matches_store(
        general, stored, zone_ids, "semana", STARTS_AT_T["semana"], END_AT_T
    )

    db.events.clear()
    alone = ok(get_history(client, user_id, hogar_id, "semana", zone_ids[paused]))
    assert HOURLY_STATEMENT not in db.events  # no lee lecturas de una zona que no cuenta
    assert alone["zona_id"] == str(zone_ids[paused])
    assert alone["total_kwh"] == 0
    assert {point["energia_kwh"] for point in alone["serie"]} == {None}
    assert {point["zonas"] is None for point in alone["serie"]} == {True}
    assert alone["participacion_zonas"] is None
    assert alone["ultimo_pico"] is None
    assert alone["comparacion"]["estado"] == "sin_datos"

    response = client.get(
        f"{API_PREFIX}/hogares/{hogar_id}/historial",
        params={"periodo": "anio"},
        headers=auth_header(make_token(user_id)),
    )
    assert response.status_code == 422, response.text
    assert response.json()["codigo"] == "VALIDACION"
