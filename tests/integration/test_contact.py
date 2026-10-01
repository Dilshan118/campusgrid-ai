"""Public pilot inquiry endpoint tests. SMTP is mocked; no real email is sent."""

from src.application.services.pilot_email_service import PilotEmailNotConfigured


VALID_INQUIRY = {
    "full_name": "Amasha Weerasuriya",
    "organization": "Example University",
    "job_title": "Facilities Manager",
    "email": "amasha.weerasuriya003@gmail.com",
    "phone": "+94 77 123 4567",
    "building_count": "4–10",
    "monthly_bill_range": "LKR 5–10 million",
    "has_solar": True,
    "has_battery": False,
    "metering_system": "Campus BMS",
    "message": "We would like to discuss an energy assessment.",
}


def test_pilot_inquiry_is_public_and_passed_to_mailer(anon_client, monkeypatch):
    sent = []
    monkeypatch.setattr("src.api.routes.contact.send_pilot_inquiry", lambda data: sent.append(data))

    response = anon_client.post("/api/contact/pilot", json=VALID_INQUIRY)

    assert response.status_code == 200
    assert response.json()["data"] == {"accepted": True}
    assert len(sent) == 1
    assert sent[0]["email"] == VALID_INQUIRY["email"]
    assert sent[0]["has_solar"] is True
    assert "website" not in sent[0]


def test_pilot_inquiry_honeypot_is_accepted_but_not_sent(anon_client, monkeypatch):
    sent = []
    monkeypatch.setattr("src.api.routes.contact.send_pilot_inquiry", lambda data: sent.append(data))
    payload = {**VALID_INQUIRY, "website": "spam bot"}

    response = anon_client.post("/api/contact/pilot", json=payload)

    assert response.status_code == 200
    assert response.json()["data"] == {"accepted": True}
    assert sent == []


def test_pilot_inquiry_reports_unconfigured_delivery(anon_client, monkeypatch):
    def not_configured(_data):
        raise PilotEmailNotConfigured()

    monkeypatch.setattr("src.api.routes.contact.send_pilot_inquiry", not_configured)
    response = anon_client.post("/api/contact/pilot", json=VALID_INQUIRY)

    assert response.status_code == 503
    assert response.json()["error_code"] == "CONTACT_DELIVERY_UNAVAILABLE"
    assert "not configured" in response.json()["message"]


def test_pilot_inquiry_validates_email_and_required_fields(anon_client):
    response = anon_client.post(
        "/api/contact/pilot",
        json={**VALID_INQUIRY, "email": "not-an-email", "organization": "x"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
