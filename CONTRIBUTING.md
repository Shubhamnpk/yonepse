# Contributing to YONEPSE

Thanks for helping improve YONEPSE. This project has two main parts:

- A static dashboard built with HTML, CSS, and JavaScript.
- Python scrapers that publish JSON datasets under `data/`.

## Ways to Contribute

- Fix broken UI, links, docs, or endpoint descriptions.
- Improve scraper reliability without changing public data shape unexpectedly.
- Add tests or validation for JSON datasets and generated files.
- Report stale, incorrect, missing, or malformed market data.
- Improve accessibility and mobile behavior.

## Local Setup

```bash
pip install -r scripts/nepse-scraper/requirements.txt
python -m http.server 8000
```

Open `http://localhost:8000` in your browser.

## Data Changes

Most JSON files in `data/` are generated. Prefer changing the scraper or builder that owns the file instead of editing generated JSON by hand.

For LTP history:

```bash
python scripts/nepse-scraper/ltp_history/build_ltp_shards.py
```

For market data:

```bash
python scripts/nepse-scraper/official_scraper.py
```

## Pull Request Checklist

Before opening a PR, please check:

- The dashboard still loads locally.
- Changed JSON files are valid JSON.
- JavaScript syntax checks pass with `node --check assets/js/script.js` and `node --check assets/js/data.js`.
- Python files compile with `python -m compileall scripts`.
- Project guardrails pass with `python scripts/validate_project.py`.
- API shape changes are reflected in `pages/docs.html`, `api/openapi.yaml`, and `README.md`.
- Generated data changes are intentional and described in the PR.

## Public API Compatibility

This project is used as a static API. Avoid removing fields, renaming endpoints, or changing data types without documenting the change. If a breaking change is necessary, explain the reason and migration path in the PR.

## Commit Style

Use short, clear commit messages, for example:

- `Fix broker filter reset`
- `Add LTP history docs`
- `Update proposed dividend parser`
