"""SMTP delivery for public pilot inquiries. Inquiry content is not stored by this service."""

from email.message import EmailMessage
import logging
import smtplib
import ssl
from typing import Any, Dict

from src.config.settings import Settings, get_settings

logger = logging.getLogger("campusgrid.pilot_email")


class PilotEmailNotConfigured(Exception):
    """Raised when the deployment has no safe mail transport configured."""


class PilotEmailDeliveryError(Exception):
    """Raised when the configured transport does not accept the inquiry."""


def send_pilot_inquiry(inquiry: Dict[str, Any], settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    host = settings.pilot_smtp_host
    username = settings.pilot_smtp_username
    password = settings.pilot_smtp_password
    sender = settings.pilot_email_from or username
    recipient = settings.pilot_email_recipient

    if not host or not sender or not recipient:
        raise PilotEmailNotConfigured("Pilot inquiry email is not configured.")
    if bool(username) != bool(password):
        raise PilotEmailNotConfigured("SMTP authentication requires both a username and password.")
    if settings.app_env == "production" and (not settings.pilot_smtp_starttls or not username or not password):
        raise PilotEmailNotConfigured("Production pilot email requires authenticated STARTTLS SMTP.")

    message = EmailMessage()
    # Keep user-controlled strings out of mail headers to prevent header injection.
    message["Subject"] = "New CampusGrid pilot inquiry"
    message["From"] = sender
    message["To"] = recipient
    message["Reply-To"] = inquiry["email"]
    def one_line(value: Any) -> str:
        return " ".join(str(value or "").splitlines()).strip()

    rows = [
        "New CampusGrid pilot inquiry",
        "",
        f"Name: {one_line(inquiry['full_name'])}",
        f"Organization: {one_line(inquiry['organization'])}",
        f"Job title: {one_line(inquiry.get('job_title') or 'Not provided')}",
        f"Email: {one_line(inquiry['email'])}",
        f"Phone: {one_line(inquiry.get('phone') or 'Not provided')}",
        f"Buildings: {one_line(inquiry.get('building_count') or 'Not provided')}",
        f"Approx. monthly bill: {one_line(inquiry.get('monthly_bill_range') or 'Not provided')}",
        f"Solar PV: {'Yes' if inquiry.get('has_solar') else 'No'}",
        f"Battery storage: {'Yes' if inquiry.get('has_battery') else 'No'}",
        f"Metering system: {one_line(inquiry.get('metering_system') or 'Not provided')}",
        "",
        "Message:",
        inquiry.get("message") or "Not provided",
    ]
    message.set_content("\n".join(rows))

    try:
        with smtplib.SMTP(host, settings.pilot_smtp_port, timeout=settings.pilot_email_timeout_seconds) as server:
            server.ehlo()
            if settings.pilot_smtp_starttls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if username and password:
                server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("Pilot inquiry email delivery failed (%s)", type(exc).__name__)
        raise PilotEmailDeliveryError("Pilot inquiry email could not be delivered.") from exc
