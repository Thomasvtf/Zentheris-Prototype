"""Pruebas del endpoint de salud."""

from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_raiz_responde():
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert "Zentheris" in respuesta.json()["mensaje"]


def test_salud_responde_ok():
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}