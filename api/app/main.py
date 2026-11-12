"""Punto de entrada de la API de Zentheris."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.errors import register_error_handlers
from app.routers import system

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación con CORS, manejadores de error y routers bajo /api/v1."""
    settings = settings or get_settings()
    app = FastAPI(
        title="Zentheris API",
        description="API de monitoreo y optimización del consumo energético",
        version="0.2.5",
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
    app.include_router(system.router, prefix=API_PREFIX)
    return app


app = create_app()
