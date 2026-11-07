
import pytest


@pytest.mark.api
def test_track_existing_shipment(api_client, created_shipment):

    tracking_id = created_shipment["tracking_id"]

    response = api_client.track_shipment(tracking_id)

    assert response.status_code == 200

    data = response.json()

    assert data["tracking_id"] == tracking_id
    assert data["status"] == "BOOKED"
    assert len(data["history"]) >= 1


@pytest.mark.api
def test_track_invalid_tracking_id(api_client):

    response = api_client.track_shipment("TRK-INVALID-123")

    assert response.status_code == 404