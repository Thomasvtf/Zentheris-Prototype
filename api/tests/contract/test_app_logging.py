"""Arranque de la app: el log de httpx no escribe las URL de Supabase (llevan el id del usuario)."""

import logging

import pytest

from app.config import Settings
from app.main import create_app


def test_create_app_raises_httpx_logger_to_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    httpx_logger = logging.getLogger("httpx")
    monkeypatch.setattr(httpx_logger, "level", logging.NOTSET)
    create_app(Settings(_env_file=None))
    assert httpx_logger.level == logging.WARNING
    assert not httpx_logger.isEnabledFor(logging.INFO)
