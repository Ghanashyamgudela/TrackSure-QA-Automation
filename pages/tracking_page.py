from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TrackingPage:

    def __init__(self, driver):

        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    def open(self, base_url):

        self.driver.get(base_url + "/track")

    def track_parcel(self, tracking_id):

        tracking_input = self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "tracking_id")
            )
        )

        tracking_input.clear()
        tracking_input.send_keys(tracking_id)

        self.driver.find_element(
            By.ID, "track-btn"
        ).click()

    def get_tracking_result(self):

        return self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "tracking-result")
            )
        ).text