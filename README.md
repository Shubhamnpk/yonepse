# YONEPSE - Real-time NEPSE Stock Dashboard & Static API

![YONEPSE Favicon](assets/img/favicon.png)

**Current app version:** YONEPSE v2

> [!NOTE]
> **Folder-based JSON endpoints are canonical.** Legacy flat paths (`data/*.json`) were removed — use `data/market/`, `data/notify/`, `data/ltp/`, `data/indices/`, and the other folder endpoints documented in the [JSON Docs](pages/docs.html).

![YONEPSE](https://img.shields.io/badge/Status-Active-success)
![License](https://img.shields.io/badge/License-MIT-blue)

A modern dashboard and static JSON API for tracking Nepal Stock Exchange (NEPSE) market data. It includes live market prices, interactive stock details, LTP price history, broker data, IPO archives, proposed dividends, open-ended mutual funds, and automated updates through GitHub Actions.

## Important Links

| Link | Description |
|------|-------------|
| [Live Dashboard](https://shubhamnpk.github.io/yonepse/) | Main YONEPSE market dashboard |
| [Data Hub](https://shubhamnpk.github.io/yonepse/pages/data.html) | Broker directory and dataset browser |
| [JSON Docs](https://shubhamnpk.github.io/yonepse/pages/docs.html) | Human-readable API documentation |
| [Migration Guide](https://shubhamnpk.github.io/yonepse/pages/migration.html) | Endpoint migration details and old-to-new mappings |
| [About](https://shubhamnpk.github.io/yonepse/pages/about.html) | Project version, philosophy, and system notes |
| [Index Terminal](https://shubhamnpk.github.io/yonepse/pages/terminal.html) | NEPSE + sub-index charts from open index history |
| [Sources & Credits](https://shubhamnpk.github.io/yonepse/pages/sources.html) | Every dataset and the open sources behind it |
| [OpenAPI Spec](https://shubhamnpk.github.io/yonepse/api/openapi.yaml) | Machine-readable API schema |
| [GitHub Repository](https://github.com/Shubhamnpk/yonepse) | Source code and project history |
| [Issues](https://github.com/Shubhamnpk/yonepse/issues) | Bug reports and feature requests |
| [Contributing Guide](CONTRIBUTING.md) | Local setup, PR checklist, and data change notes |
| [Workflow Flowchart](pages/workflow.html) | Cron schedules, data flow, update rules, and estimated runtime |
| [Security Policy](SECURITY.md) | Private vulnerability reporting |

---

## 🚀 Features

### Market Dashboard
- **Live Market Data**: Real-time stock prices, changes, and volumes
- **Sector Filtering**: Filter stocks by sectors (Hydro, Banking, Insurance, etc.)
- **Instant Search**: Search by stock symbol or company name
- **Market Indices**: Live NEPSE indices with animated marquee
- **Top Movers**: Real-time top gainers and losers
- **Stock Detail Modal**: Click any stock for detailed information
- **Interactive Price History**: View symbol-level LTP history with 1M, 1Y, and All range filters

### IPO & Corporate Actions
- **Upcoming IPOs**: Track open, upcoming, and closed IPOs
- **Nepali Date Support**: Automatic BS to AD date conversion
- **Status Badges**: Visual indicators for Open/Upcoming/Closed IPOs
- **Reserved Shares**: Special indicators for NRN/reserved share issues
- **Proposed Dividends**: Rolling latest data and append-only historical dividend records

### Data Hub
- **Broker Directory**: Complete broker listings with filters
- **Membership Types**: Filter by broker membership category
- **District/Province Filters**: Geographic broker search
- **TMS Links**: Direct access to broker trading platforms
- **Market History**: Historical market summary data
- **LTP History**: Monthly daily-history shards
- **Open-Ended Mutual Funds**: Daily/weekly/monthly NAV snapshots in dedicated dataset

### JSON API
All data is available as static JSON endpoints for developers. See the [JSON Docs](https://shubhamnpk.github.io/yonepse/pages/docs.html) for the published API reference, or [`pages/docs.html`](pages/docs.html) locally.

- Public static API spec: [published OpenAPI](https://shubhamnpk.github.io/yonepse/api/openapi.yaml) / [`api/openapi.yaml`](api/openapi.yaml)

### Historical Floor Sheets

Historical daily floor sheets can be downloaded from the MIT-licensed [NEPSE Open Data archive](https://github.com/socrateai-official/nepse-open-data) with the repository downloader. Downloads use bounded parallel workers and can be resumed safely:

```powershell
python scripts/download_floor_sheet_archive.py --sync --workers 16
```

The source CSVs are preserved in `data/floor_sheet/archive/`; compact app-ready JSON is written to `data/floor_sheet/daily/`. Existing JSON dates are skipped, and interrupted runs can be resumed with the same command. Use `--remove-csv` only when source CSV deletion is explicitly desired.

---

## 🖼️ Live Demo

Visit the dashboard at: [https://shubhamnpk.github.io/yonepse/](https://shubhamnpk.github.io/yonepse/)

---

## 🛠️ Tech Stack

- **Frontend**: HTML5, Vanilla CSS (Glassmorphism Design), Vanilla JavaScript
- **Styling**: CSS Variables, Gradient Backgrounds, Backdrop Filters
- **Fonts**: Google Fonts (Inter, Outfit)
- **Icons**: Font Awesome 6.4.0
- **Backend/Scraper**: Python 3.9 (NEPSE API + BeautifulSoup fallback)
- **Automation**: GitHub Actions (Scheduled Cron Jobs)
- **Data Sources**: 
  - Nepal Stock Exchange (NEPSE) Official API
  - [Merolagani](https://merolagani.com)
  - [ShareSansar](https://sharesansar.com)

---

## 📁 Project Structure

```
nepse-scraper/
|-- index.html                    # Main market dashboard
|-- pages/                        # Secondary HTML pages
|   |-- data.html                 # Brokers & datasets page
|   |-- docs.html                 # JSON API documentation
|   |-- migration.html            # Endpoint migration guide
|   |-- about.html                # Project/version overview
|   |-- sources.html              # Data sources & credits
|-- start_server.bat              # Windows local server starter
|-- api/                          # Machine-readable API specs
|   |-- openapi.yaml              # Published YONEPSE API schema
|-- assets/                       # Static frontend assets
|   |-- css/
|   |   |-- style.css             # Shared styling
|   |-- js/
|   |   |-- script.js             # Main dashboard logic
|   |   |-- data.js               # Data hub logic
|   |-- img/
|   |   |-- favicon.svg           # SVG favicon
|   |   |-- favicon.png           # PNG favicon/social image
|-- data/                         # JSON data files
|   |-- nepse_data.json           # Stock prices
|   |-- OMF.json                  # Open-ended mutual fund NAV data
|   |-- market/                   # Market snapshots and summaries
|   |   |-- indices.json          # Market indices
|   |   |-- sector_indices.json   # Sector indices
|   |   |-- top_stocks.json       # Top gainers/losers
|   |   |-- summary.json   # Current market summary
|   |   |-- history.json
|   |   |-- status.json    # Market open/closed status
|   |   |-- live.json      # Same rows as nepse_data.json
|   |   |-- supply_demand.json    # Supply/demand data
|   |-- ltp/                # LTP history shards
|   |   |-- manifest.json         # Available months + latest date
|   |   |-- monthly/              # Monthly sparse symbol history
|   |-- notify/            # Notices, disclosures, and exchange messages
|   |   |-- notices.json          # Exchange notices
|   |   |-- disclosures.json      # Company disclosures
|   |   |-- exchange_messages.json # Exchange announcements
|   |-- other/                    # Brokers and NEPSE reference datasets
|   |   |-- brokers.json          # Broker directory
|   |   |-- securities.json       # Securities metadata
|   |   |-- sector_codes.json     # Sector mapping for stocks
|   |-- ipo/                       # IPO datasets
|   |   |-- upcoming.json          # Upcoming IPOs
|   |   |-- old.json               # IPO archive
|   |-- dividend/                 # Proposed dividend datasets
|   |   |-- history.json          # Compact all-years proposed dividend history
|   |   |-- meta.json             # Proposed dividend scraper metadata
|-- scripts/nepse-scraper/
|   |-- official_scraper.py       # Main NEPSE API scraper
|   |-- open_ended_mutual_fund_scraper.py # ShareSansar OMF scraper (reused by official_scraper.py)
|   |-- upcoming_ipo_scraper.py   # IPO scraper
|   |-- proposed_dividend_scraper.py # Proposed dividend scraper
|   |-- scraper.py                # Backup web scraper
|   |-- requirements.txt          # Python dependencies
|   |-- official_api/             # NEPSE API client
|       |-- __init__.py
|       |-- auth.py               # Authentication
|       |-- client.py             # API client
|       |-- core.py               # Core functionality
|       |-- endpoints.py          # API endpoints
|       |-- exceptions.py         # Custom exceptions
|       |-- nepse.wasm            # WebAssembly for auth
|-- .github/workflows/
    |-- scrape.yml                # Market data automation
    |-- scrape_ipo.yml            # IPO data automation
```

---

## 📦 Installation & Usage

### 1. Fork & Setup (GitHub Pages)

1. Fork this repository
2. Enable **GitHub Actions** in the 'Actions' tab
3. Enable **GitHub Pages** from Settings > Pages (Deploy from `main` branch)
4. Your dashboard will be live at `https://<your-github-username>.github.io/<your-repo-name>/`

For this repository, the published site is [https://shubhamnpk.github.io/yonepse/](https://shubhamnpk.github.io/yonepse/).

### 2. Run Locally

#### Option A: Using Batch File (Windows)
```bash
start_server.bat
```

#### Option B: Using Python
```bash
python -m http.server 8000
```

Then open `http://localhost:8000` in your browser.

### 3. Manual Data Updates

To force a data update locally:

```bash
cd scripts/nepse-scraper
pip install -r requirements.txt

# Update all market data
python official_scraper.py

# Update broker data (forced)
python official_scraper.py --brokers

# Refresh company financial reports for all company IDs
# Existing historical reports are preserved; only new reports are appended.
# By default this all-company fetch runs at most once per NPT day.
python official_scraper.py --financials

# Refresh brief company profiles for all company IDs
# Existing profiles are replaced when NEPSE modifies the source profile data.
# By default this all-company fetch runs at most once per NPT day.
python official_scraper.py --profiles

# Manual override for same-day rechecks
python official_scraper.py --financials --profiles --force-financials --force-profiles

# Update IPO data
python upcoming_ipo_scraper.py

# Update proposed dividend data (daily mode)
python proposed_dividend_scraper.py --mode latest

# Optional full all-years backfill
python proposed_dividend_scraper.py --mode backfill

# Rebuild LTP monthly history shards from the current market data
python ltp_history/build_ltp_shards.py --latest-status final
```

---

## 🔄 Automation (GitHub Actions)

### Market Data Scraper ([`.github/workflows/scrape.yml`](.github/workflows/scrape.yml))
- **Schedule**: Every 30 minutes
- **Time**: 9:45 AM - 4:15 PM NPT (Monday - Friday)
- **Data**: Stock prices, indices, market summary, top stocks, notices, disclosures, exchange messages, supply/demand, and open-ended mutual fund NAVs
- **Files**: Updates market JSON files in `data/` and LTP history shards in `data/ltp/`
- **OMF Integration**: Refreshes `data/market/omf.json` and merges open-ended mutual funds into `data/nepse_data.json` in the same run
- **LTP History**: Refreshes today's monthly shard row while the market is open, then marks the row final after the close-time scan

### IPO Scraper ([`.github/workflows/scrape_ipo.yml`](.github/workflows/scrape_ipo.yml))
- **Schedule**: Daily at 4:00 AM UTC (9:45 AM NPT)
- **Data**: Upcoming IPO announcements + proposed dividend refresh
- **Files**: `data/ipo/upcoming.json`, `data/ipo/old.json`, `data/dividend/history.json`, `data/dividend/meta.json`
- **Features**: Auto-archives IPOs older than 10 days and updates proposed dividend datasets

### Floor-Sheet Capture ([`.github/workflows/scrape_floor_sheet.yml`](.github/workflows/scrape_floor_sheet.yml))
- **Schedule**: Weekdays at 3:15 PM NPT (9:30 AM UTC), after the market closes
- **Data**: One official all-market floor-sheet snapshot per trading day
- **Files**: `data/floor_sheet/daily/YYYY-MM-DD.json` and `data/floor_sheet/manifest.json`
- **Behavior**: Runs separately from intraday market scraping and skips the floor-sheet request before the 3:00 PM NPT close gate

---

## ?? Available JSON Endpoints

All data is accessible as static JSON endpoints:

| Endpoint | Type | Description |
|----------|------|-------------|
| `/data/nepse_data.json` | Array | Market prices + mapped open-ended mutual fund rows (`asset_type: open_ended_mutual_fund`) |
| `/data/market/omf.json` | Array | Open-ended mutual fund NAV dataset (daily/weekly/monthly NAV + fund metadata) |
| `/data/market/indices.json` | Array | Main NEPSE indices |
| `/data/market/sector_indices.json` | Array | Sector-wise indices |
| `/data/market/top_stocks.json` | Object | Top gainers, losers, turnover |
| `/data/market/summary.json` | Object | Current day market summary |
| `/data/market/history.json` | Array | Historical market data |
| `/data/market/live.json` | Array | Same current market rows as `/data/nepse_data.json` |
| `/data/ltp/manifest.json` | Object | LTP history manifest with available months and latest row status (`provisional` while open, `final` after close) |
| `/data/ltp/monthly/YYYY-MM.json` | Object | Monthly sparse daily LTP, volume, turnover, and trades history |
| `/data/market/status.json` | Object | Market open/closed status |
| `/data/notify/disclosures.json` | Array | Company disclosures |
| `/data/notify/exchange_messages.json` | Array | Exchange announcements |
| `/data/other/brokers.json` | Array | Complete broker directory with ratings, turnover, and daily stats from ShareHub |
| `/data/other/securities.json` | Array | Master list of securities metadata |
| `/data/company/profiles.json` | Array | Brief company profiles and contact facts from NEPSE |
| `/data/company/financials.json` | Array | Compact company financial reports from `/company/detail/{company_id}` |
| `/data/company/metadata.json` | Object | Metadata and document base URL for company financial reports |
| `/data/company/field_descriptions.json` | Object | Full forms and descriptions for financial report fields |
| `/data/market/supply_demand.json` | Object | Supply/demand snapshots |
| `/data/ipo/upcoming.json` | Array | Upcoming IPO listings |
| `/data/ipo/old.json` | Array | Historical IPO archive |
| `/data/notify/notices.json` | Object | Exchange & company notices |
| `/data/dividend/history.json` | Object | Compact all-years proposed dividend history |
| `/data/dividend/meta.json` | Object | Proposed dividend scraper run metadata |
| `/data/other/sector_codes.json` | Object | Sector mapping for stocks |

See [`pages/docs.html`](pages/docs.html) for complete documentation.

---

## ? Developer Quickstart

Base URL:

```text
https://shubhamnpk.github.io/yonepse
```

Common calls:

```bash
# Market status
curl -s https://shubhamnpk.github.io/yonepse/data/market/status.json

# Main ticker feed (includes mapped OMF rows)
curl -s https://shubhamnpk.github.io/yonepse/data/nepse_data.json

# Full open-ended mutual fund NAV dataset
curl -s https://shubhamnpk.github.io/yonepse/data/market/omf.json

# LTP history manifest
curl -s https://shubhamnpk.github.io/yonepse/data/ltp/manifest.json

# Monthly LTP history shard
curl -s https://shubhamnpk.github.io/yonepse/data/ltp/monthly/2026-05.json
```

OpenAPI spec:
- [`api/openapi.yaml`](api/openapi.yaml)

---

## 🎨 Design Features

- **Glassmorphism Design**: Translucent cards with backdrop blur
- **Dark Theme**: Optimized for extended viewing
- **Responsive Layout**: Mobile-friendly design
- **Gradient Accents**: Purple-to-pink gradient highlights
- **Smooth Animations**: Hover effects and transitions
- **Custom Scrollbar**: Styled for dark theme
- **Accessibility**: ARIA labels, keyboard navigation support

---

## 🧑‍💻 Development

### Prerequisites
- Python 3.9+
- Modern web browser
- (Optional) Local server for testing

### Key Components

#### Frontend
- [`index.html`](index.html) - Main dashboard with stock cards, search, filters
- [`data.html`](pages/data.html) - Broker directory with tables and filters
- [`docs.html`](pages/docs.html) - API documentation
- [`about.html`](pages/about.html) - Project/version overview
- [`script.js`](assets/js/script.js) - Dashboard logic, IPO date parsing, Nepali date conversion
- [`data.js`](assets/js/data.js) - Broker filtering, dataset rendering
- [`style.css`](assets/css/style.css) - Complete dashboard styling

#### Backend
- [`official_scraper.py`](scripts/nepse-scraper/official_scraper.py) - Main scraper using NEPSE API
- [`open_ended_mutual_fund_scraper.py`](scripts/nepse-scraper/open_ended_mutual_fund_scraper.py) - ShareSansar open-ended mutual fund scraper (called by `official_scraper.py`)
- [`upcoming_ipo_scraper.py`](scripts/nepse-scraper/upcoming_ipo_scraper.py) - IPO data from Merolagani
- [`proposed_dividend_scraper.py`](scripts/nepse-scraper/proposed_dividend_scraper.py) - Proposed dividend data from ShareSansar
- [`ltp_history/build_ltp_shards.py`](scripts/nepse-scraper/ltp_history/build_ltp_shards.py) - Builds sparse monthly LTP history shards
- [`ltp_history/generate_ltp_shard_demo.py`](scripts/nepse-scraper/ltp_history/generate_ltp_shard_demo.py) - Generates demo LTP shard data for testing
- [`official_api/`](scripts/nepse-scraper/official_api/) - NEPSE API Python client with WASM auth

---

## 📱 Data Sources

- **NEPSE Official API**: Primary source for market data — live prices, index snapshots, disclosures, floor sheets, and index history (2025-09 → now)
- **Merolagani**: IPO announcements and company news
- **ShareSansar**: Open-ended mutual fund NAVs and proposed dividend data
- **[socrateai-official/nepse-open-data](https://github.com/socrateai-official/nepse-open-data)**: Open index OHLC archive powering `data/indices/` history for 2003 → 2025 (all sub-indices)
- **[Nepse-Data-Analysis-From-1997--2022](https://github.com/sssss0008/Nepse-Data-Analysis-From-1997--2022)**: Community NEPSE main-index archive powering `data/indices/` history for 1997 → 2003

Data is scraped for educational purposes. All data credits belong to the respective owners. Full attribution with era coverage lives on the [Sources & Credits page](pages/sources.html).

---

## 🤝 Credits

- **Developers**: My Wallet Team & Yoguru Team & [@Shubhamnpk](https://github.com/Shubhamnpk)
- **Data Sources**: Nepal Stock Exchange (NEPSE), Merolagani, ShareSansar, [socrateai-official/nepse-open-data](https://github.com/socrateai-official/nepse-open-data), [Nepse-Data-Analysis-From-1997--2022](https://github.com/sssss0008/Nepse-Data-Analysis-From-1997--2022)
- **Not affiliated with**: NEPSE, Merolagani, ShareSansar, or any archive maintainer

---

## 🤝 Contributing

Contributions are welcome. Please read:

- [`CONTRIBUTING.md`](CONTRIBUTING.md) for local setup, data-change rules, and PR checks
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for community expectations
- [`SECURITY.md`](SECURITY.md) for private vulnerability reporting
- [`SUPPORT.md`](SUPPORT.md) for the right place to ask for help or report data issues
- [`CHANGELOG.md`](CHANGELOG.md) for notable changes

---

## ?? License

This project is open-source and available under the MIT License.

---

## 📞 Support

For issues, feature requests, or contributions, please open an issue on GitHub:
[https://github.com/Shubhamnpk/yonepse/issues](https://github.com/Shubhamnpk/yonepse/issues)

---

<p align="center">
  <sub>Built with ❤️ for the Nepali investment community</sub>
</p>

