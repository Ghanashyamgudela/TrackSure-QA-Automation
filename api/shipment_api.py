
import os

import requests


class ShipmentAPI:

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.csrf_token = None

    def login(self, username=None, password=None):
        response = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={
                "username": username or os.environ["TRACKSURE_BOOTSTRAP_ADMIN_USERNAME"],
                "password": password or os.environ["TRACKSURE_BOOTSTRAP_ADMIN_PASSWORD"],
            },
        )
        if response.ok:
            self.csrf_token = response.json()["csrf_token"]
        return response

    def logout(self):
        return self.session.post(
            f"{self.base_url}/api/auth/logout",
            headers={"X-CSRF-Token": self.csrf_token or ""},
        )

    def create_shipment(self, payload):
        return self.session.post(
            f"{self.base_url}/api/shipments",
            json=payload
        )

    def get_shipments(self):
        return self.session.get(
            f"{self.base_url}/api/shipments"
        )

    def get_shipment(self, shipment_id):
        return self.session.get(
            f"{self.base_url}/api/shipments/{shipment_id}"
        )

    def track_shipment(self, tracking_id):
        return self.session.get(
            f"{self.base_url}/api/track/{tracking_id}"
        )

    def update_status(self, shipment_id, status, delivery_proof=None):
        payload = {"status": status}
        if delivery_proof is not None:
            payload["delivery_proof"] = delivery_proof
        return self.session.put(
            f"{self.base_url}/api/shipments/{shipment_id}/status",
            json=payload,
            headers={"X-CSRF-Token": self.csrf_token or ""},
        )

    def cancel_shipment(self, shipment_id):
        return self.session.post(
            f"{self.base_url}/api/shipments/{shipment_id}/cancel",
            headers={"X-CSRF-Token": self.csrf_token or ""},
        )

    def create_staff_user(self, username, password, role="operator"):
        return self.session.post(
            f"{self.base_url}/api/admin/users",
            json={"username": username, "password": password, "role": role},
            headers={"X-CSRF-Token": self.csrf_token or ""},
        )
