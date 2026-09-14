"""Build monthly NEPSE index history shards from the official history API.

Same compact envelope as data/ltp/monthly/*.json:
  {"version","market","currency","month","updatedAt","dates",
   "columns":["dateIndex","close","open","high","low","turnover","volume","trades"],
   "series":{INDEXCODE:[[dateIndex,...values]]}}
Series keys are indexCode values (NEPSE, SENSIND, ...) so names never repeat.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone


VERSION = 1
MARKET = "NEPSE"
CURRENCY = "NPR"
NPT = timezone(timedelta(hours=5, minutes=45))
DEFAULT_MIN_INDICES = 3
# closingIndex/openIndex/highIndex/lowIndex/turnoverValue/turnoverVolume/totalTransaction.
# absChange/percentageChange are derived client-side, like LTP change fields.
METRIC_FIELDS = ("open", "high", "low", "turnover", "volume", "trades")
VALUE_COLUMNS = ("close",) + METRIC_FIELDS
COLUMNS = ("dateIndex",) + VALUE_COLUMNS

# All index IDs served by /api/nots/index/history/{id} (client.py validates 51-67).
ALL_INDEX_IDS = list(range(51, 68))

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


def parse_date(value):
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format") from exc


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


def history_row_values(row):
    """Map one /index/history record to VALUE_COLUMNS. None if no close."""
    if not isinstance(row, dict):
        return None
    close = normalize_number(row.get("closingIndex"))
    if close is None:
        return None
    return [
        close,
        normalize_number(row.get("openIndex")),
        normalize_number(row.get("highIndex")),
        normalize_number(row.get("lowIndex")),
        normalize_number(row.get("turnoverValue")),
        normalize_number(row.get("turnoverVolume")),
        normalize_number(row.get("totalTransaction")),
    ]


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
            # Interior nulls allowed: sources differ per era (official has full
            # OHLCV, socrateai lacks turnover/trades, 1997-2002 CSV lacks volume).
            # Only the close (values[0]) is mandatory; trailing nulls are trimmed.
            if row[1] is None:
                raise ValueError(f"Series row for {code} must have a close value.")
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


def fetch_index_history(scraper, index_id, start, end, page_size=500):
    """Fetch every page of /index/history/{id} for a date range, newest first."""
    endpoint = scraper.endpoints["head_indices_api"]
    path = f"{endpoint['api']}/{index_id}"
    rows = []
    page = 0
    while True:
        resp = scraper.session.get(
            path,
            params={"startDate": start, "endDate": end, "page": page, "size": page_size},
        )
        payload = resp.json()
        if isinstance(payload, dict):
            rows.extend(payload.get("content") or [])
            if payload.get("last", True):
                break
        elif isinstance(payload, list):
            rows.extend(payload)
            break
        else:
            break
        page += 1
    return rows


def backfill(output_dir, start, end, index_ids=None, data_dir=None,
             dry_run=False, compact=False, min_indices=DEFAULT_MIN_INDICES,
             latest_status=None):
    """Fetch history for every index id and upsert into monthly shards."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from official_api import NepseScraper

    index_ids = list(index_ids) if index_ids else list(ALL_INDEX_IDS)
    if data_dir is None:
        data_dir = os.path.normpath(os.path.join(os.path.dirname(output_dir), ".."))
        if os.path.basename(data_dir).lower() != "data":
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
            data_dir = os.path.normpath(data_dir)
    code_by_id = load_code_by_id(data_dir)

    scraper = NepseScraper(verify_ssl=False)
    per_date = {}
    fetched_codes = set()
    for index_id in index_ids:
        rows = fetch_index_history(scraper, int(index_id), start, end)
        code = normalize_code(code_by_id.get(int(index_id), ""))
        if not code:
            print(f"Skipping unknown index id {index_id}.")
            continue
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            date = str(row.get("businessDate") or "").strip()
            if not date:
                continue
            values = history_row_values(row)
            if values is None:
                continue
            per_date.setdefault(date, {})[code] = values
            count += 1
        if count:
            fetched_codes.add(code)
        print(f"{code} ({index_id}): {count} rows")

    if len(fetched_codes) < min_indices:
        raise ValueError(
            f"Only {len(fetched_codes)} valid indices found; refusing to update shards "
            f"below the minimum of {min_indices}."
        )

    updated_at = npt_now().isoformat(timespec="seconds")
    files = []
    for month in sorted({d[:7] for d in per_date}):
        month_path = os.path.join(output_dir, "monthly", f"{month}.json")
        month_data = ensure_month_shape(load_json(month_path, {}), month)
        for date in sorted(d for d in per_date if d.startswith(month)):
            month_data = upsert_month(month_data, date, per_date[date], updated_at)
        if not dry_run:
            write_json(month_path, month_data, compact=compact)
        files.append(month_path)

    latest_date = max(per_date)
    manifest_path = os.path.join(output_dir, "manifest.json")
    if not dry_run:
        manifest_data = build_manifest(output_dir, latest_date, latest_status=latest_status)
        for month in {os.path.splitext(os.path.basename(p))[0] for p in files}:
            if month not in manifest_data["availableMonths"]:
                manifest_data["availableMonths"].append(month)
        manifest_data["availableMonths"].sort()
        write_json(manifest_path, manifest_data, compact=compact)
        files.append(manifest_path)

    return {
        "output": output_dir,
        "start": start,
        "end": end,
        "index_count": len(fetched_codes),
        "date_count": len(per_date),
        "dry_run": dry_run,
        "files": files,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill monthly NEPSE index history shards from the official history API."
    )
    parser.add_argument(
        "--output",
        default=os.path.join("data", "indices"),
        help="Output directory for manifest/monthly shards.",
    )
    parser.add_argument("--start", default="2020-01-01", help="Range start as YYYY-MM-DD.")
    parser.add_argument("--end", help="Range end as YYYY-MM-DD (defaults to today NPT).")
    parser.add_argument(
        "--index-ids",
        help="Comma-separated index ids (51-67). Defaults to all.",
    )
    parser.add_argument(
        "--compact", action="store_true", help="Write compact JSON instead of pretty-printed JSON."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch and validate without writing files."
    )
    parser.add_argument(
        "--min-indices",
        type=int,
        default=DEFAULT_MIN_INDICES,
        help=f"Minimum valid indices required before writing. Defaults to {DEFAULT_MIN_INDICES}.",
    )
    parser.add_argument(
        "--latest-status",
        choices=("provisional", "final"),
        help="Mark the latest manifest date as provisional while-open data or final after-close data.",
    )
    args = parser.parse_args()

    start = parse_date(args.start).isoformat()
    end = parse_date(args.end).isoformat() if args.end else npt_now().date().isoformat()
    index_ids = (
        [int(item) for item in args.index_ids.split(",") if item.strip()]
        if args.index_ids
        else list(ALL_INDEX_IDS)
    )

    result = backfill(
        output_dir=args.output,
        start=start,
        end=end,
        index_ids=index_ids,
        dry_run=args.dry_run,
        compact=args.compact,
        min_indices=args.min_indices,
        latest_status=args.latest_status,
    )

    print(
        "Built NEPSE index shards"
        f" for {result['start']}..{result['end']} ({result['index_count']} indices,"
        f" {result['date_count']} dates)."
    )
    for path in result["files"]:
        print(f"- {path}")


if __name__ == "__main__":
    main()
