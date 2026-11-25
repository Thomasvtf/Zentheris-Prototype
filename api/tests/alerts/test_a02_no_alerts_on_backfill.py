"""A-02 · Alertas: Backfill con horas que serían críticas.

Esperado: 0 alertas. Regla: DC-35 (la recuperación en vivo sí evalúa, solo sus horas, en un
SAVEPOINT para que un fallo no impida guardar las lecturas).
Matriz: docs/pruebas/matriz-pruebas-backend-v1.md.

1. Onboarding real (`services.onboarding`, con los dobles de tests/helpers/onboarding.py) de cada
   personalidad, con la última hora del backfill de la cocina convertida en crítica: el estado de
   zona la da `critico`, pero no se llama a nada de alertas ni consejos y no hay alertas.
2. Recuperación en vivo después de un backfill con un pico crítico (sábado 19:00): solo se
   evalúan las horas nuevas; la del backfill nunca produce alerta y la nueva (domingo 19:00) sí.
"""

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.data import alerts as alerts_data
from app.data import tips as tips_data
from app.domain import alert_rules
from app.domain.states import evaluate_zone_hours
from app.services import alerts_tips, hour_recovery, live_alerts
from app.services import onboarding as onboarding_service
from app.services.thresholds import get_thresholds
from tests.helpers.onboarding import (
    LAST_HOUR,
    REFERENCE_HOUSEHOLDS,
    FakeDatabase,
    install_fake_database,
    make_payload,
    run,
)
from tests.helpers.personalities import PERSONALITY_ORDER
from tests.services.alerts_fakes import (
    BACKFILL_AT,
    DAY,
    FakeAlertsDatabase,
    critical_value,
    install_fake_alerts_database,
    install_spikes,
    spy_live_evaluation,
    zone_id,
)
from tests.services.recovery_fakes import FakeHousehold
from tests.simulator.support import bogota

each_personality = pytest.mark.parametrize("name", PERSONALITY_ORDER)
ZONE = "cocina"


# ------------------------------------------------------------------ 1. onboarding
def forbid_alerts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Toda función pública de alertas o consejos anota su nombre y falla si se llama."""
    called: list[str] = []

    def forbidden(name: str) -> Callable[..., Any]:
        def fail(*_args: Any, **_kwargs: Any) -> None:
            called.append(name)
            raise AssertionError(f"el backfill no genera alertas (DC-35): {name}")

        return fail

    for module in (alerts_data, tips_data, alert_rules, alerts_tips, live_alerts):
        for attribute, value in list(vars(module).items()):
            public = callable(value) and not isinstance(value, type) and attribute[:1] != "_"
            if public and getattr(value, "__module__", "") == module.__name__:
                monkeypatch.setattr(module, attribute, forbidden(attribute))
    return called


def spike_last_backfill_hour(monkeypatch: pytest.MonkeyPatch) -> None:
    """La última hora del backfill de la cocina pasa a ser crítica frente a su promedio real."""
    generate = onboarding_service.generate_backfill  # el de los dobles (anota el paso)

    def spiked(hogar_id: UUID, profile: Any, sensors: Any, now: datetime) -> Any:
        rows = generate(hogar_id, profile, sensors, now)
        sensor = sensors[ZONE]
        same_hour = [
            float(row["consumo_kwh"])
            for row in rows
            if row["sensor_id"] == sensor
            and row["fecha_hora"] != LAST_HOUR
            and row["fecha_hora"].hour == LAST_HOUR.hour
        ]
        value = critical_value(sum(same_hour) / len(same_hour))
        return [
            {**row, "consumo_kwh": Decimal(str(round(value, 4)))}
            if row["sensor_id"] == sensor and row["fecha_hora"] == LAST_HOUR
            else row
            for row in rows
        ]

    monkeypatch.setattr(onboarding_service, "generate_backfill", spiked)


def backfill_states(db: FakeDatabase) -> dict[str, str]:
    """Estado de zona de la última hora del backfill, calculado con el motor real."""
    zone_types = {row["id"]: row["tipo"] for row in db.saved["zonas"]}
    zone_of_sensor = {row["id"]: row["zona_id"] for row in db.saved["sensores_zona"]}
    series: dict[UUID, dict[datetime, float]] = defaultdict(dict)
    for row in db.saved["lecturas"]:
        series[zone_of_sensor[row["sensor_id"]]][row["fecha_hora"]] = float(row["consumo_kwh"])
    hours = {zona: [LAST_HOUR] for zona in series}
    return {
        zone_types[item.zona_id]: item.state
        for item in evaluate_zone_hours(series, hours, get_thresholds())
    }


@each_personality
def test_a02_onboarding_backfill_with_a_critical_hour_creates_no_alerts(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    db = install_fake_database(monkeypatch)
    spike_last_backfill_hour(monkeypatch)
    called = forbid_alerts(monkeypatch)

    run(db, make_payload(*REFERENCE_HOUSEHOLDS[name]))

    assert db.commits == 1
    assert backfill_states(db)[ZONE] == "critico"  # la hora SERÍA crítica…
    assert called == []  # …pero el onboarding no evalúa alertas ni consejos (DC-35)
    assert not {event for event in db.events if "alert" in event or "tip" in event}


# ------------------------------------------------------------------ 2. recuperación en vivo
@pytest.fixture
def alerts_db(monkeypatch: pytest.MonkeyPatch) -> FakeAlertsDatabase:
    return install_fake_alerts_database(monkeypatch)


@each_personality
def test_a02_live_recovery_evaluates_only_its_hours(
    alerts_db: FakeAlertsDatabase, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    db = alerts_db
    household = db.register(FakeHousehold(name, tag="a02"), created_at=BACKFILL_AT)
    db.add_backfill(household, BACKFILL_AT)
    sensor = household.sensors[ZONE]
    saturday, sunday = bogota(2026, 11, 21, 19), bogota(2026, 11, 22, 19)
    # Pico crítico DENTRO del backfill (sábado 19:00).
    backfill_peak = critical_value(db.same_hour_average(household, ZONE, saturday))
    db.saved[(sensor, saturday)] = {
        **db.saved[(sensor, saturday)],
        "consumo_kwh": Decimal(str(round(backfill_peak, 4))),
    }
    # Pico crítico EN VIVO (domingo 19:00).
    install_spikes(
        monkeypatch, {(sensor, sunday): critical_value(db.same_hour_average(household, ZONE, sunday))}
    )
    seen = spy_live_evaluation(monkeypatch)

    hour_recovery.fill_missing_hours(db.session(), household.id, bogota(2026, 11, 22, 20, 10))

    # La evaluación recibió solo las horas nuevas (18:00 y 19:00 del domingo), de sus zonas.
    first_live = BACKFILL_AT.replace(minute=0)
    assert seen == [{zone: [first_live, sunday] for zone in sorted(household.sensors)}]
    zona = zone_id(household, ZONE)
    keys = {alert["clave_evento"] for alert in db.alerts(household.id)}
    assert f"consumo_critico:{zona}:2026-11-21" not in keys  # el backfill nunca alerta
    assert f"consumo_critico:{zona}:{DAY}" in keys  # la hora en vivo sí
    # Ninguna alerta viene de una hora anterior a la primera en vivo (created_at = fin de la hora).
    assert all(
        alert["created_at"] - timedelta(hours=1) >= first_live for alert in db.alerts(household.id)
    )
