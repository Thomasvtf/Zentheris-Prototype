"""Punto de entrada de la API de Zentheris."""

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import Settings, get_settings
from app.errors import ERROR_DESCRIPTIONS, register_error_handlers
from app.routers import (
    alerts_tips,
    consumption,
    goals_tariff,
    households,
    members_invitations,
    onboarding,
    system,
    users,
)

API_PREFIX = "/api/v1"
APP_LOG_HANDLER = "app.console"
ROUTERS = (
    system,
    users,
    households,
    onboarding,
    members_invitations,
    consumption,
    goals_tariff,
    alerts_tips,
)


def _contract_openapi(app: FastAPI) -> dict[str, Any]:
    """OpenAPI generado, con el 422 documentado como el esquema `Error` del contrato.

    FastAPI agrega un 422 propio (`HTTPValidationError`) a toda ruta con parámetros o cuerpo;
    la API responde ese 422 con {codigo: VALIDACION, mensaje, detalles} (errors.py).
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title, version=app.version, description=app.description, routes=app.routes
    )
    error_ref = {"$ref": "#/components/schemas/ErrorResponse"}
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            response = operation.get("responses", {}).get("422")
            if response is not None:
                response["description"] = ERROR_DESCRIPTIONS[422]
                response["content"] = {"application/json": {"schema": error_ref}}
    components = schema.get("components", {}).get("schemas", {})
    for name in ("HTTPValidationError", "ValidationError"):
        components.pop(name, None)
    app.openapi_schema = schema
    return schema


def _configure_logging() -> None:
    """Deja ver los INFO de `app.*`, que uvicorn no configura; las demás librerías no cambian.

    El manejador se reconoce por su nombre, así que varias llamadas no lo repiten. Mientras la
    raíz tenga manejadores calla: el registro se propaga y ya sale por ellos.
    """
    # httpx escribe en INFO la URL de cada llamada a Supabase (lleva el id del usuario).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logger = logging.getLogger("app")
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
    if any(handler.get_name() == APP_LOG_HANDLER for handler in logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.set_name(APP_LOG_HANDLER)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    handler.addFilter(lambda _record: not logging.getLogger().handlers)
    logger.addHandler(handler)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación con CORS, manejadores de error y routers bajo /api/v1."""
    settings = settings or get_settings()
    _configure_logging()
    app = FastAPI(
        title="Zentheris API",
        description="API de monitoreo y optimización del consumo energético",
        version="0.2.7",
        # Un solo esquema por modelo, con el nombre del contrato (sin «-Input»/«-Output»).
        separate_input_output_schemas=False,
    )
    # La app nativa no necesita CORS; la lista sirve para el navegador en desarrollo.
    # Sin cookies: la app manda el token en la cabecera Authorization.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    for module in ROUTERS:
        app.include_router(module.router, prefix=API_PREFIX)
    app.openapi = lambda: _contract_openapi(app)  # type: ignore[method-assign]
    return app


app = create_app()
