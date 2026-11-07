from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class DashboardPage:

    def __init__(self, driver):

        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    def open(self, base_url):

        self.driver.get(base_url + "/dashboard")

    def get_page_title(self):

        return self.wait.until(
            EC.visibility_of_element_located(
                (By.TAG_NAME, "h2")
            )
        ).text

    def get_total_shipments(self):

        return self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "total-count")
            )
        ).text

    def is_shipment_table_displayed(self):

        return self.wait.until(
            EC.visibility_of_element_located(
                (By.ID, "shipment-table")
            )
        ).is_displayed()