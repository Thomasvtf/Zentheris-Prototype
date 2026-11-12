"""Configuración de la API leída de variables de entorno.

Las variables son las de docs/supabase/especificacion-supabase-v1.md §8 y la guía de
claves v3. Ninguna es obligatoria al importar: si falta una, el error aparece solo
cuando se usa (por ejemplo, la base de datos). Los valores reales viven en `api/.env`
(local, fuera de git) o en el panel de Render; aquí no se guarda ninguna clave.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Variables de entorno del backend. Los nombres de las variables no se traducen."""

    model_config = SettingsConfigDict(
        env_file=API_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: SecretStr | None = Field(default=None, validation_alias="DATABASE_URL")
    supabase_url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_service_role_key: SecretStr | None = Field(
        default=None, validation_alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_jwks_url: str | None = Field(default=None, validation_alias="SUPABASE_JWKS_URL")
    supabase_jwt_secret: SecretStr | None = Field(
        default=None, validation_alias="SUPABASE_JWT_SECRET"
    )

    smtp_host: str | None = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, validation_alias="SMTP_USER")
    smtp_password: SecretStr | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_sender: str | None = Field(default=None, validation_alias="SMTP_REMITENTE")

    invitation_link_base: str = Field(
        default="zentheris://invitacion?token=", validation_alias="APP_ENLACE_INVITACION"
    )
    timezone: str = Field(default="America/Bogota", validation_alias="ZONA_HORARIA")
    thresholds_path: Path = Field(
        default=Path("app/config_files/umbrales-estado.v1.json"),
        validation_alias="RUTA_UMBRALES",
    )
    backend_texts_path: Path = Field(
        default=Path("app/config_files/textos-backend.es-CO.json"),
        validation_alias="RUTA_TEXTOS_BACKEND",
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:8081"], validation_alias="CORS_ORIGENES"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        """Acepta `CORS_ORIGENES` como lista separada por comas."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("thresholds_path", "backend_texts_path", mode="after")
    @classmethod
    def resolve_from_api_dir(cls, value: Path) -> Path:
        """Las rutas `RUTA_*` son relativas a la carpeta `api/` (guía de claves v3)."""
        return value if value.is_absolute() else API_DIR / value


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración una sola vez por proceso."""
    return Settings()
