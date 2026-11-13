"""Errores de la API con la forma del contrato: {codigo, mensaje, detalles}.

`CodigoError` copia el enum del contrato docs/api/zentheris-api-v0.2.5.yaml; sus
valores no se traducen (DC-62).
"""

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class CodigoError(StrEnum):
    """Códigos de error del contrato 0.2.5 (enum `CodigoError`)."""

    FICHA_NO_CREADA = "FICHA_NO_CREADA"
    FICHA_EXISTENTE = "FICHA_EXISTENTE"
    NO_ES_ADMINISTRADOR = "NO_ES_ADMINISTRADOR"
    SIN_PERMISO_VER_CONSUMO = "SIN_PERMISO_VER_CONSUMO"
    SIN_PERMISO_VER_HISTORIAL = "SIN_PERMISO_VER_HISTORIAL"
    SIN_PERMISO_RECIBIR_ALERTAS = "SIN_PERMISO_RECIBIR_ALERTAS"
    SIN_PERMISO_MODIFICAR_METAS = "SIN_PERMISO_MODIFICAR_METAS"
    ADMIN_DEBE_TRANSFERIR = "ADMIN_DEBE_TRANSFERIR"
    MEMBRESIA_ACTIVA_EXISTENTE = "MEMBRESIA_ACTIVA_EXISTENTE"
    LIMITE_MIEMBROS = "LIMITE_MIEMBROS"
    INVITACION_EXPIRADA = "INVITACION_EXPIRADA"
    INVITACION_NO_PENDIENTE = "INVITACION_NO_PENDIENTE"
    INVITACION_PENDIENTE_EXISTENTE = "INVITACION_PENDIENTE_EXISTENTE"
    YA_ES_MIEMBRO = "YA_ES_MIEMBRO"
    CORREO_NO_COINCIDE = "CORREO_NO_COINCIDE"
    ZONAS_NO_PERMITIDAS = "ZONAS_NO_PERMITIDAS"
    ZONAS_BASICAS_FALTANTES = "ZONAS_BASICAS_FALTANTES"
    CANTIDAD_ZONAS_INVALIDA = "CANTIDAD_ZONAS_INVALIDA"
    ZONAS_DUPLICADAS = "ZONAS_DUPLICADAS"
    VIGENCIA_NO_POSTERIOR = "VIGENCIA_NO_POSTERIOR"
    CONTRASENA_ACTUAL_INCORRECTA = "CONTRASENA_ACTUAL_INCORRECTA"
    CONTRASENA_NO_CUMPLE_REGLAS = "CONTRASENA_NO_CUMPLE_REGLAS"
    CONTRASENA_IGUAL_A_ACTUAL = "CONTRASENA_IGUAL_A_ACTUAL"
    ADMIN_UNICO_MIEMBRO = "ADMIN_UNICO_MIEMBRO"
    BACKFILL_FALLIDO = "BACKFILL_FALLIDO"
    VALIDACION = "VALIDACION"


class ErrorResponse(BaseModel):
    """Cuerpo de error del contrato (esquema `Error`)."""

    codigo: CodigoError
    mensaje: str
    detalles: dict[str, Any] | None = None


class ApiError(Exception):
    """Error de negocio que la API devuelve con su código HTTP y su `codigo`."""

    def __init__(
        self,
        status_code: int,
        codigo: CodigoError,
        mensaje: str,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.status_code = status_code
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles


def _error_body(codigo: CodigoError, mensaje: str, detalles: dict[str, Any] | None) -> dict:
    return ErrorResponse(codigo=codigo, mensaje=mensaje, detalles=detalles).model_dump(
        mode="json"
    )


async def _handle_api_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.codigo, exc.mensaje, exc.detalles),
    )


async def _handle_validation_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Solo la ubicación y el mensaje de cada campo; no se repite lo que envió el cliente.
    campos = [
        {"ubicacion": [str(part) for part in error.get("loc", ())], "mensaje": error.get("msg")}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_body(
            CodigoError.VALIDACION, "Los datos enviados no cumplen las reglas.", {"campos": campos}
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Registra los manejadores que devuelven {codigo, mensaje, detalles}."""
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    # TODO(contrato): el contrato 0.2.5 no tiene un `CodigoError` para el error 500
    # genérico. Cuando se decida, agregar aquí el manejador de `Exception` sin exponer
    # la excepción interna (guía 3 §7, prueba S-01).
