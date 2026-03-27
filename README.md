# YONEPSE - Real-time NEPSE Stock Dashboard

![YONEPSE Favicon](favicon.png)

![YONEPSE](https://img.shields.io/badge/Status-Active-success)
![License](https://img.shields.io/badge/License-MIT-blue)

A modern, elegant, and comprehensive dashboard as well as open api for tracking live stock prices from the Nepal Stock Exchange (NEPSE). Features real-time market data, sector filtering, IPO tracking, broker directory, and automated data updates via GitHub Actions.

---

## 🚀 Features

### Market Dashboard
- **Live Market Data**: Real-time stock prices, changes, and volumes
- **Sector Filtering**: Filter stocks by sectors (Hydro, Banking, Insurance, etc.)
- **Instant Search**: Search by stock symbol or company name
- **Market Indices**: Live NEPSE indices with animated marquee
- **Top Movers**: Real-time top gainers and losers
- **Stock Detail Modal**: Click any stock for detailed information

### IPO Tracking
- **Upcoming IPOs**: Track open, upcoming, and closed IPOs
- **Nepali Date Support**: Automatic BS to AD date conversion
- **Status Badges**: Visual indicators for Open/Upcoming/Closed IPOs
- **Reserved Shares**: Special indicators for NRN/reserved share issues

### Data Hub
- **Broker Directory**: Complete broker listings with filters
- **Membership Types**: Filter by broker membership category
- **District/Province Filters**: Geographic broker search
- **TMS Links**: Direct access to broker trading platforms
- **Market History**: Historical market summary data
- **Open-Ended Mutual Funds**: Daily/weekly/monthly NAV snapshots in dedicated dataset

### JSON API
All data is available as static JSON endpoints for developers. See [JSON Docs](docs.html) for complete API reference.

- Public static API spec: [`openapi.yaml`](openapi.yaml)
- Legacy NEPSE upstream endpoint spec: [`openapi_legacy_nepse.yaml`](openapi_legacy_nepse.yaml)

---

## 🖼️ Live Demo

Visit the dashboard at: `https://shubhamnpk.github.io/yonepse/` or 

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
├── index.html                    # Main market dashboard
├── data.html                     # Brokers & datasets page
├── docs.html                     # JSON API documentation
├── script.js                     # Main dashboard logic
├── data.js                       # Data hub logic
├── style.css                     # All styling (glassmorphism)
├── start_server.bat              # Windows local server starter
├── favicon.png                   # Site favicon
├── data/                         # JSON data files
│   ├── nepse_data.json             # Stock prices
│   ├── OMF.json                    # Open-ended mutual fund NAV data
│   ├── indices.json              # Market indices
│   ├── sector_indices.json       # Sector indices
│   ├── top_stocks.json           # Top gainers/losers
│   ├── market_summary.json       # Current market summary
│   ├── market_summary_history.json
│   ├── market_status.json        # Market open/closed status
│   ├── notices.json              # Exchange notices
│   ├── disclosures.json          # Company disclosures
│   ├── exchange_messages.json    # Exchange announcements
│   ├── brokers.json              # Broker directory
│   ├── all_securities.json       # Securities metadata
│   ├── supply_demand.json        # Supply/demand data
│   ├── upcoming_ipo.json         # Upcoming IPOs
│   ├── oldipo.json               # IPO archive
│   ├── proposed_dividend/        # Proposed dividend datasets
│   │   ├── latest_1y.json        # Latest proposed dividends (rolling 1 year)
│   │   ├── history_all_years.json # Append-only all-years proposed dividend history
│   │   └── meta.json             # Proposed dividend scraper metadata
│   └── nepse_sector_wise_codes.json
├── scripts/nepse-scraper/
│   ├── official_scraper.py       # Main NEPSE API scraper
│   ├── open_ended_mutual_fund_scraper.py # ShareSansar OMF scraper (reused by official_scraper.py)
│   ├── upcoming_ipo_scraper.py   # IPO scraper
│   ├── proposed_dividend_scraper.py # Proposed dividend scraper
│   ├── scraper.py                # Backup web scraper
│   ├── requirements.txt          # Python dependencies
│   └── official_api/             # NEPSE API client
│       ├── __init__.py
│       ├── auth.py                 # Authentication
│       ├── client.py               # API client
│       ├── core.py                 # Core functionality
│       ├── endpoints.py            # API endpoints
│       ├── exceptions.py           # Custom exceptions
│       └── nepse.wasm              # WebAssembly for auth
└── .github/workflows/
    ├── scrape.yml                  # Market data automation
    └── scrape_ipo.yml            # IPO data automation
```

---

## 📦 Installation & Usage

### 1. Fork & Setup (GitHub Pages)

1. Fork this repository
2. Enable **GitHub Actions** in the 'Actions' tab
3. Enable **GitHub Pages** from Settings > Pages (Deploy from `main` branch)
4. Your dashboard will be live at `https://shubhamnpk.github.io/yonepse/`

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
```

---

## 🔄 Automation (GitHub Actions)

### Market Data Scraper ([`.github/workflows/scrape.yml`](.github/workflows/scrape.yml))
- **Schedule**: Every 30 minutes
- **Time**: 10:00 AM - 4:00 PM NPT (Sunday - Friday)
- **Data**: Stock prices, indices, market summary, top stocks, notices, disclosures, exchange messages, supply/demand, and open-ended mutual fund NAVs
- **Files**: Updates all JSON files in `data/` folder
- **OMF Integration**: Refreshes `data/OMF.json` and merges open-ended mutual funds into `data/nepse_data.json` in the same run

### IPO Scraper ([`.github/workflows/scrape_ipo.yml`](.github/workflows/scrape_ipo.yml))
- **Schedule**: Daily at 4:00 AM UTC (9:45 AM NPT)
- **Data**: Upcoming IPO announcements + proposed dividend refresh
- **Files**: `data/upcoming_ipo.json`, `data/oldipo.json`, `data/proposed_dividend/latest_1y.json`, `data/proposed_dividend/history_all_years.json`, `data/proposed_dividend/meta.json`
- **Features**: Auto-archives IPOs older than 10 days and updates proposed dividend datasets

---

## 📋 Available JSON Endpoints

All data is accessible as static JSON endpoints:

| Endpoint | Type | Description |
|----------|------|-------------|
| `/data/nepse_data.json` | Array | Market prices + mapped open-ended mutual fund rows (`asset_type: open_ended_mutual_fund`) |
| `/data/OMF.json` | Array | Open-ended mutual fund NAV dataset (daily/weekly/monthly NAV + fund metadata) |
| `/data/indices.json` | Array | Main NEPSE indices |
| `/data/sector_indices.json` | Array | Sector-wise indices |
| `/data/top_stocks.json` | Object | Top gainers, losers, turnover |
| `/data/market_summary.json` | Object | Current day market summary |
| `/data/market_summary_history.json` | Array | Historical market data |
| `/data/market_status.json` | Object | Market open/closed status |
| `/data/disclosures.json` | Array | Company disclosures |
| `/data/exchange_messages.json` | Array | Exchange announcements |
| `/data/brokers.json` | Array | Complete broker directory |
| `/data/all_securities.json` | Array | Master list of securities metadata |
| `/data/supply_demand.json` | Object | Supply/demand snapshots |
| `/data/upcoming_ipo.json` | Array | Upcoming IPO listings |
| `/data/oldipo.json` | Array | Historical IPO archive |
| `/data/notices.json` | Object | Exchange & company notices |
| `/data/proposed_dividend/latest_1y.json` | Array | Latest proposed dividends (rolling 1 year) |
| `/data/proposed_dividend/history_all_years.json` | Array | Append-only all-years proposed dividend history |
| `/data/proposed_dividend/meta.json` | Object | Proposed dividend scraper run metadata |
| `/data/nepse_sector_wise_codes.json` | Object | Sector mapping for stocks |

See [`docs.html`](docs.html) for complete documentation.

---

## ⚡ Developer Quickstart

Base URL:

```text
https://shubhamnpk.github.io/yonepse
```

Common calls:

```bash
# Market status
curl -s https://shubhamnpk.github.io/yonepse/data/market_status.json

# Main ticker feed (includes mapped OMF rows)
curl -s https://shubhamnpk.github.io/yonepse/data/nepse_data.json

# Full open-ended mutual fund NAV dataset
curl -s https://shubhamnpk.github.io/yonepse/data/OMF.json
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
- [`style.css`](style.css) - Complete styling (1685 lines)

#### Backend
- [`official_scraper.py`](scripts/nepse-scraper/official_scraper.py) - Main scraper using NEPSE API
- [`open_ended_mutual_fund_scraper.py`](scripts/nepse-scraper/open_ended_mutual_fund_scraper.py) - ShareSansar open-ended mutual fund scraper (called by `official_scraper.py`)
- [`upcoming_ipo_scraper.py`](scripts/nepse-scraper/upcoming_ipo_scraper.py) - IPO data from Merolagani
- [`proposed_dividend_scraper.py`](scripts/nepse-scraper/proposed_dividend_scraper.py) - Proposed dividend data from ShareSansar
- [`official_api/`](scripts/nepse-scraper/official_api/) - NEPSE API Python client with WASM auth

---

## 📱 Data Sources

- **NEPSE Official API**: Primary source for market data
- **Merolagani**: IPO announcements and company news
- **ShareSansar**: Backup data source

Data is scraped for educational purposes. All data credits belong to the respective owners.

---

## 🤝 Credits

- **Developers**: My Wallet Team & Yoguru Team & [@Shubhamnpk](https://github.com/Shubhamnpk)
- **Data Sources**: Nepal Stock Exchange (NEPSE), Merolagani, ShareSansar
- **Not affiliated with**: NEPSE, Merolagani, or ShareSansar

---

## 📄 License

This project is open-source and available under the MIT License.

---

## 📞 Support

For issues, feature requests, or contributions, please open an issue on GitHub.

---

<p align="center">
  <sub>Built with ❤️ for the Nepali investment community</sub>
</p>

