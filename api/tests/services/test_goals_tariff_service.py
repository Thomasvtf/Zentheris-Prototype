"""Pruebas de `app.services.goals_tariff` con `app.data.*` falso en memoria (fase 10).

`obtenerMeta`, `crearMeta`, `obtenerTarifa` y `crearTarifa`. Reglas: RN-V-01, RN-V-02, RN-V-03,
RN-XVI-04, RN-XVI-05, RN-XVII-04, RN-IV-05, DC-34, DC-39, DC-41 y las decisiones D3, D4, D6 y D7
de la fase 10. Los dobles imitan las sentencias de `app/data/goals.py` y `app/data/tariffs.py`
(una meta activa por hogar, `metas_rango_valido`, vigencias [desde, hasta) sin solapes, una
tarifa abierta por hogar); las lecturas y la recuperación vienen de `consumption_fakes.py`. Las
series de las personalidades salen de `tests/helpers/personalities.py` y del simulador. No
demuestra compatibilidad con PostgreSQL.
"""

import inspect
import logging
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.data import goals as goals_data
from app.data import households as households_data
from app.data import memberships as memberships_data
from app.data import tariffs as tariffs_data
from app.data.goals import ActiveGoalExistsError, ActiveGoalRow, GoalRow
from app.data.households import HouseholdRow
from app.data.memberships import MembershipRow
from app.data.tariffs import TariffOverlapError, TariffRow
from app.domain.simulator import TIMEZONE, hour_from_index
from app.domain.simulator.engine import simulate_household
from app.errors import ApiError, CodigoError
from app.schemas.goals_tariff import Meta, MetaCrear, MetaVista, Tarifa, TarifaCrear, TarifaVista
from app.services import goals_tariff as service
from app.services import hour_recovery
from app.services.hour_recovery import RECOVERY_SKIPPED_MESSAGE, HourRecoveryError
from tests.helpers.personalities import PERSONALITY_ORDER, PersonalityAverages, load_personalities
from tests.services.consumption_fakes import (
    FakeConsumptionDatabase,
    FakeSession,
    hourly_series,
    install_fake_consumption_database,
)
from tests.simulator.support import final_profiles, stable_id

HOGAR = stable_id("hogar", "metas")
OTRO_HOGAR = stable_id("hogar", "metas", "otro")
USER = stable_id("usuario", "metas")
NOW = datetime(2026, 11, 23, 15, 20, tzinfo=TIMEZONE)  # hora evaluada 14:00-15:00
HOUR = datetime(2026, 11, 23, 14, tzinfo=TIMEZONE)
TODAY = date(2026, 11, 23)
WINDOW_START = datetime(2026, 10, 24, tzinfo=TIMEZONE)  # 00:00 Bogotá de hoy − 30 días
YESTERDAY_END = datetime(2026, 11, 22, 23, tzinfo=TIMEZONE)  # última hora del último día completo

each_personality = pytest.mark.parametrize(
    "personality", load_personalities().values(), ids=lambda p: p.name
)


# ------------------------------------------------------------------ dobles de metas y tarifas
@dataclass
class StoredGoal:
    row: GoalRow
    hogar_id: UUID
    seq: int


class GoalsTariffDatabase:
    """Metas y tarifas en memoria sobre `FakeConsumptionDatabase` (zonas, lecturas y llamadas)."""

    def __init__(self, db: FakeConsumptionDatabase) -> None:
        self.db = db
        self.goals: list[StoredGoal] = []
        self.fail_insert_tariff: TariffOverlapError | None = None
        self.fail_close_tariff: TariffOverlapError | None = None
        # Membresías activas (hogar, usuario) → rol, y permiso modificar_metas por hogar. Por
        # defecto USER es administrador de HOGAR y de OTRO_HOGAR.
        self.roles: dict[tuple[UUID, UUID], str] = {
            (HOGAR, USER): "administrador",
            (OTRO_HOGAR, USER): "administrador",
        }
        self.modify_goals: dict[UUID, bool] = {}
        # Gancho que corre justo después de bloquear el hogar (otra transacción que confirmó
        # «mientras se esperaba el bloqueo»).
        self.after_lock: Any = None

    # --- preparación ---------------------------------------------------------------
    def add_goal(
        self, hogar_id: UUID, valor: float, fecha_inicio: date, *, estado: str = "activa",
        fecha_fin: date | None = None, tipo: str = "ahorro",
    ) -> UUID:
        goal_id = uuid4()
        self.goals.append(
            StoredGoal(GoalRow(goal_id, tipo, valor, estado, fecha_inicio, fecha_fin), hogar_id,
                       len(self.goals))
        )
        return goal_id

    def add_tariff(
        self, hogar_id: UUID, precio: float, desde: date, hasta: date | None = None, *,
        operador: str | None = "EPM", cargo_fijo: float | None = None,
    ) -> UUID:
        tariff_id = uuid4()
        self.db.tariffs.setdefault(hogar_id, []).append(
            TariffRow(tariff_id, precio, cargo_fijo, desde, hasta, operador)
        )
        return tariff_id

    def goal(self, goal_id: UUID) -> GoalRow:
        (stored,) = [g for g in self.goals if g.row.id == goal_id]
        return stored.row

    def tariffs_of(self, hogar_id: UUID) -> list[TariffRow]:
        return sorted(self.db.tariffs.get(hogar_id, []), key=lambda t: t.vigente_desde)

    # --- app.data.households -------------------------------------------------------
    def lock_household(self, session: Any, hogar_id: UUID) -> None:
        self.db.calls.append(("lock_household", hogar_id))
        if self.after_lock is not None:
            hook, self.after_lock = self.after_lock, None
            hook()

    def get_household(self, session: Any, hogar_id: UUID) -> HouseholdRow | None:
        self.db.calls.append(("household", hogar_id))
        if hogar_id not in (HOGAR, OTRO_HOGAR):
            return None
        return HouseholdRow(
            id=hogar_id,
            nombre="Casa Pérez",
            tipo_vivienda="apartamento",
            permiso_ver_consumo_actual=True,
            permiso_ver_historial=True,
            permiso_recibir_alertas=True,
            permiso_modificar_metas=self.modify_goals.get(hogar_id, False),
        )

    # --- app.data.memberships --------------------------------------------------------
    def get_user_membership_in_household(
        self, session: Any, hogar_id: UUID, usuario_id: UUID, *, for_update: bool = False
    ) -> MembershipRow | None:
        self.db.calls.append(("membership", hogar_id, usuario_id, for_update))
        rol = self.roles.get((hogar_id, usuario_id))
        if rol is None:
            return None
        return MembershipRow(
            membresia_id=stable_id("membresia", str(hogar_id), str(usuario_id)),
            hogar_id=hogar_id,
            usuario_id=usuario_id,
            rol=rol,
            estado="activo",
        )

    # --- app.data.goals --------------------------------------------------------------
    def get_active_goal(self, session: Any, hogar_id: UUID) -> ActiveGoalRow | None:
        self.db.calls.append(("goal", hogar_id))
        for stored in self.goals:
            if stored.hogar_id == hogar_id and stored.row.estado == "activa":
                row = stored.row
                return ActiveGoalRow(row.id, row.tipo, row.valor_kwh_mensual, row.fecha_inicio)
        return None

    def deactivate_active_goal(self, session: Any, hogar_id: UUID, fecha_fin: date | None) -> int:
        self.db.calls.append(("deactivate_goal", hogar_id, fecha_fin))
        if isinstance(fecha_fin, datetime):
            raise TypeError("fecha_fin debe ser date")
        changed = 0
        for stored in self.goals:
            if stored.hogar_id == hogar_id and stored.row.estado == "activa":
                if fecha_fin is not None and fecha_fin <= stored.row.fecha_inicio:
                    raise AssertionError("violaría metas_rango_valido (fecha_fin > fecha_inicio)")
                stored.row = replace(stored.row, estado="inactiva", fecha_fin=fecha_fin)
                changed += 1
        return changed

    def insert_goal(
        self, session: Any, *, hogar_id: UUID, tipo: str, valor_kwh_mensual: float,
        fecha_inicio: date,
    ) -> GoalRow:
        self.db.calls.append(("insert_goal", hogar_id, tipo, valor_kwh_mensual, fecha_inicio))
        if isinstance(fecha_inicio, datetime):
            raise TypeError("fecha_inicio debe ser date")
        if any(g.hogar_id == hogar_id and g.row.estado == "activa" for g in self.goals):
            raise ActiveGoalExistsError("El hogar ya tiene una meta activa.")
        goal_id = self.add_goal(hogar_id, valor_kwh_mensual, fecha_inicio, tipo=tipo)
        return self.goal(goal_id)

    # --- app.data.tariffs ------------------------------------------------------------
    def get_open_tariff(self, session: Any, hogar_id: UUID) -> TariffRow | None:
        self.db.calls.append(("open_tariff", hogar_id))
        opened = [t for t in self.db.tariffs.get(hogar_id, []) if t.vigente_hasta is None]
        assert len(opened) <= 1  # uq_tarifa_abierta_por_hogar
        return opened[0] if opened else None

    def close_tariff(
        self, session: Any, hogar_id: UUID, tarifa_id: UUID, vigente_hasta: date
    ) -> None:
        self.db.calls.append(("close_tariff", hogar_id, tarifa_id, vigente_hasta))
        if self.fail_close_tariff is not None:
            raise self.fail_close_tariff
        rows = self.db.tariffs.get(hogar_id, [])  # R-01: solo filas del hogar
        for index, tariff in enumerate(rows):
            if tariff.id == tarifa_id:
                if vigente_hasta <= tariff.vigente_desde:
                    raise TariffOverlapError(tariffs_data.RANGE_CONSTRAINT)
                rows[index] = replace(tariff, vigente_hasta=vigente_hasta)

    def insert_tariff(
        self, session: Any, *, hogar_id: UUID, operador: str | None, precio_kwh: float,
        cargo_fijo_mensual: float | None, vigente_desde: date,
    ) -> TariffRow:
        self.db.calls.append(("insert_tariff", hogar_id, operador, precio_kwh, cargo_fijo_mensual,
                              vigente_desde))
        if self.fail_insert_tariff is not None:
            raise self.fail_insert_tariff
        if isinstance(vigente_desde, datetime):
            raise TypeError("vigente_desde debe ser date")
        rows = self.db.tariffs.get(hogar_id, [])
        if any(t.vigente_hasta is None for t in rows):
            raise TariffOverlapError(tariffs_data.OPEN_TARIFF_INDEX)
        if any(t.vigente_hasta is None or t.vigente_hasta > vigente_desde for t in rows):
            raise TariffOverlapError(tariffs_data.OVERLAP_CONSTRAINT)
        tariff_id = self.add_tariff(
            hogar_id, precio_kwh, vigente_desde, operador=operador, cargo_fijo=cargo_fijo_mensual
        )
        (row,) = [t for t in self.db.tariffs[hogar_id] if t.id == tariff_id]
        return row


def _same_signature(real: Any, fake: Any) -> None:
    """El doble acepta los mismos parámetros que la función real (detecta cambios de firma)."""
    real_params = list(inspect.signature(real).parameters)
    fake_params = list(inspect.signature(fake).parameters)
    assert fake_params == real_params, (real.__name__, real_params, fake_params)


def install(monkeypatch: pytest.MonkeyPatch, spy_recovery: bool = True) -> GoalsTariffDatabase:
    base = install_fake_consumption_database(monkeypatch, spy_recovery=spy_recovery)
    fake = GoalsTariffDatabase(base)
    for module, names in (
        (households_data, ("lock_household", "get_household")),
        (memberships_data, ("get_user_membership_in_household",)),
        (goals_data, ("get_active_goal", "deactivate_active_goal", "insert_goal")),
        (tariffs_data, ("get_open_tariff", "close_tariff", "insert_tariff")),
    ):
        for name in names:
            _same_signature(getattr(module, name), getattr(fake, name))
            monkeypatch.setattr(module, name, getattr(fake, name))
    return fake


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> GoalsTariffDatabase:
    return install(monkeypatch)


def seed_zones(
    fake: GoalsTariffDatabase, values: dict[str, float], last: datetime = HOUR,
    hogar_id: UUID = HOGAR, first: datetime = WINDOW_START,
) -> dict[str, UUID]:
    ids = {}
    for tipo, value in values.items():
        ids[tipo] = fake.db.add_zone(hogar_id, tipo, tipo)
        fake.db.set_series(ids[tipo], hourly_series(lambda _m, v=value: v, first, last))
    return ids


def roundtrip(result: Any) -> Any:
    return type(result).model_validate_json(result.model_dump_json())


def _raises(status: int, codigo: CodigoError, call: Any, *args: Any, **kwargs: Any) -> ApiError:
    with pytest.raises(ApiError) as caught:
        call(*args, **kwargs)
    assert caught.value.status_code == status
    assert caught.value.codigo == codigo
    assert caught.value.mensaje
    return caught.value


# ================================================================== obtenerMeta
def test_get_goal_recovers_first_and_reads_counting_zones_from_the_window(
    fake: GoalsTariffDatabase,
) -> None:
    seed_zones(fake, {"cocina": 0.5, "sala": 0.25})
    session = FakeSession()

    result = roundtrip(service.get_goal(session, USER, HOGAR, True, NOW))

    assert isinstance(result, MetaVista)
    assert fake.db.calls[0] == ("recovery", HOGAR, NOW)
    assert fake.db.names().count("recovery") == 1
    (readings,) = [c for c in fake.db.calls if c[0] == "readings"]
    assert readings[3:] == (WINDOW_START, HOUR)
    assert session.commits == 0  # solo lectura (la recuperación hace su propio commit)


def test_get_goal_without_goal_has_null_goal_and_limit_but_shows_the_average(
    fake: GoalsTariffDatabase,
) -> None:
    seed_zones(fake, {"cocina": 0.5, "sala": 0.25})  # 0,75 kWh/h → 18 kWh/día

    result = roundtrip(service.get_goal(FakeSession(), USER, HOGAR, False, NOW))

    assert result.meta is None
    assert result.limite_diario_kwh is None
    assert result.promedio_diario_30d_kwh == pytest.approx(18.0)
    assert result.puede_editar is False


@pytest.mark.parametrize(
    ("now", "days"),
    [
        (NOW, 30),  # noviembre
        (datetime(2026, 12, 5, 9, tzinfo=TIMEZONE), 31),
        (datetime(2027, 2, 10, 9, tzinfo=TIMEZONE), 28),
        (datetime(2028, 2, 10, 9, tzinfo=TIMEZONE), 29),
        # 1/12 03:00 UTC sigue siendo el 30/11 en Bogotá: días de noviembre.
        (datetime(2026, 12, 1, 3, tzinfo=UTC), 30),
    ],
)
def test_get_goal_with_active_goal_daily_limit_uses_days_of_the_bogota_month(
    fake: GoalsTariffDatabase, now: datetime, days: int
) -> None:
    goal_id = fake.add_goal(HOGAR, 310.0, date(2026, 11, 1), tipo="presupuesto")

    result = roundtrip(service.get_goal(FakeSession(), USER, HOGAR, True, now))

    assert result.meta == Meta(
        id=goal_id, tipo="presupuesto", valor_kwh_mensual=310.0, estado="activa",
        fecha_inicio=date(2026, 11, 1), fecha_fin=None,
    )
    assert result.limite_diario_kwh == pytest.approx(310.0 / days)
    assert result.puede_editar is True


def test_get_goal_ignores_inactive_goals(fake: GoalsTariffDatabase) -> None:
    fake.add_goal(HOGAR, 200.0, date(2026, 10, 1), estado="inactiva", fecha_fin=date(2026, 11, 1))
    fake.add_goal(OTRO_HOGAR, 999.0, date(2026, 11, 1))

    result = service.get_goal(FakeSession(), USER, HOGAR, True, NOW)

    assert result.meta is None and result.limite_diario_kwh is None


def test_get_goal_average_is_null_with_less_than_seven_complete_days(
    fake: GoalsTariffDatabase,
) -> None:
    seed_zones(fake, {"cocina": 1.0}, first=datetime(2026, 11, 17, tzinfo=TIMEZONE))  # 6 días

    result = service.get_goal(FakeSession(), USER, HOGAR, True, NOW)

    assert result.promedio_diario_30d_kwh is None  # null = sin dato, nunca 0


def test_get_goal_average_with_exactly_seven_days(fake: GoalsTariffDatabase) -> None:
    seed_zones(fake, {"cocina": 1.0}, first=datetime(2026, 11, 16, tzinfo=TIMEZONE))

    result = service.get_goal(FakeSession(), USER, HOGAR, True, NOW)

    assert result.promedio_diario_30d_kwh == pytest.approx(24.0)


def test_get_goal_average_skips_incomplete_days_and_today(fake: GoalsTariffDatabase) -> None:
    """Un día al que le falta una hora no cuenta; las horas de hoy tampoco (día no terminado)."""
    ids = seed_zones(fake, {"cocina": 1.0})
    series = dict(fake.db.readings[ids["cocina"]])
    del series[datetime(2026, 11, 10, 3, tzinfo=TIMEZONE)]
    for hour in range(15):  # hoy con consumo muy alto: no debe contar
        series[datetime(2026, 11, 23, hour, tzinfo=TIMEZONE)] = 100.0
    fake.db.set_series(ids["cocina"], series)

    result = service.get_goal(FakeSession(), USER, HOGAR, True, NOW)

    assert result.promedio_diario_30d_kwh == pytest.approx(24.0)


def test_get_goal_average_uses_only_counting_zones(fake: GoalsTariffDatabase) -> None:
    ids = seed_zones(fake, {"cocina": 1.0})
    for tipo, estado, sensor in (("sala", "activa", "pausado"), ("oficina", "inactiva", "activo")):
        zona_id = fake.db.add_zone(HOGAR, tipo, tipo, estado, sensor)
        fake.db.set_series(zona_id, hourly_series(lambda _m: 50.0, WINDOW_START, HOUR))

    result = service.get_goal(FakeSession(), USER, HOGAR, True, NOW)

    assert result.promedio_diario_30d_kwh == pytest.approx(24.0)
    (readings,) = [c for c in fake.db.calls if c[0] == "readings"]
    assert readings[2] == (ids["cocina"],)


def test_get_goal_recovery_failure_answers_with_saved_data_and_warns(
    fake: GoalsTariffDatabase,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D6 + decisión de Nicolás: si la recuperación falla, la meta responde con lo guardado."""
    seed_zones(fake, {"cocina": 1.0}, last=YESTERDAY_END)
    fake.add_goal(HOGAR, 300.0, date(2026, 11, 1))

    def failing_recovery(session: Any, hogar_id: UUID, now: datetime | None = None) -> int:
        raise HourRecoveryError()

    monkeypatch.setattr(hour_recovery, "fill_missing_hours", failing_recovery)
    with caplog.at_level(logging.WARNING):
        result = roundtrip(service.get_goal(FakeSession(), USER, HOGAR, True, NOW))

    assert [r.getMessage() for r in caplog.records].count(RECOVERY_SKIPPED_MESSAGE) == 1
    assert str(HOGAR) not in caplog.text
    assert result.meta is not None
    assert result.promedio_diario_30d_kwh == pytest.approx(24.0)
    assert result.limite_diario_kwh == pytest.approx(10.0)


def test_get_goal_default_now_is_utc(fake: GoalsTariffDatabase) -> None:
    service.get_goal(FakeSession(), USER, HOGAR, True)
    assert fake.db.calls[0][2].utcoffset() == timedelta(0)


# ------------------------------------------------------------------ personalidades
def seed_personality(fake: GoalsTariffDatabase, personality: PersonalityAverages) -> UUID:
    """30 días + hoy hasta la hora evaluada con el promedio horario de cada zona (sin ruido)."""
    hogar_id = stable_id("hogar", "metas", personality.name)
    for zone in personality.zone_kwh_per_day:
        zona_id = fake.db.add_zone(hogar_id, zone, zone)
        fake.db.set_series(zona_id, hourly_series(
            lambda m, z=zone: personality.zone_kwh_for_hour(z, m.hour), WINDOW_START, HOUR
        ))
    return hogar_id


@each_personality
def test_personality_average_is_its_daily_kwh(
    fake: GoalsTariffDatabase, personality: PersonalityAverages
) -> None:
    hogar_id = seed_personality(fake, personality)

    result = roundtrip(service.get_goal(FakeSession(), USER, hogar_id, True, NOW))

    assert result.promedio_diario_30d_kwh == pytest.approx(personality.kwh_per_day)
    (readings,) = [c for c in fake.db.calls if c[0] == "readings"]
    assert len(readings[2]) == len(personality.zone_kwh_per_day)  # solo sus zonas


def test_personality_averages_follow_the_order(fake: GoalsTariffDatabase) -> None:
    averages = []
    for name in PERSONALITY_ORDER:
        hogar_id = seed_personality(fake, load_personalities()[name])
        result = service.get_goal(FakeSession(), USER, hogar_id, True, NOW)
        assert result.promedio_diario_30d_kwh is not None
        averages.append(result.promedio_diario_30d_kwh)
    assert averages == sorted(averages) and len(set(averages)) == len(averages)


def test_simulated_personality_averages_follow_the_order(fake: GoalsTariffDatabase) -> None:
    """Con el simulador (perfiles oficiales, humor, ruido y fin de semana), 30 días completos:
    compacto < eficiente < intermedio < familiar < amplio en `promedio_diario_30d_kwh`."""
    day = TODAY.toordinal()
    averages = []
    for name in PERSONALITY_ORDER:
        personality = load_personalities()[name]
        hogar_id = stable_id("hogar", "metas", "simulado", name)
        zone_ids = {
            zone: fake.db.add_zone(hogar_id, zone, zone) for zone in personality.zone_kwh_per_day
        }
        series = simulate_household(
            hogar_id, final_profiles()[name], zone_ids, (day - 30) * 24, day * 24
        )
        for zone, readings in series.items():
            fake.db.set_series(zone_ids[zone], {hour_from_index(r.index): r.total for r in readings})
        result = service.get_goal(FakeSession(), USER, hogar_id, True, NOW)
        assert result.promedio_diario_30d_kwh is not None
        averages.append(result.promedio_diario_30d_kwh)
    assert averages == sorted(averages) and len(set(averages)) == len(averages)


# ================================================================== crearMeta
def test_create_goal_without_previous_inserts_active_from_today_and_commits(
    fake: GoalsTariffDatabase,
) -> None:
    session = FakeSession()
    payload = MetaCrear.model_validate({"tipo": "ahorro", "valor_kwh_mensual": 250.5})

    result = roundtrip(service.create_goal(session, USER, HOGAR, payload, NOW))

    assert isinstance(result, Meta)
    assert result.tipo == "ahorro" and result.valor_kwh_mensual == 250.5
    assert result.estado == "activa" and result.fecha_inicio == TODAY and result.fecha_fin is None
    assert fake.db.names()[0] == "lock_household"
    assert "deactivate_goal" not in fake.db.names()
    assert "recovery" not in fake.db.names()  # guardar no depende de las lecturas
    assert session.commits == 1


def test_create_goal_closes_the_previous_with_the_new_start_date(
    fake: GoalsTariffDatabase,
) -> None:
    previous = fake.add_goal(HOGAR, 300.0, date(2026, 10, 2))
    session = FakeSession()
    payload = MetaCrear.model_validate({"tipo": "eficiencia", "valor_kwh_mensual": 280})

    result = service.create_goal(session, USER, HOGAR, payload, NOW)

    old = fake.goal(previous)
    assert old.estado == "inactiva" and old.fecha_fin == TODAY  # RN-XVI-04
    assert result.fecha_inicio == TODAY and result.estado == "activa"
    names = fake.db.names()
    assert names.index("lock_household") < names.index("goal")
    assert names.index("deactivate_goal") < names.index("insert_goal")
    assert session.commits == 1
    # La vista ya muestra la nueva.
    view = service.get_goal(FakeSession(), USER, HOGAR, True, NOW)
    assert view.meta is not None and view.meta.id == result.id


def test_create_goal_same_day_leaves_the_previous_inactive_with_null_end(
    fake: GoalsTariffDatabase,
) -> None:
    """D3: la anterior empezó hoy → `fecha_fin` null (metas_rango_valido exige fin > inicio)."""
    previous = fake.add_goal(HOGAR, 300.0, TODAY)

    service.create_goal(
        FakeSession(), USER, HOGAR,
        MetaCrear.model_validate({"tipo": "ahorro", "valor_kwh_mensual": 200}), NOW,
    )

    old = fake.goal(previous)
    assert old.estado == "inactiva" and old.fecha_fin is None
    assert ("deactivate_goal", HOGAR, None) in fake.db.calls


def test_create_goal_uses_the_bogota_date(fake: GoalsTariffDatabase) -> None:
    late = datetime(2026, 12, 1, 3, 30, tzinfo=UTC)  # 30/11 22:30 en Bogotá
    result = service.create_goal(
        FakeSession(), USER, HOGAR,
        MetaCrear.model_validate({"tipo": "ahorro", "valor_kwh_mensual": 200}), late,
    )
    assert result.fecha_inicio == date(2026, 11, 30)


def test_create_goal_unique_violation_propagates_without_commit(
    fake: GoalsTariffDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    def insert_goal(*_args: Any, **_kwargs: Any) -> Any:
        raise ActiveGoalExistsError("El hogar ya tiene una meta activa.")

    monkeypatch.setattr(goals_data, "insert_goal", insert_goal)
    session = FakeSession()

    with pytest.raises(ActiveGoalExistsError):
        service.create_goal(
            session, USER, HOGAR,
            MetaCrear.model_validate({"tipo": "ahorro", "valor_kwh_mensual": 200}), NOW,
        )
    assert session.commits == 0


def test_create_goal_naive_now_is_rejected_before_locking(fake: GoalsTariffDatabase) -> None:
    with pytest.raises(ValueError):
        service.create_goal(
            FakeSession(), USER, HOGAR,
            MetaCrear.model_validate({"tipo": "ahorro", "valor_kwh_mensual": 200}),
            NOW.replace(tzinfo=None),
        )
    assert fake.db.calls == []


# ================================================================== obtenerTarifa
def test_get_tariff_returns_the_one_in_force_today_without_recovery_or_commit(
    fake: GoalsTariffDatabase,
) -> None:
    fake.add_tariff(HOGAR, 700.0, date(2026, 10, 1), date(2026, 11, 1))
    current = fake.add_tariff(HOGAR, 820.5, date(2026, 11, 1), operador="Celsia", cargo_fijo=9000)
    session = FakeSession()

    result = roundtrip(service.get_tariff(session, USER, HOGAR, True, NOW))

    assert isinstance(result, TarifaVista)
    assert result.tarifa == Tarifa(
        id=current, operador="Celsia", precio_kwh=820.5, cargo_fijo_mensual=9000,
        vigente_desde=date(2026, 11, 1), vigente_hasta=None,
    )
    assert result.puede_editar is True
    assert ("tariff", HOGAR, TODAY) in fake.db.calls
    assert "recovery" not in fake.db.names()
    assert session.commits == 0


def test_get_tariff_future_one_does_not_apply_yet_and_bogota_date_is_used(
    fake: GoalsTariffDatabase,
) -> None:
    november = fake.add_tariff(HOGAR, 700.0, date(2026, 11, 1), date(2026, 12, 1))
    fake.add_tariff(HOGAR, 900.0, date(2026, 12, 1))
    late = datetime(2026, 12, 1, 3, 0, tzinfo=UTC)  # 30/11 en Bogotá

    result = service.get_tariff(FakeSession(), USER, HOGAR, False, late)

    assert result.tarifa is not None and result.tarifa.id == november
    assert result.puede_editar is False


def test_get_tariff_without_tariff_is_null(fake: GoalsTariffDatabase) -> None:
    fake.add_tariff(OTRO_HOGAR, 700.0, date(2026, 1, 1))
    result = roundtrip(service.get_tariff(FakeSession(), USER, HOGAR, False, NOW))
    assert result.tarifa is None
    assert result.puede_editar is False


# ================================================================== crearTarifa
def _tariff_payload(**values: Any) -> TarifaCrear:
    body: dict[str, Any] = {"precio_kwh": 850.0, "vigente_desde": "2026-11"}  # mes actual
    body.update(values)
    return TarifaCrear.model_validate(body)


def test_create_first_tariff_saves_day_one_open_and_commits(fake: GoalsTariffDatabase) -> None:
    session = FakeSession()

    result = roundtrip(service.create_tariff(
        session, USER, HOGAR, _tariff_payload(operador="EPM", cargo_fijo_mensual=12000.0), NOW
    ))

    assert isinstance(result, Tarifa)
    assert result.vigente_desde == date(2026, 11, 1) and result.vigente_hasta is None
    assert result.operador == "EPM" and result.cargo_fijo_mensual == 12000.0
    assert result.precio_kwh == 850.0
    names = fake.db.names()
    assert fake.db.calls[:2] == [
        ("lock_household", HOGAR),
        ("membership", HOGAR, USER, True),  # se vuelve a comprobar bajo el bloqueo
    ]
    assert "close_tariff" not in names
    assert "recovery" not in names
    assert session.commits == 1


def test_create_tariff_without_optional_fields(fake: GoalsTariffDatabase) -> None:
    result = service.create_tariff(FakeSession(), USER, HOGAR, _tariff_payload(), NOW)
    assert result.operador is None and result.cargo_fijo_mensual is None


def test_create_tariff_closes_the_open_one_with_the_new_start(fake: GoalsTariffDatabase) -> None:
    old = fake.add_tariff(HOGAR, 700.0, date(2026, 3, 1))
    session = FakeSession()

    result = service.create_tariff(session, USER, HOGAR, _tariff_payload(), NOW)

    old_row, new_row = fake.tariffs_of(HOGAR)
    assert old_row.id == old and old_row.vigente_hasta == date(2026, 11, 1)  # fin excluido
    assert new_row.id == result.id and new_row.vigente_hasta is None
    assert ("close_tariff", HOGAR, old, date(2026, 11, 1)) in fake.db.calls
    names = fake.db.names()
    assert names.index("lock_household") < names.index("membership")
    assert names.index("membership") < names.index("open_tariff")
    assert names.index("close_tariff") < names.index("insert_tariff")
    assert session.commits == 1
    # Desde el 1 de noviembre aplica la nueva; el 31 de octubre, la anterior (RN-V-01, DC-39).
    assert service.get_tariff(FakeSession(), USER, HOGAR, True, NOW).tarifa.id == result.id  # type: ignore[union-attr]
    october = datetime(2026, 10, 31, 23, 59, tzinfo=TIMEZONE)
    assert service.get_tariff(FakeSession(), USER, HOGAR, True, october).tarifa.id == old  # type: ignore[union-attr]


def test_create_tariff_in_a_past_month_after_the_open_one_is_allowed(
    fake: GoalsTariffDatabase,
) -> None:
    fake.add_tariff(HOGAR, 700.0, date(2026, 3, 1))
    result = service.create_tariff(
        FakeSession(), USER, HOGAR, _tariff_payload(vigente_desde="2026-09"), NOW
    )
    assert result.vigente_desde == date(2026, 9, 1)


@pytest.mark.parametrize("vigente_desde", ["2026-11", "2026-10", "2025-12"])
def test_create_tariff_not_later_than_the_open_one_is_422(
    fake: GoalsTariffDatabase, vigente_desde: str
) -> None:
    fake.add_tariff(HOGAR, 700.0, date(2026, 11, 1))
    session = FakeSession()

    error = _raises(
        422, CodigoError.VIGENCIA_NO_POSTERIOR, service.create_tariff,
        session, USER, HOGAR, _tariff_payload(vigente_desde=vigente_desde), NOW,
    )

    assert error.detalles == {"vigente_desde": "2026-11-01"}
    names = fake.db.names()
    assert "close_tariff" not in names and "insert_tariff" not in names
    assert session.commits == 0
    assert len(fake.tariffs_of(HOGAR)) == 1


def test_create_tariff_compares_only_with_the_open_one(fake: GoalsTariffDatabase) -> None:
    """D4: la «vigente» para comparar es la abierta, aunque hoy aplique otra cerrada. (Con la
    regla de 0.2.10 la API ya no crea abiertas futuras; la fila se fabrica para probar D4.)"""
    fake.add_tariff(HOGAR, 600.0, date(2026, 1, 1), date(2027, 1, 1))
    fake.add_tariff(HOGAR, 900.0, date(2027, 1, 1))  # abierta, empieza en el futuro

    error = _raises(
        422, CodigoError.VIGENCIA_NO_POSTERIOR, service.create_tariff,
        FakeSession(), USER, HOGAR, _tariff_payload(vigente_desde="2026-11"), NOW,
    )
    assert error.detalles == {"vigente_desde": "2027-01-01"}


@pytest.mark.parametrize("constraint", sorted(tariffs_data.VALIDITY_CONSTRAINTS))
def test_create_tariff_constraint_violation_on_insert_is_422_without_commit(
    fake: GoalsTariffDatabase, constraint: str
) -> None:
    """Carrera u otro choque de vigencias en la base → 422 VIGENCIA_NO_POSTERIOR, sin commit."""
    fake.add_tariff(HOGAR, 700.0, date(2026, 3, 1))
    fake.fail_insert_tariff = TariffOverlapError(constraint)
    session = FakeSession()

    error = _raises(
        422, CodigoError.VIGENCIA_NO_POSTERIOR, service.create_tariff,
        session, USER, HOGAR, _tariff_payload(), NOW,
    )

    assert error.detalles == {"vigente_desde": "2026-03-01"}
    assert session.commits == 0


def test_create_tariff_violation_without_open_tariff_has_no_details(
    fake: GoalsTariffDatabase,
) -> None:
    fake.fail_insert_tariff = TariffOverlapError(tariffs_data.OVERLAP_CONSTRAINT)
    session = FakeSession()

    error = _raises(
        422, CodigoError.VIGENCIA_NO_POSTERIOR, service.create_tariff,
        session, USER, HOGAR, _tariff_payload(), NOW,
    )

    assert error.detalles is None
    assert session.commits == 0


def test_create_tariff_violation_when_closing_is_422_without_insert(
    fake: GoalsTariffDatabase,
) -> None:
    fake.add_tariff(HOGAR, 700.0, date(2026, 3, 1))
    fake.fail_close_tariff = TariffOverlapError(tariffs_data.RANGE_CONSTRAINT)
    session = FakeSession()

    _raises(
        422, CodigoError.VIGENCIA_NO_POSTERIOR, service.create_tariff,
        session, USER, HOGAR, _tariff_payload(), NOW,
    )

    assert "insert_tariff" not in fake.db.names()
    assert session.commits == 0


def test_create_tariff_year_zero_is_422_validation_before_locking(
    fake: GoalsTariffDatabase,
) -> None:
    """El patrón del contrato acepta «0000-01», pero no es una fecha válida."""
    error = _raises(
        422, CodigoError.VALIDACION, service.create_tariff,
        FakeSession(), USER, HOGAR, _tariff_payload(vigente_desde="0000-01"), NOW,
    )
    assert error.detalles == {
        "campos": [{"ubicacion": ["body", "vigente_desde"], "mensaje": "Mes y año no válidos."}]
    }
    assert fake.db.calls == []


def test_create_tariff_does_not_touch_other_households(fake: GoalsTariffDatabase) -> None:
    other = fake.add_tariff(OTRO_HOGAR, 700.0, date(2026, 3, 1))

    service.create_tariff(FakeSession(), USER, HOGAR, _tariff_payload(), NOW)

    (row,) = fake.tariffs_of(OTRO_HOGAR)
    assert row.id == other and row.vigente_hasta is None


# ------------------------------------------------------------------ crearTarifa · meses futuros
@pytest.mark.parametrize("vigente_desde", ["2026-12", "2027-01", "2030-06"])
def test_create_tariff_future_month_is_422_validation_without_touching_the_base(
    fake: GoalsTariffDatabase, vigente_desde: str
) -> None:
    """Contrato 0.2.10: un `vigente_desde` posterior al mes actual de Bogotá → 422 VALIDACION."""
    fake.add_tariff(HOGAR, 700.0, date(2026, 3, 1))
    session = FakeSession()

    error = _raises(
        422, CodigoError.VALIDACION, service.create_tariff,
        session, USER, HOGAR, _tariff_payload(vigente_desde=vigente_desde), NOW,
    )

    assert error.detalles == {
        "campos": [{"ubicacion": ["body", "vigente_desde"], "mensaje": "No se aceptan meses futuros."}]
    }
    assert fake.db.calls == []  # ni bloqueo ni lecturas
    assert session.commits == 0


def test_create_tariff_current_month_is_accepted(fake: GoalsTariffDatabase) -> None:
    first_day = datetime(2026, 11, 1, 0, 0, tzinfo=TIMEZONE)  # primer instante del mes
    result = service.create_tariff(
        FakeSession(), USER, HOGAR, _tariff_payload(vigente_desde="2026-11"), first_day
    )
    assert result.vigente_desde == date(2026, 11, 1)


def test_create_tariff_future_month_uses_the_bogota_month_not_the_utc_month(
    fake: GoalsTariffDatabase,
) -> None:
    """1/12 02:00 UTC = 30/11 21:00 en Bogotá: «2026-12» todavía es futuro; «2026-11» no."""
    crossing = datetime(2026, 12, 1, 2, 0, tzinfo=UTC)

    _raises(
        422, CodigoError.VALIDACION, service.create_tariff,
        FakeSession(), USER, HOGAR, _tariff_payload(vigente_desde="2026-12"), crossing,
    )
    result = service.create_tariff(
        FakeSession(), USER, HOGAR, _tariff_payload(vigente_desde="2026-11"), crossing
    )
    assert result.vigente_desde == date(2026, 11, 1)


def test_create_tariff_naive_now_is_rejected_before_locking(fake: GoalsTariffDatabase) -> None:
    with pytest.raises(ValueError):
        service.create_tariff(
            FakeSession(), USER, HOGAR, _tariff_payload(), NOW.replace(tzinfo=None)
        )
    assert fake.db.calls == []


# ------------------------------------------------------------------ comprobación bajo bloqueo
GOAL_PAYLOAD = MetaCrear.model_validate({"tipo": "ahorro", "valor_kwh_mensual": 200})
MEMBER = stable_id("usuario", "metas", "miembro")


def test_create_goal_member_with_modify_goals_permission_can_save(
    fake: GoalsTariffDatabase,
) -> None:
    fake.roles[HOGAR, MEMBER] = "miembro"
    fake.modify_goals[HOGAR] = True
    session = FakeSession()

    result = service.create_goal(session, MEMBER, HOGAR, GOAL_PAYLOAD, NOW)

    assert result.estado == "activa"
    names = fake.db.names()
    assert names[:3] == ["lock_household", "membership", "household"]
    assert fake.db.calls[1] == ("membership", HOGAR, MEMBER, True)
    assert session.commits == 1


def test_create_goal_admin_does_not_need_the_permission(fake: GoalsTariffDatabase) -> None:
    fake.modify_goals[HOGAR] = False
    service.create_goal(FakeSession(), USER, HOGAR, GOAL_PAYLOAD, NOW)
    assert "household" not in fake.db.names()


def test_create_goal_permission_revoked_before_the_lock_is_403(
    fake: GoalsTariffDatabase,
) -> None:
    """El guardia vio el permiso; otra transacción lo quitó y confirmó mientras se esperaba el
    bloqueo del hogar → 403 SIN_PERMISO_MODIFICAR_METAS, sin escribir ni confirmar."""
    fake.roles[HOGAR, MEMBER] = "miembro"
    fake.modify_goals[HOGAR] = True
    fake.add_goal(HOGAR, 300.0, date(2026, 10, 1))

    def revoke() -> None:
        fake.modify_goals[HOGAR] = False

    fake.after_lock = revoke
    session = FakeSession()

    _raises(
        403, CodigoError.SIN_PERMISO_MODIFICAR_METAS, service.create_goal,
        session, MEMBER, HOGAR, GOAL_PAYLOAD, NOW,
    )

    names = fake.db.names()
    assert "deactivate_goal" not in names and "insert_goal" not in names
    assert session.commits == 0
    assert [g.row.estado for g in fake.goals] == ["activa"]


def test_create_goal_member_who_left_before_the_lock_is_404(fake: GoalsTariffDatabase) -> None:
    fake.roles[HOGAR, MEMBER] = "miembro"
    fake.modify_goals[HOGAR] = True

    def leave() -> None:
        del fake.roles[HOGAR, MEMBER]

    fake.after_lock = leave
    session = FakeSession()

    _raises(404, CodigoError.NO_ENCONTRADO, service.create_goal, session, MEMBER, HOGAR,
            GOAL_PAYLOAD, NOW)
    assert "insert_goal" not in fake.db.names()
    assert session.commits == 0


def test_create_tariff_admin_transferred_before_the_lock_is_403(
    fake: GoalsTariffDatabase,
) -> None:
    """Transferencia de la administración confirmada mientras se esperaba el bloqueo → 403
    NO_ES_ADMINISTRADOR, sin leer ni escribir tarifas."""
    def transfer() -> None:
        fake.roles[HOGAR, USER] = "miembro"

    fake.after_lock = transfer
    session = FakeSession()

    _raises(
        403, CodigoError.NO_ES_ADMINISTRADOR, service.create_tariff,
        session, USER, HOGAR, _tariff_payload(), NOW,
    )

    names = fake.db.names()
    assert "open_tariff" not in names and "insert_tariff" not in names
    assert session.commits == 0


def test_create_tariff_member_with_modify_goals_is_still_403(fake: GoalsTariffDatabase) -> None:
    """La tarifa es solo del administrador (RN-XVI-05): el permiso de metas no basta."""
    fake.roles[HOGAR, MEMBER] = "miembro"
    fake.modify_goals[HOGAR] = True

    _raises(
        403, CodigoError.NO_ES_ADMINISTRADOR, service.create_tariff,
        FakeSession(), MEMBER, HOGAR, _tariff_payload(), NOW,
    )


def test_create_tariff_without_active_membership_is_404(fake: GoalsTariffDatabase) -> None:
    session = FakeSession()

    _raises(
        404, CodigoError.NO_ENCONTRADO, service.create_tariff,
        session, MEMBER, HOGAR, _tariff_payload(), NOW,
    )
    assert "insert_tariff" not in fake.db.names()
    assert session.commits == 0
