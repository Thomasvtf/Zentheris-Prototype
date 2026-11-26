"""Envío del correo de invitación por SMTP (Brevo, DC-04, RN-IX-03).

Sin SMTP configurado (desarrollo local, DC-04) se escribe en el log solo el ENLACE de la
invitación (api/CLAUDE.md): nunca el correo del invitado. Con SMTP se envía un mensaje
`multipart/alternative` (texto plano y HTML) con STARTTLS y tiempo de espera.

Ningún log ni mensaje de error lleva correos, claves ni hashes: `EmailDeliveryError` solo dice el
tipo del error de origen. Las variables de entorno llegan por `Settings` (app/config.py).
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import Settings
from app.domain.formats import RenderedEmail

logger = logging.getLogger(__name__)

# Segundos de espera de la conexión SMTP (conectar, STARTTLS, login y envío).
SMTP_TIMEOUT_SECONDS = 10

LOCAL_LINK_MESSAGE = "SMTP sin configurar (solo desarrollo): enlace de invitación %s"
SENT_MESSAGE = "Correo de invitación enviado por SMTP."
DELIVERY_ERROR_MESSAGE = "No se pudo enviar el correo de invitación ({error})."


class EmailDeliveryError(Exception):
    """Falló el envío por SMTP. El mensaje no lleva secretos, correos ni el enlace."""


HALF_CONFIGURED_MESSAGE = (
    "SMTP configurado a medias: faltan variables de entorno (host, usuario, clave o remitente)."
)


def _smtp_values(settings: Settings) -> tuple[bool, bool, bool, bool]:
    """Presencia de host, usuario, clave (no vacía) y remitente SMTP."""
    password = settings.smtp_password
    return (
        bool(settings.smtp_host),
        bool(settings.smtp_user),
        password is not None and bool(password.get_secret_value()),
        bool(settings.smtp_sender),
    )


def smtp_configured(settings: Settings) -> bool:
    """True si hay host, usuario, clave y remitente SMTP (DC-04)."""
    return all(_smtp_values(settings))


def smtp_absent(settings: Settings) -> bool:
    """True si no hay NINGUNA de las 4 variables SMTP: modo de desarrollo local (DC-04)."""
    return not any(_smtp_values(settings))


def send_invitation_email(
    settings: Settings, *, correo_invitado: str, email: RenderedEmail, enlace: str
) -> None:
    """Envía la invitación (RN-IX-03) o, sin SMTP, escribe el enlace en el log (DC-04).

    El enlace solo va al log cuando no hay ninguna variable SMTP (desarrollo local). Con el SMTP
    configurado a medias (p. ej. falta el remitente en Render) es un error de configuración: no se
    escribe el enlace (lleva el token en claro) y se lanza `EmailDeliveryError`.

    Raises:
        EmailDeliveryError: SMTP a medias o cualquier fallo al armar o enviar el mensaje.
    """
    if smtp_absent(settings):
        logger.info(LOCAL_LINK_MESSAGE, enlace)
        return
    if not smtp_configured(settings):
        raise EmailDeliveryError(HALF_CONFIGURED_MESSAGE)
    try:
        message = _build_message(settings, correo_invitado=correo_invitado, email=email)
        _send(settings, message)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de envío es EmailDeliveryError
        # `from None`: el error de origen puede traer el servidor, el usuario o el destinatario.
        raise EmailDeliveryError(DELIVERY_ERROR_MESSAGE.format(error=type(exc).__name__)) from None
    logger.info(SENT_MESSAGE)


def _build_message(
    settings: Settings, *, correo_invitado: str, email: RenderedEmail
) -> EmailMessage:
    """`multipart/alternative`: texto plano primero y HTML después."""
    message = EmailMessage()
    message["Subject"] = email.asunto
    message["From"] = settings.smtp_sender
    message["To"] = correo_invitado
    message.set_content(email.texto)
    message.add_alternative(email.html, subtype="html")
    return message


def _send(settings: Settings, message: EmailMessage) -> None:
    host, user, password = settings.smtp_host, settings.smtp_user, settings.smtp_password
    if host is None or user is None or password is None:
        # Inalcanzable: send_invitation_email ya comprobó smtp_configured.
        raise RuntimeError(HALF_CONFIGURED_MESSAGE)
    with smtplib.SMTP(host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(user, password.get_secret_value())
        smtp.send_message(message)
