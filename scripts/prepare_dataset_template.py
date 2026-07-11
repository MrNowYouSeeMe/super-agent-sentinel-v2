
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "processed" / "mfs_training_template.csv"

HEADERS = [
    "timestamp",
    "outlet_id",
    "area_id",
    "resource_id",
    "balance",
    "safe_buffer",
    "cash_in_5m",
    "cash_out_5m",
    "transaction_count_5m",
    "repeated_amount_ratio",
    "unique_customer_ratio",
    "failure_rate",
    "feed_age_seconds",
    "reconciliation_difference",
    "completeness_ratio",
    "source_quality_score",
    "festival_or_market_day",
    "is_unusual",
    "shortage_within_60m",
    "shortage_runway_minutes",
]

EXAMPLE_ROWS = [
    [
        "2026-07-12T10:00:00",
        "OUT-1",
        "sylhet",
        "bkash",
        7000,
        3000,
        1000,
        30000,
        32,
        0.75,
        0.18,
        0.02,
        0,
        0,
        1.0,
        1.0,
        True,
        1,
        1,
        42,
    ],
    [
        "2026-07-12T10:00:00",
        "OUT-1",
        "sylhet",
        "nagad",
        120000,
        15000,
        20000,
        10000,
        10,
        0.10,
        0.90,
        0.00,
        0,
        0,
        1.0,
        1.0,
        True,
        0,
        0,
        999,
    ],
]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        print(f"Template already exists: {OUTPUT}")
        return
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        writer.writerows(EXAMPLE_ROWS)
    print(f"Created dataset template: {OUTPUT}")


if __name__ == "__main__":
    main()
