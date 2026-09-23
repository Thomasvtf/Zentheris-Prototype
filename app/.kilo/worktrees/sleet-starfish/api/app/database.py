"""Conexion a PostgreSQL en Supabase."""
from sqlmodel import Session, create_engine
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=0,
)


def get_session():
    """Entrega una sesion de base de datos a cada peticion."""
    with Session(engine) as session:
        yield session