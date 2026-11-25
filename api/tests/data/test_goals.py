"""Pruebas de app.data.goals sin base real (RN-V-03, RN-XVI-04, RN-XI-03, R-01).

El límite mensual de la meta es el consumo mensual de referencia de una personalidad real
(tests/helpers). Que el único parcial impida dos metas activas necesita Postgres.
"""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.sql.elements import TextClause

from app.data import goals
from app.data.goals import ActiveGoalRow, get_active_goal, get_goal_active_on
from tests.data.fake_session import FakeSession, assert_bound_only, normalized_sql
from tests.helpers.personalities import load_personalities

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
