"""Sesión falsa compartida por las pruebas de app.data (sin base real).

Registra cada sentencia con sus parámetros y devuelve, por llamada, las filas fabricadas
que se le den en orden. Falla si alguien usa `Session.execute` o hace commit.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.exc import IntegrityError


class FakeResult:
    """Imita el Result de SQLAlchemy: solo lo que usa la capa de datos."""

    def __init__(self, rows: Sequence[Mapping[str, Any]] = (), *, rowcount: int = -1) -> None:
        self._rows = list(rows)
        self.rowcount = rowcount

    def mappings(self) -> FakeResult:
        return self

    def all(self) -> list[Mapping[str, Any]]:
        return list(self._rows)

    def first(self) -> Mapping[str, Any] | None:
        return self._rows[0] if self._rows else None

    def one(self) -> Mapping[str, Any]:
        if len(self._rows) != 1:
            raise AssertionError("se esperaba exactamente una fila")
        return self._rows[0]


class FakeSession:
    """`results[i]` es lo que produce la llamada i; sin entrada, ninguna fila.

    Cada entrada puede ser una lista de filas, un `FakeResult` (por ejemplo, con `rowcount`)
    o una excepción, que se lanza.
    """

    def __init__(self, *results: Sequence[Mapping[str, Any]] | FakeResult | Exception) -> None:
        self._results = list(results)
        self.calls: list[tuple[Any, Mapping[str, Any] | None]] = []
        self.commits = 0

    def exec(self, statement: Any, *, params: Mapping[str, Any] | None = None) -> FakeResult:
        index = len(self.calls)
        self.calls.append((statement, params))
        result = self._results[index] if index < len(self._results) else []
        if isinstance(result, Exception):
            raise result
        return result if isinstance(result, FakeResult) else FakeResult(result)

    def execute(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        raise AssertionError("usar Session.exec (Session.execute está obsoleto en SQLModel)")

    def commit(self) -> None:  # pragma: no cover
        self.commits += 1


def normalized_sql(statement: Any) -> str:
    """SQL en minúsculas con los espacios colapsados, para comparar fragmentos."""
    return re.sub(r"\s+", " ", str(statement)).strip().lower()


def assert_bound_only(statement: Any, params: Mapping[str, Any] | None) -> None:
    """Los valores viajan como parámetros: el SQL no los contiene y no hay formateo Python.

    En las inserciones por lotes el parámetro es una lista: se comprueba cada elemento.
    """
    sql = str(statement)
    assert "{" not in sql
    assert "%" not in sql
    assert params is not None
    assert set(statement._bindparams) == set(params)
    for param in params.values():
        for value in param if isinstance(param, list) else [param]:
            if isinstance(value, str) and value:
                assert value not in sql
            elif value is not None and not isinstance(value, bool):
                assert str(value) not in sql


class FakeDiag:
    """Imita `psycopg2` `exc.diag`: solo el nombre de la restricción."""

    def __init__(self, constraint_name: str | None) -> None:
        self.constraint_name = constraint_name


class FakeDriverError(Exception):
    """Imita la excepción de psycopg2: `pgcode`, `diag` (si viene) y el mensaje de Postgres."""

    def __init__(
        self, pgcode: str | None, *, message: str = "", diag: FakeDiag | None = None
    ) -> None:
        super().__init__(message)
        self.pgcode = pgcode
        if diag is not None:
            self.diag = diag


def integrity_error(orig: Exception, statement: str = "insert ...") -> IntegrityError:
    """IntegrityError de SQLAlchemy que envuelve `orig`, como la lanzaría `Session.exec`."""
    return IntegrityError(statement, {}, orig)
