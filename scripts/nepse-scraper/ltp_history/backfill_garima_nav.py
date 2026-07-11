import argparse
import json
import os
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ltp_history.build_ltp_shards import (
    build_manifest,
    ensure_month_shape,
    load_json,
    npt_now,
    upsert_month,
    validate_snapshot_date,
    write_json,
)

GARIMA_BASE = "https://www.garimacapital.com/nav/category-data"
USER_AGENT = "nepse-scraper/1.0 (+https://github.com/shubhamnpk/yonepse)"

CATEGORIES = {
    10: "GSYA",
}


def fetch_json(url):
    req = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_daily(category_id):
    records = []
    page = 1
    while True:
        payload = fetch_json(f"{GARIMA_BASE}/{category_id}?daily_page={page}&weekly_page=1&monthly_page=1")
        items = payload.get("tables", {}).get("daily", {}).get("data", [])
        if not items:
            break
        records.extend(items)
        if not payload.get("tables", {}).get("daily", {}).get("pagination", {}).get("next_page_url"):
            break
        page += 1
    return records


def build_snapshot_rows(records, symbol):
    rows = []
    for item in records:
        date_str = item.get("publish_at")
        val = item.get("value")
        if not date_str or val is None:
            continue
        try:
            validate_snapshot_date(date_str)
        except ValueError:
            continue
        rows.append({
            "symbol": symbol,
            "ltp": float(val),
            "volume": None,
            "turnover": None,
            "trades": None,
            "last_updated": f"{date_str}T15:00:00+05:45",
        })
    return rows


def backfill_garima_nav(output_dir, dry_run=False, sleep_seconds=0.1):
    total_inserted = 0
    for category_id, symbol in CATEGORIES.items():
        print(f"Fetching {symbol} (category {category_id})...")
        records = fetch_all_daily(category_id)
        print(f"  Got {len(records)} daily NAV records")

        by_month = {}
        for item in records:
            date_str = item.get("publish_at")
            val = item.get("value")
            if not date_str or val is None:
                continue
            try:
                validate_snapshot_date(date_str)
            except ValueError:
                continue
            month = date_str[:7]
            by_month.setdefault(month, []).append((date_str, float(val)))

        for month, entries in sorted(by_month.items()):
            entries.sort(key=lambda x: x[0])
            month_path = os.path.join(output_dir, "monthly", f"{month}.json")
            month_data = ensure_month_shape(load_json(month_path, {}), month)
            dates = month_data["dates"]
            existing_rows = {r[0]: r for r in month_data["series"].get(symbol, [])}
            month_inserted = 0

            for date_str, val in entries:
                if date_str not in dates:
                    continue
                idx = dates.index(date_str)
                if idx in existing_rows:
                    continue
                existing_rows[idx] = [idx, val]
                month_inserted += 1

            if month_inserted == 0:
                continue
            month_data["series"][symbol] = sorted(existing_rows.values(), key=lambda r: r[0])
            if not dry_run:
                write_json(month_path, month_data)
            total_inserted += month_inserted
            print(f"  {month}: {symbol} -> {month_inserted} new entries")

        if not dry_run:
            manifest_data = build_manifest(output_dir, npt_now().date().isoformat())
            write_json(os.path.join(output_dir, "manifest.json"), manifest_data)

    return total_inserted


def main():
    parser = argparse.ArgumentParser(description="Backfill NAV history from Garima Capital into LTP shards.")
    parser.add_argument("--output", default=os.path.join("data", "ltp"), help="LTP output directory.")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing files.")
    parser.add_argument("--sleep", type=float, default=0.1, help="Seconds between API calls.")
    args = parser.parse_args()

    result = backfill_garima_nav(args.output, dry_run=args.dry_run, sleep_seconds=args.sleep)
    print(f"\nDone. {result} total entries processed.")

    if args.dry_run:
        print("Dry-run mode — no files were written.")


if __name__ == "__main__":
    main()
