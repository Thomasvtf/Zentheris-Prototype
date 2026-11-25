"""Arranque y apagado de la app: la tarea programada de generación horaria (RN-IV-05, DC-34).

`create_app` registra un `lifespan` que, al arrancar, carga y valida los umbrales (RN-XI-07) y
los textos del backend (RN-XI-09, DC-24) y luego llama `scheduler.start_scheduler(settings)`; al
apagar, `scheduler.stop_scheduler(<lo devuelto>)`. Las funciones del planificador se reemplazan
por dobles: ninguna prueba abre hilos ni conexiones reales.
"""

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app
from app.services import backend_texts, scheduler, thresholds

HEALTH_PATH = "/api/v1/salud"
# Marca dentro de los archivos inválidos: no debe salir en el error ni en el log.
PRIVATE_MARK = "CONTENIDO-DEL-ARCHIVO-NO-DEBE-SALIR"


# Los cargadores reales (con caché), guardados antes de que una prueba los reemplace.
CACHED_LOADERS = (thresholds.get_thresholds, backend_texts.get_backend_texts)


@pytest.fixture(autouse=True)
def fresh_config_loaders() -> Iterator[None]:
    """Cada prueba lee los archivos de nuevo: los cargadores guardan el resultado por proceso."""
    for loader in CACHED_LOADERS:
        loader.cache_clear()
    yield
    for loader in CACHED_LOADERS:
        loader.cache_clear()


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


# --- validación de los archivos de configuración al arrancar ----------------------------------


def point_to(monkeypatch: pytest.MonkeyPatch, variable: str, path: Path) -> None:
    """Hace que `get_settings()` (la que leen los cargadores) apunte `variable` a `path`."""
    monkeypatch.setenv(variable, str(path))
    get_settings.cache_clear()


def test_startup_loads_the_real_thresholds_and_backend_texts(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, running_scheduler: object
) -> None:
    install(monkeypatch, running_scheduler)

    with TestClient(create_app(settings)) as client:
        assert client.get(HEALTH_PATH).status_code == 200
        # Quedan cargados: los servicios reciben lo mismo que se validó al arrancar.
        assert thresholds.get_thresholds.cache_info().currsize == 1
        assert backend_texts.get_backend_texts.cache_info().currsize == 1


def test_config_files_are_validated_before_the_scheduler_starts(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, running_scheduler: object
) -> None:
    calls: list[str] = []
    real_thresholds = thresholds.get_thresholds
    real_texts = backend_texts.get_backend_texts
    monkeypatch.setattr(
        thresholds, "get_thresholds", lambda: calls.append("umbrales") or real_thresholds()
    )
    monkeypatch.setattr(
        backend_texts, "get_backend_texts", lambda: calls.append("textos") or real_texts()
    )
    monkeypatch.setattr(
        scheduler, "start_scheduler", lambda _settings: calls.append("planificador")
    )
    monkeypatch.setattr(scheduler, "stop_scheduler", lambda _running: None)

    with TestClient(create_app(settings)):
        pass

    assert calls == ["umbrales", "textos", "planificador"]


INVALID_FILES = {
    "umbrales sin claves": ("RUTA_UMBRALES", json.dumps({"marca": PRIVATE_MARK})),
    "umbrales que no son JSON": ("RUTA_UMBRALES", f"{{{PRIVATE_MARK}"),
    "textos sin plantillas": ("RUTA_TEXTOS_BACKEND", json.dumps({"alertas": PRIVATE_MARK})),
    "textos que no son JSON": ("RUTA_TEXTOS_BACKEND", f"[{PRIVATE_MARK}"),
}


@pytest.mark.parametrize(("variable", "content"), INVALID_FILES.values(), ids=INVALID_FILES)
def test_an_invalid_config_file_stops_the_startup_without_exposing_it(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    settings: Settings,
    running_scheduler: object,
    variable: str,
    content: str,
) -> None:
    invalid = tmp_path / "invalido.json"
    invalid.write_text(content, encoding="utf-8")
    point_to(monkeypatch, variable, invalid)
    double = install(monkeypatch, running_scheduler)

    with (
        caplog.at_level(logging.ERROR, logger="app.main"),
        pytest.raises(RuntimeError) as raised,
        TestClient(create_app(settings)),
    ):
        pytest.fail("la app no debía arrancar")

    assert variable in str(raised.value)
    assert PRIVATE_MARK not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__
    assert any(variable in record.getMessage() for record in caplog.records)
    assert PRIVATE_MARK not in caplog.text
    assert double.starts == []
    assert double.stops == []


def test_a_missing_config_file_stops_the_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, settings: Settings, running_scheduler: object
) -> None:
    point_to(monkeypatch, "RUTA_TEXTOS_BACKEND", tmp_path / "no-existe.json")
    double = install(monkeypatch, running_scheduler)

    with pytest.raises(RuntimeError, match="RUTA_TEXTOS_BACKEND"), TestClient(create_app(settings)):
        pytest.fail("la app no debía arrancar")

    assert double.starts == []
