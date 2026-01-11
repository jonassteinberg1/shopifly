import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DASHBOARD_URL = "http://54.197.8.56:8501"


@pytest.fixture
def browser():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    yield driver
    driver.quit()


def test_dashboard_loads(browser):
    """Dashboard should load and show title."""
    browser.get(DASHBOARD_URL)
    WebDriverWait(browser, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "h1"))
    )
    assert "Shopify" in browser.title or "Streamlit" in browser.title


def test_dashboard_has_metrics(browser):
    """Dashboard should show metric cards."""
    browser.get(DASHBOARD_URL)
    WebDriverWait(browser, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid=stMetric]"))
    )
    metrics = browser.find_elements(By.CSS_SELECTOR, "[data-testid=stMetric]")
    assert len(metrics) >= 3, f"Expected 3+ metrics, got {len(metrics)}"


def test_dashboard_has_charts(browser):
    """Dashboard should render at least one chart."""
    browser.get(DASHBOARD_URL)
    WebDriverWait(browser, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".plotly, .js-plotly-plot"))
    )
