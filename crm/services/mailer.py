"""Sending email through a generic SMTP server (settings [email], password in .env)."""

import smtplib
from email.message import EmailMessage

from ..config import settings
from .errors import EmailError


def send_email(
    *, recipient: str, subject: str, body: str, attachments: list[tuple[str, bytes, str]] | None = None
) -> None:
    """Send a plain-text email with optional (filename, content, mime type) attachments.

    Raises EmailError when the server is not configured or the delivery fails.
    """
    cfg = settings.email
    if not cfg.smtp_host or not cfg.sender:
        raise EmailError("Falta configurar el servidor de correo (EMAIL_SMTP_HOST y EMAIL_SENDER)")
    message = EmailMessage()
    message["From"] = cfg.sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    for filename, content, mime_type in attachments or []:
        maintype, _, subtype = mime_type.partition("/")
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    try:
        # smtp_ssl = TLS from the first byte (usually port 465); otherwise plain connection + STARTTLS (587)
        connect = smtplib.SMTP_SSL if cfg.smtp_ssl else smtplib.SMTP
        with connect(cfg.smtp_host, cfg.smtp_port, timeout=cfg.smtp_timeout_seconds) as server:
            if cfg.smtp_starttls and not cfg.smtp_ssl:
                server.starttls()
            if cfg.smtp_username:
                server.login(cfg.smtp_username, cfg.smtp_password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailError(f"No se pudo enviar el correo: {exc}") from exc
