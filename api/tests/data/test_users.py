"""Pruebas de app.data.users sin base real (RN-IX-01, RN-IX-07, RN-I-02, RN-VII-01, RN-VI-04).

Una sesión falsa registra cada sentencia y sus parámetros: se comprueba el SQL generado
(filtro por el usuario, valores como parámetros, lista blanca fija en el SET), los valores
por defecto de preferencias y el mapeo de filas.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import TextClause

from app.data import users
from app.data.users import (
    PREFERENCE_FIELDS,
    USER_PROFILE_FIELDS,
    AuthUserMissingError,
    PreferencesRow,
    UserProfileRow,
    get_preferences,
    get_user_profile,
    insert_user_with_default_preferences,
    set_avatar_url,
    update_preferences,
    update_user_profile,
)
from tests.data.fake_session import FakeSession, assert_bound_only, normalized_sql

ALL_STATEMENTS = (
    users.USER_PROFILE_SQL,
    users.INSERT_USER_SQL,
    users.INSERT_DEFAULT_PREFERENCES_SQL,
    users.UPDATE_USER_PROFILE_SQL,
    users.SET_AVATAR_URL_SQL,
    users.PREFERENCES_SQL,
    users.UPDATE_PREFERENCES_SQL,
)


@pytest.fixture
def usuario_id() -> UUID:
    return uuid4()


def _profile_row(usuario_id: UUID, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": usuario_id,
        "nombre_completo": "Ana Pérez",
        "telefono": "3001234567",
        "avatar_url": f"{usuario_id}/avatar.png",
        "notif_consumo": True,
        "notif_consejos": False,
        "base_comparacion": "meta",
    }
    row.update(overrides)
    return row


# --- Sentencias constantes -------------------------------------------------------------------


@pytest.mark.parametrize("statement", ALL_STATEMENTS)
def test_every_statement_is_a_constant_text_without_python_formatting(statement: Any) -> None:
    assert isinstance(statement, TextClause)
    sql = str(statement)
    assert "{" not in sql
    assert "%" not in sql


@pytest.mark.parametrize("statement", ALL_STATEMENTS)
def test_every_statement_filters_by_the_user(statement: Any) -> None:
    """R-01: toda sentencia está atada al usuario autenticado por parámetro."""
    assert "usuario_id" in statement._bindparams


def test_whitelists_match_the_schema_columns() -> None:
    assert USER_PROFILE_FIELDS == frozenset({"nombre_completo", "telefono"})
    assert PREFERENCE_FIELDS == frozenset({"notif_consumo", "notif_consejos", "base_comparacion"})


# --- get_user_profile ------------------------------------------------------------------------


def test_get_user_profile_joins_preferences_and_filters_by_user(usuario_id: UUID) -> None:
    session = FakeSession()

    get_user_profile(session, usuario_id)  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert params == {"usuario_id": usuario_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "from usuarios u" in sql
    assert "join preferencias_usuario p on p.usuario_id = u.id" in sql
    assert "where u.id = :usuario_id" in sql


def test_get_user_profile_maps_row(usuario_id: UUID) -> None:
    session = FakeSession([_profile_row(usuario_id)])

    result = get_user_profile(session, usuario_id)  # type: ignore[arg-type]

    assert result == UserProfileRow(
        id=usuario_id,
        nombre_completo="Ana Pérez",
        telefono="3001234567",
        avatar_url=f"{usuario_id}/avatar.png",
        preferencias=PreferencesRow(
            notif_consumo=True, notif_consejos=False, base_comparacion="meta"
        ),
    )


def test_get_user_profile_keeps_nulls_as_none(usuario_id: UUID) -> None:
    """null es «sin dato»: teléfono y avatar nulos llegan como None."""
    session = FakeSession([_profile_row(str(usuario_id), telefono=None, avatar_url=None)])

    result = get_user_profile(session, usuario_id)  # type: ignore[arg-type]

    assert result is not None
    assert result.id == usuario_id
    assert isinstance(result.id, UUID)
    assert result.telefono is None
    assert result.avatar_url is None


def test_get_user_profile_returns_none_without_profile(usuario_id: UUID) -> None:
    assert get_user_profile(FakeSession(), usuario_id) is None  # type: ignore[arg-type]


# --- insert_user_with_default_preferences ----------------------------------------------------


def test_insert_creates_user_and_default_preferences(usuario_id: UUID) -> None:
    session = FakeSession([{"id": usuario_id}])

    created = insert_user_with_default_preferences(
        session,  # type: ignore[arg-type]
        usuario_id,
        "Ana Pérez",
        "3001234567",
    )

    assert created is True
    assert len(session.calls) == 2
    insert_user, user_params = session.calls[0]
    assert user_params == {
        "usuario_id": usuario_id,
        "nombre_completo": "Ana Pérez",
        "telefono": "3001234567",
    }
    assert_bound_only(insert_user, user_params)
    sql = normalized_sql(insert_user)
    assert "insert into usuarios (id, nombre_completo, telefono)" in sql
    assert "on conflict (id) do nothing" in sql
    assert "returning id" in sql

    insert_prefs, prefs_params = session.calls[1]
    assert prefs_params == {"usuario_id": usuario_id}
    assert_bound_only(insert_prefs, prefs_params)


def test_default_preferences_come_from_the_table_defaults(usuario_id: UUID) -> None:
    """RN-IX-07: solo se inserta usuario_id; la tabla pone true, true y 'promedio'."""
    sql = normalized_sql(users.INSERT_DEFAULT_PREFERENCES_SQL)

    assert sql == "insert into preferencias_usuario (usuario_id) values (:usuario_id)"


def test_insert_returns_false_and_skips_preferences_when_profile_exists(usuario_id: UUID) -> None:
    session = FakeSession([])

    created = insert_user_with_default_preferences(
        session,  # type: ignore[arg-type]
        usuario_id,
        "Ana Pérez",
        None,
    )

    assert created is False
    assert len(session.calls) == 1
    assert session.calls[0][1] == {
        "usuario_id": usuario_id,
        "nombre_completo": "Ana Pérez",
        "telefono": None,
    }


# --- update_user_profile ---------------------------------------------------------------------


def test_update_user_profile_sets_only_requested_columns(usuario_id: UUID) -> None:
    session = FakeSession([{"id": usuario_id}])

    updated = update_user_profile(
        session,  # type: ignore[arg-type]
        usuario_id,
        {"nombre_completo": "Ana María Pérez"},
    )

    assert updated is True
    statement, params = session.calls[0]
    assert params == {
        "usuario_id": usuario_id,
        "set_nombre_completo": True,
        "nombre_completo": "Ana María Pérez",
        "set_telefono": False,
        "telefono": None,
    }
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql.startswith("update usuarios set")
    assert "where id = :usuario_id" in sql
    assert "returning id" in sql


def test_update_user_profile_null_phone_clears_it(usuario_id: UUID) -> None:
    session = FakeSession([{"id": usuario_id}])

    update_user_profile(session, usuario_id, {"telefono": None})  # type: ignore[arg-type]

    params = session.calls[0][1]
    assert params is not None
    assert params["set_telefono"] is True
    assert params["telefono"] is None
    assert params["set_nombre_completo"] is False


def test_update_user_profile_returns_false_without_row(usuario_id: UUID) -> None:
    session = FakeSession([])

    changes = {"telefono": "3109876543"}

    assert update_user_profile(session, usuario_id, changes) is False  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"avatar_url": "x/avatar.png"},
        {"nombre_completo": "Ana", "id": "otro"},
        {"nombre_completo = 'x'; --": "Ana"},
        {"nombre_completo": None},
    ],
)
def test_update_user_profile_rejects_invalid_changes(
    usuario_id: UUID, changes: dict[str, Any]
) -> None:
    session = FakeSession()

    with pytest.raises(ValueError):
        update_user_profile(session, usuario_id, changes)  # type: ignore[arg-type]

    assert session.calls == []


# --- set_avatar_url --------------------------------------------------------------------------


def test_set_avatar_url_updates_only_avatar(usuario_id: UUID) -> None:
    session = FakeSession([{"id": usuario_id}])
    path = f"{usuario_id}/avatar.webp"

    assert set_avatar_url(session, usuario_id, path) is True  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert params == {"usuario_id": usuario_id, "avatar_url": path}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "update usuarios set avatar_url = :avatar_url where id = :usuario_id" in sql


def test_set_avatar_url_none_clears_it_and_reports_missing_row(usuario_id: UUID) -> None:
    session = FakeSession([])

    assert set_avatar_url(session, usuario_id, None) is False  # type: ignore[arg-type]
    assert session.calls[0][1] == {"usuario_id": usuario_id, "avatar_url": None}


# --- get_preferences -------------------------------------------------------------------------


def test_get_preferences_filters_by_user_and_maps_row(usuario_id: UUID) -> None:
    session = FakeSession(
        [{"notif_consumo": False, "notif_consejos": True, "base_comparacion": "promedio"}]
    )

    result = get_preferences(session, usuario_id)  # type: ignore[arg-type]

    assert result == PreferencesRow(
        notif_consumo=False, notif_consejos=True, base_comparacion="promedio"
    )
    statement, params = session.calls[0]
    assert params == {"usuario_id": usuario_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "from preferencias_usuario where usuario_id = :usuario_id" in sql


def test_get_preferences_returns_none_without_row(usuario_id: UUID) -> None:
    assert get_preferences(FakeSession(), usuario_id) is None  # type: ignore[arg-type]


# --- update_preferences ----------------------------------------------------------------------


def test_update_preferences_sets_only_requested_columns_and_returns_row(usuario_id: UUID) -> None:
    session = FakeSession(
        [{"notif_consumo": True, "notif_consejos": False, "base_comparacion": "meta"}]
    )

    result = update_preferences(
        session,  # type: ignore[arg-type]
        usuario_id,
        {"notif_consejos": False, "base_comparacion": "meta"},
    )

    assert result == PreferencesRow(
        notif_consumo=True, notif_consejos=False, base_comparacion="meta"
    )
    statement, params = session.calls[0]
    assert params == {
        "usuario_id": usuario_id,
        "set_notif_consumo": False,
        "notif_consumo": None,
        "set_notif_consejos": True,
        "notif_consejos": False,
        "set_base_comparacion": True,
        "base_comparacion": "meta",
    }
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql.startswith("update preferencias_usuario set")
    assert "where usuario_id = :usuario_id" in sql
    assert "returning notif_consumo, notif_consejos, base_comparacion" in sql


def test_update_preferences_returns_none_without_row(usuario_id: UUID) -> None:
    session = FakeSession([])

    changes = {"notif_consumo": False}

    assert update_preferences(session, usuario_id, changes) is None  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"usuario_id": "otro"},
        {"notif_consumo": True, "updated_at": "2026-11-20"},
        {"notif_consumo": None},
        {"base_comparacion": None},
    ],
)
def test_update_preferences_rejects_invalid_changes(
    usuario_id: UUID, changes: dict[str, Any]
) -> None:
    session = FakeSession()

    with pytest.raises(ValueError):
        update_preferences(session, usuario_id, changes)  # type: ignore[arg-type]

    assert session.calls == []


# --- Transacción -----------------------------------------------------------------------------


def test_no_function_commits(usuario_id: UUID) -> None:
    session = FakeSession(
        [_profile_row(usuario_id)],
        [{"id": usuario_id}],
        [],
        [{"id": usuario_id}],
        [{"id": usuario_id}],
        [{"notif_consumo": True, "notif_consejos": True, "base_comparacion": "promedio"}],
        [{"notif_consumo": True, "notif_consejos": True, "base_comparacion": "promedio"}],
    )

    get_user_profile(session, usuario_id)  # type: ignore[arg-type]
    insert_user_with_default_preferences(session, usuario_id, "Ana", None)  # type: ignore[arg-type]
    update_user_profile(session, usuario_id, {"nombre_completo": "Ana"})  # type: ignore[arg-type]
    set_avatar_url(session, usuario_id, None)  # type: ignore[arg-type]
    get_preferences(session, usuario_id)  # type: ignore[arg-type]
    update_preferences(session, usuario_id, {"notif_consumo": True})  # type: ignore[arg-type]

    assert session.commits == 0


# --- Cuenta de Auth ya borrada (FK 23503) ----------------------------------------------------


class _FakeDriverError(Exception):
    """Imita la excepción de psycopg2: solo `pgcode`."""

    def __init__(self, pgcode: str | None) -> None:
        super().__init__("detalle del controlador")
        self.pgcode = pgcode


class _RaisingSession(FakeSession):
    """La primera sentencia falla con la IntegrityError dada."""

    def __init__(self, error: IntegrityError) -> None:
        super().__init__()
        self.error = error

    def exec(self, statement: Any, *, params: Any = None) -> Any:
        self.calls.append((statement, params))
        raise self.error


def _integrity_error(pgcode: str | None) -> IntegrityError:
    return IntegrityError("insert into usuarios ...", {}, _FakeDriverError(pgcode))


def test_insert_raises_auth_user_missing_on_foreign_key_violation(usuario_id: UUID) -> None:
    """Token todavía válido de una cuenta ya borrada en Auth: el servicio responde 401."""
    session = _RaisingSession(_integrity_error("23503"))

    with pytest.raises(AuthUserMissingError) as exc_info:
        insert_user_with_default_preferences(
            session,  # type: ignore[arg-type]
            usuario_id,
            "Ana",
            None,
        )

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert str(usuario_id) not in str(exc_info.value)
    assert len(session.calls) == 1  # no intenta insertar las preferencias
    assert session.commits == 0


@pytest.mark.parametrize("pgcode", ["23505", "23502", "23514", None])
def test_insert_reraises_other_integrity_errors(usuario_id: UUID, pgcode: str | None) -> None:
    error = _integrity_error(pgcode)
    session = _RaisingSession(error)

    with pytest.raises(IntegrityError) as exc_info:
        insert_user_with_default_preferences(
            session,  # type: ignore[arg-type]
            usuario_id,
            "Ana",
            None,
        )

    assert exc_info.value is error


def test_auth_user_missing_error_is_not_an_integrity_error() -> None:
    assert issubclass(AuthUserMissingError, Exception)
    assert not issubclass(AuthUserMissingError, IntegrityError)
