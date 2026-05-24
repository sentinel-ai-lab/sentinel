"""
Fix sentinel.companies rows where name = ticker.

Uses the _REGISTRY already defined in fetchers.py as the source of truth.
Adds sector mapping while we're here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

from packages.common.config import get_settings
from packages.ingestion.fetchers import _REGISTRY

# Map ticker → sector enum name (lowercase, matches Postgres enum values)
_SECTOR: dict[str, str] = {
    "TCS": "it",
    "INFY": "it",
    "WIPRO": "it",
    "HCLTECH": "it",
    "HDFCBANK": "banking",
    "ICICIBANK": "banking",
    "AXISBANK": "banking",
    "KOTAKBANK": "banking",
    "BAJFINANCE": "finance",
    "RELIANCE": "energy",
    "POWERGRID": "energy",
    "NTPC": "energy",
    "MARUTI": "auto",
    "SUNPHARMA": "pharma",
    "ULTRACEMCO": "cement",
    "LT": "infrastructure",
    "NESTLEIND": "fmcg",
    "ITC": "fmcg",
    "ASIANPAINT": "consumer",
    "TITAN": "consumer",
}


def main() -> None:
    settings = get_settings()
    url = settings.database_url.replace("postgres://", "postgresql+psycopg://", 1)
    engine = create_engine(url)

    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, ticker, name, sector FROM sentinel.companies ORDER BY id")
        ).fetchall()

        print(f"{'ID':>3}  {'TICKER':<12}  {'OLD NAME':<20}  {'NEW NAME':<30}  {'SECTOR'}")
        print("-" * 90)

        updated = 0
        for row in rows:
            rid, ticker, old_name, _old_sector = row
            entry = _REGISTRY.get(ticker)
            if entry is None:
                print(f"{rid:>3}  {ticker:<12}  {old_name:<20}  !! not in registry — skipped")
                continue

            new_name = entry["name"]
            new_sector = _SECTOR.get(ticker, "other")

            print(f"{rid:>3}  {ticker:<12}  {old_name:<20}  {new_name:<30}  {new_sector}")

            conn.execute(
                text("UPDATE sentinel.companies SET name = :name, sector = :sector WHERE id = :id"),
                {"name": new_name, "sector": new_sector, "id": rid},
            )
            updated += 1

    print(f"\n✅  Updated {updated} rows in sentinel.companies")


if __name__ == "__main__":
    main()
