"""`app.services.thresholds.get_thresholds`: lector compartido de los umbrales (RN-XI-07).

Lee el archivo de `get_settings().thresholds_path` (`RUTA_UMBRALES`) una sola vez por proceso y
lo convierte con `app.domain.states.parse_thresholds`. Sin base ni red.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domain import states
from app.services import thresholds as service


@pytest.fixture(autouse=True)
def clear_cache():
    service.get_thresholds.cache_clear()
    yield
    service.get_thresholds.cache_clear()


def test_reads_configured_file_and_is_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = json.loads(service.get_settings().thresholds_path.read_text(encoding="utf-8"))
    raw["referencia"]["ventana_promedio_dias"] = 14
    custom = tmp_path / "umbrales.json"
    custom.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(thresholds_path=custom))

    first = service.get_thresholds()
    assert first.window_days == 14
    custom.write_text("no es json", encoding="utf-8")
    assert service.get_thresholds() is first  # en caché: no vuelve a leer


def test_default_is_the_config_file() -> None:
    path = service.get_settings().thresholds_path
    assert path.parts[-2:] == ("config_files", "umbrales-estado.v1.json")
    expected = states.parse_thresholds(json.loads(path.read_text(encoding="utf-8")))
    assert service.get_thresholds() == expected
    assert expected.window_days == 30 and expected.min_days_with_data == 7


def test_invalid_file_raises_value_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom = tmp_path / "umbrales.json"
    custom.write_text(json.dumps({"referencia": {}}), encoding="utf-8")
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(thresholds_path=custom))
    with pytest.raises(ValueError):
        service.get_thresholds()
