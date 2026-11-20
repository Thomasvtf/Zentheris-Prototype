"""Errores de la API con la forma del contrato: {codigo, mensaje, detalles}.

`CodigoError` copia el enum del contrato docs/api/zentheris-api.yaml; sus
valores no se traducen (DC-62). Ningún manejador devuelve el texto, el tipo ni la traza
de una excepción interna (guía 3 §7, prueba S-01).

Códigos genéricos (DC-16): 401 `NO_AUTENTICADO` (con `WWW-Authenticate: Bearer`, DC-44),
404 `NO_ENCONTRADO` (también sin membresía activa, RN-I-03, y rutas inexistentes) y 500
`ERROR_INTERNO`. Su `mensaje` es una descripción técnica corta (`*_MESSAGE`); la app resuelve
el texto para el usuario con `codigo`. `ERROR_DESCRIPTIONS` solo alimenta `responses=` del
OpenAPI.
"""

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class CodigoError(StrEnum):
    """Códigos de error del contrato (enum `CodigoError`)."""

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
    NO_AUTENTICADO = "NO_AUTENTICADO"
    NO_ENCONTRADO = "NO_ENCONTRADO"
    ERROR_INTERNO = "ERROR_INTERNO"


class ErrorResponse(BaseModel):
    """Cuerpo de error del contrato (esquema `Error`)."""

    codigo: CodigoError
    mensaje: str
    detalles: dict[str, Any] | None = None


# Mensajes técnicos cortos de los errores genéricos (el contrato define `mensaje` como
# descripción técnica). Los usan el 401 de `current_user`, el 404 de `membership` y de las
# rutas inexistentes, y el 500 genérico.
UNAUTHORIZED_MESSAGE = "Token ausente, inválido o vencido."
NOT_FOUND_MESSAGE = "Recurso no encontrado."
INTERNAL_ERROR_MESSAGE = "Error interno."

# Descripciones de `components.responses` del contrato, por código HTTP. Solo para
# `responses=` del OpenAPI, no para el cuerpo de las respuestas genéricas.
ERROR_DESCRIPTIONS = {
    401: "Token ausente, inválido o vencido (`codigo` = `NO_AUTENTICADO`).",
    403: "El usuario no tiene el rol o el permiso necesario.",
    404: "El recurso no existe o el usuario no tiene membresía activa en ese hogar (`codigo` = `NO_ENCONTRADO`).",
    409: "La operación choca con el estado actual (límites, membresía o invitación).",
    422: "Los datos enviados no cumplen las reglas.",
    500: "Error interno (`codigo` = `ERROR_INTERNO`). En `POST /onboarding` el código es `BACKFILL_FALLIDO` y no queda ningún dato creado.",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """Respuestas de error de una operación, con el esquema `Error` del contrato."""
    return {
        code: {"model": ErrorResponse, "description": ERROR_DESCRIPTIONS[code]} for code in codes
    }


class ApiError(Exception):
    """Error de negocio que la API devuelve con su código HTTP y su `codigo`."""

    def __init__(
        self,
        status_code: int,
        codigo: CodigoError,
        mensaje: str,
        detalles: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.status_code = status_code
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalles = detalles
        self.headers = headers


def _error_body(codigo: CodigoError, mensaje: str, detalles: dict[str, Any] | None) -> dict:
    return ErrorResponse(codigo=codigo, mensaje=mensaje, detalles=detalles).model_dump(mode="json")


async def _handle_api_error(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.codigo, exc.mensaje, exc.detalles),
        headers=exc.headers,
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


def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """500 `ERROR_INTERNO`: la excepción va al log, nunca a la respuesta (S-01)."""
    # Plantilla de la ruta (`/hogares/{hogar_id}/...`), no la URL: sin valores del cliente.
    route = request.scope.get("route")
    path = getattr(route, "path", None) or "(ruta desconocida)"
    logger.exception("Error interno no controlado en %s %s", request.method, path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_error_body(CodigoError.ERROR_INTERNO, INTERNAL_ERROR_MESSAGE, None),
    )


async def _handle_http_exception(request: Request, exc: Exception) -> Response:
    """404 de Starlette (ruta inexistente) con la forma del contrato; el resto, por defecto."""
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content=_error_body(CodigoError.NO_ENCONTRADO, NOT_FOUND_MESSAGE, None),
            headers=exc.headers,
        )
    # TODO(pendiente: código de error para 405, no existe en CodigoError)
    return await http_exception_handler(request, exc)


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
    # Ruta inexistente → 404 `NO_ENCONTRADO`; 405 y otros, respuesta por defecto de FastAPI.
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    # TEMPORAL (esqueleto): 501 para las operaciones que aún no están implementadas.
    app.add_exception_handler(NotImplementedOperation, _handle_not_implemented)
    # 500 `ERROR_INTERNO` sin exponer la excepción interna (guía 3 §7, prueba S-01).
    app.add_exception_handler(Exception, _handle_unexpected_error)
