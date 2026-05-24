"""
Sentinel — FY2025 Bulk PDF Downloader
Usage: python scripts/download_fy2025.py [--dest DIR]

Downloads FY2025 (2024-25) annual report PDFs for 19 Nifty-50 companies
from NSE Archives using a session-warmed httpx client.

PDFs are saved to tmp/fy2025/{TICKER}_2025.pdf (skipped if already present).
KOTAKBANK has no direct URL and is skipped.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import typer

app = typer.Typer(name="download-fy2025", add_completion=False)

NSE_HOME = "https://www.nseindia.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

URLS: dict[str, str] = {
    "TCS": "https://nsearchives.nseindia.com/annual_reports/AR_26456_TCS_2024_2025_A_27052025233502.pdf",
    "INFY": "https://nsearchives.nseindia.com/annual_reports/AR_26481_INFY_2024_2025_A_02062025153945.pdf",
    "HDFCBANK": "https://nsearchives.nseindia.com/annual_reports/AR_27115_HDFCBANK_2024_2025_U_25072025220054.pdf",
    "RELIANCE": "https://nsearchives.nseindia.com/annual_reports/AR_27322_RELIANCE_2024_2025_A_07082025114457.pdf",
    "ICICIBANK": "https://nsearchives.nseindia.com/annual_reports/AR_27289_ICICIBANK_2024_2025_A_05082025201317.pdf",
    "WIPRO": "https://nsearchives.nseindia.com/annual_reports/AR_26582_WIPRO_2024_2025_A_21062025124943.pdf",
    "HCLTECH": "https://nsearchives.nseindia.com/annual_reports/AR_27254_HCLTECH_2024_2025_A_02082025194851.pdf",
    "BAJFINANCE": "https://nsearchives.nseindia.com/annual_reports/AR_26674_BAJFINANCE_2024_2025_A_02072025000055.pdf",
    "ASIANPAINT": "https://nsearchives.nseindia.com/annual_reports/AR_26496_ASIANPAINT_2024_2025_A_03062025224818.pdf",
    "MARUTI": "https://nsearchives.nseindia.com/annual_reports/AR_27293_MARUTI_2024_2025_A_05082025210558.pdf",
    "SUNPHARMA": "https://nsearchives.nseindia.com/annual_reports/AR_26732_SUNPHARMA_2024_2025_A_04072025175058.pdf",
    "TITAN": "https://nsearchives.nseindia.com/annual_reports/AR_26625_TITAN_2024_2025_A_27062025152121.pdf",
    "LT": "https://nsearchives.nseindia.com/annual_reports/AR_26451_LT_2024_2025_A_26052025131455.pdf",
    "ULTRACEMCO": "http://nsearchives.nseindia.com/annual_reports/AR_27126_ULTRACEMCO_2024_2025_A_28072025142546.pdf",
    "NESTLEIND": "https://nsearchives.nseindia.com/annual_reports/AR_26487_NESTLEIND_2024_2025_A_03062025002440.pdf",
    "POWERGRID": "https://nsearchives.nseindia.com/annual_reports/AR_27256_POWERGRID_2024_2025_A_03082025200555.pdf",
    "NTPC": "https://nsearchives.nseindia.com/annual_reports/AR_27336_NTPC_2024_2025_A_07082025183440.pdf",
    "ITC": "https://nsearchives.nseindia.com/annual_reports/AR_26624_ITC_2024_2025_A_27062025150548.pdf",
    "AXISBANK": "https://nsearchives.nseindia.com/annual_reports/AR_26622_AXISBANK_2024_2025_A_27062025104637.pdf",
    # KOTAKBANK: no direct URL available yet — will be added manually
}


def _download_one(client: httpx.Client, ticker: str, url: str, dest: Path) -> bool:
    """Download one PDF; returns True on success. Retries once on failure."""
    for attempt in range(2):
        try:
            resp = client.get(url, headers=_HEADERS, timeout=90, follow_redirects=True)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                typer.echo(f"  ERROR {ticker}: unexpected content-type '{content_type}'", err=True)
                return False
            dest.write_bytes(resp.content)
            typer.echo(f"  OK  {ticker}: {len(resp.content) / 1_048_576:.1f} MB → {dest.name}")
            return True
        except Exception as exc:
            if attempt == 0:
                typer.echo(f"  WARN {ticker}: {exc} — retrying in 5 s", err=True)
                time.sleep(5)
            else:
                typer.echo(f"  FAIL {ticker}: {exc}", err=True)
    return False


@app.command()
def download(
    dest: Path = typer.Option(
        Path("tmp/fy2025"),
        "--dest",
        help="Directory to save PDFs into",
        show_default=True,
    ),
) -> None:
    """Download FY2025 annual report PDFs for all 19 covered companies."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)

    typer.echo(f"\n=== FY2025 PDF Downloader — {len(URLS)} companies ===\n")
    typer.echo("[1/2] Warming up NSE session (visiting homepage)...")

    with httpx.Client(follow_redirects=True) as client:
        try:
            client.get(
                NSE_HOME,
                headers={**_HEADERS, "Accept": "text/html,application/xhtml+xml"},
                timeout=15,
            )
        except Exception as exc:
            typer.echo(f"  WARN: session warm-up failed ({exc}) — continuing anyway", err=True)
        time.sleep(1)

        typer.echo(f"[2/2] Downloading PDFs to {dest}/\n")
        ok, skip, fail = 0, 0, 0

        for ticker, url in URLS.items():
            pdf_path = dest / f"{ticker}_2025.pdf"
            if pdf_path.exists() and pdf_path.stat().st_size > 10_000:
                typer.echo(
                    f"  SKIP {ticker}: already downloaded "
                    f"({pdf_path.stat().st_size / 1_048_576:.1f} MB)"
                )
                skip += 1
                continue

            if _download_one(client, ticker, url, pdf_path):
                ok += 1
            else:
                fail += 1

    typer.echo(f"\nDone: {ok} downloaded, {skip} skipped, {fail} failed.")
    if fail:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
