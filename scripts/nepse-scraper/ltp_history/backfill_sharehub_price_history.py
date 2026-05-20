import argparse
import json
import os
import sys
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ltp_history.build_ltp_shards import (
    CURRENCY,
    MARKET,
    VERSION,
    build_manifest,
    ensure_month_shape,
    extract_ltp_snapshot,
    load_json,
    normalize_non_negative_number,
    normalize_symbol,
    npt_now,
    upsert_month,
    validate_snapshot_date,
    write_json,
)


BASE_URL = "https://sharehubnepal.com/data/api/v1/price-history"
DEFAULT_PAGE_SIZE = 500
DEFAULT_SLEEP_SECONDS = 0.15
USER_AGENT = "nepse-scraper/1.0 (+https://github.com/shubhamnpk/yonepse)"


def parse_date(value):
    return validate_snapshot_date(value)


def numeric(value):
    return normalize_non_negative_number(value)


def sharehub_row_to_snapshot(row):
    if not isinstance(row, dict):
        return None

    symbol = normalize_symbol(row.get("symbol"))
    ltp = numeric(row.get("close"))
    if not symbol or ltp is None:
        return None

    return {
        "symbol": symbol,
        "ltp": ltp,
        "volume": numeric(row.get("volume")),
        "turnover": numeric(row.get("turnover")),
        "trades": numeric(row.get("transactions")),
        "last_updated": f"{row.get('date')}T15:00:00+05:45",
    }


def clean_sharehub_row(row):
    return {
        "symbol": normalize_symbol(row.get("symbol")),
        "date": row.get("date"),
        "open": numeric(row.get("open")),
        "high": numeric(row.get("high")),
        "low": numeric(row.get("low")),
        "close": numeric(row.get("close")),
        "averageTradedPrice": numeric(row.get("averageTradedPrice")),
        "volume": numeric(row.get("volume")),
        "turnover": numeric(row.get("turnover")),
        "transactions": numeric(row.get("transactions")),
        "change": row.get("change"),
        "changePercent": row.get("changePercent"),
        "sourceId": row.get("id"),
    }


def fetch_price_history_page(page, page_size):
    query = urlencode({"page": page, "size": page_size})
    request = Request(
        f"{BASE_URL}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"ShareHub request failed with HTTP {exc.code} for page {page}.") from exc
    except URLError as exc:
        raise RuntimeError(f"ShareHub request failed for page {page}: {exc.reason}") from exc

    if not payload.get("success"):
        raise RuntimeError(f"ShareHub returned an unsuccessful response for page {page}: {payload}")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"ShareHub response for page {page} did not include data.")

    content = data.get("content")
    if not isinstance(content, list):
        raise RuntimeError(f"ShareHub response for page {page} did not include a content list.")

    return data


def collect_rows_by_date(from_date, to_date, page_size, max_pages, sleep_seconds):
    rows_by_date = {}
    scanned_pages = 0
    scanned_rows = 0
    hit_older_rows = False

    page = 1
    while True:
        data = fetch_price_history_page(page, page_size)
        content = data["content"]
        scanned_pages += 1
        scanned_rows += len(content)

        if not content:
            break

        page_dates = []
        for row in content:
            row_date_text = row.get("date")
            if not row_date_text:
                continue
            try:
                row_date = datetime.strptime(row_date_text, "%Y-%m-%d").date()
            except ValueError:
                continue

            page_dates.append(row_date)
            if from_date <= row_date <= to_date:
                rows_by_date.setdefault(row_date_text, []).append(row)
            elif row_date < from_date:
                hit_older_rows = True

        if hit_older_rows:
            break
        if max_pages and page >= max_pages:
            break
        if not data.get("hasNext"):
            break

        page += 1
        if sleep_seconds:
            time.sleep(sleep_seconds)

    return rows_by_date, {
        "scanned_pages": scanned_pages,
        "scanned_rows": scanned_rows,
    }


def write_raw_rows(raw_dir, date_text, rows, compact):
    if not raw_dir:
        return None

    path = os.path.join(raw_dir, f"{date_text}.json")
    payload = {
        "version": VERSION,
        "market": MARKET,
        "currency": CURRENCY,
        "source": "sharehubnepal.com/data/api/v1/price-history",
        "date": date_text,
        "updatedAt": npt_now().isoformat(timespec="seconds"),
        "columns": [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "averageTradedPrice",
            "volume",
            "turnover",
            "transactions",
            "change",
            "changePercent",
            "sourceId",
        ],
        "rows": sorted((clean_sharehub_row(row) for row in rows), key=lambda item: item["symbol"]),
    }
    write_json(path, payload, compact=compact)
    return path


def update_manifest(output_dir, written_dates, latest_status=None, compact=False, dry_run=False):
    manifest_path = os.path.join(output_dir, "manifest.json")
    existing = load_json(manifest_path, {})
    existing_latest = existing.get("latestDate") if isinstance(existing, dict) else None
    latest_candidates = [date for date in written_dates]
    if existing_latest:
        latest_candidates.append(existing_latest)
    latest_date = max(latest_candidates) if latest_candidates else existing_latest

    manifest = build_manifest(output_dir, latest_date, latest_status=existing.get("latestStatus"))
    if isinstance(existing, dict):
        if existing.get("latestStatus") and "latestStatus" not in manifest:
            manifest["latestStatus"] = existing["latestStatus"]
        if existing.get("finalizedThrough"):
            manifest["finalizedThrough"] = existing["finalizedThrough"]

    if latest_status and latest_date in written_dates:
        manifest["latestStatus"] = latest_status
        if latest_status == "final":
            manifest["finalizedThrough"] = latest_date

    if not dry_run:
        write_json(manifest_path, manifest, compact=compact)
    return manifest_path


def upsert_date_rows(output_dir, date_text, rows, min_symbols, compact=False, dry_run=False):
    normalized_rows = []
    for row in rows:
        normalized = sharehub_row_to_snapshot(row)
        if normalized:
            normalized_rows.append(normalized)

    snapshot_series, skipped = extract_ltp_snapshot(normalized_rows)
    if len(snapshot_series) < min_symbols:
        raise ValueError(
            f"Only {len(snapshot_series)} valid symbols found for {date_text}; "
            f"refusing to update below the minimum of {min_symbols}."
        )

    month = date_text[:7]
    month_path = os.path.join(output_dir, "monthly", f"{month}.json")
    month_data = ensure_month_shape(load_json(month_path, {}), month)
    month_data = upsert_month(
        month_data,
        date_text,
        snapshot_series,
        npt_now().isoformat(timespec="seconds"),
    )

    if not dry_run:
        write_json(month_path, month_data, compact=compact)

    return month_path, len(snapshot_series), skipped


def backfill_sharehub_price_history(
    output_dir,
    from_date,
    to_date,
    page_size=DEFAULT_PAGE_SIZE,
    max_pages=None,
    sleep_seconds=DEFAULT_SLEEP_SECONDS,
    min_symbols=100,
    latest_status="final",
    raw_dir=None,
    compact=False,
    dry_run=False,
    skip_low_symbol_days=False,
):
    from_date_obj = parse_date(from_date)
    to_date_obj = parse_date(to_date)
    if from_date_obj > to_date_obj:
        raise ValueError("--from-date must be before or equal to --to-date.")

    rows_by_date, scan_stats = collect_rows_by_date(
        from_date_obj,
        to_date_obj,
        page_size=page_size,
        max_pages=max_pages,
        sleep_seconds=sleep_seconds,
    )

    if not rows_by_date:
        raise ValueError(f"No ShareHub price-history rows found from {from_date} to {to_date}.")

    files = []
    written_dates = []
    results = []
    skipped_dates = []

    for date_text in sorted(rows_by_date):
        try:
            month_path, symbol_count, skipped = upsert_date_rows(
                output_dir,
                date_text,
                rows_by_date[date_text],
                min_symbols=min_symbols,
                compact=compact,
                dry_run=dry_run,
            )
        except ValueError as exc:
            if not skip_low_symbol_days:
                raise
            skipped_dates.append(
                {
                    "date": date_text,
                    "rawRows": len(rows_by_date[date_text]),
                    "reason": str(exc),
                }
            )
            continue
        raw_path = write_raw_rows(raw_dir, date_text, rows_by_date[date_text], compact) if not dry_run else None

        files.append(month_path)
        if raw_path:
            files.append(raw_path)
        written_dates.append(date_text)
        results.append(
            {
                "date": date_text,
                "symbols": symbol_count,
                "skipped": skipped,
                "rawRows": len(rows_by_date[date_text]),
            }
        )

    manifest_path = update_manifest(
        output_dir,
        written_dates,
        latest_status=latest_status,
        compact=compact,
        dry_run=dry_run,
    )
    files.append(manifest_path)

    return {
        "output": output_dir,
        "from_date": from_date,
        "to_date": to_date,
        "dates": results,
        "skipped_dates": skipped_dates,
        "dry_run": dry_run,
        "files": sorted(set(files)),
        **scan_stats,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Backfill NEPSE daily LTP history from ShareHub price-history. "
            "ShareHub's close field is stored as this project's ltp value."
        )
    )
    parser.add_argument("--date", help="Single trading date to backfill as YYYY-MM-DD.")
    parser.add_argument("--from-date", help="Start trading date as YYYY-MM-DD.")
    parser.add_argument("--to-date", help="End trading date as YYYY-MM-DD.")
    parser.add_argument(
        "--output",
        default=os.path.join("data", "ltp"),
        help="Output directory for manifest/monthly shards. Defaults to data/ltp.",
    )
    parser.add_argument(
        "--raw-output",
        help="Optional directory for raw ShareHub OHLC daily JSON files.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"ShareHub page size. Defaults to {DEFAULT_PAGE_SIZE}; the API rejects values above 500.",
    )
    parser.add_argument("--max-pages", type=int, help="Safety limit for scanned ShareHub pages.")
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help=f"Delay between page requests. Defaults to {DEFAULT_SLEEP_SECONDS} seconds.",
    )
    parser.add_argument(
        "--min-symbols",
        type=int,
        default=100,
        help="Minimum valid symbols required per date before writing. Defaults to 100.",
    )
    parser.add_argument(
        "--latest-status",
        choices=("provisional", "final"),
        default="final",
        help="Manifest status to apply only when the backfilled date becomes latestDate.",
    )
    parser.add_argument("--compact", action="store_true", help="Write compact JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing files.")
    parser.add_argument(
        "--skip-low-symbol-days",
        action="store_true",
        help="Skip dates below --min-symbols instead of stopping the backfill.",
    )
    args = parser.parse_args()

    if args.date:
        from_date = to_date = args.date
    else:
        if not args.from_date or not args.to_date:
            raise SystemExit("Use --date for one day, or both --from-date and --to-date for a range.")
        from_date = args.from_date
        to_date = args.to_date

    result = backfill_sharehub_price_history(
        output_dir=args.output,
        from_date=from_date,
        to_date=to_date,
        page_size=args.page_size,
        max_pages=args.max_pages,
        sleep_seconds=args.sleep,
        min_symbols=args.min_symbols,
        latest_status=args.latest_status,
        raw_dir=args.raw_output,
        compact=args.compact,
        dry_run=args.dry_run,
        skip_low_symbol_days=args.skip_low_symbol_days,
    )

    print(
        "Backfilled ShareHub price history"
        f" from {result['from_date']} to {result['to_date']}"
        f" after scanning {result['scanned_pages']} pages / {result['scanned_rows']} rows."
    )
    for item in result["dates"]:
        print(
            f"- {item['date']}: {item['symbols']} symbols"
            f" ({item['rawRows']} raw rows, {item['skipped']} skipped)"
        )
    if result["skipped_dates"]:
        print(f"Skipped {len(result['skipped_dates'])} low-symbol dates:")
        for item in result["skipped_dates"][:20]:
            print(f"- {item['date']}: {item['rawRows']} raw rows")
        if len(result["skipped_dates"]) > 20:
            print(f"- ... {len(result['skipped_dates']) - 20} more")
    for path in result["files"]:
        print(f"- {path}")


if __name__ == "__main__":
    main()
