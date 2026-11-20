"""Pruebas del motor de app.data.database sin conectarse a ninguna base.

create_engine no abre conexión hasta el primer uso, así que basta con inspeccionar
el motor creado con una URL local de prueba (sin credenciales).
"""

from collections.abc import Iterator

import pytest
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.data import database

TEST_DATABASE_URL = "postgresql+psycopg2://localhost:5432/zentheris_prueba"


@pytest.fixture
def test_engine_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Configuración aislada (sin leer api/.env) y caché de get_engine limpia antes y después."""
    settings = Settings(_env_file=None, DATABASE_URL=TEST_DATABASE_URL)
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    database.get_engine.cache_clear()
    yield
    database.get_engine.cache_clear()


@pytest.mark.usefixtures("test_engine_settings")
def test_engine_hides_sql_parameters_in_errors() -> None:
    """S-01: los valores de los parámetros no aparecen en los errores ni en los logs."""
    engine = database.get_engine()

    assert engine.hide_parameters is True


@pytest.mark.usefixtures("test_engine_settings")
def test_engine_keeps_null_pool_for_transaction_pooler() -> None:
    engine = database.get_engine()

    assert isinstance(engine.pool, NullPool)


def test_engine_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None)
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    database.get_engine.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            database.get_engine()
    finally:
        database.get_engine.cache_clear()
