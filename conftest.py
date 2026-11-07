import os

import pytest
from utilities.driver_factory import get_driver


@pytest.fixture
def driver():

    browser = get_driver()

    yield browser

    browser.quit()


@pytest.fixture
def base_url():
    return os.environ.get("TRACKSURE_TEST_BASE_URL", "http://127.0.0.1:8000")

import pytest
from api.shipment_api import ShipmentAPI


@pytest.fixture
def api_client(base_url):
    client = ShipmentAPI(base_url)
    response = client.login()
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def sample_shipment():
    return {
        "sender_name": "Rahul",
        "receiver_name": "Arjun",
        "receiver_address": "Vijayawada",
        "parcel_description": "Laptop Accessories"
    }


@pytest.fixture
def created_shipment(api_client, sample_shipment):
    response = api_client.create_shipment(sample_shipment)
    assert response.status_code == 201
    return response.json()