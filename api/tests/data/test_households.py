"""Pruebas de app.data.households sin base real (RN-IX-09, DC-36).

El borrado en cascada real (I-04) necesita Postgres: está en tests/integrity. Aquí se
comprueba el SQL generado, el FOR UPDATE y que los valores viajan como parámetros.
"""

from uuid import uuid4

from sqlalchemy.sql.elements import TextClause

from app.data import households
from app.data.households import delete_household, lock_household
from tests.data.fake_session import FakeSession, assert_bound_only, normalized_sql


def test_lock_household_selects_the_row_for_update() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert lock_household(session, hogar_id) is None  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql == "select id from hogares where id = :hogar_id for update"


def test_delete_household_deletes_only_that_household() -> None:
    hogar_id = uuid4()
    session = FakeSession()

    assert delete_household(session, hogar_id) is None  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert params == {"hogar_id": hogar_id}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == "delete from hogares where id = :hogar_id"


def test_statements_are_constants_and_functions_do_not_commit() -> None:
    session = FakeSession()

    lock_household(session, uuid4())  # type: ignore[arg-type]
    delete_household(session, uuid4())  # type: ignore[arg-type]

    assert session.commits == 0
    for statement in (households.LOCK_HOUSEHOLD_SQL, households.DELETE_HOUSEHOLD_SQL):
        assert isinstance(statement, TextClause)
        assert "{" not in str(statement)
        assert "%" not in str(statement)
