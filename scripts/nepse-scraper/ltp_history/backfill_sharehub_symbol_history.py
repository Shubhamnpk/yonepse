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

from ltp_history.backfill_sharehub_price_history import BASE_URL, clean_sharehub_row
from ltp_history.build_ltp_shards import (
    CURRENCY,
    MARKET,
    METRIC_FIELDS,
    VERSION,
    build_manifest,
    compact_sparse_row,
    ensure_month_shape,
    load_json,
    normalize_ltp,
    normalize_non_negative_number,
    normalize_symbol,
    npt_now,
    sparse_row_date_index,
    validate_month_data,
    write_json,
)


DEFAULT_PAGE_SIZE = 500
DEFAULT_SYMBOLS_PATH = os.path.join("data", "nepse_sector_wise_codes.json")
USER_AGENT = "YoNepseDataBackfill/1.0 (+https://github.com/shubhamnpk/yonepse)"


def load_symbols(path):
    data = load_json(path, {})
    symbols = set()

    if isinstance(data, dict):
        for entries in data.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict):
                    symbol = normalize_symbol(entry.get("symbol"))
                else:
                    symbol = normalize_symbol(entry)
                if symbol:
                    symbols.add(symbol)
    elif isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                symbol = normalize_symbol(entry.get("symbol"))
            else:
                symbol = normalize_symbol(entry)
            if symbol:
                symbols.add(symbol)

    return sorted(symbols)


def fetch_page(symbol, page, page_size, retries=3):
    query = urlencode({"symbol": symbol.lower(), "page": page, "size": page_size})
    request = Request(
        f"{BASE_URL}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not payload.get("success"):
                raise RuntimeError(f"unsuccessful response: {payload}")
            data = payload.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("content"), list):
                raise RuntimeError(f"invalid response shape: {payload}")
            return data
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            if attempt == retries:
                raise RuntimeError(f"ShareHub request failed for {symbol} page {page}: {exc}") from exc
            time.sleep(0.8 * attempt)


def fetch_symbol_history(symbol, page_size, sleep_seconds=0):
    rows = []
    page = 1
    scanned_pages = 0

    while True:
        data = fetch_page(symbol, page, page_size)
        content = data["content"]
        rows.extend(content)
        scanned_pages += 1

        if not data.get("hasNext") or not content:
            break

        page += 1
        if sleep_seconds:
            time.sleep(sleep_seconds)

    return rows, scanned_pages


def row_values(row):
    ltp = normalize_ltp(row.get("close"))
    if ltp is None:
        return None
    return [
        ltp,
        normalize_non_negative_number(row.get("volume")),
        normalize_non_negative_number(row.get("turnover")),
        normalize_non_negative_number(row.get("transactions")),
    ]


def upsert_symbol_rows(month_cache, symbol, rows):
    inserted = 0
    skipped = 0

    for row in rows:
        date_text = row.get("date")
        if not date_text:
            skipped += 1
            continue
        try:
            datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError:
            skipped += 1
            continue

        values = row_values(row)
        if values is None:
            skipped += 1
            continue

        month = date_text[:7]
        if month not in month_cache:
            month_cache[month] = ensure_month_shape(month_cache.get(month, {}), month)
        month_data = month_cache[month]

        dates = month_data["dates"]
        series = month_data["series"]
        if date_text in dates:
            date_index = dates.index(date_text)
        else:
            dates.append(date_text)
            dates.sort()
            date_index = dates.index(date_text)
            for symbol_rows in series.values():
                for existing_row in symbol_rows:
                    if existing_row[0] >= date_index:
                        existing_row[0] += 1

        compact_row = compact_sparse_row(date_index, values)
        if compact_row is None:
            skipped += 1
            continue

        current_rows = series.setdefault(symbol, [])
        current_rows = [
            existing_row
            for existing_row in current_rows
            if sparse_row_date_index(existing_row) != date_index
        ]
        current_rows.append(compact_row)
        series[symbol] = sorted(current_rows, key=lambda item: item[0])
        inserted += 1

    return inserted, skipped


def flush_months(output_dir, month_cache, compact=False, dry_run=False):
    files = []
    updated_at = npt_now().isoformat(timespec="seconds")

    for month, month_data in sorted(month_cache.items()):
        month_data["updatedAt"] = updated_at
        month_data["columns"] = ["dateIndex", "ltp", *METRIC_FIELDS]
        month_data["series"] = dict(sorted(month_data["series"].items()))
        validate_month_data(month_data)

        path = os.path.join(output_dir, "monthly", f"{month}.json")
        files.append(path)
        if not dry_run:
            write_json(path, month_data, compact=compact)

    return files


def write_raw_symbol(raw_dir, symbol, rows, compact=False, dry_run=False):
    if not raw_dir:
        return None

    path = os.path.join(raw_dir, f"{symbol}.json")
    payload = {
        "version": VERSION,
        "market": MARKET,
        "currency": CURRENCY,
        "source": "sharehubnepal.com/data/api/v1/price-history",
        "symbol": symbol,
        "updatedAt": npt_now().isoformat(timespec="seconds"),
        "rows": [clean_sharehub_row(row) for row in rows],
    }
    if not dry_run:
        write_json(path, payload, compact=compact)
    return path


def update_manifest(output_dir, written_months, latest_status="final", compact=False, dry_run=False):
    manifest_path = os.path.join(output_dir, "manifest.json")
    existing = load_json(manifest_path, {})
    latest_date = existing.get("latestDate") if isinstance(existing, dict) else None

    for month in written_months:
        month_path = os.path.join(output_dir, "monthly", f"{month}.json")
        month_data = load_json(month_path, {})
        if isinstance(month_data, dict):
            dates = month_data.get("dates")
            if isinstance(dates, list) and dates:
                month_latest = max(dates)
                latest_date = max(latest_date, month_latest) if latest_date else month_latest

    manifest = build_manifest(output_dir, latest_date, latest_status=latest_status)
    if isinstance(existing, dict) and existing.get("availableDays"):
        manifest["availableDays"] = sorted(set(manifest["availableDays"]) | set(existing["availableDays"]))
    if latest_status == "final" and latest_date:
        manifest["finalizedThrough"] = latest_date

    if not dry_run:
        write_json(manifest_path, manifest, compact=compact)
    return manifest_path


def backfill_symbols(
    symbols_path=DEFAULT_SYMBOLS_PATH,
    output_dir=os.path.join("data", "ltp"),
    symbols=None,
    limit=None,
    page_size=DEFAULT_PAGE_SIZE,
    sleep_seconds=0,
    raw_dir=None,
    compact=False,
    dry_run=False,
):
    all_symbols = [normalize_symbol(symbol) for symbol in symbols] if symbols else load_symbols(symbols_path)
    all_symbols = [symbol for symbol in all_symbols if symbol]
    if limit:
        all_symbols = all_symbols[:limit]

    existing_months = {}
    monthly_dir = os.path.join(output_dir, "monthly")
    if os.path.isdir(monthly_dir):
        for filename in os.listdir(monthly_dir):
            if filename.endswith(".json"):
                month = os.path.splitext(filename)[0]
                existing_months[month] = load_json(os.path.join(monthly_dir, filename), {})

    month_cache = {
        month: ensure_month_shape(month_data, month)
        for month, month_data in existing_months.items()
    }

    stats = []
    files = []
    total_pages = 0
    total_rows = 0

    for index, symbol in enumerate(all_symbols, start=1):
        print(f"[{index}/{len(all_symbols)}] fetching {symbol}", flush=True)
        rows, pages = fetch_symbol_history(symbol, page_size=page_size, sleep_seconds=sleep_seconds)
        inserted, skipped = upsert_symbol_rows(month_cache, symbol, rows)
        raw_path = write_raw_symbol(raw_dir, symbol, rows, compact=compact, dry_run=dry_run)
        if raw_path:
            files.append(raw_path)

        total_pages += pages
        total_rows += len(rows)
        stats.append(
            {
                "symbol": symbol,
                "rows": len(rows),
                "pages": pages,
                "inserted": inserted,
                "skipped": skipped,
            }
        )

    files.extend(flush_months(output_dir, month_cache, compact=compact, dry_run=dry_run))
    files.append(
        update_manifest(
            output_dir,
            written_months=month_cache.keys(),
            compact=compact,
            dry_run=dry_run,
        )
    )

    return {
        "symbols": len(all_symbols),
        "rows": total_rows,
        "pages": total_pages,
        "stats": stats,
        "files": sorted(set(files)),
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill ShareHub price history symbol-by-symbol into sparse LTP monthly shards."
    )
    parser.add_argument("--symbols-file", default=DEFAULT_SYMBOLS_PATH)
    parser.add_argument("--output", default=os.path.join("data", "ltp"))
    parser.add_argument("--symbol", action="append", help="Limit to one symbol. Can be repeated.")
    parser.add_argument("--limit", type=int, help="Limit to the first N symbols from the symbols file.")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--sleep", type=float, default=0)
    parser.add_argument("--raw-output", help="Optional per-symbol raw ShareHub output directory.")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = backfill_symbols(
        symbols_path=args.symbols_file,
        output_dir=args.output,
        symbols=args.symbol,
        limit=args.limit,
        page_size=args.page_size,
        sleep_seconds=args.sleep,
        raw_dir=args.raw_output,
        compact=args.compact,
        dry_run=args.dry_run,
    )

    print(
        "Backfilled ShareHub symbol history"
        f" for {result['symbols']} symbols, {result['rows']} rows, {result['pages']} pages."
    )
    empty = [item["symbol"] for item in result["stats"] if item["rows"] == 0]
    if empty:
        print(f"Symbols with no ShareHub rows: {', '.join(empty[:30])}")
        if len(empty) > 30:
            print(f"... {len(empty) - 30} more")
    for path in result["files"]:
        print(f"- {path}")


if __name__ == "__main__":
    main()
