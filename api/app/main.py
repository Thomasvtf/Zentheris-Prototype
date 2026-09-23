"""Punto de entrada de la API de Zentheris."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import Depends, HTTPException
from sqlmodel import Session, text

from app.database import get_session

app = FastAPI(
    title="Zentheris API",
    description="API de monitoreo y optimizacion del consumo energetico",
    version="0.1.0",
)

# Permite que la app movil consuma la API durante el desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def raiz():
    """Mensaje de bienvenida."""
    return {"mensaje": "Zentheris API funcionando", "version": "0.1.0"}


@app.get("/salud")
def salud():
    """Verifica que el servicio este activo."""
    return {"estado": "ok"}






@app.get("/salud/bd")
def salud_bd(session: Session = Depends(get_session)):
    """Verifica la conexion con Supabase."""
    try:
        resultado = session.exec(text("select count(*) from zonas")).one()
        return {"base_de_datos": "conectada", "zonas_registradas": resultado[0]}
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Sin conexion: {error}")