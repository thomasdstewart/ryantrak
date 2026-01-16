from __future__ import annotations

from pathlib import Path

from ryanair_scraper import SearchConfig, append_csv, RyanairScraper


class DummyElement:
    def __init__(self, text: str, attributes: dict[str, str] | None = None) -> None:
        self.text = text
        self._attributes = attributes or {}

    def get_attribute(self, name: str) -> str | None:
        return self._attributes.get(name)


def test_search_url_contains_expected_params() -> None:
    config = SearchConfig(
        origin="STN",
        destination="BGY",
        date_out="2024-08-22",
        date_return="2024-09-04",
        adults=2,
        currency="EUR",
    )

    url = config.to_search_url()

    assert url.startswith("https://www.ryanair.com/gb/en/trip/flights/select?")
    assert "originIata=STN" in url
    assert "destinationIata=BGY" in url
    assert "dateOut=2024-08-22" in url
    assert "dateIn=2024-09-04" in url
    assert "adults=2" in url
    assert "currency=EUR" in url


def test_clean_text_collapses_whitespace() -> None:
    assert RyanairScraper._clean_text("  Hello\n  world \t") == "Hello world"


def test_extract_element_text_prefers_first_non_empty() -> None:
    element = DummyElement("", {"innerText": "  £199.99  "})
    scraper = RyanairScraper.__new__(RyanairScraper)

    assert scraper._extract_element_text(element) == "£199.99"


def test_extract_price_from_text_matches_currency() -> None:
    assert RyanairScraper._extract_price_from_text("Fly now for £19.99!") == "£19.99"
    assert (
        RyanairScraper._extract_price_from_text("Total price 24.50 EUR")
        == "24.50 EUR"
    )


def test_append_csv_writes_header_once(tmp_path: Path) -> None:
    csv_path = tmp_path / "prices.csv"

    append_csv(
        csv_path,
        {
            "timestamp_utc": "2024-01-01T00:00:00",
            "origin": "STN",
            "destination": "BGY",
            "departure_date": "2024-08-22T06:30",
            "arrival_date": "2024-08-22T08:45",
            "price": "£123.45",
            "currency": "GBP",
        },
    )
    append_csv(
        csv_path,
        {
            "timestamp_utc": "2024-01-02T00:00:00",
            "origin": "STN",
            "destination": "BGY",
            "departure_date": "2024-08-22T12:10",
            "arrival_date": "2024-08-22T14:25",
            "price": "£156.00",
            "currency": "GBP",
        },
    )

    lines = csv_path.read_text(encoding="utf-8").splitlines()

    assert lines[0].startswith("timestamp_utc,origin,destination,departure_date")
    assert len(lines) == 3
