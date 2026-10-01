"""SMTP composition tests; no real network or mailbox access."""

from src.application.services import pilot_email_service
from src.application.services.pilot_email_service import send_pilot_inquiry
from src.config.settings import Settings


def test_smtp_mailer_uses_the_configured_campusgrid_mailbox(monkeypatch):
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            captured["connection"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def ehlo(self):
            captured["ehlo"] = True

        def starttls(self, context):
            captured["tls"] = context

        def login(self, username, password):
            captured["login"] = (username, password)

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr(pilot_email_service.smtplib, "SMTP", FakeSMTP)
    settings = Settings(
        app_env="test",
        pilot_smtp_host="smtp.gmail.test",
        pilot_smtp_username="amasha.weerasuriya003@gmail.com",
        pilot_smtp_password="test-only-secret",
    )
    inquiry = {
        "full_name": "Amasha Weerasuriya",
        "organization": "Example University\nBcc: injected@example.net",
        "email": "sender@example.org",
        "has_solar": True,
        "has_battery": False,
    }

    send_pilot_inquiry(inquiry, settings)

    assert captured["connection"] == ("smtp.gmail.test", 587, 10.0)
    assert captured["login"] == ("amasha.weerasuriya003@gmail.com", "test-only-secret")
    assert captured["message"]["To"] == "amasha.weerasuriya003@gmail.com"
    assert captured["message"]["From"] == "amasha.weerasuriya003@gmail.com"
    assert captured["message"]["Subject"] == "New CampusGrid pilot inquiry"
    assert captured["message"].get("Bcc") is None
    assert captured["message"]["Reply-To"] == "sender@example.org"
    assert "Organization: Example University Bcc: injected@example.net" in captured["message"].get_content()


def test_production_mailer_rejects_plaintext_or_unauthenticated_smtp():
    settings = Settings(
        app_env="production",
        jwt_secret_key="j" * 48,
        audit_signing_key="a" * 48,
        pilot_smtp_host="smtp.example.org",
        pilot_email_from="campusgrid@example.org",
        pilot_smtp_starttls=False,
    )

    try:
        send_pilot_inquiry({"full_name": "Test", "organization": "University", "email": "test@example.org"}, settings)
    except pilot_email_service.PilotEmailNotConfigured:
        pass
    else:
        raise AssertionError("Production SMTP without authenticated STARTTLS must be rejected")


def test_mailer_does_not_attempt_gmail_delivery_without_app_password():
    settings = Settings(
        app_env="development",
        pilot_smtp_host="smtp.gmail.com",
        pilot_smtp_username="amasha.weerasuriya003@gmail.com",
        pilot_smtp_password=None,
    )

    try:
        send_pilot_inquiry({"full_name": "Test", "organization": "University", "email": "test@example.org"}, settings)
    except pilot_email_service.PilotEmailNotConfigured:
        pass
    else:
        raise AssertionError("Gmail delivery must not be attempted without an App Password")
