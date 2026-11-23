"""Arranque de la app: qué registros salen por la consola.

- Los INFO de `app.*` salen una sola vez (por ejemplo, los tiempos del onboarding, DC-33), aunque
  `create_app` se llame varias veces, y no se repiten si la raíz ya tiene manejadores.
- El log de httpx no escribe las URL de Supabase (llevan el id del usuario).
"""

import io
import logging
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from app.config import Settings
from app.main import create_app

NAME = "app.services.onboarding"
MESSAGE = "Onboarding creado: zonas=9"
LIBRARIES = ("httpx", "httpcore", "sqlalchemy", "apscheduler")


def make_app() -> None:
    create_app(Settings(_env_file=None))


@pytest.fixture(autouse=True)
def app_logger() -> Iterator[logging.Logger]:
    """El logger `app` como en un proceso nuevo; al terminar, queda como estaba."""
    logger = logging.getLogger("app")
    handlers, level = logger.handlers[:], logger.level
    logger.handlers[:] = []
    logger.setLevel(logging.NOTSET)
    yield logger
    logger.handlers[:] = handlers
    logger.setLevel(level)


@contextmanager
def bare_root() -> Iterator[logging.Logger]:
    """La raíz como con uvicorn: WARNING y sin manejadores.

    No es un fixture: pytest pone sus manejadores en la raíz al empezar el cuerpo de la prueba.
    """
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers[:] = []
    root.setLevel(logging.WARNING)
    try:
        yield root
    finally:
        root.handlers[:] = handlers
        root.setLevel(level)


# --- INFO de app.* ------------------------------------------------------------------------


def test_info_is_hidden_before_create_app(capsys: pytest.CaptureFixture[str]) -> None:
    """El punto de partida: sin `create_app`, los INFO de `app.*` no salen."""
    with bare_root():
        logging.getLogger(NAME).info(MESSAGE)
    assert capsys.readouterr() == ("", "")


def test_info_of_app_is_printed_once(capsys: pytest.CaptureFixture[str]) -> None:
    with bare_root():
        make_app()
        logging.getLogger(NAME).info(MESSAGE)
    assert capsys.readouterr() == ("", f"INFO {NAME}: {MESSAGE}\n")


def test_creating_the_app_twice_does_not_duplicate_the_line(
    app_logger: logging.Logger, capsys: pytest.CaptureFixture[str]
) -> None:
    with bare_root():
        make_app()
        make_app()
        logging.getLogger(NAME).info(MESSAGE)
    assert capsys.readouterr().err.count(MESSAGE) == 1
    assert len(app_logger.handlers) == 1


def test_errors_are_printed_once_with_their_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    """El manejador sustituye al de último recurso de `logging`: el error no sale dos veces."""
    with bare_root():
        make_app()
        try:
            raise RuntimeError("fallo de prueba")
        except RuntimeError:
            logging.getLogger("app.errors").exception("Error interno")
    err = capsys.readouterr().err
    assert err.count("ERROR app.errors: Error interno") == 1
    assert err.count("RuntimeError: fallo de prueba") == 1


def test_debug_of_app_is_not_printed(capsys: pytest.CaptureFixture[str]) -> None:
    with bare_root():
        make_app()
        logging.getLogger(NAME).debug(MESSAGE)
    assert capsys.readouterr() == ("", "")


def test_a_level_set_before_is_kept(app_logger: logging.Logger) -> None:
    app_logger.setLevel(logging.DEBUG)
    make_app()
    assert app_logger.level == logging.DEBUG


# --- la raíz con manejadores propios --------------------------------------------------------


@pytest.mark.parametrize("root_first", [True, False], ids=["raiz-antes", "raiz-despues"])
def test_root_handlers_do_not_duplicate_the_line(
    capsys: pytest.CaptureFixture[str], root_first: bool
) -> None:
    """Si la raíz ya escribe (antes o después de crear la app), la línea sale solo por ella."""
    stream = io.StringIO()
    with bare_root() as root:
        if not root_first:
            make_app()
        root.addHandler(logging.StreamHandler(stream))
        if root_first:
            make_app()
        logging.getLogger(NAME).info(MESSAGE)
    assert stream.getvalue() == f"{MESSAGE}\n"
    assert capsys.readouterr() == ("", "")


def test_caplog_still_sees_the_records(
    app_logger: logging.Logger, caplog: pytest.LogCaptureFixture
) -> None:
    make_app()
    make_app()
    logging.getLogger(NAME).info(MESSAGE)
    assert caplog.record_tuples == [(NAME, logging.INFO, MESSAGE)]
    assert app_logger.propagate


# --- otras librerías ------------------------------------------------------------------------


def test_root_and_other_libraries_stay_as_they_were(capsys: pytest.CaptureFixture[str]) -> None:
    with bare_root() as root:
        before = {name: logging.getLogger(name).handlers[:] for name in LIBRARIES}
        make_app()
        assert root.level == logging.WARNING
        assert root.handlers == []
        for name in LIBRARIES:
            logger = logging.getLogger(name)
            assert logger.handlers == before[name]
            assert not logger.isEnabledFor(logging.INFO), name
            logger.info("INFO de otra librería")
    assert capsys.readouterr() == ("", "")


def test_create_app_raises_httpx_logger_to_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    httpx_logger = logging.getLogger("httpx")
    monkeypatch.setattr(httpx_logger, "level", logging.NOTSET)
    make_app()
    assert httpx_logger.level == logging.WARNING
    assert not httpx_logger.isEnabledFor(logging.INFO)
