#!/usr/bin/env python3
"""Generate flight price charts from CSV history.

Outputs one PNG per unique (origin, destination, departure_date) series.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


@dataclass(frozen=True)
class PlotConfig:
    csv_path: Path
    output_dir: Path
    currency: str


def _parse_price(value: str) -> Optional[float]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace("£", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value)


def build_charts(config: PlotConfig) -> list[Path]:
    df = pd.read_csv(config.csv_path)
    if df.empty:
        return []

    df = df.copy()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    df["capture_date"] = pd.to_datetime(df["timestamp_utc"], errors="coerce")
    df["price_value"] = df["price"].apply(_parse_price)
    df = df.dropna(subset=["capture_date", "price_value"])
    if df.empty:
        return []

    df = df.sort_values("capture_date")

    output_paths: list[Path] = []
    group_columns = ["origin", "destination", "departure_date"]
    for (origin, destination, departure_date), group in df.groupby(group_columns):
        if group.empty:
            continue
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(group["capture_date"], group["price_value"], marker="o")
        ax.set_title(f"{origin} → {destination} ({departure_date})")
        ax.set_xlabel("Capture date")
        ax.set_ylabel(f"Price ({config.currency})")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()

        filename = "_".join(
            [
                _slugify(origin),
                _slugify(destination),
                _slugify(departure_date),
            ]
        )
        output_path = config.output_dir / f"{filename}.png"
        config.output_dir.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        output_paths.append(output_path)

    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate flight price charts.")
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=Path("data/flight_prices.csv"),
        help="Path to flight_prices.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("site/charts"),
        help="Directory to write PNG charts.",
    )
    parser.add_argument(
        "--currency",
        default="GBP",
        help="Currency label to display on charts.",
    )
    args = parser.parse_args()

    config = PlotConfig(
        csv_path=args.csv_path,
        output_dir=args.output_dir,
        currency=args.currency,
    )
    output_paths = build_charts(config)
    print(f"Generated {len(output_paths)} chart(s).")


if __name__ == "__main__":
    main()
