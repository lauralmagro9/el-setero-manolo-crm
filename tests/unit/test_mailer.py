"""Tests for the SMTP sender."""

import smtplib

import pytest

from crm.config import settings
from crm.services import mailer
from crm.services.errors import EmailError


class FakeSMTP:
    """Stand-in for smtplib.SMTP that records what happens."""

    instances = []
    fail = False

    def __init__(self, host, port, timeout):
        self.host, self.port, self.calls, self.message = host, port, [], None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        if FakeSMTP.fail:
            raise smtplib.SMTPException("rechazado")
        self.message = message


@pytest.fixture
def smtp(monkeypatch):
    """Configure SMTP settings and replace smtplib.SMTP with FakeSMTP."""
    data = settings.email.as_dict()
    for key, value in {"smtp_host": "smtp.example.com", "sender": "crm@example.com",
                       "smtp_username": "user", "smtp_password": "secret",
                       "smtp_ssl": False, "smtp_starttls": True}.items():
        monkeypatch.setitem(data, key, value)
    FakeSMTP.instances, FakeSMTP.fail = [], False
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", type("FakeSMTPSSL", (FakeSMTP,), {}))
    return FakeSMTP


class TestSendEmail:
    """Tests for send_email."""

    def test_0_sends_message_with_attachment(self, smtp):
        """The message has the right headers, text and PDF attachment, after STARTTLS and login."""
        mailer.send_email(recipient="a@example.com", subject="Asunto", body="Hola",
                          attachments=[("f.pdf", b"%PDF-1.4", "application/pdf")])
        server = smtp.instances[0]
        assert server.calls == ["starttls", ("login", "user", "secret")]
        assert server.message["To"] == "a@example.com"
        assert server.message["Subject"] == "Asunto"
        attachment = list(server.message.iter_attachments())[0]
        assert attachment.get_filename() == "f.pdf"
        assert attachment.get_content() == b"%PDF-1.4"

    def test_3_ssl_mode_uses_implicit_tls_without_starttls(self, smtp, monkeypatch):
        """With smtp_ssl the SSL connection class is used and STARTTLS is skipped."""
        monkeypatch.setitem(settings.email.as_dict(), "smtp_ssl", True)
        mailer.send_email(recipient="a@example.com", subject="s", body="b")
        server = mailer.smtplib.SMTP_SSL.instances[-1]
        assert type(server).__name__ == "FakeSMTPSSL"
        assert "starttls" not in server.calls and ("login", "user", "secret") in server.calls

    def test_1_unconfigured_server_raises(self, monkeypatch):
        """Without host and sender a clear EmailError is raised."""
        monkeypatch.setitem(settings.email.as_dict(), "smtp_host", "")
        with pytest.raises(EmailError, match="EMAIL_SMTP_HOST"):
            mailer.send_email(recipient="a@example.com", subject="s", body="b")

    def test_2_delivery_failure_becomes_email_error(self, smtp):
        """SMTP errors are wrapped in EmailError."""
        smtp.fail = True
        with pytest.raises(EmailError, match="rechazado"):
            mailer.send_email(recipient="a@example.com", subject="s", body="b")
