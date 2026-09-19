# YONEPSE - NEPSE Stock Dashboard & Static API

![YONEPSE Favicon](assets/img/favicon.png)
![Status](https://img.shields.io/badge/Status-Active-success)
![License](https://img.shields.io/badge/License-MIT-blue)

**YONEPSE v2** — Dashboard and static JSON API for Nepal Stock Exchange (NEPSE). Live prices, LTP history, broker data, IPOs, dividends, and automated GitHub Actions updates.

> [!NOTE]
> Folder-based JSON endpoints are canonical. Use `data/market/`, `data/ltp/`, `data/notify/`, `data/indices/` etc. See [JSON Docs](pages/docs.html).

## Important Links

| Link | Description |
|------|-------------|
| [Live Dashboard](https://shubhamnpk.github.io/yonepse/) | Main market dashboard |
| [Data Hub](https://shubhamnpk.github.io/yonepse/pages/data.html) | Broker directory & dataset browser |
| [JSON Docs](https://shubhamnpk.github.io/yonepse/pages/docs.html) | API documentation |
| [OpenAPI Spec](api/openapi.yaml) | Machine-readable schema |
| [Workflow](pages/workflow.html) | Cron schedules & data flow |
| [Sources & Credits](pages/sources.html) | Data sources & attribution |

## Features

- **Market:** Live prices, sector filter, search (symbol/name), indices marquee, top gainers/losers, stock detail modal with LTP history (1M/1Y/All)
- **IPO & Dividends:** Upcoming/open/closed IPOs, BS↔AD dates, proposed dividends (latest + compact history)
- **Data Hub:** Broker directory (membership/district/province/TMS), market history, LTP monthly shards, OMF NAVs
- **API:** Static JSON endpoints + OpenAPI spec

## Tech Stack

- Frontend: HTML5, Vanilla CSS (glassmorphism), Vanilla JS, Inter/Outfit, Font Awesome 6.4
- Scraper: Python 3.11, NEPSE API + BeautifulSoup, `wasmtime` auth
- Automation: GitHub Actions triggered externally via [cron-job.org](https://cron-job.org) (`workflow_dispatch`)
- Sources: NEPSE Official API, Merolagani, ShareSansar, ShareHub, socrateai-official/nepse-open-data

## Project Structure

```
index.html
pages/          # data.html, docs.html, about.html, sources.html, terminal.html, workflow.html
api/openapi.yaml
assets/{css,js,img}/
data/
  nepse_data.json
  market/       # indices, sector_indices, top_stocks, summary, history, status, live, supply_demand, omf
  ltp/manifest.json + monthly/   # sparse monthly LTP shards
  notify/       # notices, disclosures, exchange_messages
  other/        # brokers, securities, sector_codes
  company/      # profiles, financials, metadata
  ipo/          # upcoming, old
  dividend/     # history, meta
  floor_sheet/daily/ + archive/
  indices/
scripts/nepse-scraper/
  official_scraper.py
  ltp_history/build_ltp_shards.py, backfill_sharehub_price_history.py
  proposed_dividend_scraper.py, upcoming_ipo_scraper.py
  official_api/ # WASM auth client
.github/workflows/ scrape.yml (market), scrape_ipo.yml (company/IPO/dividend)
```

## Installation

```bash
# local server
start_server.bat          # Windows
# or
python -m http.server 8000
# open http://localhost:8000
```

```bash
# manual scrape
pip install -r scripts/nepse-scraper/requirements.txt
python scripts/nepse-scraper/official_scraper.py --ltp-history live-close
python scripts/nepse-scraper/proposed_dividend_scraper.py --mode latest
python scripts/nepse-scraper/ltp_history/build_ltp_shards.py --latest-status final
```

See `CONTRIBUTING.md` for full setup and data-change rules.

## Automation

Workflows are `workflow_dispatch` only (triggered by cron-job.org). No GitHub `schedule` cron.

- **Market** (`scrape.yml`, ~25 min timeout): Intraday, every ~30 min during trading hours Mon–Fri (11 AM–3 PM NPT). Runs `official_scraper.py --ltp-history live-close`, updates `data/nepse_data.json`, `data/market/*`, `data/ltp/*`, `data/notify/*`, validates (`node --check`, `compileall`, `validate_project.py`), commits as `YONEPSE Data Bot`.
- **Company/IPO/Dividend** (`scrape_ipo.yml`, ~60 min timeout): Daily Mon–Fri ~5 PM NPT. Runs `--financials --profiles`, `upcoming_ipo_scraper.py`, `proposed_dividend_scraper.py --mode latest`, sectors/brokers. Daily guard via `data/company/run_metadata.json`. Commits as `YONEPSE Ipo Bot`.
- **Floor Sheet** (`scrape_floor_sheet.yml`): Weekdays ~3:15 PM NPT after close, writes `data/floor_sheet/daily/YYYY-MM-DD.json`.

LTP shards: `live-close` updates intraday and finalizes after close; manifests track `provisional` vs `final`.

## JSON Endpoints

| Endpoint | Description |
|----------|-------------|
| `/data/nepse_data.json` | Live prices (+ OMF rows `asset_type: open_ended_mutual_fund`) |
| `/data/market/{indices,sector_indices,top_stocks,summary,history,status,live,supply_demand,omf}.json` | Market snapshots |
| `/data/ltp/manifest.json` | Available months + latest status |
| `/data/ltp/monthly/YYYY-MM.json` | Sparse daily LTP/volume/turnover/trades |
| `/data/notify/{notices,disclosures,exchange_messages}.json` | Notices & disclosures |
| `/data/other/{brokers,securities,sector_codes}.json` | Brokers & reference |
| `/data/company/{profiles,financials,metadata}.json` | Company data |
| `/data/ipo/{upcoming,old}.json` | IPO listings |
| `/data/dividend/{history,meta}.json` | Proposed dividends |

Full reference: `pages/docs.html` and `api/openapi.yaml`.

## Quickstart

```bash
curl -s https://shubhamnpk.github.io/yonepse/data/market/status.json
curl -s https://shubhamnpk.github.io/yonepse/data/nepse_data.json | head -c 500
curl -s https://shubhamnpk.github.io/yonepse/data/ltp/manifest.json
curl -s https://shubhamnpk.github.io/yonepse/data/ltp/monthly/2026-09.json | head -c 500
```

Base URL: `https://shubhamnpk.github.io/yonepse`

## Data Sources

- NEPSE Official API (prices, indices, disclosures, floor sheets)
- Merolagani (IPOs), ShareSansar (dividends/OMF), ShareHub (price history), socrateai-official/nepse-open-data (indices 2003–2025)

Full attribution: [Sources & Credits](pages/sources.html).

## Contributing

See `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`.

## License

MIT — see `LICENSE`.

<p align="center"><sub>Built for the Nepali investment community</sub></p>
