"""Esquemas del contrato 0.2.5 · Etiqueta «Usuario»: ficha, preferencias, contraseña y avatar.

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api-v0.2.5.yaml y revisado a mano."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.schemas.common import ReferenciaTipo, Rol


class Preferencias(BaseModel):
    """Esquema `Preferencias` del contrato."""

    notif_consumo: bool
    notif_consejos: bool
    base_comparacion: ReferenciaTipo


class PreferenciasActualizar(BaseModel):
    """Esquema `PreferenciasActualizar` del contrato."""

    model_config = ConfigDict(extra="forbid")

    notif_consumo: bool = Field(default=None)
    notif_consejos: bool = Field(default=None)
    base_comparacion: ReferenciaTipo = Field(default=None)


class MembresiaResumen(BaseModel):
    """Esquema `MembresiaResumen` del contrato."""

    membresia_id: UUID
    hogar_id: UUID
    rol: Rol


class UsuarioActual(BaseModel):
    """Esquema `UsuarioActual` del contrato."""

    id: UUID
    correo: EmailStr
    nombre_completo: str
    telefono: str | None
    avatar_url: str | None
    preferencias: Preferencias
    membresia: MembresiaResumen | None


class UsuarioCrear(BaseModel):
    """Esquema `UsuarioCrear` del contrato."""

    model_config = ConfigDict(extra="forbid")

    nombre_completo: str = Field(min_length=1)
    telefono: str | None = Field(default=None)


class UsuarioActualizar(BaseModel):
    """Esquema `UsuarioActualizar` del contrato."""

    model_config = ConfigDict(extra="forbid")

    nombre_completo: str = Field(default=None, min_length=1)
    telefono: str | None = Field(default=None)


class AvatarGuardar(BaseModel):
    """Esquema `AvatarGuardar` del contrato."""

    model_config = ConfigDict(extra="forbid")

    avatar_url: str = Field(min_length=1)


class ContrasenaVerificar(BaseModel):
    """Esquema `ContrasenaVerificar` del contrato."""

    model_config = ConfigDict(extra="forbid")

    contrasena_actual: SecretStr


class ContrasenaCambiar(BaseModel):
    """Esquema `ContrasenaCambiar` del contrato."""

    model_config = ConfigDict(extra="forbid")

    contrasena_actual: SecretStr
    contrasena_nueva: SecretStr = Field(min_length=8)
