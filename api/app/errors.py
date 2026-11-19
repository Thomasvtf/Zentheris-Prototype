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


# Descripciones de `components.responses` del contrato, por código HTTP.
ERROR_DESCRIPTIONS = {
    401: "Token ausente, inválido o vencido.",
    403: "El usuario no tiene el rol o el permiso necesario.",
    404: "El recurso no existe o el usuario no tiene membresía activa en ese hogar.",
    409: "La operación choca con el estado actual (límites, membresía o invitación).",
    422: "Los datos enviados no cumplen las reglas.",
    500: "Error interno. En el onboarding, `BACKFILL_FALLIDO`; no queda ningún dato creado.",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """Respuestas de error de una operación, con el esquema `Error` del contrato."""
    return {code: {"model": ErrorResponse, "description": ERROR_DESCRIPTIONS[code]} for code in codes}


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


class NotImplementedOperation(Exception):
    """TEMPORAL (esqueleto del PR 5): la operación del contrato aún no está implementada.

    Responde 501 con `{"detail": "TODO(<operationId>)"}`. El 501 no está en el contrato ni
    aparece en el OpenAPI. Se borra cuando las 40 operaciones estén implementadas.
    """

    def __init__(self, operation_id: str) -> None:
        super().__init__(operation_id)
        self.operation_id = operation_id


async def _handle_not_implemented(_request: Request, exc: Exception) -> JSONResponse:
    # TEMPORAL: ver NotImplementedOperation.
    assert isinstance(exc, NotImplementedOperation)
    return JSONResponse(status_code=501, content={"detail": f"TODO({exc.operation_id})"})


def register_error_handlers(app: FastAPI) -> None:
    """Registra los manejadores que devuelven {codigo, mensaje, detalles}."""
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    # TEMPORAL (esqueleto): 501 para las operaciones que aún no están implementadas.
    app.add_exception_handler(NotImplementedOperation, _handle_not_implemented)
    # TODO(contrato): el contrato 0.2.5 no tiene un `CodigoError` para el error 500
    # genérico. Cuando se decida, agregar aquí el manejador de `Exception` sin exponer
    # la excepción interna (guía 3 §7, prueba S-01).
