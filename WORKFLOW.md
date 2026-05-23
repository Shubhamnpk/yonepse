# YONEPSE Data Workflow

This chart shows how the scheduled data jobs move through the repository.

```mermaid
flowchart TD
    Repo[GitHub Repository] --> MarketCron
    Repo --> DailyCron
    Repo --> Guardrails

    MarketCron["Market Cron<br/>.github/workflows/scrape.yml<br/>Every 30 min, Mon-Fri<br/>~09:45-16:15 NPT"]
    DailyCron["Daily IPO + Company Cron<br/>.github/workflows/scrape_ipo.yml<br/>Once daily<br/>09:45 NPT"]
    Guardrails["Guardrails<br/>.github/workflows/guardrails.yml<br/>Pull request or manual only"]

    MarketCron --> MarketSetup["Checkout repo<br/>Install Python deps<br/>Install PyYAML"]
    MarketSetup --> MarketRun["Run official_scraper.py<br/>--ltp-history live-close"]

    MarketRun --> MarketData["Market + reference data"]
    MarketData --> LiveFiles["Live prices<br/>data/nepse_data.json<br/>data/market/live.json"]
    MarketData --> IndexFiles["Indices + summary<br/>data/market/indices.json<br/>data/market/summary.json<br/>data/market/status.json"]
    MarketData --> NotifyFiles["Notices + disclosures<br/>data/notify/notices.json<br/>data/notify/disclosures.json<br/>data/notify/exchange_messages.json"]
    MarketData --> LtpFiles["LTP history<br/>data/ltp/monthly/*<br/>data/ltp/daily/*"]
    MarketData --> OtherFiles["Reference data<br/>data/other/securities.json<br/>brokers only when due"]

    LiveFiles --> MarketValidate
    IndexFiles --> MarketValidate
    NotifyFiles --> MarketValidate
    LtpFiles --> MarketValidate
    OtherFiles --> MarketValidate

    MarketValidate["Validate<br/>JS syntax<br/>Python compile<br/>validate_project.py"] --> MarketCommit["Commit changed data<br/>git add data<br/>YONEPSE Data Bot"]

    DailyCron --> DailySetup["Checkout repo<br/>Install Python deps<br/>Install PyYAML"]
    DailySetup --> CompanyRun["Run official_scraper.py<br/>--financials --profiles --ltp-history skip"]

    CompanyRun --> DailyGuard["Daily guard<br/>data/company/run_metadata.json<br/>skip if already checked today"]
    DailyGuard --> Financials["Financial reports<br/>data/company/financials.json<br/>append-only"]
    DailyGuard --> Profiles["Company profiles<br/>data/company/profiles.json<br/>replace-on-change"]
    Financials --> CompanyMeta["Financial metadata<br/>data/company/metadata.json"]

    CompanyMeta --> IpoRun
    Profiles --> IpoRun
    IpoRun["Run IPO + dividend + sector scripts"]
    IpoRun --> IpoFiles["IPO archive<br/>data/ipo/upcoming.json<br/>data/ipo/old.json<br/>legacy IPO aliases"]
    IpoRun --> DividendFiles["Proposed dividends<br/>data/proposed_dividend/latest_1y.json<br/>data/proposed_dividend/history_all_years.json<br/>data/proposed_dividend/meta.json"]
    IpoRun --> SectorFiles["Sector aliases<br/>data/nepse_sector_wise_codes.json"]

    IpoFiles --> DailyValidate
    DividendFiles --> DailyValidate
    SectorFiles --> DailyValidate
    DailyValidate["Validate<br/>JS syntax<br/>Python compile<br/>validate_project.py"] --> DailyCommit["Commit selected data<br/>data/company + IPO/dividend/sector files<br/>YONEPSE Ipo Bot"]

    Guardrails --> GuardSetup["Checkout repo<br/>Set up Python + Node"]
    GuardSetup --> GuardChecks["JS syntax<br/>Python compile<br/>validate_project.py"]
    GuardChecks --> NoCommit["No scraping<br/>No data commit"]

    classDef cron fill:#172554,stroke:#60a5fa,color:#eff6ff
    classDef run fill:#312e81,stroke:#a78bfa,color:#f5f3ff
    classDef data fill:#064e3b,stroke:#34d399,color:#ecfdf5
    classDef validate fill:#3f2e07,stroke:#fbbf24,color:#fffbeb
    classDef commit fill:#4c0519,stroke:#fb7185,color:#fff1f2

    class MarketCron,DailyCron,Guardrails cron
    class MarketRun,CompanyRun,IpoRun,MarketSetup,DailySetup,GuardSetup,DailyGuard run
    class MarketData,LiveFiles,IndexFiles,NotifyFiles,LtpFiles,OtherFiles,Financials,Profiles,CompanyMeta,IpoFiles,DividendFiles,SectorFiles data
    class MarketValidate,DailyValidate,GuardChecks validate
    class MarketCommit,DailyCommit,NoCommit commit
```

## Estimated Runtime

| Workflow | Schedule | Estimated time | Purpose |
| --- | --- | ---: | --- |
| Market cron | Every 30 min, Mon-Fri market window | Usually a few minutes | Live market, notices, indices, LTP history |
| Daily IPO + company cron | Once daily at 09:45 NPT | About 2-4 minutes | Company financials/profiles, IPOs, dividends, sectors |
| Guardrails | Pull request/manual | Under 1 minute | Validation only |

## Key Rules

| Dataset | Update style | Why |
| --- | --- | --- |
| `data/company/financials.json` | Append-only | Historical financial reports should not be rewritten once captured |
| `data/company/profiles.json` | Replace-on-change | Company descriptions/contact details can be edited by NEPSE |
| `data/company/run_metadata.json` | Daily guard | Prevents financial/profile fetches from running more than once per Nepal day |
| Market files under `data/market`, `data/notify`, `data/ltp` | Frequent refresh/merge | These change during market activity |

