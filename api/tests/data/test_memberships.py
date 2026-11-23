"""Pruebas de app.data.memberships sin base real (RN-I-03, RN-XVII).

Una sesión falsa registra la sentencia y sus parámetros: se comprueba el SQL generado
(filtro por hogar, usuario y estado 'activo'), que los valores viajan como parámetros
y el mapeo de la fila a ActiveMembershipRow.
"""

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg2.errors
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import TextClause

from app.data import memberships
from app.data.memberships import (
    ActiveMembershipExistsError,
    ActiveMembershipRow,
    MembershipSummaryRow,
    close_membership,
    count_other_active_members,
    get_active_membership,
    get_active_membership_of_user,
    insert_admin_membership,
)
from tests.data.fake_session import FakeSession as QueuedFakeSession
from tests.data.fake_session import assert_bound_only, normalized_sql


class FakeResult:
    """Imita el Result de SQLAlchemy: solo lo que usa la capa de datos."""

    def __init__(self, rows: list[Mapping[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> FakeResult:
        return self

    def first(self) -> Mapping[str, Any] | None:
        return self._rows[0] if self._rows else None

    def one_or_none(self) -> Mapping[str, Any] | None:
        if len(self._rows) > 1:
            raise AssertionError("se esperaba como máximo una fila")
        return self.first()


class FakeSession:
    """Registra cada sentencia y sus parámetros; devuelve filas fabricadas."""

    def __init__(self, rows: list[Mapping[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[Any, Mapping[str, Any] | None]] = []
        self.commits = 0

    def exec(self, statement: Any, *, params: Mapping[str, Any] | None = None) -> FakeResult:
        self.calls.append((statement, params))
        return FakeResult(self.rows)

    def execute(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        raise AssertionError("usar Session.exec (Session.execute está obsoleto en SQLModel)")

    def commit(self) -> None:  # pragma: no cover
        self.commits += 1


def _normalized_sql(statement: Any) -> str:
    return re.sub(r"\s+", " ", str(statement)).strip().lower()


def _row(usuario_id: UUID, hogar_id: UUID, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "membresia_id": uuid4(),
        "hogar_id": hogar_id,
        "usuario_id": usuario_id,
        "rol": "miembro",
        "permiso_ver_consumo_actual": True,
        "permiso_ver_historial": True,
        "permiso_recibir_alertas": True,
        "permiso_modificar_metas": False,
    }
    row.update(overrides)
    return row


@pytest.fixture
def ids() -> tuple[UUID, UUID]:
    return uuid4(), uuid4()


def test_executes_a_single_parametrized_text_statement(ids: tuple[UUID, UUID]) -> None:
    usuario_id, hogar_id = ids
    session = FakeSession()

    get_active_membership(session, usuario_id, hogar_id)  # type: ignore[arg-type]

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {"usuario_id": usuario_id, "hogar_id": hogar_id}


def test_sql_joins_hogares_and_filters_by_household_user_and_active_state(
    ids: tuple[UUID, UUID],
) -> None:
    """R-01 / P-01: filtro obligatorio por hogar; solo estado 'activo' (RN-I-03)."""
    usuario_id, hogar_id = ids
    session = FakeSession()

    get_active_membership(session, usuario_id, hogar_id)  # type: ignore[arg-type]

    sql = _normalized_sql(session.calls[0][0])
    assert "from hogar_miembros m" in sql
    assert "join hogares h on h.id = m.hogar_id" in sql
    assert "m.usuario_id = :usuario_id" in sql
    assert "m.hogar_id = :hogar_id" in sql
    assert "m.estado = 'activo'" in sql
    for column in (
        "h.permiso_ver_consumo_actual",
        "h.permiso_ver_historial",
        "h.permiso_recibir_alertas",
        "h.permiso_modificar_metas",
        "m.rol",
    ):
        assert column in sql


def test_values_are_bound_not_interpolated(ids: tuple[UUID, UUID]) -> None:
    usuario_id, hogar_id = ids
    session = FakeSession()

    get_active_membership(session, usuario_id, hogar_id)  # type: ignore[arg-type]

    statement, _ = session.calls[0]
    sql = str(statement)
    assert str(usuario_id) not in sql
    assert str(hogar_id) not in sql
    assert set(statement._bindparams) == {"usuario_id", "hogar_id"}


def test_maps_row_to_active_membership_row(ids: tuple[UUID, UUID]) -> None:
    usuario_id, hogar_id = ids
    row = _row(
        usuario_id,
        hogar_id,
        rol="administrador",
        permiso_ver_historial=False,
        permiso_modificar_metas=True,
    )
    session = FakeSession([row])

    result = get_active_membership(session, usuario_id, hogar_id)  # type: ignore[arg-type]

    assert result == ActiveMembershipRow(
        membresia_id=row["membresia_id"],
        hogar_id=hogar_id,
        usuario_id=usuario_id,
        rol="administrador",
        permiso_ver_consumo_actual=True,
        permiso_ver_historial=False,
        permiso_recibir_alertas=True,
        permiso_modificar_metas=True,
    )


def test_maps_string_uuids_to_uuid(ids: tuple[UUID, UUID]) -> None:
    """Si el controlador devuelve los UUID como texto, igual se entregan como UUID."""
    usuario_id, hogar_id = ids
    membresia_id = uuid4()
    row = _row(usuario_id, hogar_id)
    row.update(
        membresia_id=str(membresia_id),
        hogar_id=str(hogar_id),
        usuario_id=str(usuario_id),
    )
    session = FakeSession([row])

    result = get_active_membership(session, usuario_id, hogar_id)  # type: ignore[arg-type]

    assert result is not None
    assert result.membresia_id == membresia_id
    assert isinstance(result.membresia_id, UUID)
    assert isinstance(result.hogar_id, UUID)
    assert isinstance(result.usuario_id, UUID)
    for flag in (
        result.permiso_ver_consumo_actual,
        result.permiso_ver_historial,
        result.permiso_recibir_alertas,
        result.permiso_modificar_metas,
    ):
        assert type(flag) is bool


def test_returns_none_without_row(ids: tuple[UUID, UUID]) -> None:
    usuario_id, hogar_id = ids
    session = FakeSession([])

    assert get_active_membership(session, usuario_id, hogar_id) is None  # type: ignore[arg-type]


def test_does_not_commit(ids: tuple[UUID, UUID]) -> None:
    usuario_id, hogar_id = ids
    session = FakeSession([_row(usuario_id, hogar_id)])

    get_active_membership(session, usuario_id, hogar_id)  # type: ignore[arg-type]

    assert session.commits == 0


def test_module_sql_has_no_python_formatting() -> None:
    """La sentencia es una constante: sin f-strings, % ni .format con datos."""
    sql = str(memberships.ACTIVE_MEMBERSHIP_SQL)
    assert "{" not in sql
    assert "%" not in sql


# --- Fase 3: eliminar cuenta (RN-IX-09, DC-36) -----------------------------------------------


def test_active_membership_of_user_filters_by_user_and_active_state() -> None:
    """uq_miembros_usuario_activo: como máximo una membresía activa por usuario."""
    usuario_id = uuid4()
    session = QueuedFakeSession()

    assert get_active_membership_of_user(session, usuario_id) is None  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert params == {"usuario_id": usuario_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "from hogar_miembros" in sql
    assert "where usuario_id = :usuario_id and estado = 'activo'" in sql
    assert "for update" not in sql


def test_active_membership_of_user_for_update_locks_the_row() -> None:
    usuario_id = uuid4()
    session = QueuedFakeSession()

    get_active_membership_of_user(session, usuario_id, for_update=True)  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert params == {"usuario_id": usuario_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql.endswith("estado = 'activo' for update")


def test_active_membership_of_user_maps_row_with_string_uuids() -> None:
    usuario_id, membresia_id, hogar_id = uuid4(), uuid4(), uuid4()
    session = QueuedFakeSession(
        [{"membresia_id": str(membresia_id), "hogar_id": str(hogar_id), "rol": "administrador"}]
    )

    result = get_active_membership_of_user(session, usuario_id)  # type: ignore[arg-type]

    assert result == MembershipSummaryRow(
        membresia_id=membresia_id, hogar_id=hogar_id, rol="administrador"
    )
    assert isinstance(result.membresia_id, UUID)
    assert isinstance(result.hogar_id, UUID)


def test_count_other_active_members_excludes_the_user_and_filters_by_household() -> None:
    hogar_id, usuario_id = uuid4(), uuid4()
    session = QueuedFakeSession([{"total": 2}])

    assert count_other_active_members(session, hogar_id, usuario_id) == 2  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert params == {"hogar_id": hogar_id, "usuario_id": usuario_id}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert "select count(*) as total from hogar_miembros" in sql
    assert "hogar_id = :hogar_id" in sql
    assert "estado = 'activo'" in sql
    assert "usuario_id <> :usuario_id" in sql


def test_count_other_active_members_returns_int_zero() -> None:
    session = QueuedFakeSession([{"total": 0}])

    result = count_other_active_members(session, uuid4(), uuid4())  # type: ignore[arg-type]

    assert result == 0
    assert type(result) is int


def test_close_membership_sets_inactive_and_exit_date() -> None:
    """RN-X-07, DC-36: estado 'inactivo' y fecha_salida; el resto de la fila queda intacta."""
    membresia_id = uuid4()
    closed_at = datetime(2026, 11, 20, 15, 30, tzinfo=UTC)
    session = QueuedFakeSession()

    assert close_membership(session, membresia_id, closed_at) is None  # type: ignore[arg-type]

    statement, params = session.calls[0]
    assert params == {"membresia_id": membresia_id, "closed_at": closed_at}
    assert_bound_only(statement, params)
    sql = normalized_sql(statement)
    assert sql.startswith(
        "update hogar_miembros set estado = 'inactivo', fecha_salida = :closed_at"
    )
    assert "where id = :membresia_id" in sql
    assert "usuario_id" not in sql


def test_phase3_membership_functions_do_not_commit() -> None:
    session = QueuedFakeSession(
        [{"membresia_id": uuid4(), "hogar_id": uuid4(), "rol": "miembro"}], [{"total": 1}]
    )

    get_active_membership_of_user(session, uuid4(), for_update=True)  # type: ignore[arg-type]
    count_other_active_members(session, uuid4(), uuid4())  # type: ignore[arg-type]
    close_membership(session, uuid4(), datetime.now(UTC))  # type: ignore[arg-type]

    assert session.commits == 0


@pytest.mark.parametrize(
    "statement",
    [
        memberships.ACTIVE_MEMBERSHIP_OF_USER_SQL,
        memberships.ACTIVE_MEMBERSHIP_OF_USER_FOR_UPDATE_SQL,
        memberships.COUNT_OTHER_ACTIVE_MEMBERS_SQL,
        memberships.CLOSE_MEMBERSHIP_SQL,
    ],
)
def test_phase3_statements_are_constants_without_python_formatting(statement: Any) -> None:
    assert isinstance(statement, TextClause)
    assert "{" not in str(statement)
    assert "%" not in str(statement)


# --- Fase 4: membresía del administrador en el onboarding (RN-X-03, RN-II-01) -----------------


class _FakeDiag:
    def __init__(self, constraint_name: str | None) -> None:
        self.constraint_name = constraint_name


class _FakeDriverError(Exception):
    """Imita la excepción de psycopg2: `pgcode`, `diag` (si viene) y el mensaje con el índice."""

    def __init__(
        self, pgcode: str | None, *, message: str = "", diag: _FakeDiag | None = None
    ) -> None:
        super().__init__(message)
        self.pgcode = pgcode
        if diag is not None:
            self.diag = diag


def _unique_message(constraint: str) -> str:
    return f'duplicate key value violates unique constraint "{constraint}"\n'


def _integrity_error(orig: Exception) -> IntegrityError:
    return IntegrityError("insert into hogar_miembros ...", {}, orig)


def _insert_admin(session: QueuedFakeSession, **overrides: Any) -> None:
    values: dict[str, Any] = {
        "hogar_id": uuid4(),
        "usuario_id": uuid4(),
        "joined_at": datetime(2026, 11, 22, 10, 0, tzinfo=UTC),
    }
    values.update(overrides)
    insert_admin_membership(session, **values)  # type: ignore[arg-type]


def test_insert_admin_membership_sql_and_params() -> None:
    hogar_id, usuario_id = uuid4(), uuid4()
    joined_at = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)
    session = QueuedFakeSession()

    _insert_admin(session, hogar_id=hogar_id, usuario_id=usuario_id, joined_at=joined_at)

    assert len(session.calls) == 1
    statement, params = session.calls[0]
    assert isinstance(statement, TextClause)
    assert params == {"hogar_id": hogar_id, "usuario_id": usuario_id, "joined_at": joined_at}
    assert_bound_only(statement, params)
    assert normalized_sql(statement) == (
        "insert into hogar_miembros (hogar_id, usuario_id, rol, estado, fecha_ingreso) "
        "values (:hogar_id, :usuario_id, 'administrador', 'activo', :joined_at)"
    )
    assert session.commits == 0


@pytest.mark.parametrize(
    "orig",
    [
        _FakeDriverError("23505", diag=_FakeDiag("uq_miembros_usuario_activo")),
        _FakeDriverError("23505", message=_unique_message("uq_miembros_usuario_activo")),
        _FakeDriverError(
            "23505",
            message=_unique_message("uq_miembros_usuario_activo"),
            diag=_FakeDiag(None),
        ),
    ],
    ids=["diag", "sin diag", "diag sin nombre"],
)
def test_insert_admin_membership_raises_when_user_already_has_a_household(
    orig: Exception,
) -> None:
    """RN-II-01: el índice único cierra la carrera entre dos onboardings del mismo usuario."""
    usuario_id = uuid4()
    session = QueuedFakeSession(_integrity_error(orig))

    with pytest.raises(ActiveMembershipExistsError) as exc_info:
        _insert_admin(session, usuario_id=usuario_id)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    assert str(usuario_id) not in str(exc_info.value)
    assert not isinstance(exc_info.value, IntegrityError)
    assert session.commits == 0


@pytest.mark.parametrize(
    "orig",
    [
        _FakeDriverError("23505", diag=_FakeDiag("uq_miembros_admin_activo")),
        _FakeDriverError("23505", message=_unique_message("uq_miembros_admin_activo")),
        _FakeDriverError(
            "23505",
            message=_unique_message("uq_miembros_usuario_activo"),
            diag=_FakeDiag("uq_miembros_admin_activo"),
        ),
        _FakeDriverError("23505"),
        _FakeDriverError("23503", diag=_FakeDiag("hogar_miembros_usuario_id_fkey")),
        _FakeDriverError("23503", message=_unique_message("uq_miembros_usuario_activo")),
        _FakeDriverError("23514"),
        _FakeDriverError(None),
        psycopg2.errors.UniqueViolation(),
    ],
    ids=[
        "otro índice en diag",
        "otro índice en el mensaje",
        "diag manda sobre el mensaje",
        "23505 sin nombre",
        "FK de usuarios",
        "otro SQLSTATE con el nombre",
        "trigger de 5 miembros",
        "sin SQLSTATE",
        "excepción real de psycopg2 sin datos",
    ],
)
def test_insert_admin_membership_reraises_any_other_integrity_error(orig: Exception) -> None:
    error = _integrity_error(orig)
    session = QueuedFakeSession(error)

    with pytest.raises(IntegrityError) as exc_info:
        _insert_admin(session)

    assert exc_info.value is error


def test_active_user_index_name_matches_the_migration() -> None:
    """El nombre del índice que detecta el código es el de la migración 0003."""
    migrations = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
    (migration,) = migrations.glob("*_0003_*.sql")

    expected = f"create unique index {memberships.ACTIVE_USER_INDEX}\n"
    assert expected in migration.read_text(encoding="utf-8")
