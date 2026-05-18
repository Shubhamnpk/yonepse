# YONEPSE - Real-time NEPSE Stock Dashboard & Static API

![YONEPSE Favicon](favicon.png)

![YONEPSE](https://img.shields.io/badge/Status-Active-success)
![License](https://img.shields.io/badge/License-MIT-blue)

A modern dashboard and static JSON API for tracking Nepal Stock Exchange (NEPSE) market data. It includes live market prices, interactive stock details, LTP price history, broker data, IPO archives, proposed dividends, open-ended mutual funds, and automated updates through GitHub Actions.

## Important Links

| Link | Description |
|------|-------------|
| [Live Dashboard](https://shubhamnpk.github.io/yonepse/) | Main YONEPSE market dashboard |
| [Data Hub](https://shubhamnpk.github.io/yonepse/data.html) | Broker directory and dataset browser |
| [JSON Docs](https://shubhamnpk.github.io/yonepse/docs.html) | Human-readable API documentation |
| [Migration Guide](https://shubhamnpk.github.io/yonepse/migration.html) | Endpoint migration details and old-to-new mappings |
| [OpenAPI Spec](https://shubhamnpk.github.io/yonepse/openapi.yaml) | Machine-readable API schema |
| [GitHub Repository](https://github.com/Shubhamnpk/yonepse) | Source code and project history |
| [Issues](https://github.com/Shubhamnpk/yonepse/issues) | Bug reports and feature requests |
| [Contributing Guide](CONTRIBUTING.md) | Local setup, PR checklist, and data change notes |
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
- **LTP History**: Monthly price history shards for efficient portfolio range views
- **Open-Ended Mutual Funds**: Daily/weekly/monthly NAV snapshots in dedicated dataset

### JSON API
All data is available as static JSON endpoints for developers. See the [JSON Docs](https://shubhamnpk.github.io/yonepse/docs.html) for the published API reference, or [`docs.html`](docs.html) locally.

- **Endpoint migration notice**: New folder-based endpoints are now canonical. Legacy endpoint paths will continue to be supported for six months, until **November 18, 2026**, and will be removed after that date. See the [Migration Guide](migration.html) for old-to-new mappings and code examples.
- Public static API spec: [published OpenAPI](https://shubhamnpk.github.io/yonepse/openapi.yaml) / [`openapi.yaml`](openapi.yaml)
- Legacy NEPSE upstream endpoint spec: [`openapi_legacy_nepse.yaml`](openapi_legacy_nepse.yaml)

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
|-- data.html                     # Brokers & datasets page
|-- docs.html                     # JSON API documentation
|-- script.js                     # Main dashboard logic
|-- data.js                       # Data hub logic
|-- style.css                     # All styling
|-- start_server.bat              # Windows local server starter
|-- favicon.png                   # Site favicon
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
|   |-- ltp/                # Daily LTP history shards
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
|   |-- proposed_dividend/        # Proposed dividend datasets
|   |   |-- latest_1y.json        # Latest proposed dividends (rolling 1 year)
|   |   |-- history_all_years.json # Append-only all-years proposed dividend history
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

# Update IPO data
python upcoming_ipo_scraper.py

# Update proposed dividend data (daily mode)
python proposed_dividend_scraper.py --mode latest

# Optional full all-years backfill
python proposed_dividend_scraper.py --mode backfill

# Rebuild LTP monthly history shards from the current market data
python ltp_history/build_ltp_shards.py
```

---

## 🔄 Automation (GitHub Actions)

### Market Data Scraper ([`.github/workflows/scrape.yml`](.github/workflows/scrape.yml))
- **Schedule**: Every 30 minutes
- **Time**: 10:00 AM - 4:00 PM NPT (Sunday - Friday)
- **Data**: Stock prices, indices, market summary, top stocks, notices, disclosures, exchange messages, supply/demand, and open-ended mutual fund NAVs
- **Files**: Updates market JSON files in `data/` and LTP history shards in `data/ltp/`
- **OMF Integration**: Refreshes `data/OMF.json` and merges open-ended mutual funds into `data/nepse_data.json` in the same run
- **LTP History**: Updates monthly shards after the close-time scan so daily history changes once per market day

### IPO Scraper ([`.github/workflows/scrape_ipo.yml`](.github/workflows/scrape_ipo.yml))
- **Schedule**: Daily at 4:00 AM UTC (9:45 AM NPT)
- **Data**: Upcoming IPO announcements + proposed dividend refresh
- **Files**: `data/ipo/upcoming.json`, `data/ipo/old.json`, `data/proposed_dividend/latest_1y.json`, `data/proposed_dividend/history_all_years.json`, `data/proposed_dividend/meta.json`
- **Features**: Auto-archives IPOs older than 10 days and updates proposed dividend datasets

---

## ?? Available JSON Endpoints

All data is accessible as static JSON endpoints:

Migration notice: use the new endpoints listed below for all new integrations. Legacy paths such as `/data/indices.json`, `/data/market_status.json`, `/data/upcoming_ipo.json`, `/data/oldipo.json`, `/data/brokers.json`, `/data/all_securities.json`, `/data/nepse_sector_wise_codes.json`, and `/data/notices.json` are supported only until **November 18, 2026**.

| Endpoint | Type | Description |
|----------|------|-------------|
| `/data/nepse_data.json` | Array | Market prices + mapped open-ended mutual fund rows (`asset_type: open_ended_mutual_fund`) |
| `/data/OMF.json` | Array | Open-ended mutual fund NAV dataset (daily/weekly/monthly NAV + fund metadata) |
| `/data/market/indices.json` | Array | Main NEPSE indices |
| `/data/market/sector_indices.json` | Array | Sector-wise indices |
| `/data/market/top_stocks.json` | Object | Top gainers, losers, turnover |
| `/data/market/summary.json` | Object | Current day market summary |
| `/data/market/history.json` | Array | Historical market data |
| `/data/market/live.json` | Array | Same current market rows as `/data/nepse_data.json` |
| `/data/ltp/manifest.json` | Object | Daily LTP history manifest with available months |
| `/data/ltp/monthly/YYYY-MM.json` | Object | Monthly sparse daily LTP, volume, turnover, and trades history |
| `/data/market/status.json` | Object | Market open/closed status |
| `/data/notify/disclosures.json` | Array | Company disclosures |
| `/data/notify/exchange_messages.json` | Array | Exchange announcements |
| `/data/other/brokers.json` | Array | Complete broker directory |
| `/data/other/securities.json` | Array | Master list of securities metadata |
| `/data/market/supply_demand.json` | Object | Supply/demand snapshots |
| `/data/ipo/upcoming.json` | Array | Upcoming IPO listings |
| `/data/ipo/old.json` | Array | Historical IPO archive |
| `/data/notify/notices.json` | Object | Exchange & company notices |
| `/data/proposed_dividend/latest_1y.json` | Array | Latest proposed dividends (rolling 1 year) |
| `/data/proposed_dividend/history_all_years.json` | Array | Append-only all-years proposed dividend history |
| `/data/proposed_dividend/meta.json` | Object | Proposed dividend scraper run metadata |
| `/data/other/sector_codes.json` | Object | Sector mapping for stocks |

See [`docs.html`](docs.html) for complete documentation.

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
curl -s https://shubhamnpk.github.io/yonepse/data/OMF.json

# LTP history manifest
curl -s https://shubhamnpk.github.io/yonepse/data/ltp/manifest.json

# Monthly LTP history shard
curl -s https://shubhamnpk.github.io/yonepse/data/ltp/monthly/2026-05.json
```

OpenAPI spec:
- [`openapi.yaml`](openapi.yaml)
- [`openapi_legacy_nepse.yaml`](openapi_legacy_nepse.yaml) (legacy NEPSE upstream reference)

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
- [`data.html`](data.html) - Broker directory with tables and filters
- [`docs.html`](docs.html) - API documentation
- [`script.js`](script.js) - Dashboard logic, IPO date parsing, Nepali date conversion
- [`data.js`](data.js) - Broker filtering, dataset rendering
- [`style.css`](style.css) - Complete dashboard styling

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

- **NEPSE Official API**: Primary source for market data
- **Merolagani**: IPO announcements and company news
- **ShareSansar**: Open-ended mutual fund NAVs and proposed dividend data

Data is scraped for educational purposes. All data credits belong to the respective owners.

---

## 🤝 Credits

- **Developers**: My Wallet Team & Yoguru Team & [@Shubhamnpk](https://github.com/Shubhamnpk)
- **Data Sources**: Nepal Stock Exchange (NEPSE), Merolagani, ShareSansar
- **Not affiliated with**: NEPSE, Merolagani, or ShareSansar

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

