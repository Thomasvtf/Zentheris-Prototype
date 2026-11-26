"""Pruebas de app.services.email (DC-04, RN-IX-03) con smtplib falso (sin red).

Sin ninguna variable SMTP (desarrollo local): solo el enlace va al log (nunca el correo del
invitado). Configuración a medias: EmailDeliveryError y el enlace NO va al log. Con SMTP completo:
STARTTLS, login y un mensaje multipart/alternative con asunto, texto y HTML. Cualquier error de
SMTP sale como EmailDeliveryError sin la clave ni el correo.
"""

import logging
import smtplib
from email.message import EmailMessage
from typing import Any, ClassVar, Self

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.domain.formats import RenderedEmail
from app.services import email as email_service
from app.services.email import EmailDeliveryError

CORREO = "invitada@example.com"
ENLACE = "zentheris://invitacion?token=abc123_token-claro"
SECRET = "clave-smtp-super-secreta"
RENDERED = RenderedEmail(
    asunto="Ana te invitó a Casa Pérez en Zentheris",
    texto="Hola.\n\nÚnete: " + ENLACE,
    html=f'<p>Hola.</p><p><a href="{ENLACE}">Únete</a></p>',
)


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "usuario-smtp",
        "smtp_password": SecretStr(SECRET),
        "smtp_sender": "Zentheris <no-responder@example.com>",
    }
    values.update(overrides)
    # model_construct: sin leer .env ni variables del sistema.
    return Settings.model_construct(**values)


class FakeSMTP:
    """Registra cada llamada; `fail_on` hace fallar ese paso con `error`."""

    instances: ClassVar[list[FakeSMTP]] = []
    fail_on: ClassVar[str | None] = None
    error: ClassVar[Exception] = smtplib.SMTPException()

    def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
        self.calls: list[tuple[Any, ...]] = [("connect", host, port, timeout)]
        self.sent: list[EmailMessage] = []
        FakeSMTP.instances.append(self)
        self._maybe_fail("connect")

    def _maybe_fail(self, step: str) -> None:
        if FakeSMTP.fail_on == step:
            raise FakeSMTP.error

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.calls.append(("quit",))

    def starttls(self, **kwargs: Any) -> None:
        self.calls.append(("starttls", "context" in kwargs))
        self._maybe_fail("starttls")

    def login(self, user: str, password: str) -> None:
        self.calls.append(("login", user, password))
        self._maybe_fail("login")

    def send_message(self, message: EmailMessage) -> None:
        self.calls.append(("send_message",))
        self._maybe_fail("send_message")
        self.sent.append(message)


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[FakeSMTP]:
    FakeSMTP.instances = []
    FakeSMTP.fail_on = None
    # El error del servidor repite la clave: no debe llegar a EmailDeliveryError.
    FakeSMTP.error = smtplib.SMTPAuthenticationError(535, b"bad credentials " + SECRET.encode())
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    return FakeSMTP


@pytest.mark.parametrize("missing", ["smtp_host", "smtp_user", "smtp_password", "smtp_sender"])
def test_smtp_configured_needs_host_user_password_and_sender(missing: str) -> None:
    assert email_service.smtp_configured(_settings()) is True
    assert email_service.smtp_configured(_settings(**{missing: None})) is False


def test_smtp_configured_empty_password_counts_as_missing() -> None:
    assert email_service.smtp_configured(_settings(smtp_password=SecretStr(""))) is False


def test_without_smtp_logs_only_the_link_and_never_the_email(
    fake_smtp: type[FakeSMTP], caplog: pytest.LogCaptureFixture
) -> None:
    settings = _settings(smtp_host=None, smtp_user=None, smtp_password=None, smtp_sender=None)

    with caplog.at_level(logging.INFO, logger=email_service.logger.name):
        email_service.send_invitation_email(
            settings, correo_invitado=CORREO, email=RENDERED, enlace=ENLACE
        )

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1
    assert caplog.records[0].levelno == logging.INFO
    assert ENLACE in messages[0]
    assert CORREO not in messages[0]
    assert fake_smtp.instances == []  # no intenta conectar


@pytest.mark.parametrize(
    "present",
    [
        ("smtp_host",),
        ("smtp_user", "smtp_password"),
        ("smtp_host", "smtp_user", "smtp_password"),
        ("smtp_sender",),
    ],
)
def test_half_configured_smtp_is_error_and_does_not_log_the_link(
    fake_smtp: type[FakeSMTP], caplog: pytest.LogCaptureFixture, present: tuple[str, ...]
) -> None:
    missing = {"smtp_host", "smtp_user", "smtp_password", "smtp_sender"} - set(present)
    settings = _settings(**dict.fromkeys(missing))

    with (
        caplog.at_level(logging.DEBUG, logger=email_service.logger.name),
        pytest.raises(EmailDeliveryError) as caught,
    ):
        email_service.send_invitation_email(
            settings, correo_invitado=CORREO, email=RENDERED, enlace=ENLACE
        )

    logged = " ".join(record.getMessage() for record in caplog.records)
    assert ENLACE not in logged
    assert fake_smtp.instances == []  # no intenta conectar
    text = str(caught.value)
    for secret in (SECRET, CORREO, ENLACE, "usuario-smtp", "smtp.example.com"):
        assert secret not in text


def test_empty_password_with_the_rest_present_is_half_configured(
    fake_smtp: type[FakeSMTP], caplog: pytest.LogCaptureFixture
) -> None:
    with (
        caplog.at_level(logging.DEBUG, logger=email_service.logger.name),
        pytest.raises(EmailDeliveryError),
    ):
        email_service.send_invitation_email(
            _settings(smtp_password=SecretStr("")),
            correo_invitado=CORREO,
            email=RENDERED,
            enlace=ENLACE,
        )
    assert ENLACE not in " ".join(record.getMessage() for record in caplog.records)


def test_with_smtp_sends_multipart_with_starttls_and_login(
    fake_smtp: type[FakeSMTP], caplog: pytest.LogCaptureFixture
) -> None:
    settings = _settings()

    with caplog.at_level(logging.DEBUG, logger=email_service.logger.name):
        email_service.send_invitation_email(
            settings, correo_invitado=CORREO, email=RENDERED, enlace=ENLACE
        )

    (smtp,) = fake_smtp.instances
    assert smtp.calls == [
        ("connect", "smtp.example.com", 587, email_service.SMTP_TIMEOUT_SECONDS),
        ("starttls", True),
        ("login", "usuario-smtp", SECRET),
        ("send_message",),
        ("quit",),
    ]
    (message,) = smtp.sent
    assert message["Subject"] == RENDERED.asunto
    assert message["To"] == CORREO
    assert message["From"] == "Zentheris <no-responder@example.com>"
    assert message.get_content_type() == "multipart/alternative"
    parts = list(message.iter_parts())
    assert [part.get_content_type() for part in parts] == ["text/plain", "text/html"]
    assert parts[0].get_content().strip() == RENDERED.texto
    assert parts[1].get_content().strip() == RENDERED.html
    # En modo SMTP el log no lleva ni el enlace (con el token) ni el correo ni la clave.
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert ENLACE not in logged
    assert CORREO not in logged
    assert SECRET not in logged


@pytest.mark.parametrize("step", ["connect", "starttls", "login", "send_message"])
def test_smtp_error_is_email_delivery_error_without_secrets(
    fake_smtp: type[FakeSMTP], step: str
) -> None:
    fake_smtp.fail_on = step

    with pytest.raises(EmailDeliveryError) as caught:
        email_service.send_invitation_email(
            _settings(), correo_invitado=CORREO, email=RENDERED, enlace=ENLACE
        )

    text = str(caught.value)
    assert SECRET not in text
    assert CORREO not in text
    assert ENLACE not in text
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_network_error_is_email_delivery_error(
    fake_smtp: type[FakeSMTP],
) -> None:
    fake_smtp.fail_on = "connect"
    fake_smtp.error = TimeoutError("timed out")

    with pytest.raises(EmailDeliveryError, match="TimeoutError"):
        email_service.send_invitation_email(
            _settings(), correo_invitado=CORREO, email=RENDERED, enlace=ENLACE
        )
