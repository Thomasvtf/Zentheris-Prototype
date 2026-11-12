"""Conexion a PostgreSQL en Supabase."""
from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # Requerido para Transaction Pooler (Puerto 6543)
)


def get_session():
    """Entrega una sesion de base de datos a cada peticion."""
    with Session(engine) as session:
        yield session