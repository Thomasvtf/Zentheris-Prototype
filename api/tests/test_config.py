"""Pruebas de la configuración leída de variables de entorno."""

from app.config import API_DIR, Settings


def test_template_empty_values_are_treated_as_missing() -> None:
    settings = Settings(_env_file=API_DIR / ".env.example")
    assert settings.database_url is None
    assert settings.supabase_url is None
    assert settings.supabase_service_role_key is None
    assert settings.smtp_port == 587
    assert settings.cors_origins == ["http://localhost:8081"]
