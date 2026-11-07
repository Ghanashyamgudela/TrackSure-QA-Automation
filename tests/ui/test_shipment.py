
import pytest


@pytest.mark.api
def test_create_shipment_success(api_client, sample_shipment):

    response = api_client.create_shipment(sample_shipment)

    assert response.status_code == 201

    data = response.json()

    assert data["tracking_id"].startswith("TRK-")
    assert data["status"] == "BOOKED"
    assert data["sender_name"] == "Rahul"
    assert data["receiver_name"] == "Arjun"


@pytest.mark.api
def test_create_shipment_missing_required_field(api_client):

    payload = {
        "sender_name": "Rahul",
        "receiver_name": "Arjun"
    }

    response = api_client.create_shipment(payload)

    assert response.status_code == 422


@pytest.mark.api
def test_get_nonexistent_shipment(api_client):

    response = api_client.get_shipment(999999)

    assert response.status_code == 404
