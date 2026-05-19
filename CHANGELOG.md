# Changelog

Notable project changes should be recorded here.

The format is intentionally simple. Add newest entries at the top.

## Unreleased

## v2 - 2026-05-19

- Reorganized the frontend structure with root dashboard entry, secondary pages under `pages/`, static assets under `assets/`, and OpenAPI specs under `api/`.
- Added a modern About page for YONEPSE v2 with app version, migration notice, data-use guidance, contribution links, sources, automation notes, and guardrail summary.
- Simplified user-facing navigation by keeping developer-heavy links inside About instead of the main dashboard and Data Hub nav.
- Updated documentation, README links, issue templates, PR checklist, and contribution notes for the v2 file layout.
- Compacted public notification feeds for disclosures, exchange messages, and notices by removing heavy upstream fields and normalizing titles, body text, dates, and document links.
- Compacted broker data and kept frontend compatibility with the older broker shape.
- Cleaned proposed dividend records by removing redundant company, LTP, price date, scrape timestamp, and `[Closed]` book-close suffix fields.
- Improved LTP history handling with live-close support, latest status metadata, and official-security-based snapshot date inference.
- Added project guardrails through `scripts/validate_project.py` and a PR/manual GitHub workflow, and wired guardrail checks into scraper workflows before generated data is committed.
- Updated scraper workflow coordination to reduce overlapping data writer runs.

## Earlier

- Added open-source community files, issue templates, pull request template, and validation workflow.
- Added LTP history documentation and interactive price history UI.
