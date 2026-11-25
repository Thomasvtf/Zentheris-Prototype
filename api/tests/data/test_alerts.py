"""Pruebas de app.data.alerts sin base real (RN-XIV-05, RN-XIV-08, DC-25, RN-VI-02/04/05, R-01).

Se comprueba el SQL generado (filtro por hogar y persona, ON CONFLICT, orden), que los valores
viajan como parámetros y la conversión de filas. Que el único de clave_evento descarte de verdad
la repetida, o que una zona de otro hogar no inserte, necesita Postgres (tests/integrity).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from app.data import alerts, tips
from app.data.alerts import (
    UserAlertRow,
    count_unread_alerts,
    insert_alert,
    insert_alert_deliveries,
    list_existing_event_keys,
    list_user_alerts,
    mark_alerts_read,
)
from tests.data.fake_session import FakeResult, FakeSession, assert_bound_only, normalized_sql

NOW = datetime(2026, 11, 24, 15, 0, tzinfo=UTC)
EVENT_AT = datetime(2026, 11, 24, 14, 0, tzinfo=UTC)
READ_AFTER = NOW - timedelta(days=7)
LIMIT = 37
NAIVE = EVENT_AT.replace(tzinfo=None)

ALL_STATEMENTS = (
    alerts.EXISTING_EVENT_KEYS_SQL,
    alerts.INSERT_ALERT_SQL,
    alerts.INSERT_ALERT_DELIVERIES_SQL,
    alerts.USER_ALERTS_SQL,
    alerts.USER_ALERTS_BY_CATEGORY_SQL,
    alerts.COUNT_UNREAD_ALERTS_SQL,
    alerts.MARK_ALERTS_READ_SQL,
)


def _alert_row(**overrides: Any) -> dict[str, Any]:
    """Fila como la entregaría psycopg2 (ids UUID, fechas con zona horaria)."""
    row: dict[str, Any] = {
        "id": uuid4(),
        "categoria": "consumo",
        "severidad": "critica",
        "titulo": "Título resuelto",
        "mensaje": "Mensaje resuelto",
        "zona_id": uuid4(),
        "zona_tipo": "cocina",
        "created_at": EVENT_AT,
        "leida_en": None,
    }
    row.update(overrides)
    return row


def _insert_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "hogar_id": uuid4(),
        "categoria": "consumo",
        "severidad": "critica",
        "titulo": "Consumo crítico en Cocina",
        "mensaje": "Mensaje con datos del usuario",
        "zona_id": uuid4(),
        "regla_origen": "consumo_critico",
        "clave_evento": f"consumo_critico:{uuid4()}:2026-11-24",
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


# ------------------------------------------------------------------ list_existing_event_keys


def test_existing_event_keys_empty_runs_no_sql() -> None:
    session = FakeSession()

    assert list_existing_event_keys(session, uuid4(), []) == set()  # type: ignore[arg-type]
    assert session.calls == []


def test_existing_event_keys_binds_household_and_keys() -> None:
    hogar_id = uuid4()
    keys = [f"zona_critica:{uuid4()}:2026-11-24", f"consumo_elevado:{uuid4()}:2026-11-24"]
    session = FakeSession([{"clave_evento": keys[1]}])

    found = list_existing_event_keys(session, hogar_id, keys)  # type: ignore[arg-type]

    assert found == {keys[1]}
    statement, params = session.calls[0]
    assert statement is alerts.EXISTING_EVENT_KEYS_SQL
    assert params == {"hogar_id": hogar_id, "claves": keys}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "where hogar_id = :hogar_id" in sql
    assert "clave_evento = any(cast(:claves as text[]))" in sql
    assert session.commits == 0


def test_existing_event_keys_accepts_a_tuple() -> None:
    keys = ("a:b", "c:d")
    session = FakeSession()

    assert list_existing_event_keys(session, uuid4(), keys) == set()  # type: ignore[arg-type]
    assert session.calls[0][1]["claves"] == ["a:b", "c:d"]  # type: ignore[index]


# ------------------------------------------------------------------ insert_alert


def test_insert_alert_returns_the_new_id_and_binds_every_value() -> None:
    alert_id = uuid4()
    kwargs = _insert_kwargs()
    session = FakeSession([{"id": str(alert_id)}])

    assert insert_alert(session, **kwargs) == alert_id  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is alerts.INSERT_ALERT_SQL
    assert params == kwargs
    assert_bound_only(statement, params)
    assert session.commits == 0


def test_insert_alert_returns_none_when_the_key_already_existed() -> None:
    """RN-XIV-08, DC-25, A-01: ON CONFLICT DO NOTHING no devuelve fila."""
    session = FakeSession([])

    assert insert_alert(session, **_insert_kwargs()) is None  # type: ignore[arg-type]


def test_insert_alert_sql_ignores_duplicates_and_stamps_both_dates() -> None:
    sql = normalized_sql(alerts.INSERT_ALERT_SQL)
    assert "on conflict (clave_evento) do nothing returning id" in sql
    assert "cast(:created_at as timestamptz), cast(:created_at as timestamptz)" in sql
    assert "regla_origen, clave_evento, created_at, updated_at" in sql


def test_insert_alert_sql_checks_the_zone_belongs_to_the_household() -> None:
    """I-01, R-01: una zona de otro hogar no inserta."""
    sql = normalized_sql(alerts.INSERT_ALERT_SQL)
    assert "where cast(:zona_id as uuid) is null or exists" in sql
    assert "z.id = cast(:zona_id as uuid) and z.hogar_id = cast(:hogar_id as uuid)" in sql


def test_insert_alert_without_zone_sends_null() -> None:
    """Las alertas de cierre de mes y de consejo general no tienen zona."""
    session = FakeSession([{"id": uuid4()}])

    insert_alert(session, **_insert_kwargs(zona_id=None))  # type: ignore[arg-type]

    assert session.calls[0][1]["zona_id"] is None  # type: ignore[index]


def test_insert_alert_rejects_a_naive_date_without_sql() -> None:
    session = FakeSession()

    with pytest.raises(ValueError):
        insert_alert(session, **_insert_kwargs(created_at=NAIVE))  # type: ignore[arg-type]
    assert session.calls == []


# ------------------------------------------------------------------ insert_alert_deliveries


def test_deliveries_empty_runs_no_sql() -> None:
    session = FakeSession()

    assert insert_alert_deliveries(session, uuid4(), []) == 0  # type: ignore[arg-type]
    assert session.calls == []


def test_deliveries_send_one_statement_with_ids_as_text() -> None:
    alert_id = uuid4()
    users = [uuid4(), uuid4(), uuid4()]
    session = FakeSession(FakeResult(rowcount=3))

    assert insert_alert_deliveries(session, alert_id, users) == 3  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert statement is alerts.INSERT_ALERT_DELIVERIES_SQL
    assert params == {"alerta_id": alert_id, "usuario_ids": [str(user) for user in users]}
    assert_bound_only(statement, params)
    assert session.commits == 0


def test_deliveries_sql_only_reaches_active_members_and_ignores_repeats() -> None:
    """RN-VI-02, RN-XIV-06, R-01: solo miembros activos del hogar de la alerta; sin leer."""
    sql = normalized_sql(alerts.INSERT_ALERT_DELIVERIES_SQL)
    assert sql.startswith("insert into alertas_usuario (alerta_id, usuario_id) select")
    assert "leida_en" not in sql  # queda nula (valor por defecto)
    assert "unnest(cast(:usuario_ids as uuid[]))" in sql
    assert "join alertas a on a.id = cast(:alerta_id as uuid)" in sql
    assert "m.hogar_id = a.hogar_id" in sql
    assert "m.estado = 'activo'" in sql
    assert sql.endswith("on conflict (alerta_id, usuario_id) do nothing")


def test_deliveries_unknown_rowcount_is_zero() -> None:
    session = FakeSession(FakeResult(rowcount=-1))

    assert insert_alert_deliveries(session, uuid4(), [uuid4()]) == 0  # type: ignore[arg-type]


# ------------------------------------------------------------------ list_user_alerts


def test_user_alerts_without_category_binds_person_household_and_window() -> None:
    usuario_id, hogar_id = uuid4(), uuid4()
    session = FakeSession()

    rows = list_user_alerts(session, usuario_id, hogar_id, None, LIMIT, READ_AFTER)  # type: ignore[arg-type]

    assert rows == []
    statement, params = session.calls[0]
    assert statement is alerts.USER_ALERTS_SQL
    assert params == {
        "usuario_id": usuario_id,
        "hogar_id": hogar_id,
        "read_after": READ_AFTER,
        "limite": LIMIT,
    }
    assert_bound_only(statement, params)
    assert "categoria = :categoria" not in normalized_sql(statement)


def test_user_alerts_with_category_adds_the_filter() -> None:
    session = FakeSession()

    list_user_alerts(session, uuid4(), uuid4(), "consejo", LIMIT, READ_AFTER)  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is alerts.USER_ALERTS_BY_CATEGORY_SQL
    assert params is not None and params["categoria"] == "consejo"
    assert_bound_only(statement, params)
    assert "and a.categoria = :categoria order by" in normalized_sql(statement)


@pytest.mark.parametrize("statement", [alerts.USER_ALERTS_SQL, alerts.USER_ALERTS_BY_CATEGORY_SQL])
def test_user_alerts_sql_hides_old_read_ones_and_orders_newest_first(
    statement: TextClause,
) -> None:
    """RN-XIV-05: las leídas en read_after o antes se ocultan; las no leídas nunca."""
    sql = normalized_sql(statement)
    assert "where au.usuario_id = :usuario_id and a.hogar_id = :hogar_id" in sql
    assert "(au.leida_en is null or au.leida_en > :read_after)" in sql
    assert "left join zonas z on z.id = a.zona_id" in sql
    assert sql.endswith("order by a.created_at desc, a.id desc limit :limite")


@pytest.mark.parametrize("statement", [alerts.USER_ALERTS_SQL, alerts.USER_ALERTS_BY_CATEGORY_SQL])
def test_user_alerts_read_exactly_at_the_border_is_hidden_like_tips(
    statement: TextClause,
) -> None:
    """RN-XIV-05: borde estricto (`>`), igual que las completadas de consejos; nunca `>=`."""
    sql = normalized_sql(statement)
    assert ">= :read_after" not in sql
    assert "cu.completada_en > :completed_after" in normalized_sql(tips.USER_TIPS_SQL)


def test_user_alerts_map_rows() -> None:
    alert_id, zone_id = uuid4(), uuid4()
    read_at = NOW - timedelta(days=1)
    session = FakeSession(
        [
            _alert_row(id=str(alert_id), zona_id=str(zone_id), leida_en=read_at),
            _alert_row(
                categoria="informacion",
                severidad="informativa",
                zona_id=None,
                zona_tipo=None,
            ),
        ]
    )

    rows = list_user_alerts(session, uuid4(), uuid4(), None, LIMIT, READ_AFTER)  # type: ignore[arg-type]

    assert rows[0] == UserAlertRow(
        id=alert_id,
        categoria="consumo",
        severidad="critica",
        titulo="Título resuelto",
        mensaje="Mensaje resuelto",
        zona_id=zone_id,
        zona_tipo="cocina",
        created_at=EVENT_AT,
        leida_en=read_at,
    )
    assert isinstance(rows[0].id, UUID) and isinstance(rows[0].zona_id, UUID)
    assert rows[1].zona_id is None
    assert rows[1].zona_tipo is None
    assert rows[1].leida_en is None


def test_user_alerts_reject_bad_input_without_sql() -> None:
    session = FakeSession()

    with pytest.raises(ValueError):
        list_user_alerts(session, uuid4(), uuid4(), None, LIMIT, NAIVE)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        list_user_alerts(session, uuid4(), uuid4(), None, 0, READ_AFTER)  # type: ignore[arg-type]
    assert session.calls == []


# ------------------------------------------------------------------ count_unread_alerts


def test_count_unread_binds_person_and_household() -> None:
    usuario_id, hogar_id = uuid4(), uuid4()
    session = FakeSession([{"total": 4}])

    assert count_unread_alerts(session, usuario_id, hogar_id) == 4  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is alerts.COUNT_UNREAD_ALERTS_SQL
    assert params == {"usuario_id": usuario_id, "hogar_id": hogar_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "where au.usuario_id = :usuario_id and a.hogar_id = :hogar_id" in sql
    assert sql.endswith("and au.leida_en is null")


def test_count_unread_without_row_is_zero() -> None:
    assert count_unread_alerts(FakeSession([]), uuid4(), uuid4()) == 0  # type: ignore[arg-type]


# ------------------------------------------------------------------ mark_alerts_read


def test_mark_read_empty_runs_no_sql() -> None:
    session = FakeSession()

    assert mark_alerts_read(session, uuid4(), uuid4(), [], NOW) == 0  # type: ignore[arg-type]
    assert session.calls == []


def test_mark_read_binds_everything_and_returns_rowcount() -> None:
    usuario_id, hogar_id = uuid4(), uuid4()
    ids = [uuid4(), uuid4()]
    session = FakeSession(FakeResult(rowcount=1))

    assert mark_alerts_read(session, usuario_id, hogar_id, ids, NOW) == 1  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert statement is alerts.MARK_ALERTS_READ_SQL
    assert params == {
        "usuario_id": usuario_id,
        "hogar_id": hogar_id,
        "alerta_ids": [str(alert_id) for alert_id in ids],
        "read_at": NOW,
    }
    assert_bound_only(statement, params)
    assert session.commits == 0


def test_mark_read_sql_only_touches_unread_rows_of_the_person_in_the_household() -> None:
    """RN-VI-05, R-01: solo filas de la persona, de alertas del hogar y aún sin leer."""
    sql = normalized_sql(alerts.MARK_ALERTS_READ_SQL)
    assert sql.startswith("update alertas_usuario au set leida_en = :read_at from alertas a")
    assert "a.hogar_id = :hogar_id" in sql
    assert "au.usuario_id = :usuario_id" in sql
    assert "au.alerta_id = any(cast(:alerta_ids as uuid[]))" in sql
    assert sql.endswith("and au.leida_en is null")


def test_mark_read_rejects_a_naive_date_without_sql() -> None:
    session = FakeSession()

    with pytest.raises(ValueError):
        mark_alerts_read(session, uuid4(), uuid4(), [uuid4()], NAIVE)  # type: ignore[arg-type]
    assert session.calls == []
