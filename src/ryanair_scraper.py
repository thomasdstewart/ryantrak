#!/usr/bin/env python3
"""Ryanair price tracker using Selenium.

This script is designed to run in CI (e.g., GitHub Actions) or locally.
It records a daily price point for a fixed route/date pairing into a CSV file.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://www.ryanair.com/gb/en"
CSV_HEADERS = [
    "timestamp_utc",
    "origin",
    "destination",
    "depart_date",
    "return_date",
    "price",
    "currency",
    "status",
    "notes",
]


@dataclass(frozen=True)
class SearchConfig:
    origin: str
    destination: str
    depart_date: str
    return_date: str
    adults: int = 1
    currency: str = "GBP"

    def to_search_url(self) -> str:
        """Build a Ryanair search URL.

        Note: Ryanair may update their URL format. Adjust as needed.
        """
        return (
            f"{BASE_URL}/trip/flights/select?"
            f"adults={self.adults}"
            f"&teens=0&children=0&infants=0"
            f"&originIata={self.origin}"
            f"&destinationIata={self.destination}"
            f"&dateOut={self.depart_date}"
            f"&dateIn={self.return_date}"
            f"&isReturn=true&flexdaysBeforeOut=0&flexdaysOut=0"
            f"&flexdaysBeforeIn=0&flexdaysIn=0"
            f"&roundTrip=true&discount=0"
            f"&promoCode=&isConnectedFlight=false"
            f"&isDomestic=false&isReturn=true"
            f"&currency={self.currency}"
        )


class RyanairScraper:
    def __init__(self, headless: bool, debug_dir: Optional[Path], timeout: int) -> None:
        self.headless = headless
        self.debug_dir = debug_dir
        self.timeout = timeout
        self.driver = self._build_driver()

    def _build_driver(self) -> webdriver.Chrome:
        options = Options()
        options.add_argument("--window-size=1400,900")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        if self.headless:
            options.add_argument("--headless=new")
        try:
            driver = webdriver.Chrome(options=options)
        except WebDriverException as exc:
            logging.exception("Failed to start Chrome driver")
            raise exc
        driver.set_page_load_timeout(self.timeout)
        return driver

    def close(self) -> None:
        self.driver.quit()

    def _save_debug_artifacts(self, label: str) -> None:
        if not self.debug_dir:
            return
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        screenshot_path = self.debug_dir / f"{label}-{timestamp}.png"
        html_path = self.debug_dir / f"{label}-{timestamp}.html"
        try:
            self.driver.save_screenshot(str(screenshot_path))
            html_path.write_text(self.driver.page_source, encoding="utf-8")
            logging.info("Saved debug artifacts to %s", self.debug_dir)
        except WebDriverException:
            logging.exception("Failed to write debug artifacts")

    def _accept_cookies(self) -> None:
        selectors: tuple[tuple[By, str], ...] = (
            (By.CSS_SELECTOR, "button[data-ref='cookie.accept-all']"),
            (By.CSS_SELECTOR, "button[data-ref='cookie.popup.accept-all']"),
            (By.CSS_SELECTOR, "button[data-testid='accept-all-cookies']"),
            (By.CSS_SELECTOR, "button#cookie-popup-with-overlay-accept"),
            (
                By.XPATH,
                "//button[contains(translate(.,"
                " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),"
                " 'accept')"
                " and contains(translate(.,"
                " 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),"
                " 'cookie')]",
            ),
        )
        for by, selector in selectors:
            try:
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((by, selector))
                )
                button.click()
                logging.info("Accepted cookies banner using selector: %s", selector)
                return
            except TimeoutException:
                continue
            except WebDriverException:
                logging.exception("Failed to accept cookies banner")
                return

    def fetch_return_price(self, config: SearchConfig) -> tuple[Optional[str], str, str]:
        """Fetch return price from Ryanair booking flow.

        Returns a tuple: (price, currency, status)
        """
        search_url = config.to_search_url()
        logging.info("Navigating to %s", search_url)
        try:
            self.driver.get(search_url)
        except TimeoutException:
            logging.warning("Timeout while loading the search URL")
            self._save_debug_artifacts("timeout")
            return None, config.currency, "timeout"

        try:
            wait = WebDriverWait(self.driver, self.timeout)
            self._accept_cookies()

            # TODO: Update selectors if Ryanair changes their DOM structure.
            price_selector = "[data-ref='price']"
            price_element = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, price_selector))
            )
            price_text = price_element.text.strip()
            logging.info("Found price text: %s", price_text)
            return price_text, config.currency, "ok"
        except TimeoutException:
            logging.warning("Timed out waiting for price element")
            self._save_debug_artifacts("missing-price")
            return None, config.currency, "missing-price"
        except WebDriverException:
            logging.exception("WebDriver error while extracting price")
            self._save_debug_artifacts("webdriver-error")
            return None, config.currency, "webdriver-error"


def configure_logging(log_path: Path, verbose: bool) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(),
    ]
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


def append_csv(csv_path: Path, row: dict[str, str]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track Ryanair return flight prices.")
    parser.add_argument("--origin", default="STN", help="Origin airport IATA code")
    parser.add_argument("--destination", default="BGY", help="Destination IATA code")
    parser.add_argument("--depart-date", default="2024-08-22", help="Departure date")
    parser.add_argument("--return-date", default="2024-09-04", help="Return date")
    parser.add_argument("--currency", default="GBP", help="Currency to display")
    parser.add_argument(
        "--csv-path", default="data/flight_prices.csv", help="CSV output path"
    )
    parser.add_argument(
        "--log-path", default="logs/ryanair_scrape.log", help="Log file path"
    )
    parser.add_argument("--timeout", type=int, default=40, help="Page load timeout")
    parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
    parser.add_argument(
        "--debug-dir",
        default="debug_artifacts",
        help="Directory to store screenshots/html",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    debug_dir = Path(args.debug_dir) if args.debug_dir else None
    configure_logging(Path(args.log_path), args.verbose)

    config = SearchConfig(
        origin=args.origin,
        destination=args.destination,
        depart_date=args.depart_date,
        return_date=args.return_date,
        currency=args.currency,
    )

    scraper = RyanairScraper(
        headless=args.headless, debug_dir=debug_dir, timeout=args.timeout
    )
    timestamp = dt.datetime.utcnow().replace(microsecond=0).isoformat()

    try:
        price, currency, status = scraper.fetch_return_price(config)
        row = {
            "timestamp_utc": timestamp,
            "origin": config.origin,
            "destination": config.destination,
            "depart_date": config.depart_date,
            "return_date": config.return_date,
            "price": price or "",
            "currency": currency,
            "status": status,
            "notes": "",
        }
        append_csv(Path(args.csv_path), row)
        logging.info("Appended row to %s", args.csv_path)
    finally:
        scraper.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
