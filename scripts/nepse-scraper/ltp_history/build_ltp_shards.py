import argparse
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone


VERSION = 1
MARKET = "NEPSE"
CURRENCY = "NPR"
SOURCE = "nepse"
NPT = timezone(timedelta(hours=5, minutes=45))
DEFAULT_MIN_SYMBOLS = 100


def load_json(path, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def write_json(path, data, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=os.path.dirname(path),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if compact:
                json.dump(data, f, separators=(",", ":"))
            else:
                json.dump(data, f, indent=2)
                f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise

def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=NPT)
        return parsed.astimezone(NPT)
    except ValueError:
        return None


def npt_now():
    return datetime.now(NPT)


def infer_snapshot_datetime(rows):
    parsed_dates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parsed = parse_datetime(row.get("last_updated"))
        if parsed:
            parsed_dates.append(parsed)
    return max(parsed_dates) if parsed_dates else npt_now()


def normalize_symbol(value):
    return str(value or "").strip().upper()


def normalize_ltp(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not (number == number) or number < 0:
        return None
    return int(number) if number.is_integer() else number


def extract_ltp_snapshot(rows):
    prices = {}
    skipped = 0

    for row in rows:
        if not isinstance(row, dict):
            skipped += 1
            continue

        symbol = normalize_symbol(row.get("symbol"))
        ltp = normalize_ltp(row.get("ltp"))
        if not symbol or ltp is None:
            skipped += 1
            continue

        prices[symbol] = ltp

    return dict(sorted(prices.items())), skipped


def validate_snapshot_date(snapshot_date, allow_future=False):
    try:
        parsed = datetime.strptime(snapshot_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("snapshot date must use YYYY-MM-DD format") from exc

    tomorrow_npt = npt_now().date() + timedelta(days=1)
    if not allow_future and parsed > tomorrow_npt:
        raise ValueError(f"snapshot date {snapshot_date} is too far in the future")

    return parsed


def ensure_month_shape(month_data, month):
    if not isinstance(month_data, dict):
        month_data = {}

    existing_month = month_data.get("month")
    if existing_month and existing_month != month:
        raise ValueError(f"Existing shard month {existing_month} does not match target month {month}.")

    dates = month_data.get("dates")
    prices = month_data.get("prices")

    if not isinstance(dates, list):
        dates = []
    dates = [str(date) for date in dates if date]
    if len(dates) != len(set(dates)):
        raise ValueError(f"Month shard {month} contains duplicate dates.")
    if dates != sorted(dates):
        raise ValueError(f"Month shard {month} dates must be sorted.")
    bad_dates = [date for date in dates if not date.startswith(f"{month}-")]
    if bad_dates:
        raise ValueError(f"Month shard {month} contains dates outside the month: {bad_dates[:3]}.")

    if not isinstance(prices, dict):
        prices = {}

    normalized_prices = {}
    for symbol, series in prices.items():
        normalized_symbol = normalize_symbol(symbol)
        if not normalized_symbol:
            continue
        if not isinstance(series, list):
            series = []
        aligned = list(series[: len(dates)])
        if len(aligned) < len(dates):
            aligned.extend([None] * (len(dates) - len(aligned)))
        normalized_prices[normalized_symbol] = aligned

    return {
        "version": VERSION,
        "market": MARKET,
        "currency": CURRENCY,
        "month": month,
        "source": SOURCE,
        "updatedAt": month_data.get("updatedAt"),
        "dates": dates,
        "prices": normalized_prices,
    }


def validate_month_data(month_data):
    month = month_data.get("month")
    dates = month_data.get("dates")
    prices = month_data.get("prices")

    if not isinstance(month, str) or len(month) != 7:
        raise ValueError("Month shard has an invalid month field.")
    if not isinstance(dates, list):
        raise ValueError(f"Month shard {month} dates must be a list.")
    if dates != sorted(dates):
        raise ValueError(f"Month shard {month} dates must be sorted.")
    if len(dates) != len(set(dates)):
        raise ValueError(f"Month shard {month} contains duplicate dates.")
    if any(not str(item).startswith(f"{month}-") for item in dates):
        raise ValueError(f"Month shard {month} contains dates outside its month.")
    if not isinstance(prices, dict):
        raise ValueError(f"Month shard {month} prices must be an object.")

    for symbol, series in prices.items():
        if normalize_symbol(symbol) != symbol:
            raise ValueError(f"Month shard {month} has an invalid symbol key: {symbol}")
        if not isinstance(series, list):
            raise ValueError(f"Price series for {symbol} must be a list.")
        if len(series) != len(dates):
            raise ValueError(
                f"Price series for {symbol} has {len(series)} values but {len(dates)} dates."
            )


def upsert_month(month_data, date, snapshot_prices, updated_at):
    dates = month_data["dates"]
    prices = month_data["prices"]

    if date in dates:
        date_index = dates.index(date)
    else:
        dates.append(date)
        dates.sort()
        date_index = dates.index(date)
        for series in prices.values():
            series.insert(date_index, None)

    for symbol in snapshot_prices:
        if symbol not in prices:
            prices[symbol] = [None] * len(dates)
        elif len(prices[symbol]) < len(dates):
            prices[symbol].extend([None] * (len(dates) - len(prices[symbol])))

    for symbol, ltp in snapshot_prices.items():
        prices[symbol][date_index] = ltp

    month_data["updatedAt"] = updated_at
    month_data["dates"] = dates
    month_data["prices"] = dict(sorted(prices.items()))
    validate_month_data(month_data)
    return month_data


def build_manifest(output_dir, latest_date):
    monthly_dir = os.path.join(output_dir, "monthly")
    months = []
    if os.path.isdir(monthly_dir):
        months = [
            os.path.splitext(name)[0]
            for name in os.listdir(monthly_dir)
            if name.endswith(".json")
        ]

    return {
        "version": VERSION,
        "latestDate": latest_date,
        "availableMonths": sorted(set(months)),
        "retention": "no-limit",
    }


def build_shards(
    source_path,
    output_dir,
    date=None,
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
    month = snapshot_date[:7]
    updated_at = npt_now().isoformat(timespec="seconds")
    snapshot_prices, skipped = extract_ltp_snapshot(rows)

    if not snapshot_prices:
        raise ValueError("No valid LTP rows found in source snapshot.")
    if len(snapshot_prices) < min_symbols:
        raise ValueError(
            f"Only {len(snapshot_prices)} valid symbols found; refusing to update shards "
            f"below the minimum of {min_symbols}."
        )

    month_path = os.path.join(output_dir, "monthly", f"{month}.json")
    manifest_path = os.path.join(output_dir, "manifest.json")

    month_data = ensure_month_shape(load_json(month_path, {}), month)
    month_data = upsert_month(month_data, snapshot_date, snapshot_prices, updated_at)

    if not dry_run:
        write_json(month_path, month_data, compact=compact)
        manifest_data = build_manifest(output_dir, snapshot_date)
        if month not in manifest_data["availableMonths"]:
            manifest_data["availableMonths"].append(month)
            manifest_data["availableMonths"].sort()
        write_json(manifest_path, manifest_data, compact=compact)

    return {
        "source": source_path,
        "output": output_dir,
        "date": snapshot_date,
        "month": month,
        "symbol_count": len(snapshot_prices),
        "skipped_rows": skipped,
        "dry_run": dry_run,
        "files": [manifest_path, month_path],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build monthly NEPSE LTP JSON shards from data/nepse_data.json."
    )
    parser.add_argument(
        "--source",
        default=os.path.join("data", "nepse_data.json"),
        help="Source snapshot JSON file. Defaults to data/nepse_data.json.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("data", "nepse-ltp"),
        help="Output directory for manifest/latest/monthly shards.",
    )
    parser.add_argument(
        "--date",
        help="Override snapshot date as YYYY-MM-DD. Defaults to latest row timestamp date.",
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

    if args.date:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError as exc:
            raise SystemExit("--date must use YYYY-MM-DD format.") from exc

    result = build_shards(
        source_path=args.source,
        output_dir=args.output,
        date=args.date,
        compact=args.compact,
        dry_run=args.dry_run,
        min_symbols=args.min_symbols,
        allow_future=args.allow_future,
    )

    print(
        "Built NEPSE LTP shards"
        f" for {result['date']} ({result['symbol_count']} symbols,"
        f" {result['skipped_rows']} skipped rows)."
    )
    for path in result["files"]:
        print(f"- {path}")


if __name__ == "__main__":
    main()
