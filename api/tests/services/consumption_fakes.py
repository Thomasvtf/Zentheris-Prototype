"""Dobles en memoria de `app.data` para los casos de uso de consumo (fase 6).

Sin base ni red. Se reemplazan con monkeypatch `list_household_zones`, `get_hourly_readings`,
`get_preferences`, `get_active_goal` y `get_current_tariff`, que leen de `FakeConsumptionDatabase`
y filtran como la consulta real (por `hogar_id`, zonas pedidas, [start, end] inclusivo y
vigencia [desde, hasta)). La recuperación de horas se reemplaza por un espía
(`hour_recovery.fill_missing_hours`), salvo que la prueba instale la real. Cada llamada queda en
`calls` para comprobar el orden. No demuestra compatibilidad con PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.data import goals as goals_data
from app.data import households as households_data
from app.data import readings as readings_data
from app.data import tariffs as tariffs_data
from app.data import users as users_data
from app.data.goals import ActiveGoalRow
from app.data.households import ZoneRow
from app.data.readings import HourlyReadingRow
from app.data.tariffs import TariffRow
from app.data.users import PreferencesRow
from app.services import hour_recovery
from tests.simulator.support import stable_id


class FakeSession:
    """Sesión falsa: cuenta commits y rollbacks (la consulta no debe hacer commit)."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeConsumptionDatabase:
    """Zonas, lecturas, preferencias, metas y tarifas en memoria."""

    def __init__(self) -> None:
        self.zones: dict[UUID, list[ZoneRow]] = {}
        self.zone_household: dict[UUID, UUID] = {}
        self.readings: dict[UUID, dict[datetime, float]] = {}
        self.preferences: dict[UUID, PreferencesRow] = {}
        self.goals: dict[UUID, ActiveGoalRow] = {}
        self.tariffs: dict[UUID, list[TariffRow]] = {}
        self.calls: list[tuple[Any, ...]] = []
        # Fuente extra de lecturas (p. ej. lo que guardó la recuperación real).
        self.extra_readings: Callable[[], dict[UUID, dict[datetime, float]]] | None = None

    # --- preparación ---------------------------------------------------------------
    def add_zone(
        self,
        hogar_id: UUID,
        tipo: str,
        nombre: str,
        estado: str = "activa",
        sensor_estado: str | None = "activo",
        zona_id: UUID | None = None,
    ) -> UUID:
        zona_id = zona_id or stable_id("zona", str(hogar_id), tipo)
        self.zones.setdefault(hogar_id, []).append(
            ZoneRow(id=zona_id, tipo=tipo, nombre=nombre, estado=estado,
                    sensor_estado=sensor_estado)
        )
        self.zone_household[zona_id] = hogar_id
        return zona_id

    def set_series(self, zona_id: UUID, series: dict[datetime, float]) -> None:
        self.readings[zona_id] = dict(series)

    def set_preferences(self, usuario_id: UUID, base_comparacion: str) -> None:
        self.preferences[usuario_id] = PreferencesRow(
            notif_consumo=True, notif_consejos=True, base_comparacion=base_comparacion
        )

    def set_goal(self, hogar_id: UUID, monthly_kwh: float) -> None:
        self.goals[hogar_id] = ActiveGoalRow(
            id=stable_id("meta", str(hogar_id)),
            tipo="ahorro",
            valor_kwh_mensual=monthly_kwh,
            fecha_inicio=date(2026, 11, 1),
        )

    def add_tariff(
        self,
        hogar_id: UUID,
        precio_kwh: float,
        desde: date,
        hasta: date | None = None,
        cargo_fijo: float | None = None,
    ) -> None:
        self.tariffs.setdefault(hogar_id, []).append(
            TariffRow(
                id=stable_id("tarifa", str(hogar_id), desde.isoformat()),
                precio_kwh=precio_kwh,
                cargo_fijo_mensual=cargo_fijo,
                vigente_desde=desde,
                vigente_hasta=hasta,
            )
        )

    def names(self) -> list[str]:
        return [call[0] for call in self.calls]

    # --- dobles de app.data --------------------------------------------------------
    def fill_missing_hours(self, session: Any, hogar_id: UUID, now: datetime | None = None) -> int:
        self.calls.append(("recovery", hogar_id, now))
        return 0

    def list_household_zones(self, session: Any, hogar_id: UUID) -> list[ZoneRow]:
        self.calls.append(("zones", hogar_id))
        return sorted(self.zones.get(hogar_id, []), key=lambda z: (z.nombre, str(z.id)))

    def get_hourly_readings(
        self,
        session: Any,
        hogar_id: UUID,
        zona_ids: Sequence[UUID],
        start: datetime,
        end: datetime,
    ) -> list[HourlyReadingRow]:
        self.calls.append(("readings", hogar_id, tuple(zona_ids), start, end))
        if not zona_ids:
            return []
        if start.utcoffset() is None or end.utcoffset() is None:
            raise ValueError("start y end deben llevar zona horaria")
        if start > end:
            raise ValueError("start > end")
        stored = {zona: dict(series) for zona, series in self.readings.items()}
        if self.extra_readings is not None:
            for zona, series in self.extra_readings().items():
                stored.setdefault(zona, {}).update(series)
        rows = []
        for zona_id in sorted(set(zona_ids), key=str):
            if self.zone_household.get(zona_id) != hogar_id:
                continue  # R-01: zona de otro hogar
            for moment, kwh in sorted(stored.get(zona_id, {}).items()):
                if start <= moment <= end:
                    rows.append(HourlyReadingRow(zona_id=zona_id, fecha_hora=moment,
                                                 consumo_kwh=float(kwh)))
        return rows

    def get_preferences(self, session: Any, usuario_id: UUID) -> PreferencesRow | None:
        self.calls.append(("preferences", usuario_id))
        return self.preferences.get(usuario_id)

    def get_active_goal(self, session: Any, hogar_id: UUID) -> ActiveGoalRow | None:
        self.calls.append(("goal", hogar_id))
        return self.goals.get(hogar_id)

    def get_current_tariff(self, session: Any, hogar_id: UUID, today: date) -> TariffRow | None:
        self.calls.append(("tariff", hogar_id, today))
        if isinstance(today, datetime):
            raise TypeError("today debe ser una fecha")
        for tariff in self.tariffs.get(hogar_id, []):
            if tariff.vigente_desde <= today and (
                tariff.vigente_hasta is None or today < tariff.vigente_hasta
            ):
                return tariff
        return None


def install_fake_consumption_database(
    monkeypatch: pytest.MonkeyPatch, spy_recovery: bool = True
) -> FakeConsumptionDatabase:
    db = FakeConsumptionDatabase()
    if spy_recovery:
        monkeypatch.setattr(hour_recovery, "fill_missing_hours", db.fill_missing_hours)
    monkeypatch.setattr(households_data, "list_household_zones", db.list_household_zones)
    monkeypatch.setattr(readings_data, "get_hourly_readings", db.get_hourly_readings)
    monkeypatch.setattr(users_data, "get_preferences", db.get_preferences)
    monkeypatch.setattr(goals_data, "get_active_goal", db.get_active_goal)
    monkeypatch.setattr(tariffs_data, "get_current_tariff", db.get_current_tariff)
    return db


def hourly_series(
    value: Callable[[datetime], float], first: datetime, last: datetime,
    skip: frozenset[datetime] = frozenset(),
) -> dict[datetime, float]:
    """Serie horaria de `first` a `last` inclusive (inicios de hora en Bogotá)."""
    series, moment = {}, first
    while moment <= last:
        if moment not in skip:
            series[moment] = value(moment)
        moment += timedelta(hours=1)
    return series
