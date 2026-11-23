"""`OnboardingCrear.nombre_hogar` sin caracteres de control (revisión de seguridad, fase 4).

Un carácter Unicode de categoría Cc da 422 `VALIDACION` antes de tocar la base: NUL no se puede
guardar en PostgreSQL y CR/LF acabaría en el asunto del correo de invitación. El resto del texto
(tildes, emoji, comillas) se acepta tal cual. El JSON Schema publicado no cambia: el contrato solo
declara `minLength: 1`.
"""

from collections.abc import Iterator
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.data.database import get_session
from app.domain.zone_rules import BASIC_ZONES
from app.main import API_PREFIX, create_app
from tests.contract.test_skeleton_matches_contract import CONTRACT_PATH, canon
from tests.helpers.auth import auth_header, install_test_jwks, make_test_settings, make_token
from tests.helpers.onboarding import USER_ID, FakeDatabase, install_fake_database

CONTRACT: dict[str, Any] = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
URL = f"{API_PREFIX}/onboarding"

CONTROL_NAMES = {
    "nul": "Casa\x00Gómez",
    "cr": "Casa\rGómez",
    "lf": "Casa\nGómez",
    "crlf-al-final": "Casa Gómez\r\n",
    "tab": "Casa\tGómez",
    "escape": "Casa\x1bGómez",
    "del": "Casa\x7fGómez",
    "c1-nel": "Casa\x85Gómez",
    "solo-control": "\x07",
}
VALID_NAMES = {
    "tildes": "Hogar Ñandú de María José",
    "emoji": "Casa 🏡 Gómez",
    "comillas": 'La "Casona"',
    "apostrofo": "Hogar d'Ángelo",
    "espacios": "  Casa  Gómez  ",
}


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> FakeDatabase:
    install_test_jwks(monkeypatch)
    return install_fake_database(monkeypatch)


@pytest.fixture
def client(db: FakeDatabase) -> Iterator[TestClient]:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_settings] = make_test_settings

    def session_override() -> Iterator[FakeDatabase]:
        yield db

    app.dependency_overrides[get_session] = session_override
    yield TestClient(app)
    app.dependency_overrides.clear()


def post(client: TestClient, name: str) -> Any:
    body = {"nombre_hogar": name, "tipo_vivienda": "apartamento", "zonas": list(BASIC_ZONES)}
    return client.post(URL, json=body, headers=auth_header(make_token(USER_ID)))


@pytest.mark.parametrize("name", CONTROL_NAMES.values(), ids=CONTROL_NAMES.keys())
def test_control_characters_are_rejected_before_the_database(
    name: str, client: TestClient, db: FakeDatabase
) -> None:
    response = post(client, name)
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["codigo"] == "VALIDACION"
    assert [campo["ubicacion"] for campo in body["detalles"]["campos"]] == [
        ["body", "nombre_hogar"]
    ]
    assert "Gómez" not in response.text  # no repite el valor enviado
    assert db.events == []
    db.assert_nothing_saved()


@pytest.mark.parametrize("name", VALID_NAMES.values(), ids=VALID_NAMES.keys())
def test_printable_names_are_saved_as_sent(name: str, client: TestClient, db: FakeDatabase) -> None:
    response = post(client, name)
    assert response.status_code == 201, response.text
    assert response.json()["nombre"] == name
    (household,) = db.saved["hogares"]
    assert household["nombre"] == name


def test_published_schema_is_still_the_contract() -> None:
    generated = create_app(Settings(_env_file=None)).openapi()["components"]["schemas"]
    expected = CONTRACT["components"]["schemas"]["OnboardingCrear"]
    assert canon(generated["OnboardingCrear"], "gen") == canon(expected, "contract")
    assert generated["OnboardingCrear"]["properties"]["nombre_hogar"] == {
        "type": "string",
        "minLength": 1,
        "title": "Nombre Hogar",
    }
