"""Configuración común de las pruebas: sin base de datos real y sin leer `.env`."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app

ENV_VARS = (
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWKS_URL",
    "SUPABASE_JWT_SECRET",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_REMITENTE",
    "APP_ENLACE_INVITACION",
    "ZONA_HORARIA",
    "RUTA_UMBRALES",
    "RUTA_TEXTOS_BACKEND",
    "CORS_ORIGENES",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Cada prueba empieza sin las variables de la especificación §8."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    """Configuración con los valores por defecto, sin leer ningún `.env` local."""
    return Settings(_env_file=None)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    """Cliente de prueba de la app, sin conexión a la base."""
    return TestClient(create_app(settings))
