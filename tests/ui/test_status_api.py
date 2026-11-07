
import pytest


@pytest.mark.api
def test_valid_status_transition(api_client, created_shipment):

    shipment_id = created_shipment["id"]

    response = api_client.update_status(
        shipment_id,
        "PICKED_UP"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "PICKED_UP"


@pytest.mark.api
def test_invalid_status_transition(api_client, created_shipment):

    shipment_id = created_shipment["id"]

    # BOOKED cannot move directly to IN_TRANSIT
    response = api_client.update_status(
        shipment_id,
        "IN_TRANSIT"
    )

    assert response.status_code == 400


@pytest.mark.api
def test_cancel_active_shipment(api_client, created_shipment):

    shipment_id = created_shipment["id"]

    response = api_client.cancel_shipment(shipment_id)

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
