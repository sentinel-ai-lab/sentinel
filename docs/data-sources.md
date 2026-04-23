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

> **TODO for Data Analyst:** Fill in BSE code, NSE symbol, and IR page for each company.

| Company | BSE Code | NSE Symbol | IR Page | Annual Report URL | Status |
|---|---|---|---|---|---|
| TCS | 532540 | TCS | [link](https://www.tcs.com/investor-relations) | — | ⏳ |
| Infosys | 500209 | INFY | [link](https://www.infosys.com/investors.html) | — | ⏳ |
| HDFC Bank | 500180 | HDFCBANK | [link](https://www.hdfcbank.com/content/bbp/repositories/723fb80a-2dde-42a3-9793-7ae1be57c87f/?folderPath=/HPSCLFileStructure/images/aboutus/investor-relation/) | — | ⏳ |
| Reliance Industries | 500325 | RELIANCE | [link](https://www.ril.com/investor-relations) | — | ⏳ |
| ICICI Bank | 532174 | ICICIBANK | [link](https://www.icicibank.com/aboutus/annual.page) | — | ⏳ |
| Wipro | 507685 | WIPRO | [link](https://www.wipro.com/investors/) | — | ⏳ |
| HCL Technologies | 532281 | HCLTECH | [link](https://www.hcltech.com/investor-relations) | — | ⏳ |
| Kotak Mahindra Bank | 500247 | KOTAKBANK | [link](https://www.kotak.com/en/investor-relations.html) | — | ⏳ |
| Bajaj Finance | 500034 | BAJFINANCE | [link](https://www.bajajfinserv.in/investor-relations-bajaj-finance) | — | ⏳ |
| Asian Paints | 500820 | ASIANPAINT | [link](https://www.asianpaints.com/investors.html) | — | ⏳ |
| Maruti Suzuki | 532500 | MARUTI | [link](https://www.marutisuzuki.com/corporate/investors) | — | ⏳ |
| Sun Pharma | 524715 | SUNPHARMA | [link](https://sunpharma.com/investor-relations/) | — | ⏳ |
| Titan Company | 500114 | TITAN | [link](https://www.titancompany.in/investors) | — | ⏳ |
| Larsen & Toubro | 500510 | LT | [link](https://www.larsentoubro.com/investor-relations/) | — | ⏳ |
| UltraTech Cement | 532538 | ULTRACEMCO | [link](https://www.ultratechcement.com/investors) | — | ⏳ |
| Nestle India | 500790 | NESTLEIND | [link](https://www.nestle.in/investors) | — | ⏳ |
| Power Grid Corp | 532898 | POWERGRID | [link](https://www.powergridindia.com/investor-relations) | — | ⏳ |
| NTPC | 532555 | NTPC | [link](https://www.ntpc.co.in/en/investors) | — | ⏳ |
| ITC | 500875 | ITC | [link](https://www.itcportal.com/investor-relations/) | — | ⏳ |
| Axis Bank | 532215 | AXISBANK | [link](https://www.axisbank.com/shareholders-corner) | — | ⏳ |

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

- [ ] Verify annual report PDF URL for all 20 companies
- [ ] Test BSE API endpoint for each BSE code
- [ ] Document any companies requiring special handling (login walls, JS rendering)
- [ ] Identify which companies have machine-readable PDFs vs scanned (OCR needed)
- [ ] Add Q3 FY24 earnings transcript URLs where available
