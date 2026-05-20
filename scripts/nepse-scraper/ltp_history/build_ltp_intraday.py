import argparse
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from ltp_history.build_ltp_shards import (
    CURRENCY,
    DEFAULT_MIN_SYMBOLS,
    MARKET,
    METRIC_FIELDS,
    VERSION,
    compact_sparse_row,
    extract_ltp_snapshot,
    infer_snapshot_datetime,
    load_json,
    npt_now,
    normalize_symbol,
    sparse_row_date_index,
    validate_snapshot_date,
    write_json,
)


VALUE_COLUMNS = ("ltp",) + METRIC_FIELDS
COLUMNS = ("timeIndex",) + VALUE_COLUMNS


def validate_snapshot_time(snapshot_time):
    try:
        datetime.strptime(snapshot_time, "%H:%M")
    except ValueError as exc:
        raise ValueError("snapshot time must use HH:MM format") from exc


def ensure_day_shape(day_data, snapshot_date):
    if not isinstance(day_data, dict):
        day_data = {}

    existing_date = day_data.get("date")
    if existing_date and existing_date != snapshot_date:
        raise ValueError(
            f"Existing intraday shard date {existing_date} does not match target date {snapshot_date}."
        )

    times = day_data.get("times")
    if not isinstance(times, list):
        times = []
    times = [str(item) for item in times if item]
    if len(times) != len(set(times)):
        raise ValueError(f"Intraday shard {snapshot_date} contains duplicate times.")
    if times != sorted(times):
        raise ValueError(f"Intraday shard {snapshot_date} times must be sorted.")
    for item in times:
        validate_snapshot_time(item)

    return {
        "version": VERSION,
        "market": MARKET,
        "currency": CURRENCY,
        "date": snapshot_date,
        "updatedAt": day_data.get("updatedAt"),
        "times": times,
        "columns": list(COLUMNS),
        "series": normalize_existing_series(day_data, times),
    }


def normalize_existing_series(day_data, times):
    raw_series = day_data.get("series")
    if not isinstance(raw_series, dict):
        return {}

    normalized = {}
    for symbol, rows in raw_series.items():
        normalized_symbol = normalize_symbol(symbol)
        if not normalized_symbol or not isinstance(rows, list):
            continue

        compact_rows = []
        for row_index, row in enumerate(rows):
            existing_time_index = sparse_row_date_index(row)
            if existing_time_index is not None:
                if existing_time_index < len(times) and len(row) > 1:
                    compact_rows.append(row)
                continue

            if row_index < len(times):
                compact_row = compact_sparse_row(row_index, row)
                if compact_row is not None:
                    compact_rows.append(compact_row)

        if compact_rows:
            normalized[normalized_symbol] = sorted(compact_rows, key=lambda item: item[0])

    return normalized


def validate_day_data(day_data):
    snapshot_date = day_data.get("date")
    times = day_data.get("times")
    columns = day_data.get("columns")
    series = day_data.get("series")

    validate_snapshot_date(snapshot_date)
    if not isinstance(times, list):
        raise ValueError(f"Intraday shard {snapshot_date} times must be a list.")
    if times != sorted(times):
        raise ValueError(f"Intraday shard {snapshot_date} times must be sorted.")
    if len(times) != len(set(times)):
        raise ValueError(f"Intraday shard {snapshot_date} contains duplicate times.")
    for item in times:
        validate_snapshot_time(item)
    if columns != list(COLUMNS):
        raise ValueError(f"Intraday shard {snapshot_date} has invalid columns.")
    if not isinstance(series, dict):
        raise ValueError(f"Intraday shard {snapshot_date} series must be an object.")

    for symbol, rows in series.items():
        if normalize_symbol(symbol) != symbol:
            raise ValueError(f"Intraday shard {snapshot_date} has an invalid symbol key: {symbol}")
        if not isinstance(rows, list):
            raise ValueError(f"Series for {symbol} must be a list.")
        previous_index = -1
        for row in rows:
            if not isinstance(row, list) or len(row) < 2 or len(row) > len(COLUMNS):
                raise ValueError(f"Series row for {symbol} must be [timeIndex, ...values].")
            time_index = sparse_row_date_index(row)
            if time_index is None or time_index >= len(times):
                raise ValueError(f"Series row for {symbol} has an invalid time index.")
            if time_index <= previous_index:
                raise ValueError(f"Series rows for {symbol} must be sorted and unique by time index.")
            if any(value is None for value in row):
                raise ValueError(f"Series row for {symbol} must omit missing values, not use null.")
            previous_index = time_index


def upsert_intraday_snapshot(day_data, snapshot_time, snapshot_series, updated_at):
    times = day_data["times"]
    series = day_data["series"]

    if snapshot_time in times:
        time_index = times.index(snapshot_time)
    else:
        times.append(snapshot_time)
        times.sort()
        time_index = times.index(snapshot_time)
        for rows in series.values():
            for row in rows:
                if row[0] >= time_index:
                    row[0] += 1

    for symbol in snapshot_series:
        if symbol not in series:
            series[symbol] = []

    for symbol, values in snapshot_series.items():
        compact_row = compact_sparse_row(time_index, values)
        if compact_row is None:
            continue

        rows = [
            row
            for row in series[symbol]
            if sparse_row_date_index(row) != time_index
        ]
        rows.append(compact_row)
        series[symbol] = sorted(rows, key=lambda item: item[0])

    day_data["updatedAt"] = updated_at
    day_data["times"] = times
    day_data["columns"] = list(COLUMNS)
    day_data["series"] = dict(sorted(series.items()))
    validate_day_data(day_data)
    return day_data


def build_intraday_shard(
    source_path,
    output_dir,
    date=None,
    time=None,
    compact=False,
    dry_run=False,
    min_symbols=DEFAULT_MIN_SYMBOLS,
    allow_future=False,
):
    rows = load_json(source_path, [])
    if not isinstance(rows, list):
        raise ValueError(f"Expected {source_path} to contain a JSON array.")

    snapshot_dt = infer_snapshot_datetime(rows)
    snapshot_date = date or snapshot_dt.date().isoformat()
    validate_snapshot_date(snapshot_date, allow_future=allow_future)

    snapshot_time = time or snapshot_dt.strftime("%H:%M")
    validate_snapshot_time(snapshot_time)

    updated_at = npt_now().isoformat(timespec="seconds")
    snapshot_series, skipped = extract_ltp_snapshot(rows)

    if not snapshot_series:
        raise ValueError("No valid LTP rows found in source snapshot.")
    if len(snapshot_series) < min_symbols:
        raise ValueError(
            f"Only {len(snapshot_series)} valid symbols found; refusing to update intraday shard "
            f"below the minimum of {min_symbols}."
        )

    day_path = os.path.join(output_dir, "daily", f"{snapshot_date}.json")
    day_data = ensure_day_shape(load_json(day_path, {}), snapshot_date)
    day_data = upsert_intraday_snapshot(day_data, snapshot_time, snapshot_series, updated_at)

    if not dry_run:
        write_json(day_path, day_data, compact=compact)

    return {
        "source": source_path,
        "output": output_dir,
        "date": snapshot_date,
        "time": snapshot_time,
        "symbol_count": len(snapshot_series),
        "skipped_rows": skipped,
        "dry_run": dry_run,
        "files": [day_path],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build daily intraday NEPSE LTP JSON shards from data/nepse_data.json."
    )
    parser.add_argument(
        "--source",
        default=os.path.join("data", "nepse_data.json"),
        help="Source snapshot JSON file. Defaults to data/nepse_data.json.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("data", "ltp"),
        help="Output directory containing the daily folder. Defaults to data/ltp.",
    )
    parser.add_argument(
        "--date",
        help="Override snapshot date as YYYY-MM-DD. Defaults to latest row timestamp date.",
    )
    parser.add_argument(
        "--time",
        help="Override snapshot time as HH:MM. Defaults to latest row timestamp time.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON instead of pretty-printed JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the planned output without writing files.",
    )
    parser.add_argument(
        "--min-symbols",
        type=int,
        default=DEFAULT_MIN_SYMBOLS,
        help=f"Minimum valid symbols required before writing. Defaults to {DEFAULT_MIN_SYMBOLS}.",
    )
    parser.add_argument(
        "--allow-future",
        action="store_true",
        help="Allow future snapshot dates. Intended only for fake/demo data.",
    )
    args = parser.parse_args()

    result = build_intraday_shard(
        source_path=args.source,
        output_dir=args.output,
        date=args.date,
        time=args.time,
        compact=args.compact,
        dry_run=args.dry_run,
        min_symbols=args.min_symbols,
        allow_future=args.allow_future,
    )

    print(
        "Built NEPSE intraday LTP shard"
        f" for {result['date']} {result['time']} ({result['symbol_count']} symbols,"
        f" {result['skipped_rows']} skipped rows)."
    )
    for path in result["files"]:
        print(f"- {path}")


if __name__ == "__main__":
    main()
