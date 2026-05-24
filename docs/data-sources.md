# Data Sources

> **Owner:** Data & Retrieval Engineer
> **Status:** 🔄 In Progress (Phase 1)

This document maps every data source Sentinel ingests, including URL patterns, rate limits, terms of use, and notes for the ingestion pipeline.

---

## 1. BSE (Bombay Stock Exchange) Filings

**Base URL:** `https://www.bseindia.com`

### Annual Reports
BSE hosts annual reports as PDFs under the corporate filings section.

| Field | Detail |
|---|---|
| URL pattern | `https://www.bseindia.com/xml-data/corpfiling/AttachHis/{filename}.pdf` |
| Search endpoint | `https://api.bseindia.com/BseIndiaAPI/api/AnnualReport/w?scripcode={CODE}` |
| Rate limit | No official limit; use 1 req/sec to be safe |
| Authentication | None for public filings |
| Terms | Public data; no redistribution of raw PDFs |

### Quarterly Results
| Field | Detail |
|---|---|
| URL pattern | `https://api.bseindia.com/BseIndiaAPI/api/QuarterlyRslts/w?scripcode={CODE}` |
| Format | JSON with PDF links |

---

## 2. NSE (National Stock Exchange) Filings

**Base URL:** `https://www.nseindia.com`

| Field | Detail |
|---|---|
| Annual reports | `https://www.nseindia.com/companies-listing/corporate-filings-annual-reports` |
| API | `https://www.nseindia.com/api/annual-reports?index=equities&symbol={SYMBOL}` |
| Rate limit | ~10 req/min; requires session cookie |
| Note | NSE blocks headless requests; use session with headers |

---

## 3. Target Companies (20 Nifty-50 subset)

> **Status:** Annual report URLs filled for all 20 companies (FY2024-25, sourced via NSE archives API).
> Remaining TODO: verify machine-readable vs scanned, add Q3 FY24 transcript URLs.

| Company | BSE Code | NSE Symbol | IR Page | Annual Report URL (FY2024-25) | Status |
|---|---|---|---|---|---|
| TCS | 532540 | TCS | [link](https://www.tcs.com/investor-relations) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26456_TCS_2024_2025_A_27052025233502.pdf) | ✅ |
| Infosys | 500209 | INFY | [link](https://www.infosys.com/investors.html) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26481_INFY_2024_2025_A_02062025153945.pdf) | ✅ |
| HDFC Bank | 500180 | HDFCBANK | [link](https://www.hdfcbank.com/content/bbp/repositories/723fb80a-2dde-42a3-9793-7ae1be57c87f/?folderPath=/HPSCLFileStructure/images/aboutus/investor-relation/) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_27115_HDFCBANK_2024_2025_U_25072025220054.pdf) | ✅ |
| Reliance Industries | 500325 | RELIANCE | [link](https://www.ril.com/investor-relations) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_27322_RELIANCE_2024_2025_A_07082025114457.pdf) | ✅ |
| ICICI Bank | 532174 | ICICIBANK | [link](https://www.icicibank.com/aboutus/annual.page) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_27289_ICICIBANK_2024_2025_A_05082025201317.pdf) | ✅ |
| Wipro | 507685 | WIPRO | [link](https://www.wipro.com/investors/) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26582_WIPRO_2024_2025_A_21062025124943.pdf) | ✅ |
| HCL Technologies | 532281 | HCLTECH | [link](https://www.hcltech.com/investor-relations) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_27254_HCLTECH_2024_2025_A_02082025194851.pdf) | ✅ |
| Kotak Mahindra Bank | 500247 | KOTAKBANK | [link](https://www.kotak.com/en/investor-relations.html) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_27794_KOTAKBANK_2024_2025_A_12174639_28082025142226.pdf) | ✅ |
| Bajaj Finance | 500034 | BAJFINANCE | [link](https://www.bajajfinserv.in/investor-relations-bajaj-finance) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26674_BAJFINANCE_2024_2025_A_02072025000055.pdf) | ✅ |
| Asian Paints | 500820 | ASIANPAINT | [link](https://www.asianpaints.com/investors.html) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26496_ASIANPAINT_2024_2025_A_03062025224818.pdf) | ✅ |
| Maruti Suzuki | 532500 | MARUTI | [link](https://www.marutisuzuki.com/corporate/investors) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_27293_MARUTI_2024_2025_A_05082025210558.pdf) | ✅ |
| Sun Pharma | 524715 | SUNPHARMA | [link](https://sunpharma.com/investor-relations/) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26732_SUNPHARMA_2024_2025_A_04072025175058.pdf) | ✅ |
| Titan Company | 500114 | TITAN | [link](https://www.titancompany.in/investors) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26625_TITAN_2024_2025_A_27062025152121.pdf) | ✅ |
| Larsen & Toubro | 500510 | LT | [link](https://www.larsentoubro.com/investor-relations/) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26451_LT_2024_2025_A_26052025131455.pdf) | ✅ |
| UltraTech Cement | 532538 | ULTRACEMCO | [link](https://www.ultratechcement.com/investors) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_27126_ULTRACEMCO_2024_2025_A_28072025142546.pdf) | ✅ |
| Nestle India | 500790 | NESTLEIND | [link](https://www.nestle.in/investors) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26487_NESTLEIND_2024_2025_A_03062025002440.pdf) | ✅ |
| Power Grid Corp | 532898 | POWERGRID | [link](https://www.powergridindia.com/investor-relations) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_27256_POWERGRID_2024_2025_A_03082025200555.pdf) | ✅ |
| NTPC | 532555 | NTPC | [link](https://www.ntpc.co.in/en/investors) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_27336_NTPC_2024_2025_A_07082025183440.pdf) | ✅ |
| ITC | 500875 | ITC | [link](https://www.itcportal.com/investor-relations/) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26624_ITC_2024_2025_A_27062025150548.pdf) | ✅ |
| Axis Bank | 532215 | AXISBANK | [link](https://www.axisbank.com/shareholders-corner) | [PDF](https://nsearchives.nseindia.com/annual_reports/AR_26622_AXISBANK_2024_2025_A_27062025104637.pdf) | ✅ |

---

## 4. News Sources

### NewsAPI
| Field | Detail |
|---|---|
| Endpoint | `https://newsapi.org/v2/everything` |
| Free tier | 100 req/day, articles up to 1 month old |
| Query | `q={company_name} OR {NSE_symbol}` |
| Env var | `NEWS_API_KEY` |

---

## 5. Price Data

### Yahoo Finance (via `yfinance`)
| Field | Detail |
|---|---|
| Library | `yfinance` — no API key needed |
| Symbol format | `{NSE_SYMBOL}.NS` (e.g., `TCS.NS`) |
| Rate limit | ~2,000 req/hour unofficial |
| Use case | Daily OHLCV, 52-week high/low for context |

---

## 6. Ingestion Notes

- All PDFs are downloaded to local temp storage, processed, then discarded — we store extracted text only, not raw PDFs
- Page numbers are preserved in chunk metadata for citations
- Retry logic: 3 attempts with exponential backoff for all HTTP requests
- Filing freshness: re-ingest if `last_updated` > 90 days

---

## TODO Checklist (Data Analyst)

- [x] Verify annual report PDF URL for all 20 companies — FY2024-25 PDFs from NSE archives (via `scripts/fetch_annual_report_urls.py`)
- [ ] Test BSE API endpoint for each BSE code
- [ ] Document any companies requiring special handling (login walls, JS rendering)
- [ ] Identify which companies have machine-readable PDFs vs scanned (OCR needed)
- [ ] Add Q3 FY24 earnings transcript URLs where available
