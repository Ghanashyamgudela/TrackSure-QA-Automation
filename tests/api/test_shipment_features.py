import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import requests

from api.shipment_api import ShipmentAPI
from applications.database import SessionLocal
from applications.main import is_delayed
from applications.models import Shipment


@pytest.mark.api
def test_tracking_timeline_eta_and_delivery_proof(api_client, created_shipment):
    shipment_id = created_shipment["id"]
    for status in ("PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY"):
        response = api_client.update_status(shipment_id, status)
        assert response.status_code == 200

    missing_proof = api_client.update_status(shipment_id, "DELIVERED")
    assert missing_proof.status_code == 422

    proof = {
        "receiver_name": "Arjun",
        "remarks": "Left with the receiver",
        "signature": "Arjun G",
    }
    delivered = api_client.update_status(
        shipment_id,
        "DELIVERED",
        delivery_proof=proof,
    )
    assert delivered.status_code == 200

    tracked = api_client.track_shipment(created_shipment["tracking_id"])
    assert tracked.status_code == 200
    result = tracked.json()
    assert [step["status"] for step in result["timeline"]] == [
        "BOOKED",
        "PICKED_UP",
        "IN_TRANSIT",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
    ]
    assert result["timeline"][-1]["current"] is True
    booked_at = datetime.fromisoformat(created_shipment["created_at"])
    if booked_at.tzinfo is None:
        booked_at = booked_at.replace(tzinfo=timezone.utc)
    estimated_delivery = datetime.fromisoformat(result["estimated_delivery"])
    assert estimated_delivery == booked_at + timedelta(days=5)
    assert all(step["updated_at"] for step in result["timeline"])
    assert result["delivery_proof"]["receiver_name"] == "Arjun"
    assert "signature" not in result["delivery_proof"]

    audit = api_client.session.get(
        f"{api_client.base_url}/api/shipments/{shipment_id}/audit"
    )
    assert audit.status_code == 200
    assert audit.json()[-1]["changed_by"] == os.environ[
        "TRACKSURE_BOOTSTRAP_ADMIN_USERNAME"
    ]
    assert audit.json()[-1]["new_status"] == "DELIVERED"


@pytest.mark.api
def test_analytics_and_shipment_search(api_client, created_shipment):
    response = api_client.session.get(
        f"{api_client.base_url}/api/shipments",
        params={"q": created_shipment["tracking_id"], "sort_by": "tracking_id"},
    )
    assert response.status_code == 200
    assert [item["tracking_id"] for item in response.json()] == [
        created_shipment["tracking_id"]
    ]

    analytics = api_client.session.get(f"{api_client.base_url}/api/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["total"] >= 1
    assert analytics.json()["booked"] >= 1
    assert len(analytics.json()["weekly_shipments"]) == 7
    assert "BOOKED" in analytics.json()["status_distribution"]
    assert any(
        event["tracking_id"] == created_shipment["tracking_id"]
        for event in analytics.json()["recent_activity"]
    )

    export = api_client.session.get(
        f"{api_client.base_url}/api/shipments/export.csv",
        params={"q": created_shipment["tracking_id"]},
    )
    assert export.status_code == 200
    assert "text/csv" in export.headers["content-type"]
    assert created_shipment["tracking_id"] in export.text

    formula_shipment = api_client.create_shipment(
        {
            "sender_name": "=1+1",
            "receiver_name": "Receiver",
            "receiver_address": "Address",
            "parcel_description": "Test package",
        }
    ).json()
    formula_export = api_client.session.get(
        f"{api_client.base_url}/api/shipments/export.csv",
        params={"q": formula_shipment["tracking_id"]},
    )
    assert "'=1+1" in formula_export.text


@pytest.mark.api
def test_staff_roles_restrict_administration(api_client, created_shipment, base_url):
    username = f"operator-{uuid4().hex[:8]}"
    password = "operator-test-password"
    created = api_client.create_staff_user(username, password)
    assert created.status_code == 201

    operator = ShipmentAPI(base_url)
    assert operator.login(username, password).status_code == 200
    response = operator.create_staff_user(
        f"blocked-{uuid4().hex[:8]}",
        "another-test-password",
    )
    assert response.status_code == 403

    changed = operator.update_status(created_shipment["id"], "PICKED_UP")
    assert changed.status_code == 200

    users = api_client.session.get(f"{base_url}/api/admin/users")
    operator_id = next(item["id"] for item in users.json() if item["username"] == username)
    deactivated = api_client.session.patch(
        f"{base_url}/api/admin/users/{operator_id}/active",
        params={"active": "false"},
        headers={"X-CSRF-Token": api_client.csrf_token},
    )
    assert deactivated.status_code == 200
    revoked_session = operator.session.get(f"{base_url}/api/auth/me")
    assert revoked_session.status_code == 200
    assert revoked_session.json()["authenticated"] is False

    own_id = next(
        item["id"]
        for item in users.json()
        if item["username"] == os.environ["TRACKSURE_BOOTSTRAP_ADMIN_USERNAME"]
    )
    last_admin = api_client.session.patch(
        f"{base_url}/api/admin/users/{own_id}/active",
        params={"active": "false"},
        headers={"X-CSRF-Token": api_client.csrf_token},
    )
    assert last_admin.status_code == 400


@pytest.mark.api
def test_status_updates_require_login_and_csrf(api_client, created_shipment):
    endpoint = (
        f"{api_client.base_url}/api/shipments/"
        f"{created_shipment['id']}/status"
    )
    anonymous = requests.Session().put(endpoint, json={"status": "PICKED_UP"})
    assert anonymous.status_code == 401

    missing_csrf = api_client.session.put(
        endpoint,
        json={"status": "PICKED_UP"},
    )
    assert missing_csrf.status_code == 403


@pytest.mark.api
def test_delayed_alert_and_reason(api_client, sample_shipment):
    created = api_client.create_shipment(sample_shipment).json()
    stale_at = datetime.now(timezone.utc) - timedelta(hours=25)
    with SessionLocal() as db:
        shipment = db.query(Shipment).filter(Shipment.id == created["id"]).first()
        shipment.created_at = stale_at
        shipment.history[0].updated_at = stale_at
        db.commit()

    alerts = api_client.session.get(
        f"{api_client.base_url}/api/alerts/delayed"
    )
    matching = [
        alert for alert in alerts.json()
        if alert["tracking_id"] == created["tracking_id"]
    ]
    assert alerts.status_code == 200
    assert len(matching) == 1
    assert matching[0]["delayed_hours"] >= 24
    assert matching[0]["reason"] is None

    with SessionLocal() as db:
        shipment = db.query(Shipment).filter(Shipment.id == created["id"]).first()
        shipment_id = shipment.id
    saved = api_client.session.put(
        f"{api_client.base_url}/api/shipments/{shipment_id}/delay-reason",
        json={"reason": "Awaiting carrier pickup"},
        headers={"X-CSRF-Token": api_client.csrf_token},
    )
    assert saved.status_code == 200
    assert saved.json()["reason"] == "Awaiting carrier pickup"


def test_delay_threshold_and_final_statuses():
    old = datetime.now(timezone.utc) - timedelta(hours=25)
    recent = datetime.now(timezone.utc) - timedelta(hours=23)
    delayed_shipment = Shipment(status="IN_TRANSIT", created_at=old, history=[])
    recent_shipment = Shipment(status="BOOKED", created_at=recent, history=[])
    delivered_shipment = Shipment(status="DELIVERED", created_at=old, history=[])

    assert is_delayed(delayed_shipment)
    assert not is_delayed(recent_shipment)
    assert not is_delayed(delivered_shipment)
