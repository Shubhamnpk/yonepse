import argparse
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone


VERSION = 1
MARKET = "NEPSE"
CURRENCY = "NPR"
NPT = timezone(timedelta(hours=5, minutes=45))
DEFAULT_MIN_INDICES = 3
# close=currentValue, then OHLC context. Change/perChange are derived client-side.
METRIC_FIELDS = ("high", "low", "prevClose")
VALUE_COLUMNS = ("close",) + METRIC_FIELDS
COLUMNS = ("dateIndex",) + VALUE_COLUMNS

# Fallback when sector_indices.json is unavailable. id -> indexCode.
FALLBACK_CODE_BY_ID = {
    51: "BANKSUBIND",
    52: "HOTELIND",
    53: "OTHERSIND",
    54: "HYDPOWIND",
    55: "DEVBANKIND",
    56: "MANPROCIND",
    57: "SENSIND",
    58: "NEPSE",
    59: "NONLIFIND",
    60: "FININD",
    61: "TRDIND",
    62: "FLOATIND",
    63: "SENSFLTIND",
    64: "MICRFININD",
    65: "LIFINSIND",
    66: "MUTUALIND",
    67: "INVIDX",
}


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
                f.write(format_pretty_json(data))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


def format_pretty_json(data):
    text = json.dumps(data, indent=2)
    columns = data.get("columns") if isinstance(data, dict) else None
    if isinstance(columns, list):
        multiline = '"columns": [\n' + ",\n".join(
            f'    "{column}"' for column in columns
        ) + "\n  ]"
        inline = '"columns": ' + json.dumps(columns)
        text = text.replace(multiline, inline)

    series = data.get("series") if isinstance(data, dict) else None
    if isinstance(series, dict):
        for rows in series.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, list):
                    continue
                multiline = "      [\n" + ",\n".join(
                    f"        {json.dumps(value)}" for value in row
                ) + "\n      ]"
                inline = "      " + json.dumps(row)
                text = text.replace(multiline, inline)
    return text + "\n"


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


def load_code_by_id(data_dir):
    mapping = dict(FALLBACK_CODE_BY_ID)
    for candidate in (
        os.path.join(data_dir, "market", "sector_indices.json"),
        os.path.join(data_dir, "sector_indices.json"),
    ):
        rows = load_json(candidate, [])
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                try:
                    idx = int(row.get("id"))
                except (TypeError, ValueError):
                    continue
                code = str(row.get("indexCode") or "").strip().upper()
                if code:
                    mapping[idx] = code
    return mapping


def normalize_code(value):
    return str(value or "").strip().upper()


def normalize_number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not (number == number) or number < 0:
        return None
    return int(number) if number.is_integer() else number


def infer_snapshot_datetime(rows):
    parsed_dates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parsed = parse_datetime(row.get("generatedTime"))
        if parsed:
            parsed_dates.append(parsed)
    return max(parsed_dates) if parsed_dates else npt_now()


def extract_index_snapshot(rows, code_by_id=None):
    series = {}
    skipped = 0
    code_by_id = code_by_id or {}

    for row in rows:
        if not isinstance(row, dict):
            skipped += 1
            continue
        try:
            idx = int(row.get("id")) if row.get("id") is not None else None
        except (TypeError, ValueError):
            idx = None
        code = normalize_code(code_by_id.get(idx) if idx is not None else None)
        if not code:
            # Fallback: derive from display name e.g. "NEPSE Index" -> "NEPSE".
            name = str(row.get("index") or row.get("indexName") or "")
            token = name.strip().upper().replace(" INDEX", "").replace(" ", "_")
            code = normalize_code(token)
        close = normalize_number(
            row.get("currentValue") if row.get("currentValue") is not None else row.get("close")
        )
        if not code or close is None:
            skipped += 1
            continue
        values = [close]
        source = {
            "high": row.get("high"),
            "low": row.get("low"),
            "prevClose": row.get("previousClose"),
        }
        for field in METRIC_FIELDS:
            values.append(normalize_number(source.get(field)))
        series[code] = values

    return dict(sorted(series.items())), skipped


def validate_snapshot_date(snapshot_date, allow_future=False):
    try:
        parsed = datetime.strptime(snapshot_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("snapshot date must use YYYY-MM-DD format") from exc

    tomorrow_npt = npt_now().date() + timedelta(days=1)
    if not allow_future and parsed > tomorrow_npt:
        raise ValueError(f"snapshot date {snapshot_date} is too far in the future")

    return parsed


def sparse_row_date_index(row):
    if not isinstance(row, list) or not row:
        return None
    index = row[0]
    return index if isinstance(index, int) and index >= 0 else None


def normalize_day_values(values):
    if not isinstance(values, list):
        values = []
    normalized = list(values[: len(VALUE_COLUMNS)])
    if len(normalized) < len(VALUE_COLUMNS):
        normalized.extend([None] * (len(VALUE_COLUMNS) - len(normalized)))
    return normalized


def compact_sparse_row(date_index, values):
    normalized = normalize_day_values(values)
    if normalized[0] is None:
        return None
    while normalized and normalized[-1] is None:
        normalized.pop()
    return [date_index, *normalized]


def normalize_existing_series(month_data, dates):
    raw_series = month_data.get("series")
    if not isinstance(raw_series, dict):
        return {}
    normalized = {}
    for code, rows in raw_series.items():
        code = normalize_code(code)
        if not code or not isinstance(rows, list):
            continue
        compact_rows = []
        for row in rows:
            date_index = sparse_row_date_index(row)
            if date_index is not None:
                if date_index < len(dates) and len(row) > 1:
                    compact_rows.append(row)
                continue
        if compact_rows:
            normalized[code] = sorted(compact_rows, key=lambda item: item[0])
    return normalized


def ensure_month_shape(month_data, month):
    if not isinstance(month_data, dict):
        month_data = {}

    existing_month = month_data.get("month")
    if existing_month and existing_month != month:
        raise ValueError(f"Existing shard month {existing_month} does not match target month {month}.")

    dates = month_data.get("dates")
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

    return {
        "version": VERSION,
        "market": MARKET,
        "currency": CURRENCY,
        "month": month,
        "updatedAt": month_data.get("updatedAt"),
        "dates": dates,
        "columns": list(COLUMNS),
        "series": normalize_existing_series(month_data, dates),
    }


def validate_month_data(month_data):
    month = month_data.get("month")
    dates = month_data.get("dates")
    columns = month_data.get("columns")
    series = month_data.get("series")

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
    if columns != list(COLUMNS):
        raise ValueError(f"Month shard {month} has invalid columns.")
    if not isinstance(series, dict):
        raise ValueError(f"Month shard {month} series must be an object.")

    for code, rows in series.items():
        if normalize_code(code) != code:
            raise ValueError(f"Month shard {month} has an invalid index key: {code}")
        if not isinstance(rows, list):
            raise ValueError(f"Series for {code} must be a list.")
        previous_index = -1
        for row in rows:
            if not isinstance(row, list) or len(row) < 2 or len(row) > len(COLUMNS):
                raise ValueError(f"Series row for {code} must be [dateIndex, ...values].")
            date_index = sparse_row_date_index(row)
            if date_index is None or date_index >= len(dates):
                raise ValueError(f"Series row for {code} has an invalid date index.")
            if date_index <= previous_index:
                raise ValueError(f"Series rows for {code} must be sorted and unique by date index.")
            if any(value is None for value in row):
                raise ValueError(f"Series row for {code} must omit missing values, not use null.")
            previous_index = date_index


def upsert_month(month_data, date, snapshot_series, updated_at):
    dates = month_data["dates"]
    series = month_data["series"]

    if date in dates:
        date_index = dates.index(date)
    else:
        dates.append(date)
        dates.sort()
        date_index = dates.index(date)
        for rows in series.values():
            for row in rows:
                if row[0] >= date_index:
                    row[0] += 1

    for code in snapshot_series:
        if code not in series:
            series[code] = []

    for code, values in snapshot_series.items():
        compact_row = compact_sparse_row(date_index, values)
        if compact_row is None:
            continue
        rows = [row for row in series[code] if sparse_row_date_index(row) != date_index]
        rows.append(compact_row)
        series[code] = sorted(rows, key=lambda item: item[0])

    month_data["updatedAt"] = updated_at
    month_data["dates"] = dates
    month_data["columns"] = list(COLUMNS)
    month_data["series"] = dict(sorted(series.items()))
    validate_month_data(month_data)
    return month_data


def build_manifest(output_dir, latest_date, latest_status=None):
    monthly_dir = os.path.join(output_dir, "monthly")
    existing_manifest = load_json(os.path.join(output_dir, "manifest.json"), {})
    months = []
    if os.path.isdir(monthly_dir):
        months = [
            os.path.splitext(name)[0]
            for name in os.listdir(monthly_dir)
            if name.endswith(".json")
        ]

    manifest = {
        "version": VERSION,
        "latestDate": latest_date,
        "availableMonths": sorted(set(months)),
        "retention": "no-limit",
    }
    if latest_status:
        manifest["latestStatus"] = latest_status
        if latest_status == "final":
            manifest["finalizedThrough"] = latest_date
        elif isinstance(existing_manifest, dict) and existing_manifest.get("finalizedThrough"):
            manifest["finalizedThrough"] = existing_manifest["finalizedThrough"]
    return manifest


def build_shards(
    source_path,
    output_dir,
    data_dir=None,
    date=None,
    compact=False,
    dry_run=False,
    min_indices=DEFAULT_MIN_INDICES,
    allow_future=False,
    latest_status=None,
):
    rows = load_json(source_path, [])
    if not isinstance(rows, list):
        raise ValueError(f"Expected {source_path} to contain a JSON array.")

    snapshot_dt = infer_snapshot_datetime(rows)
    snapshot_date = date or snapshot_dt.date().isoformat()
    validate_snapshot_date(snapshot_date, allow_future=allow_future)
    month = snapshot_date[:7]
    updated_at = npt_now().isoformat(timespec="seconds")

    base_dir = data_dir
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        base_dir = os.path.join(base_dir, "..", "..")
        base_dir = os.path.normpath(os.path.join(os.path.dirname(source_path), ".."))
    code_by_id = load_code_by_id(base_dir)
    snapshot_series, skipped = extract_index_snapshot(rows, code_by_id)

    if not snapshot_series:
        raise ValueError("No valid index rows found in source snapshot.")
    if len(snapshot_series) < min_indices:
        raise ValueError(
            f"Only {len(snapshot_series)} valid indices found; refusing to update shards "
            f"below the minimum of {min_indices}."
        )

    month_path = os.path.join(output_dir, "monthly", f"{month}.json")
    manifest_path = os.path.join(output_dir, "manifest.json")

    month_data = ensure_month_shape(load_json(month_path, {}), month)
    month_data = upsert_month(month_data, snapshot_date, snapshot_series, updated_at)

    if not dry_run:
        write_json(month_path, month_data, compact=compact)
        manifest_data = build_manifest(output_dir, snapshot_date, latest_status=latest_status)
        if month not in manifest_data["availableMonths"]:
            manifest_data["availableMonths"].append(month)
            manifest_data["availableMonths"].sort()
        write_json(manifest_path, manifest_data, compact=compact)

    return {
        "source": source_path,
        "output": output_dir,
        "date": snapshot_date,
        "month": month,
        "index_count": len(snapshot_series),
        "skipped_rows": skipped,
        "dry_run": dry_run,
        "files": [manifest_path, month_path],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build monthly NEPSE index history shards from data/market/indices.json."
    )
    parser.add_argument(
        "--source",
        default=os.path.join("data", "market", "indices.json"),
        help="Source snapshot JSON file. Defaults to data/market/indices.json.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("data", "indices"),
        help="Output directory for manifest/monthly shards.",
    )
    parser.add_argument("--date", help="Override snapshot date as YYYY-MM-DD.")
    parser.add_argument(
        "--compact", action="store_true", help="Write compact JSON instead of pretty-printed JSON."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and print the planned output without writing files."
    )
    parser.add_argument(
        "--min-indices",
        type=int,
        default=DEFAULT_MIN_INDICES,
        help=f"Minimum valid indices required before writing. Defaults to {DEFAULT_MIN_INDICES}.",
    )
    parser.add_argument(
        "--allow-future", action="store_true", help="Allow future snapshot dates. Intended only for tests."
    )
    parser.add_argument(
        "--latest-status",
        choices=("provisional", "final"),
        help="Mark the latest manifest date as provisional intraday data or final after-close data.",
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
        min_indices=args.min_indices,
        allow_future=args.allow_future,
        latest_status=args.latest_status,
    )

    print(
        "Built NEPSE index shards"
        f" for {result['date']} ({result['index_count']} indices,"
        f" {result['skipped_rows']} skipped rows)."
    )
    for path in result["files"]:
        print(f"- {path}")


if __name__ == "__main__":
    main()
