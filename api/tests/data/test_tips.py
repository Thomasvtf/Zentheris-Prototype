"""Pruebas de app.data.tips sin base real (RN-XV-03/04/05/06, DC-24, RN-VI-03, R-01).

Se comprueba el SQL generado (filtro por hogar y persona, DISTINCT ON, ON CONFLICT, orden), que
los valores viajan como parámetros y la conversión de filas. El orden real de las filas y los
checks de la tabla necesitan Postgres (tests/integrity).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from app.data import tips
from app.data.tips import (
    TipHistoryRow,
    UserTipRow,
    get_user_tip,
    insert_tip,
    insert_tip_assignments,
    list_latest_tips,
    list_user_tips,
    update_user_tip_status,
)
from tests.data.fake_session import FakeResult, FakeSession, assert_bound_only, normalized_sql

NOW = datetime(2026, 11, 24, 15, 0, tzinfo=UTC)
EVENT_AT = datetime(2026, 11, 24, 14, 0, tzinfo=UTC)
WEEK_AGO = NOW - timedelta(days=7)
NAIVE = EVENT_AT.replace(tzinfo=None)

ALL_STATEMENTS = (
    tips.LATEST_TIPS_SQL,
    tips.INSERT_TIP_SQL,
    tips.INSERT_TIP_ASSIGNMENTS_SQL,
    tips.USER_TIPS_SQL,
    tips.USER_TIP_SQL,
    tips.UPDATE_USER_TIP_STATUS_SQL,
)


def _tip_row(**overrides: Any) -> dict[str, Any]:
    """Fila como la entregaría psycopg2 (ids UUID, fechas con zona horaria)."""
    row: dict[str, Any] = {
        "id": uuid4(),
        "categoria": "zona",
        "prioridad": "alta",
        "titulo": "Título resuelto",
        "descripcion": "Descripción resuelta",
        "zona_id": uuid4(),
        "zona_tipo": "lavanderia",
        "estado": "pendiente",
        "completada_en": None,
        "created_at": EVENT_AT,
    }
    row.update(overrides)
    return row


def _insert_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "hogar_id": uuid4(),
        "categoria": "zona",
        "prioridad": "media",
        "zona_id": uuid4(),
        "titulo": "Título del catálogo",
        "descripcion": "Descripción del catálogo",
        "regla_origen": "zona_elevada",
        "created_at": EVENT_AT,
    }
    kwargs.update(overrides)
    return kwargs


@pytest.mark.parametrize("statement", ALL_STATEMENTS)
def test_every_statement_is_constant_and_filters_by_household(statement: TextClause) -> None:
    """R-01: cada sentencia es texto constante y está atada al hogar."""
    assert isinstance(statement, TextClause)
    sql = normalized_sql(statement)
    assert "{" not in sql
    assert "%" not in sql
    assert "hogar_id" in sql


# ------------------------------------------------------------------ list_latest_tips


def test_latest_tips_bind_only_the_household() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert list_latest_tips(session, hogar_id) == []  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is tips.LATEST_TIPS_SQL
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    assert session.commits == 0


def test_latest_tips_sql_keeps_the_newest_per_rule_and_zone() -> None:
    """RN-XV-05, DC-24 (variante alterna; la anterior se reconoce por su título): DISTINCT ON (regla_origen, zona_id) con created_at desc, id desc."""
    sql = normalized_sql(tips.LATEST_TIPS_SQL)
    assert sql.startswith("select distinct on (regla_origen, zona_id)")
    assert "from consejos where hogar_id = :hogar_id" in sql
    assert sql.endswith("order by regla_origen, zona_id, created_at desc, id desc")


def test_latest_tips_map_rows_with_and_without_zone() -> None:
    zone_id = uuid4()
    session = FakeSession(
        [
            {
                "regla_origen": "cierre_mes_encima",
                "zona_id": None,
                "titulo": "T1",
                "created_at": EVENT_AT,
            },
            {
                "regla_origen": "zona_critica",
                "zona_id": str(zone_id),
                "titulo": "T2",
                "created_at": EVENT_AT,
            },
        ]
    )

    rows = list_latest_tips(session, uuid4())  # type: ignore[arg-type]

    assert rows == [
        TipHistoryRow("cierre_mes_encima", None, "T1", EVENT_AT),
        TipHistoryRow("zona_critica", zone_id, "T2", EVENT_AT),
    ]
    assert isinstance(rows[1].zona_id, UUID)


# ------------------------------------------------------------------ insert_tip


def test_insert_tip_returns_the_id_and_binds_every_value() -> None:
    # Consejo general: el valor «zona» de la categoría también es una palabra del SQL (zonas).
    tip_id = uuid4()
    kwargs = _insert_kwargs(
        categoria="general", prioridad="baja", zona_id=None, regla_origen="cierre_mes_encima"
    )
    session = FakeSession([{"id": str(tip_id)}])

    assert insert_tip(session, **kwargs) == tip_id  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is tips.INSERT_TIP_SQL
    assert params == kwargs
    assert_bound_only(statement, params)
    assert session.commits == 0


def test_insert_tip_sql_stamps_both_dates_and_checks_the_zone() -> None:
    """I-01 y created_at = momento del evento (fin de la hora); una zona de otro hogar no inserta."""
    sql = normalized_sql(tips.INSERT_TIP_SQL)
    assert "regla_origen, created_at, updated_at" in sql
    assert "cast(:created_at as timestamptz), cast(:created_at as timestamptz)" in sql
    assert "where cast(:zona_id as uuid) is null or exists" in sql
    assert "z.id = cast(:zona_id as uuid) and z.hogar_id = cast(:hogar_id as uuid)" in sql
    assert sql.endswith("returning id")


def test_insert_general_tip_sends_null_zone() -> None:
    session = FakeSession([{"id": uuid4()}])

    insert_tip(
        session,  # type: ignore[arg-type]
        **_insert_kwargs(categoria="general", prioridad="baja", zona_id=None),
    )

    assert session.calls[0][1]["zona_id"] is None  # type: ignore[index]


def test_insert_tip_without_returned_row_is_an_error() -> None:
    """I-01: la zona no es del hogar → la sentencia no inserta."""
    with pytest.raises(ValueError):
        insert_tip(FakeSession([]), **_insert_kwargs())  # type: ignore[arg-type]


def test_insert_tip_rejects_a_naive_date_without_sql() -> None:
    session = FakeSession()

    with pytest.raises(ValueError):
        insert_tip(session, **_insert_kwargs(created_at=NAIVE))  # type: ignore[arg-type]
    assert session.calls == []


# ------------------------------------------------------------------ insert_tip_assignments


def test_assignments_empty_runs_no_sql() -> None:
    session = FakeSession()

    assert insert_tip_assignments(session, uuid4(), []) == 0  # type: ignore[arg-type]
    assert session.calls == []


def test_assignments_send_one_statement_with_ids_as_text() -> None:
    tip_id = uuid4()
    users = [uuid4(), uuid4()]
    session = FakeSession(FakeResult(rowcount=2))

    assert insert_tip_assignments(session, tip_id, users) == 2  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is tips.INSERT_TIP_ASSIGNMENTS_SQL
    assert params == {"consejo_id": tip_id, "usuario_ids": [str(user) for user in users]}
    assert_bound_only(statement, params)


def test_assignments_sql_are_pending_for_active_members_and_ignore_repeats() -> None:
    """RN-VI-03, RN-XV-06, R-01."""
    sql = normalized_sql(tips.INSERT_TIP_ASSIGNMENTS_SQL)
    assert "(consejo_id, usuario_id, estado, completada_en)" in sql
    assert "select c.id, m.usuario_id, 'pendiente', null" in sql
    assert "unnest(cast(:usuario_ids as uuid[]))" in sql
    assert "join consejos c on c.id = cast(:consejo_id as uuid)" in sql
    assert "m.hogar_id = c.hogar_id" in sql
    assert "m.estado = 'activo'" in sql
    assert sql.endswith("on conflict (consejo_id, usuario_id) do nothing")


# ------------------------------------------------------------------ list_user_tips


def test_user_tips_bind_person_household_and_windows() -> None:
    usuario_id, hogar_id = uuid4(), uuid4()
    completed_after = WEEK_AGO - timedelta(hours=1)
    session = FakeSession()

    assert list_user_tips(session, usuario_id, hogar_id, WEEK_AGO, completed_after) == []  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is tips.USER_TIPS_SQL
    assert params == {
        "usuario_id": usuario_id,
        "hogar_id": hogar_id,
        "pending_created_after": WEEK_AGO,
        "completed_after": completed_after,
    }
    assert_bound_only(statement, params)


def test_user_tips_sql_filters_and_orders_pending_then_completed() -> None:
    """RN-XV-03, RN-XV-05: pendientes vigentes por prioridad; luego completadas recientes."""
    sql = normalized_sql(tips.USER_TIPS_SQL)
    assert "where cu.usuario_id = :usuario_id and c.hogar_id = :hogar_id" in sql
    assert "(cu.estado = 'pendiente' and c.created_at > :pending_created_after)" in sql
    assert "(cu.estado = 'completada' and cu.completada_en > :completed_after)" in sql
    order = sql[sql.index("order by") :]
    assert order.index("case cu.estado when 'pendiente' then 0 else 1 end") < order.index(
        "case c.prioridad when 'alta' then 0 when 'media' then 1 else 2 end"
    )
    assert order.index("c.prioridad") < order.index("then c.created_at end desc")
    assert order.index("then c.created_at end desc") < order.index("cu.completada_en desc")
    assert order.endswith("cu.completada_en desc, c.id desc")


def test_user_tips_map_rows() -> None:
    tip_id, zone_id = uuid4(), uuid4()
    done_at = NOW - timedelta(days=2)
    session = FakeSession(
        [
            _tip_row(id=str(tip_id), zona_id=str(zone_id)),
            _tip_row(
                categoria="general",
                prioridad="baja",
                zona_id=None,
                zona_tipo=None,
                estado="completada",
                completada_en=done_at,
            ),
        ]
    )

    rows = list_user_tips(session, uuid4(), uuid4(), WEEK_AGO, WEEK_AGO)  # type: ignore[arg-type]

    assert rows[0] == UserTipRow(
        id=tip_id,
        categoria="zona",
        prioridad="alta",
        titulo="Título resuelto",
        descripcion="Descripción resuelta",
        zona_id=zone_id,
        zona_tipo="lavanderia",
        estado="pendiente",
        completada_en=None,
        created_at=EVENT_AT,
    )
    assert isinstance(rows[0].id, UUID)
    assert rows[1].zona_id is None and rows[1].zona_tipo is None
    assert rows[1].completada_en == done_at


def test_user_tips_reject_naive_dates_without_sql() -> None:
    session = FakeSession()

    with pytest.raises(ValueError):
        list_user_tips(session, uuid4(), uuid4(), NAIVE, WEEK_AGO)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        list_user_tips(session, uuid4(), uuid4(), WEEK_AGO, NAIVE)  # type: ignore[arg-type]
    assert session.calls == []


# ------------------------------------------------------------------ get_user_tip


def test_get_user_tip_binds_person_household_and_tip() -> None:
    usuario_id, hogar_id, tip_id = uuid4(), uuid4(), uuid4()
    session = FakeSession([_tip_row(id=tip_id)])

    row = get_user_tip(session, usuario_id, hogar_id, tip_id)  # type: ignore[arg-type]

    assert row is not None and row.id == tip_id
    statement, params = session.calls[0]
    assert statement is tips.USER_TIP_SQL
    assert params == {"usuario_id": usuario_id, "hogar_id": hogar_id, "consejo_id": tip_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "where cu.usuario_id = :usuario_id and c.hogar_id = :hogar_id" in sql
    assert sql.endswith("and c.id = :consejo_id")


def test_get_user_tip_without_row_is_none() -> None:
    assert get_user_tip(FakeSession([]), uuid4(), uuid4(), uuid4()) is None  # type: ignore[arg-type]


# ------------------------------------------------------------------ update_user_tip_status


@pytest.mark.parametrize(("estado", "completada_en"), [("completada", NOW), ("pendiente", None)])
def test_update_status_binds_everything(estado: str, completada_en: datetime | None) -> None:
    usuario_id, hogar_id, tip_id = uuid4(), uuid4(), uuid4()
    session = FakeSession(FakeResult(rowcount=1))

    assert update_user_tip_status(
        session,  # type: ignore[arg-type]
        usuario_id,
        hogar_id,
        tip_id,
        estado,
        completada_en,
    )

    statement, params = session.calls[0]
    assert statement is tips.UPDATE_USER_TIP_STATUS_SQL
    assert params == {
        "usuario_id": usuario_id,
        "hogar_id": hogar_id,
        "consejo_id": tip_id,
        "estado": estado,
        "completada_en": completada_en,
    }
    # El valor «completada» también es parte del nombre de columna completada_en: se comprueba
    # que no aparece como literal y que el resto viaja como parámetro.
    sql = str(statement)
    assert f"'{estado}'" not in sql
    assert_bound_only(statement, {**params, "estado": None})
    assert session.commits == 0


def test_update_status_without_row_is_false() -> None:
    session = FakeSession(FakeResult(rowcount=0))

    assert not update_user_tip_status(session, uuid4(), uuid4(), uuid4(), "completada", NOW)  # type: ignore[arg-type]


def test_update_status_sql_touches_only_the_person_row_of_a_household_tip() -> None:
    sql = normalized_sql(tips.UPDATE_USER_TIP_STATUS_SQL)
    assert sql.startswith("update consejos_usuario cu set estado = :estado")
    assert "completada_en = cast(:completada_en as timestamptz)" in sql
    assert "updated_at = now()" in sql
    assert "c.hogar_id = :hogar_id" in sql
    assert "cu.usuario_id = :usuario_id" in sql
    assert sql.endswith("and cu.consejo_id = :consejo_id")


@pytest.mark.parametrize(
    ("estado", "completada_en"),
    [
        ("leida", None),
        ("completada", None),
        ("pendiente", NOW),
        ("completada", NAIVE),
    ],
)
def test_update_status_rejects_incoherent_input_without_sql(
    estado: str, completada_en: datetime | None
) -> None:
    """Check consejos_usuario_estado_coherente: pendiente ↔ sin fecha; completada ↔ con fecha."""
    session = FakeSession()

    with pytest.raises(ValueError):
        update_user_tip_status(session, uuid4(), uuid4(), uuid4(), estado, completada_en)  # type: ignore[arg-type]
    assert session.calls == []
