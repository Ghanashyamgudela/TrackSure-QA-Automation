
import requests


class ShipmentAPI:

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()

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

    def update_status(self, shipment_id, status):
        return self.session.put(
            f"{self.base_url}/api/shipments/{shipment_id}/status",
            json={"status": status}
        )

    def cancel_shipment(self, shipment_id):
        return self.session.post(
            f"{self.base_url}/api/shipments/{shipment_id}/cancel"
        )
