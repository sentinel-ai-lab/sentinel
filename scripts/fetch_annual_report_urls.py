#!/usr/bin/env python3
"""
Fetch annual report PDF URLs for the 20 target Nifty-50 companies.

How it works:
  1. NSE path (preferred): NSE has a JSON API but blocks headless bots.
     Fix: hit the homepage first to get session cookies, then call the API.
  2. BSE path (fallback): BSE API sometimes works without auth, sometimes
     redirects to a login page. We try it as a fallback.

Output: prints a markdown table you can paste into docs/data-sources.md

Run:
    python scripts/fetch_annual_report_urls.py
    python scripts/fetch_annual_report_urls.py --source nse   # NSE only
    python scripts/fetch_annual_report_urls.py --source bse   # BSE only
"""

import time
import json
import argparse
from typing import Optional

import httpx

# ── Target companies ──────────────────────────────────────────────────────────

COMPANIES = [
    {"name": "TCS",                  "bse": "532540", "nse": "TCS"},
    {"name": "Infosys",              "bse": "500209", "nse": "INFY"},
    {"name": "HDFC Bank",            "bse": "500180", "nse": "HDFCBANK"},
    {"name": "Reliance Industries",  "bse": "500325", "nse": "RELIANCE"},
    {"name": "ICICI Bank",           "bse": "532174", "nse": "ICICIBANK"},
    {"name": "Wipro",                "bse": "507685", "nse": "WIPRO"},
    {"name": "HCL Technologies",     "bse": "532281", "nse": "HCLTECH"},
    {"name": "Kotak Mahindra Bank",  "bse": "500247", "nse": "KOTAKBANK"},
    {"name": "Bajaj Finance",        "bse": "500034", "nse": "BAJFINANCE"},
    {"name": "Asian Paints",         "bse": "500820", "nse": "ASIANPAINT"},
    {"name": "Maruti Suzuki",        "bse": "532500", "nse": "MARUTI"},
    {"name": "Sun Pharma",           "bse": "524715", "nse": "SUNPHARMA"},
    {"name": "Titan Company",        "bse": "500114", "nse": "TITAN"},
    {"name": "Larsen & Toubro",      "bse": "500510", "nse": "LT"},
    {"name": "UltraTech Cement",     "bse": "532538", "nse": "ULTRACEMCO"},
    {"name": "Nestle India",         "bse": "500790", "nse": "NESTLEIND"},
    {"name": "Power Grid Corp",      "bse": "532898", "nse": "POWERGRID"},
    {"name": "NTPC",                 "bse": "532555", "nse": "NTPC"},
    {"name": "ITC",                  "bse": "500875", "nse": "ITC"},
    {"name": "Axis Bank",            "bse": "532215", "nse": "AXISBANK"},
]

# ── URL templates ─────────────────────────────────────────────────────────────

NSE_HOME    = "https://www.nseindia.com"
NSE_API     = "https://www.nseindia.com/api/annual-reports?index=equities&symbol={symbol}"
BSE_API     = "https://api.bseindia.com/BseIndiaAPI/api/AnnualReport/w?scripcode={code}"
BSE_PDF_BASE = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/"

# NSE blocks requests without a real browser User-Agent + Referer.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
}


# ── NSE helpers ───────────────────────────────────────────────────────────────

def init_nse_session(client: httpx.Client) -> bool:
    """
    NSE requires a real browser session — cookies from the homepage are
    checked by the API endpoints. This step mimics opening nseindia.com
    in a browser tab before making any API calls.
    """
    try:
        resp = client.get(
            NSE_HOME,
            headers={**BROWSER_HEADERS, "Accept": "text/html,application/xhtml+xml"},
            timeout=15,
        )
        print(f"  NSE session init: HTTP {resp.status_code}, "
              f"cookies: {list(resp.cookies.keys())}")
        return resp.status_code == 200
    except Exception as exc:
        print(f"  NSE session init failed: {exc}")
        return False


def fetch_nse_reports(client: httpx.Client, symbol: str) -> list[dict]:
    """
    Call the NSE annual-reports API.
    Returns list of report dicts; each has 'pdfLink' and 'year' keys.
    """
    url = NSE_API.format(symbol=symbol)
    try:
        resp = client.get(
            url,
            headers={**BROWSER_HEADERS, "Referer": NSE_HOME + "/"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            # NSE returns {"data": [...]} or just a list depending on endpoint version
            if isinstance(data, dict):
                return data.get("data", [])
            if isinstance(data, list):
                return data
        else:
            print(f"    NSE HTTP {resp.status_code}")
    except Exception as exc:
        print(f"    NSE error: {exc}")
    return []


# ── BSE helpers ───────────────────────────────────────────────────────────────

def fetch_bse_reports(code: str) -> list[dict]:
    """
    Call the BSE annual-reports API. Uses a fresh client (no session needed
    most of the time). Returns raw JSON or empty list on failure.
    BSE redirects to a login page for some companies — we detect that.
    """
    url = BSE_API.format(code=code)
    try:
        # follow_redirects=False so we detect the auth redirect
        resp = httpx.get(
            url,
            headers={**BROWSER_HEADERS, "Referer": "https://www.bseindia.com/"},
            timeout=15,
            follow_redirects=False,
        )
        if resp.status_code in (301, 302):
            print(f"    BSE redirect to {resp.headers.get('location')} — auth required")
            return []
        if resp.status_code == 200:
            return resp.json() if resp.text.strip() else []
    except Exception as exc:
        print(f"    BSE error: {exc}")
    return []


def bse_pdf_url(filename: str) -> str:
    return BSE_PDF_BASE + filename


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch annual report URLs")
    parser.add_argument("--source", choices=["nse", "bse", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print company list without fetching")
    args = parser.parse_args()

    if args.dry_run:
        for c in COMPANIES:
            print(f"{c['name']:25s}  BSE={c['bse']}  NSE={c['nse']}")
        return

    results: list[dict] = []

    # One persistent httpx.Client for NSE (keeps the session cookies alive)
    with httpx.Client(follow_redirects=True) as nse_client:

        if args.source in ("nse", "both"):
            print("── Step 1: Initialize NSE session ──")
            init_nse_session(nse_client)
            time.sleep(2)  # brief pause after homepage load

        for company in COMPANIES:
            name = company["name"]
            print(f"\n[{name}]")
            pdf_url: Optional[str] = None
            year: str = "—"
            source_used = "—"

            # ── Try NSE ──
            if args.source in ("nse", "both"):
                reports = fetch_nse_reports(nse_client, company["nse"])
                if reports:
                    latest = reports[0]
                    # NSE field names vary; try common keys
                    pdf_url = (
                        latest.get("pdfLink")
                        or latest.get("fileName")
                        or latest.get("attachment")
                    )
                    year = latest.get("year") or latest.get("finYear", "—")
                    source_used = "NSE"
                    print(f"  ✓ NSE: {year} → {str(pdf_url)[:80]}")
                else:
                    print(f"  ✗ NSE: no data")

            # ── Try BSE if NSE failed ──
            if pdf_url is None and args.source in ("bse", "both"):
                bse_data = fetch_bse_reports(company["bse"])
                if bse_data:
                    # Raw BSE response — dump first entry for inspection
                    first = bse_data[0] if isinstance(bse_data, list) else bse_data
                    print(f"  ✓ BSE raw: {json.dumps(first, indent=2)[:200]}")
                    # Try to extract filename field (varies by BSE API version)
                    fn = (
                        first.get("ATTACHMENTNAME")
                        or first.get("filename")
                        or first.get("Filename")
                    )
                    if fn:
                        pdf_url = bse_pdf_url(fn)
                        source_used = "BSE"
                        print(f"  ✓ BSE URL: {pdf_url}")
                    else:
                        print(f"  ✗ BSE: unexpected shape — inspect raw above")
                else:
                    print(f"  ✗ BSE: no data")

            if pdf_url is None:
                pdf_url = "MANUAL_LOOKUP_NEEDED"

            results.append({
                "name":   name,
                "bse":    company["bse"],
                "nse":    company["nse"],
                "year":   year,
                "url":    pdf_url,
                "source": source_used,
            })

            time.sleep(1)  # 1 req/sec — be polite to the APIs

    # ── Print markdown table ──────────────────────────────────────────────────
    print("\n\n" + "=" * 80)
    print("RESULTS — paste the URL column into docs/data-sources.md")
    print("=" * 80 + "\n")

    print("| Company | BSE Code | NSE Symbol | IR Page | Annual Report URL | Status |")
    print("|---|---|---|---|---|---|")
    for r in results:
        ok = r["url"] != "MANUAL_LOOKUP_NEEDED"
        status = "✅" if ok else "⏳"
        url_cell = r["url"] if ok else "—"
        print(f"| {r['name']} | {r['bse']} | {r['nse']} | — | {url_cell} | {status} |")

    manual = [r["name"] for r in results if r["url"] == "MANUAL_LOOKUP_NEEDED"]
    if manual:
        print(f"\n⚠️  Manual lookup needed for: {', '.join(manual)}")
        print("   → Go to the company's IR page (see data-sources.md) and")
        print("     find the latest Annual Report PDF link directly.")


if __name__ == "__main__":
    main()
