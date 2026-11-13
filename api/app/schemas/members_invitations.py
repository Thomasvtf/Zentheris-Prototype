"""Esquemas del contrato 0.2.5 · Etiqueta «Miembros e invitaciones».

Los nombres de clases y campos son los del contrato (no se traducen, DC-62).
Generado una vez desde docs/api/zentheris-api-v0.2.5.yaml y revisado a mano."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import Rol
from app.schemas.households import Permisos


class Miembro(BaseModel):
    """Esquema `Miembro` del contrato."""

    membresia_id: UUID
    usuario_id: UUID
    nombre_completo: str
    avatar_url: str | None
    rol: Rol
    estado: Literal['activo']
    fecha_ingreso: datetime


class InvitacionPendiente(BaseModel):
    """Esquema `InvitacionPendiente` del contrato."""

    id: UUID
    correo_invitado: EmailStr
    estado: Literal['pendiente']
    expira_en: datetime


class MiembrosHogar(BaseModel):
    """Esquema `MiembrosHogar` del contrato."""

    miembros_activos: int = Field(ge=1, le=5)
    miembros: list[Miembro]
    invitaciones_pendientes: list[InvitacionPendiente] | None
    permisos: Permisos
    puede_gestionar: bool


class InvitacionCrear(BaseModel):
    """Esquema `InvitacionCrear` del contrato."""

    model_config = ConfigDict(extra="forbid")

    correo_invitado: EmailStr


class InvitacionToken(BaseModel):
    """Esquema `InvitacionToken` del contrato."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1)


class InvitacionRecibida(BaseModel):
    """Esquema `InvitacionRecibida` del contrato."""

    id: UUID
    hogar_nombre: str
    invitado_por_nombre: str
    expira_en: datetime


class InvitacionesRecibidasLista(BaseModel):
    """Respuesta 200 de `listarInvitacionesRecibidas` (objeto en línea en el contrato)."""

    invitaciones: list[InvitacionRecibida]
