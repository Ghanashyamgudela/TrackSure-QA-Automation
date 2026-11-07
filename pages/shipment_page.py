from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class ShipmentPage:

    def __init__(self, driver):

        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    def open(self, base_url):

        self.driver.get(base_url + "/create-shipment")

    def create_shipment(
        self,
        sender,
        receiver,
        address,
        description
    ):

        self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "sender_name")
            )
        ).send_keys(sender)

        self.driver.find_element(
            By.ID, "receiver_name"
        ).send_keys(receiver)

        self.driver.find_element(
            By.ID, "receiver_address"
        ).send_keys(address)

        self.driver.find_element(
            By.ID, "parcel_description"
        ).send_keys(description)

        self.driver.find_element(
            By.ID, "create-btn"
        ).click()

    def get_result(self):

        return self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "result")
            )
        ).text