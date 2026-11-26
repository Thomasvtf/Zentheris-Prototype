"""Pruebas de app.data.goals sin base real (RN-V-03, RN-XVI-04, RN-XI-03, R-01).

El límite mensual de la meta es el consumo mensual de referencia de una personalidad real
(tests/helpers). Que el único parcial impida dos metas activas necesita Postgres; aquí se
comprueba su traducción a ActiveGoalExistsError (DC-41).
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import TextClause

from app.data import goals
from app.data.goals import (
    ActiveGoalExistsError,
    ActiveGoalRow,
    GoalRow,
    deactivate_active_goal,
    get_active_goal,
    get_goal_active_on,
    insert_goal,
)
from tests.data.fake_session import (
    FakeDiag,
    FakeDriverError,
    FakeResult,
    FakeSession,
    assert_bound_only,
    integrity_error,
    normalized_sql,
)
from tests.helpers.personalities import PERSONALITY_ORDER, load_personalities

MONTHLY_KWH = Decimal(str(load_personalities()["Consumo familiar"].kwh_per_month))
START = date(2026, 11, 1)


def _goal_row(**overrides: Any) -> dict[str, Any]:
    """Fila como la entregaría psycopg2: numeric como Decimal y date como date."""
    row: dict[str, Any] = {
        "id": uuid4(),
        "tipo": "ahorro",
        "valor_kwh_mensual": MONTHLY_KWH,
        "fecha_inicio": START,
    }
    row.update(overrides)
    return row


def test_active_goal_sends_only_the_household_as_parameter() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert get_active_goal(session, hogar_id) is None  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is goals.ACTIVE_GOAL_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)


def test_active_goal_sql_filters_by_household_and_active_state() -> None:
    """RN-V-03, RN-XVI-04: solo la meta 'activa' (la que cubre uq_meta_activa_por_hogar)."""
    assert normalized_sql(goals.ACTIVE_GOAL_SQL) == (
        "select id, tipo, valor_kwh_mensual, fecha_inicio "
        "from metas_consumo "
        "where hogar_id = :hogar_id and estado = 'activa'"
    )


def test_active_goal_maps_numeric_to_float_and_id_to_uuid() -> None:
    goal_id = uuid4()
    session = FakeSession([_goal_row(id=str(goal_id), tipo="presupuesto")])

    goal = get_active_goal(session, uuid4())  # type: ignore[arg-type]

    assert goal == ActiveGoalRow(
        id=goal_id,
        tipo="presupuesto",
        valor_kwh_mensual=float(MONTHLY_KWH),
        fecha_inicio=START,
    )
    assert isinstance(goal.id, UUID)
    assert type(goal.valor_kwh_mensual) is float


def test_active_goal_keeps_a_uuid_id() -> None:
    goal_id = uuid4()
    session = FakeSession([_goal_row(id=goal_id, tipo="eficiencia")])

    goal = get_active_goal(session, uuid4())  # type: ignore[arg-type]

    assert goal is not None
    assert goal.id == goal_id
    assert goal.tipo == "eficiencia"


def test_no_active_goal_returns_none() -> None:
    """Sin meta activa el servicio compara contra el promedio (RN-XI-03)."""
    session = FakeSession([])

    assert get_active_goal(session, uuid4()) is None  # type: ignore[arg-type]


def test_active_goal_does_not_commit_and_has_no_python_formatting() -> None:
    session = FakeSession([_goal_row()])

    get_active_goal(session, uuid4())  # type: ignore[arg-type]

    assert session.commits == 0
    sql = str(goals.ACTIVE_GOAL_SQL)
    assert "{" not in sql
    assert "%" not in sql


# ------------------------------------------------------------------ meta vigente un día (DC-32, RN-XIV-07)

MONTH_LAST_DAY = date(2026, 10, 31)


def test_goal_active_on_binds_household_and_day() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert get_goal_active_on(session, hogar_id, MONTH_LAST_DAY) is None  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is goals.GOAL_ACTIVE_ON_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id, "day": MONTH_LAST_DAY}
    assert_bound_only(statement, params)
    assert session.commits == 0


def test_goal_active_on_sql_uses_the_validity_range_and_not_the_state() -> None:
    """DC-32 y RN-XIV-07 (cierre de mes): [fecha_inicio, fecha_fin) contiene el día; la meta pudo cerrarse después."""
    sql = normalized_sql(goals.GOAL_ACTIVE_ON_SQL)
    assert "where hogar_id = :hogar_id" in sql
    assert "fecha_inicio <= :day" in sql
    assert "(fecha_fin is null or fecha_fin > :day)" in sql
    assert "estado" not in sql
    assert sql.endswith("order by fecha_inicio desc, created_at desc, id desc limit 1")


def test_goal_active_on_maps_the_row() -> None:
    goal_id = uuid4()
    session = FakeSession([_goal_row(id=str(goal_id))])

    goal = get_goal_active_on(session, uuid4(), MONTH_LAST_DAY)  # type: ignore[arg-type]

    assert goal == ActiveGoalRow(
        id=goal_id, tipo="ahorro", valor_kwh_mensual=float(MONTHLY_KWH), fecha_inicio=START
    )
    assert type(goal.valor_kwh_mensual) is float


# ------------------------------------------------------------------ guardar meta (RN-V-03, RN-XVI-04)

NEW_START = date(2026, 11, 26)


def test_deactivate_active_goal_binds_household_and_end_and_returns_rowcount() -> None:
    hogar_id = uuid4()
    session = FakeSession(FakeResult(rowcount=1))

    assert deactivate_active_goal(session, hogar_id, NEW_START) == 1  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is goals.DEACTIVATE_ACTIVE_GOAL_SQL
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id, "fecha_fin": NEW_START}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "update metas_consumo set estado = 'inactiva', fecha_fin = :fecha_fin, "
        "updated_at = now() where hogar_id = :hogar_id and estado = 'activa'"
    )
    assert session.commits == 0


def test_deactivate_active_goal_without_active_goal_returns_zero() -> None:
    session = FakeSession(FakeResult(rowcount=0))

    assert deactivate_active_goal(session, uuid4(), NEW_START) == 0  # type: ignore[arg-type]


def test_deactivate_active_goal_same_day_sends_a_null_end() -> None:
    """D3: si la anterior empezó el mismo día, fecha_fin NULL (metas_rango_valido)."""
    session = FakeSession(FakeResult(rowcount=1))

    deactivate_active_goal(session, uuid4(), None)  # type: ignore[arg-type]

    params = session.calls[0][1]
    assert params is not None
    assert params["fecha_fin"] is None


def test_deactivate_active_goal_rejects_a_datetime_without_sql() -> None:
    session = FakeSession()

    with pytest.raises(TypeError, match="date"):
        deactivate_active_goal(session, uuid4(), datetime(2026, 11, 26, tzinfo=UTC))  # type: ignore[arg-type]

    assert session.calls == []


def _stored_goal(**overrides: Any) -> dict[str, Any]:
    row = _goal_row(fecha_inicio=NEW_START, estado="activa", fecha_fin=None)
    row.update(overrides)
    return row


def _insert(session: FakeSession, **overrides: Any) -> GoalRow:
    kwargs: dict[str, Any] = {
        "hogar_id": uuid4(),
        "tipo": "ahorro",
        "valor_kwh_mensual": float(MONTHLY_KWH),
        "fecha_inicio": NEW_START,
    }
    kwargs.update(overrides)
    return insert_goal(session, **kwargs)  # type: ignore[arg-type]


def test_insert_goal_sql_params_and_mapping() -> None:
    hogar_id, goal_id = uuid4(), uuid4()
    session = FakeSession([_stored_goal(id=str(goal_id), tipo="presupuesto")])

    goal = _insert(session, hogar_id=hogar_id, tipo="presupuesto")

    statement, params = session.calls[0]
    assert statement is goals.INSERT_GOAL_SQL
    assert params == {
        "hogar_id": hogar_id,
        "tipo": "presupuesto",
        "valor_kwh_mensual": float(MONTHLY_KWH),
        "fecha_inicio": NEW_START,
    }
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "insert into metas_consumo "
        "(hogar_id, tipo, valor_kwh_mensual, estado, fecha_inicio, fecha_fin) "
        "values (:hogar_id, :tipo, :valor_kwh_mensual, 'activa', :fecha_inicio, null) "
        "returning id, tipo, valor_kwh_mensual, estado, fecha_inicio, fecha_fin"
    )
    assert goal == GoalRow(
        id=goal_id,
        tipo="presupuesto",
        valor_kwh_mensual=float(MONTHLY_KWH),
        estado="activa",
        fecha_inicio=NEW_START,
        fecha_fin=None,
    )
    assert isinstance(goal.id, UUID)
    assert type(goal.valor_kwh_mensual) is float
    assert session.commits == 0


@pytest.mark.parametrize("name", PERSONALITY_ORDER)
def test_insert_goal_maps_each_personality_monthly_reference(name: str) -> None:
    """El límite mensual de cada personalidad (Decimal en la fila) vuelve como float."""
    monthly = Decimal(str(load_personalities()[name].kwh_per_month))
    session = FakeSession([_stored_goal(valor_kwh_mensual=monthly)])

    goal = _insert(session, valor_kwh_mensual=float(monthly))

    assert goal.valor_kwh_mensual == float(monthly)
    assert type(goal.valor_kwh_mensual) is float


def test_insert_goal_rejects_a_datetime_without_sql() -> None:
    session = FakeSession()

    with pytest.raises(TypeError, match="date"):
        _insert(session, fecha_inicio=datetime(2026, 11, 26, tzinfo=UTC))

    assert session.calls == []


ACTIVE_INDEX_MESSAGE = (
    'duplicate key value violates unique constraint "uq_meta_activa_por_hogar"\n'
    "DETAIL: Key (hogar_id)=(x) already exists."
)


@pytest.mark.parametrize(
    "orig",
    [
        FakeDriverError("23505", diag=FakeDiag("uq_meta_activa_por_hogar")),
        FakeDriverError("23505", message=ACTIVE_INDEX_MESSAGE),
        FakeDriverError("23505", message=ACTIVE_INDEX_MESSAGE, diag=FakeDiag(None)),
    ],
    ids=["diag", "sin diag", "diag sin nombre"],
)
def test_insert_goal_raises_active_goal_exists(orig: Exception) -> None:
    """DC-41: el único parcial cierra la carrera entre dos metas activas."""
    session = FakeSession(integrity_error(orig))

    with pytest.raises(ActiveGoalExistsError) as exc_info:
        _insert(session)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert not isinstance(exc_info.value, IntegrityError)


@pytest.mark.parametrize(
    "orig",
    [
        FakeDriverError("23514", diag=FakeDiag("metas_consumo_valor_kwh_mensual_check")),
        FakeDriverError("23514", diag=FakeDiag("metas_rango_valido")),
        FakeDriverError("23503", diag=FakeDiag("metas_consumo_hogar_id_fkey")),
        FakeDriverError("23503", message=ACTIVE_INDEX_MESSAGE),
        FakeDriverError("23505", message=ACTIVE_INDEX_MESSAGE, diag=FakeDiag("otro_unico")),
        FakeDriverError("23505"),
        FakeDriverError(None),
    ],
    ids=[
        "check del valor",
        "rango",
        "FK",
        "otro SQLSTATE",
        "diag manda",
        "sin nombre",
        "sin SQLSTATE",
    ],
)
def test_insert_goal_reraises_any_other_integrity_error(orig: Exception) -> None:
    error = integrity_error(orig)
    session = FakeSession(error)

    with pytest.raises(IntegrityError) as exc_info:
        _insert(session)

    assert exc_info.value is error


def test_active_goal_index_name_matches_the_migration() -> None:
    migrations = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
    (migration,) = migrations.glob("*_0003_*.sql")

    expected = (
        f"create unique index {goals.ACTIVE_GOAL_INDEX}\n"
        "  on public.metas_consumo (hogar_id) where estado = 'activa';"
    )
    assert expected in migration.read_text(encoding="utf-8")
