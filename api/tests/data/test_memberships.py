"""Pruebas de app.data.memberships sin base real (RN-I-03, RN-XVII).

Una sesión falsa registra la sentencia y sus parámetros: se comprueba el SQL generado
(filtro por hogar, usuario y estado 'activo'), que los valores viajan como parámetros
y el mapeo de la fila a ActiveMembershipRow.
"""

import re
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from app.data import memberships
from app.data.memberships import ActiveMembershipRow, get_active_membership


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
