"""Sesión falsa compartida por las pruebas de app.data (sin base real).

Registra cada sentencia con sus parámetros y devuelve, por llamada, las filas fabricadas
que se le den en orden. Falla si alguien usa `Session.execute` o hace commit.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any


class FakeResult:
    """Imita el Result de SQLAlchemy: solo lo que usa la capa de datos."""

    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = list(rows)

    def mappings(self) -> FakeResult:
        return self

    def first(self) -> Mapping[str, Any] | None:
        return self._rows[0] if self._rows else None

    def one(self) -> Mapping[str, Any]:
        if len(self._rows) != 1:
            raise AssertionError("se esperaba exactamente una fila")
        return self._rows[0]


class FakeSession:
    """`results[i]` son las filas que devuelve la llamada i; sin entrada, ninguna fila."""

    def __init__(self, *results: Sequence[Mapping[str, Any]]) -> None:
        self._results = list(results)
        self.calls: list[tuple[Any, Mapping[str, Any] | None]] = []
        self.commits = 0

    def exec(self, statement: Any, *, params: Mapping[str, Any] | None = None) -> FakeResult:
        index = len(self.calls)
        self.calls.append((statement, params))
        rows = self._results[index] if index < len(self._results) else []
        return FakeResult(rows)

    def execute(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        raise AssertionError("usar Session.exec (Session.execute está obsoleto en SQLModel)")

    def commit(self) -> None:  # pragma: no cover
        self.commits += 1


def normalized_sql(statement: Any) -> str:
    """SQL en minúsculas con los espacios colapsados, para comparar fragmentos."""
    return re.sub(r"\s+", " ", str(statement)).strip().lower()


def assert_bound_only(statement: Any, params: Mapping[str, Any] | None) -> None:
    """Los valores viajan como parámetros: el SQL no los contiene y no hay formateo Python."""
    sql = str(statement)
    assert "{" not in sql
    assert "%" not in sql
    assert params is not None
    assert set(statement._bindparams) == set(params)
    for value in params.values():
        if isinstance(value, str) and value:
            assert value not in sql
        elif value is not None and not isinstance(value, bool):
            assert str(value) not in sql
