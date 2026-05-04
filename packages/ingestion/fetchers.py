"""
Sentinel — Filing Fetchers

Three public functions used by the ingestion pipeline:
  - lookup_company(ticker)      → CompanyInfo (name, bse_code, nse_symbol)
  - fetch_annual_report_url(ticker, client) → PDF URL string from NSE API
  - download_pdf(url, client)   → raw bytes of the PDF

NSE session note: NSE blocks headless requests. The caller must pass a shared
httpx.Client that has already visited the NSE homepage (init_nse_session).
The ingest.py CLI handles this setup once per run.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ── Company registry ──────────────────────────────────────────────────────────
# Single source of truth for ticker → BSE code + NSE symbol mapping.
# Mirrors the 20 companies in docs/data-sources.md.

_REGISTRY: dict[str, dict[str, str]] = {
    "TCS":        {"name": "Tata Consultancy Services", "bse": "532540", "nse": "TCS"},
    "INFY":       {"name": "Infosys",                   "bse": "500209", "nse": "INFY"},
    "HDFCBANK":   {"name": "HDFC Bank",                 "bse": "500180", "nse": "HDFCBANK"},
    "RELIANCE":   {"name": "Reliance Industries",       "bse": "500325", "nse": "RELIANCE"},
    "ICICIBANK":  {"name": "ICICI Bank",                "bse": "532174", "nse": "ICICIBANK"},
    "WIPRO":      {"name": "Wipro",                     "bse": "507685", "nse": "WIPRO"},
    "HCLTECH":    {"name": "HCL Technologies",          "bse": "532281", "nse": "HCLTECH"},
    "KOTAKBANK":  {"name": "Kotak Mahindra Bank",       "bse": "500247", "nse": "KOTAKBANK"},
    "BAJFINANCE": {"name": "Bajaj Finance",             "bse": "500034", "nse": "BAJFINANCE"},
    "ASIANPAINT": {"name": "Asian Paints",              "bse": "500820", "nse": "ASIANPAINT"},
    "MARUTI":     {"name": "Maruti Suzuki",             "bse": "532500", "nse": "MARUTI"},
    "SUNPHARMA":  {"name": "Sun Pharma",                "bse": "524715", "nse": "SUNPHARMA"},
    "TITAN":      {"name": "Titan Company",             "bse": "500114", "nse": "TITAN"},
    "LT":         {"name": "Larsen & Toubro",           "bse": "500510", "nse": "LT"},
    "ULTRACEMCO": {"name": "UltraTech Cement",          "bse": "532538", "nse": "ULTRACEMCO"},
    "NESTLEIND":  {"name": "Nestle India",              "bse": "500790", "nse": "NESTLEIND"},
    "POWERGRID":  {"name": "Power Grid Corp",           "bse": "532898", "nse": "POWERGRID"},
    "NTPC":       {"name": "NTPC",                      "bse": "532555", "nse": "NTPC"},
    "ITC":        {"name": "ITC",                       "bse": "500875", "nse": "ITC"},
    "AXISBANK":   {"name": "Axis Bank",                 "bse": "532215", "nse": "AXISBANK"},
}


@dataclass
class CompanyInfo:
    ticker: str
    name: str
    bse_code: str
    nse_symbol: str


# ── NSE constants ─────────────────────────────────────────────────────────────

NSE_HOME = "https://www.nseindia.com"
NSE_ANNUAL_REPORTS_API = (
    "https://www.nseindia.com/api/annual-reports?index=equities&symbol={symbol}"
)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",  # omit brotli — httpx needs extra dep for br
    "Connection":      "keep-alive",
}


# ── Public API ────────────────────────────────────────────────────────────────

def lookup_company(ticker: str) -> CompanyInfo:
    """
    Return CompanyInfo for a ticker (case-insensitive).
    Raises ValueError for unknown tickers.
    """
    key = ticker.upper()
    entry = _REGISTRY.get(key)
    if entry is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown ticker '{ticker}'. Supported: {supported}")
    return CompanyInfo(
        ticker=key,
        name=entry["name"],
        bse_code=entry["bse"],
        nse_symbol=entry["nse"],
    )


def init_nse_session(client: httpx.Client) -> None:
    """
    Warm up the NSE session by visiting the homepage.

    NSE's API endpoints check for cookies set by the homepage. Without this
    step every API call returns 401/403. One call per httpx.Client is enough
    because the client persists cookies across requests.
    """
    client.get(
        NSE_HOME,
        headers={**_BROWSER_HEADERS, "Accept": "text/html,application/xhtml+xml"},
        timeout=15,
    )
    time.sleep(1)  # brief pause — mimics a real browser tab loading


def fetch_annual_report_url(ticker: str, client: httpx.Client) -> str:
    """
    Return the PDF URL of the latest annual report for *ticker* from NSE.

    The client must have been warmed up with init_nse_session() first.
    Raises RuntimeError if NSE returns no data for the ticker.
    """
    company = lookup_company(ticker)
    url = NSE_ANNUAL_REPORTS_API.format(symbol=company.nse_symbol)

    resp = client.get(
        url,
        headers={**_BROWSER_HEADERS, "Referer": NSE_HOME + "/"},
        timeout=15,
    )
    resp.raise_for_status()

    data = resp.json()
    reports: list[dict] = data.get("data", data) if isinstance(data, dict) else data

    if not reports:
        raise RuntimeError(f"NSE returned no annual reports for '{ticker}'")

    latest = reports[0]
    pdf_url = (
        latest.get("pdfLink")
        or latest.get("fileName")
        or latest.get("attachment")
    )
    if not pdf_url:
        raise RuntimeError(
            f"Could not extract PDF URL from NSE response for '{ticker}': {latest}"
        )

    return str(pdf_url)


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def download_pdf(url: str, client: httpx.Client) -> bytes:
    """
    Download a PDF from *url* and return its raw bytes.

    Retries up to 3 times with exponential backoff (2s → 4s → 8s) on any
    HTTP or timeout error. The @retry decorator from tenacity handles this.
    """
    resp = client.get(
        url,
        headers=_BROWSER_HEADERS,
        timeout=60,
        follow_redirects=True,
    )
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "pdf" not in content_type and not url.endswith(".pdf"):
        raise RuntimeError(
            f"Expected a PDF but got content-type '{content_type}' from {url}"
        )

    return resp.content
