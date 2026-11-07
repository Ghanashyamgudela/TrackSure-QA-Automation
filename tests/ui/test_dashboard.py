from pages.dashboard_page import DashboardPage


def test_dashboard_loads(driver, base_url):

    dashboard = DashboardPage(driver)

    dashboard.open(base_url)

    assert dashboard.get_page_title() == "Shipment Dashboard"

    assert dashboard.is_shipment_table_displayed()

    print("Dashboard test passed!")