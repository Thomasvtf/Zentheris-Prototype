"""Arranque y apagado de la app: la tarea programada de generación horaria (RN-IV-05, DC-34).

`create_app` registra un `lifespan` que llama `scheduler.start_scheduler(settings)` al arrancar y
`scheduler.stop_scheduler(<lo devuelto>)` al apagar. Las funciones del planificador se reemplazan
por dobles: ninguna prueba abre hilos ni conexiones reales.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import scheduler

HEALTH_PATH = "/api/v1/salud"


@dataclass
class SchedulerDouble:
    """Registra las llamadas a start/stop y devuelve `returned` desde start."""

    returned: Any
    starts: list[Settings] = field(default_factory=list)
    stops: list[Any] = field(default_factory=list)

    def start(self, settings: Settings) -> Any:
        self.starts.append(settings)
        return self.returned

    def stop(self, running: Any) -> None:
        self.stops.append(running)


@pytest.fixture
def running_scheduler() -> object:
    """Lo que devolvería un planificador arrancado; solo importa su identidad."""
    return object()


def install(monkeypatch: pytest.MonkeyPatch, returned: Any) -> SchedulerDouble:
    double = SchedulerDouble(returned=returned)
    monkeypatch.setattr(scheduler, "start_scheduler", double.start)
    monkeypatch.setattr(scheduler, "stop_scheduler", double.stop)
    return double


def test_start_on_enter_and_stop_on_exit_with_the_same_settings(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, running_scheduler: object
) -> None:
    double = install(monkeypatch, running_scheduler)
    app = create_app(settings)
    assert double.starts == []

    with TestClient(app):
        assert len(double.starts) == 1
        assert double.starts[0] is settings
        assert double.stops == []

    assert len(double.starts) == 1
    assert len(double.stops) == 1
    assert double.stops[0] is running_scheduler


def test_without_database_start_returns_none_and_stop_receives_none(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    double = install(monkeypatch, None)

    with TestClient(create_app(settings)):
        pass

    assert double.starts == [settings]
    assert double.stops == [None]


def test_health_still_answers_while_the_scheduler_runs(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, running_scheduler: object
) -> None:
    install(monkeypatch, running_scheduler)

    with TestClient(create_app(settings)) as client:
        response = client.get(HEALTH_PATH)

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}


def test_without_the_with_block_start_is_never_called(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, running_scheduler: object
) -> None:
    """Crear la app (como `app = create_app()` al importar `app.main`) no arranca nada."""
    double = install(monkeypatch, running_scheduler)

    client = TestClient(create_app(settings))
    assert client.get(HEALTH_PATH).status_code == 200

    assert double.starts == []
    assert double.stops == []


def test_create_app_without_settings_passes_the_resolved_settings(
    monkeypatch: pytest.MonkeyPatch, running_scheduler: object
) -> None:
    """Sin argumento, start recibe la misma configuración que resolvió `create_app`."""
    resolved = Settings(_env_file=None)
    monkeypatch.setattr("app.main.get_settings", lambda: resolved)
    double = install(monkeypatch, running_scheduler)

    with TestClient(create_app()):
        pass

    assert len(double.starts) == 1
    assert double.starts[0] is resolved


def test_stop_runs_even_if_the_body_fails(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, running_scheduler: object
) -> None:
    double = install(monkeypatch, running_scheduler)

    with pytest.raises(RuntimeError), TestClient(create_app(settings)):
        raise RuntimeError("fallo de prueba")

    assert double.stops == [running_scheduler]
