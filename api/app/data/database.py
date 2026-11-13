"""Conexión a PostgreSQL en Supabase.

El motor se crea al primer uso, no al importar: así la API arranca aunque falte
DATABASE_URL, y el error aparece solo cuando una ruta necesita la base.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine
from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Crea el motor una vez. NullPool: requerido por el Transaction Pooler (puerto 6543)."""
    database_url = get_settings().database_url
    if database_url is None:
        raise RuntimeError("Falta DATABASE_URL en las variables de entorno.")
    return create_engine(database_url.get_secret_value(), echo=False, poolclass=NullPool)


def get_session() -> Iterator[Session]:
    """Entrega una sesión de base de datos a cada petición."""
    with Session(get_engine()) as session:
        yield session
