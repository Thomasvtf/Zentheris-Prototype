"""Envío del correo de invitación por SMTP (Brevo, DC-04).

Sin SMTP configurado (desarrollo local) se escribe el enlace en el log (api/CLAUDE.md).
Esqueleto: se implementa con la sesión de invitaciones.
"""


def send_invitation_email(correo_invitado: str, enlace: str) -> None:
    """Envía la invitación con el enlace `APP_ENLACE_INVITACION` + token."""
    raise NotImplementedError("TODO(sesión de invitaciones): correo de invitación")
