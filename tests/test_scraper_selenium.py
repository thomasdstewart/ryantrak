from __future__ import annotations

from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from ryanair_scraper import RyanairScraper


@pytest.fixture()
def selenium_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,900")
    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        pytest.skip(f"Chrome driver unavailable: {exc}")
    yield driver
    driver.quit()


def test_extract_flight_cards_from_offline_html(selenium_driver: webdriver.Chrome) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "ryanair_flight_cards.html"
    selenium_driver.get(fixture_path.resolve().as_uri())

    scraper = RyanairScraper.__new__(RyanairScraper)
    scraper.driver = selenium_driver
    scraper.timeout = 10

    wait = WebDriverWait(selenium_driver, scraper.timeout)
    cards = scraper._locate_flight_cards(wait)

    assert len(cards) == 2

    price_selectors = (
        (By.CSS_SELECTOR, "[data-ref='price']"),
        (By.CSS_SELECTOR, "[data-testid='price']"),
        (By.CSS_SELECTOR, "[data-testid='price-value']"),
        (By.CSS_SELECTOR, "[data-testid='flight-price']"),
        (By.CSS_SELECTOR, "[data-e2e='flight-price']"),
        (By.CSS_SELECTOR, ".flight-card__price"),
        (By.CSS_SELECTOR, ".flight-price"),
        (By.CSS_SELECTOR, ".price"),
    )
    time_selectors = (
        (By.CSS_SELECTOR, "[data-ref='flight-time']"),
        (By.CSS_SELECTOR, "[data-testid='flight-time']"),
        (By.CSS_SELECTOR, ".flight-card__time"),
        (By.CSS_SELECTOR, ".flight-time"),
        (By.CSS_SELECTOR, ".flight-info__hour"),
    )

    first_price = scraper._extract_text(cards[0], price_selectors)
    first_times = scraper._extract_times(cards[0], time_selectors)
    second_price = scraper._extract_text(cards[1], price_selectors)
    second_times = scraper._extract_times(cards[1], time_selectors)

    assert first_price == "£123.45"
    assert first_times == ["06:30", "08:45"]
    assert second_price == "£156.00"
    assert second_times == ["12:10", "14:25"]
