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
import re
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
    "departure_date",
    "arrival_date",
    "price",
    "currency",
    "status",
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


@dataclass(frozen=True)
class FlightOption:
    price: Optional[str]
    depart_time: str
    return_time: str
    currency: str
    status: str
    flight_date: str


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

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join(text.split())

    def _extract_element_text(
        self, element: webdriver.remote.webelement.WebElement
    ) -> str:
        attributes = ("textContent", "innerText", "aria-label", "data-label")
        candidates = [element.text]
        for attribute in attributes:
            try:
                value = element.get_attribute(attribute)
            except WebDriverException:
                value = None
            if value:
                candidates.append(value)
        for candidate in candidates:
            cleaned = self._clean_text(candidate)
            if cleaned:
                return cleaned
        return ""

    def _extract_text(
        self,
        element: webdriver.remote.webelement.WebElement,
        selectors: tuple[tuple[By, str], ...],
    ) -> str:
        for by, selector in selectors:
            try:
                target = element.find_element(by, selector)
            except WebDriverException:
                continue
            text = self._extract_element_text(target)
            if text:
                return text
        return ""

    def _extract_page_text(
        self, wait: WebDriverWait, selectors: tuple[tuple[By, str], ...]
    ) -> str:
        for by, selector in selectors:
            try:
                wait.until(EC.presence_of_element_located((by, selector)))
            except TimeoutException:
                continue
            elements = self.driver.find_elements(by, selector)
            for element in elements:
                text = self._extract_element_text(element)
                if text:
                    return text
        return ""

    @staticmethod
    def _extract_price_from_text(text: str) -> str:
        cleaned = RyanairScraper._clean_text(text)
        if not cleaned:
            return ""
        patterns = (
            r"(£|€|\$)\s*\d+(?:[.,]\d{2})?",
            r"\d+(?:[.,]\d{2})?\s*(£|€|\$)",
            r"\b(?:GBP|EUR|USD)\s*\d+(?:[.,]\d{2})?\b",
            r"\d+(?:[.,]\d{2})?\s*(?:GBP|EUR|USD)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if match:
                return match.group(0).strip()
        return ""

    def _extract_times(
        self,
        element: webdriver.remote.webelement.WebElement,
        selectors: tuple[tuple[By, str], ...],
    ) -> list[str]:
        for by, selector in selectors:
            try:
                targets = element.find_elements(by, selector)
            except WebDriverException:
                continue
            times = [target.text.strip() for target in targets if target.text.strip()]
            if times:
                return times
        return []

    def _locate_flight_cards(
        self, wait: WebDriverWait
    ) -> list[webdriver.remote.webelement.WebElement]:
        selectors: tuple[tuple[By, str], ...] = (
            (By.CSS_SELECTOR, "[data-ref='flight-card']"),
            (By.CSS_SELECTOR, "[data-testid='flight-card']"),
            (By.CSS_SELECTOR, ".flight-card"),
            (By.CSS_SELECTOR, "[data-ref='flight-card-container']"),
        )
        for by, selector in selectors:
            try:
                wait.until(EC.presence_of_element_located((by, selector)))
            except TimeoutException:
                continue
            cards = self.driver.find_elements(by, selector)
            if cards:
                return cards
        return []

    def fetch_return_flights(self, config: SearchConfig) -> list[FlightOption]:
        """Fetch return flight options from Ryanair booking flow."""
        search_url = config.to_search_url()
        logging.info("Navigating to %s", search_url)
        try:
            self.driver.get(search_url)
        except TimeoutException:
            logging.warning("Timeout while loading the search URL")
            self._save_debug_artifacts("timeout")
            return [
                FlightOption(
                    price=None,
                    depart_time="",
                    return_time="",
                    currency=config.currency,
                    status="timeout",
                    flight_date=config.depart_date,
                )
            ]

        try:
            wait = WebDriverWait(self.driver, self.timeout)
            self._accept_cookies()

            flight_cards = self._locate_flight_cards(wait)

            price_selectors: tuple[tuple[By, str], ...] = (
                (By.CSS_SELECTOR, "[data-ref='price']"),
                (By.CSS_SELECTOR, "[data-testid='price']"),
                (By.CSS_SELECTOR, "[data-testid='price-value']"),
                (By.CSS_SELECTOR, "[data-testid='flight-price']"),
                (By.CSS_SELECTOR, "[data-e2e='flight-price']"),
                (By.CSS_SELECTOR, ".flight-card__price"),
                (By.CSS_SELECTOR, ".flight-price"),
                (By.CSS_SELECTOR, ".price"),
            )
            time_selectors: tuple[tuple[By, str], ...] = (
                (By.CSS_SELECTOR, "[data-ref='flight-time']"),
                (By.CSS_SELECTOR, "[data-testid='flight-time']"),
                (By.CSS_SELECTOR, ".flight-card__time"),
                (By.CSS_SELECTOR, ".flight-time"),
                (By.CSS_SELECTOR, ".flight-info__hour"),
            )

            if not flight_cards:
                price_text = self._extract_page_text(wait, price_selectors)
                if not price_text:
                    try:
                        body = self.driver.find_element(By.TAG_NAME, "body")
                    except WebDriverException:
                        body = None
                    if body is not None:
                        price_text = self._extract_price_from_text(
                            self._extract_element_text(body)
                        )
                logging.info("Found price text: %s", price_text)
                return [
                    FlightOption(
                        price=price_text or None,
                        depart_time="",
                        return_time="",
                        currency=config.currency,
                        status="ok" if price_text else "missing-price",
                        flight_date=config.depart_date,
                    )
                ]

            options: list[FlightOption] = []
            for card in flight_cards:
                price_text = self._extract_text(card, price_selectors)
                if not price_text:
                    price_text = self._extract_price_from_text(
                        self._extract_element_text(card)
                    )
                time_texts = self._extract_times(card, time_selectors)
                depart_time = time_texts[0] if len(time_texts) > 0 else ""
                return_time = time_texts[1] if len(time_texts) > 1 else ""
                status = "ok" if price_text else "missing-price"
                options.append(
                    FlightOption(
                        price=price_text or None,
                        depart_time=depart_time,
                        return_time=return_time,
                        currency=config.currency,
                        status=status,
                        flight_date=config.depart_date,
                    )
                )
            if len(options) > 1 and len(options) % 2 == 0:
                midpoint = len(options) // 2
                logging.info(
                    "Detected %s total options; assigning %s outbound and %s return results",
                    len(options),
                    midpoint,
                    len(options) - midpoint,
                )
                options = [
                    FlightOption(
                        price=option.price,
                        depart_time=option.depart_time,
                        return_time=option.return_time,
                        currency=option.currency,
                        status=option.status,
                        flight_date=(
                            config.depart_date if idx < midpoint else config.return_date
                        ),
                    )
                    for idx, option in enumerate(options)
                ]
            logging.info("Found %s flight options", len(options))
            return options
        except TimeoutException:
            logging.warning("Timed out waiting for price element")
            self._save_debug_artifacts("missing-price")
            return [
                FlightOption(
                    price=None,
                    depart_time="",
                    return_time="",
                    currency=config.currency,
                    status="missing-price",
                    flight_date=config.depart_date,
                )
            ]
        except WebDriverException:
            logging.exception("WebDriver error while extracting price")
            self._save_debug_artifacts("webdriver-error")
            return [
                FlightOption(
                    price=None,
                    depart_time="",
                    return_time="",
                    currency=config.currency,
                    status="webdriver-error",
                    flight_date=config.depart_date,
                )
            ]


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


def format_flight_datetime(date_str: str, time_str: str) -> str:
    if time_str:
        return f"{date_str}T{time_str}"
    return date_str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track Ryanair return flight prices.")
    parser.add_argument("--origin", default="STN", help="Origin airport IATA code")
    parser.add_argument("--destination", default="BGY", help="Destination IATA code")
    parser.add_argument("--depart-date", default="2026-08-22", help="Departure date")
    parser.add_argument("--return-date", default="2026-09-04", help="Return date")
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
        flights = scraper.fetch_return_flights(config)
        for flight in flights:
            row = {
                "timestamp_utc": timestamp,
                "origin": config.origin,
                "destination": config.destination,
                "departure_date": format_flight_datetime(
                    flight.flight_date, flight.depart_time
                ),
                "arrival_date": format_flight_datetime(
                    flight.flight_date, flight.return_time
                ),
                "price": flight.price or "",
                "currency": flight.currency,
                "status": flight.status,
            }
            append_csv(Path(args.csv_path), row)
        logging.info("Appended %s rows to %s", len(flights), args.csv_path)
    finally:
        scraper.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
