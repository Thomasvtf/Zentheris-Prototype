"""Pruebas de app.data.supabase_admin sin red (RN-IX-09, RN-I-02, DC-36, DC-43).

httpx.MockTransport reemplaza la red: se comprueban la URL, el método, las cabeceras con la
clave de servicio, el cuerpo de Storage, el 404 de Auth solo con `user_not_found`, el 404 de
Storage como error, la exigencia de https, los errores convertidos en SupabaseAdminError y que
la clave nunca aparece en los logs ni en el mensaje del error.
"""

import inspect
import json
import logging
from collections.abc import Callable
from uuid import UUID, uuid4

import httpx
import pytest

from app.config import Settings
from app.data import supabase_admin
from app.data.supabase_admin import (
    AVATAR_BUCKET,
    AVATAR_EXTENSIONS,
    TIMEOUT_SECONDS,
    SupabaseAdminError,
    delete_auth_user,
    delete_avatar_files,
)

FAKE_URL = "https://proyecto-prueba.supabase.co"
FAKE_SERVICE_KEY = "clave-de-servicio-falsa-solo-para-pruebas"

Operation = Callable[[Settings, UUID], None]
OPERATIONS: list[Operation] = [delete_auth_user, delete_avatar_files]


def _settings(url: str | None = FAKE_URL, key: str | None = FAKE_SERVICE_KEY) -> Settings:
    """Configuración aislada: no lee api/.env."""
    values: dict[str, str] = {}
    if url is not None:
        values["SUPABASE_URL"] = url
    if key is not None:
        values["SUPABASE_SERVICE_ROLE_KEY"] = key
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


class Recorder:
    """Transporte falso: guarda las peticiones y responde con lo que diga `handler`."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las variables del entorno real no se cuelan en Settings."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Recorder]:
    """Instala un MockTransport en el cliente del módulo y devuelve el registrador."""

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> Recorder:
        recorder = Recorder(handler)
        monkeypatch.setattr(
            supabase_admin,
            "_build_client",
            lambda: httpx.Client(transport=httpx.MockTransport(recorder)),
        )
        return recorder

    return install


def _status(code: int, body: object = None) -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(code, json=body if body is not None else {})


def test_constants() -> None:
    assert AVATAR_BUCKET == "avatares"
    assert AVATAR_EXTENSIONS == ("jpg", "png", "webp")
    assert TIMEOUT_SECONDS == 10.0


# --- delete_auth_user ------------------------------------------------------------------------


@pytest.mark.parametrize("code", [200, 204])
def test_delete_auth_user_sends_admin_delete(
    no_network: Callable[..., Recorder], code: int
) -> None:
    usuario_id = uuid4()
    recorder = no_network(lambda request: httpx.Response(code))

    delete_auth_user(_settings(url=FAKE_URL + "/"), usuario_id)

    assert len(recorder.requests) == 1
    request = recorder.requests[0]
    assert request.method == "DELETE"
    assert str(request.url) == f"{FAKE_URL}/auth/v1/admin/users/{usuario_id}"
    assert request.headers["apikey"] == FAKE_SERVICE_KEY
    assert request.headers["Authorization"] == f"Bearer {FAKE_SERVICE_KEY}"


def test_delete_auth_user_treats_404_user_not_found_as_already_deleted(
    no_network: Callable[..., Recorder],
) -> None:
    """Idempotente: si la cuenta ya no existía, reintentar eliminarCuenta no falla."""
    recorder = no_network(
        _status(404, {"code": 404, "error_code": "user_not_found", "msg": "User not found"})
    )

    delete_auth_user(_settings(), uuid4())

    assert len(recorder.requests) == 1


@pytest.mark.parametrize(
    "make_response",
    [
        lambda: httpx.Response(404, json={"msg": "User not found"}),
        lambda: httpx.Response(404, json={"error_code": "not_found"}),
        lambda: httpx.Response(404, json=["user_not_found"]),
        lambda: httpx.Response(404, text="<html>404 Not Found</html>"),
        lambda: httpx.Response(404),
    ],
    ids=["sin-error_code", "otro-error_code", "json-no-objeto", "html", "sin-cuerpo"],
)
def test_delete_auth_user_other_404_is_an_error(
    no_network: Callable[..., Recorder], make_response: Callable[[], httpx.Response]
) -> None:
    """Un 404 ajeno (p. ej., SUPABASE_URL mal configurada) no da la cuenta por borrada."""
    no_network(lambda request: make_response())

    with pytest.raises(SupabaseAdminError) as exc_info:
        delete_auth_user(_settings(), uuid4())

    message = str(exc_info.value)
    assert "404" in message
    assert "html" not in message.lower()
    assert "not found" not in message.lower()


def test_delete_auth_user_accepts_string_uuid_and_rejects_garbage(
    no_network: Callable[..., Recorder],
) -> None:
    usuario_id = uuid4()
    recorder = no_network(_status(200))

    delete_auth_user(_settings(), str(usuario_id))  # type: ignore[arg-type]
    assert str(recorder.requests[0].url).endswith(f"/admin/users/{usuario_id}")

    with pytest.raises(ValueError):
        delete_auth_user(_settings(), "../../otra-ruta")  # type: ignore[arg-type]
    assert len(recorder.requests) == 1


# --- delete_avatar_files ---------------------------------------------------------------------


@pytest.mark.parametrize("code", [200, 204])
def test_delete_avatar_files_sends_the_three_allowed_paths(
    no_network: Callable[..., Recorder], code: int
) -> None:
    """Migración 0005: solo existen {id}/avatar.jpg|png|webp en el bucket privado."""
    usuario_id = uuid4()
    recorder = no_network(lambda request: httpx.Response(code, json=[]))

    delete_avatar_files(_settings(), usuario_id)

    request = recorder.requests[0]
    assert request.method == "DELETE"
    assert str(request.url) == f"{FAKE_URL}/storage/v1/object/avatares"
    assert request.headers["apikey"] == FAKE_SERVICE_KEY
    assert request.headers["Authorization"] == f"Bearer {FAKE_SERVICE_KEY}"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == {
        "prefixes": [
            f"{usuario_id}/avatar.jpg",
            f"{usuario_id}/avatar.png",
            f"{usuario_id}/avatar.webp",
        ]
    }


def test_delete_avatar_files_404_is_an_error(no_network: Callable[..., Recorder]) -> None:
    """El borrado por prefijos responde 200 aunque no haya objetos: un 404 es bucket o URL mal."""
    no_network(_status(404, {"error": "not_found", "error_code": "user_not_found"}))

    with pytest.raises(SupabaseAdminError) as exc_info:
        delete_avatar_files(_settings(), uuid4())

    assert "404" in str(exc_info.value)


# --- Errores comunes -------------------------------------------------------------------------


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("code", [400, 401, 403, 409, 500, 503])
def test_unexpected_status_raises_supabase_admin_error(
    no_network: Callable[..., Recorder],
    caplog: pytest.LogCaptureFixture,
    operation: Operation,
    code: int,
) -> None:
    usuario_id = uuid4()
    secret_body = {"msg": f"detalle interno con {FAKE_SERVICE_KEY}", "correo": "ana@example.com"}
    no_network(_status(code, secret_body))
    caplog.set_level(logging.DEBUG)

    with pytest.raises(SupabaseAdminError) as exc_info:
        operation(_settings(), usuario_id)

    message = str(exc_info.value)
    assert str(code) in message
    for leaked in (FAKE_SERVICE_KEY, "ana@example.com", "detalle interno", str(usuario_id)):
        assert leaked not in caplog.text
        assert leaked not in message


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("sin conexión"),
        httpx.ReadTimeout("tiempo agotado"),
        httpx.RemoteProtocolError("protocolo"),
        httpx.InvalidURL("URL inválida"),
    ],
    ids=["connect", "timeout", "protocol", "invalid-url"],
)
def test_network_error_raises_supabase_admin_error_without_chaining(
    no_network: Callable[..., Recorder],
    caplog: pytest.LogCaptureFixture,
    operation: Operation,
    error: Exception,
) -> None:
    usuario_id = uuid4()

    def fail(request: httpx.Request) -> httpx.Response:
        raise error

    no_network(fail)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(SupabaseAdminError) as exc_info:
        operation(_settings(), usuario_id)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    for leaked in (FAKE_SERVICE_KEY, str(usuario_id), str(error)):
        assert leaked not in caplog.text
        assert leaked not in str(exc_info.value)


def test_invalid_url_built_by_httpx_is_wrapped(no_network: Callable[..., Recorder]) -> None:
    """httpx.InvalidURL no hereda de httpx.HTTPError: también se convierte, sin encadenar."""
    assert not issubclass(httpx.InvalidURL, httpx.HTTPError)
    recorder = no_network(_status(200))

    with pytest.raises(SupabaseAdminError) as exc_info:
        delete_auth_user(_settings(url=FAKE_URL + ":puerto"), uuid4())

    assert recorder.requests == []
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize(
    ("url", "key"),
    [(None, FAKE_SERVICE_KEY), (FAKE_URL, None), (None, None), ("  ", FAKE_SERVICE_KEY)],
)
def test_missing_configuration_raises_before_any_request(
    no_network: Callable[..., Recorder],
    operation: Operation,
    url: str | None,
    key: str | None,
) -> None:
    recorder = no_network(_status(200))

    with pytest.raises(SupabaseAdminError) as exc_info:
        operation(_settings(url=url, key=key), uuid4())

    assert recorder.requests == []
    assert FAKE_SERVICE_KEY not in str(exc_info.value)


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize(
    "url",
    [
        "http://proyecto-prueba.supabase.co",
        "http://192.168.1.10:54321",
        "ftp://proyecto-prueba.supabase.co",
        "proyecto-prueba.supabase.co",
        "https://",
        "http://localhost.evil.example",
    ],
)
def test_non_https_url_is_rejected_before_any_request(
    no_network: Callable[..., Recorder], operation: Operation, url: str
) -> None:
    """La clave de servicio nunca viaja sin TLS a un host remoto."""
    recorder = no_network(_status(200, []))

    with pytest.raises(SupabaseAdminError) as exc_info:
        operation(_settings(url=url), uuid4())

    assert recorder.requests == []
    assert FAKE_SERVICE_KEY not in str(exc_info.value)


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize(
    "url",
    ["http://localhost:54321", "http://127.0.0.1:54321/", "HTTPS://Proyecto-Prueba.supabase.co"],
)
def test_local_http_and_https_urls_are_allowed(
    no_network: Callable[..., Recorder], operation: Operation, url: str
) -> None:
    """`supabase start` sirve en http://localhost o http://127.0.0.1."""
    recorder = no_network(_status(200, []))

    operation(_settings(url=url), uuid4())

    assert len(recorder.requests) == 1


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("code", [200, 500])
def test_module_writes_no_logs(
    no_network: Callable[..., Recorder],
    caplog: pytest.LogCaptureFixture,
    operation: Operation,
    code: int,
) -> None:
    """El fallo lo registra el manejador genérico o el servicio; aquí no se escribe nada."""
    no_network(_status(code, []))
    caplog.set_level(logging.DEBUG)

    try:
        operation(_settings(), uuid4())
    except SupabaseAdminError:
        pass

    assert [record for record in caplog.records if record.name.startswith("app.data")] == []
    assert FAKE_SERVICE_KEY not in caplog.text


def test_supabase_admin_error_is_internal_runtime_error() -> None:
    assert issubclass(SupabaseAdminError, RuntimeError)


def test_real_client_uses_the_fixed_timeout() -> None:
    """Sin red: solo se inspecciona el cliente que construiría el módulo."""
    with supabase_admin._build_client() as client:
        assert client.timeout == httpx.Timeout(TIMEOUT_SECONDS)


def test_timeout_is_set_only_in_the_client_factory() -> None:
    """El tiempo máximo se fija en un solo lugar: la constante y _build_client."""
    source = inspect.getsource(supabase_admin)
    assert source.count("TIMEOUT_SECONDS") == 2
