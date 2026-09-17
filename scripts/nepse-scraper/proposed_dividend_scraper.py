import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


BASE_URL = "https://www.sharesansar.com/proposed-dividend"
HISTORY_FILE = "history.json"
COLUMNS = ["symbol", "bonus", "cash", "total", "announce", "bookclose", "fiscalYear"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

SYMBOL_FIXES = {
    "NMBSBF": "NMBSBFE",
    "GSYA": "GSYM",
}


def get_data_dir() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data", "dividend")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def clean_html_anchor(value: str) -> Tuple[str, str]:
    if value is None:
        return "", ""
    soup = BeautifulSoup(value, "html.parser")
    anchor = soup.find("a")
    if anchor:
        return anchor.get_text(strip=True), anchor.get("href", "")
    return soup.get_text(strip=True), ""


def clean_bookclose_date(value) -> Optional[str]:
    val = str(value or "").replace("[Closed]", "").strip()
    return val if val else None


def normalize_record(row: Dict) -> Dict:
    symbol_text, _ = clean_html_anchor(row.get("symbol"))
    symbol_text = SYMBOL_FIXES.get(symbol_text, symbol_text)
    return {
        "symbol": symbol_text,
        "bonus": row.get("bonus_share") or None,
        "cash": row.get("cash_dividend") or None,
        "total": row.get("total_dividend") or None,
        "announce": row.get("announcement_date") or None,
        "bookclose": clean_bookclose_date(row.get("bookclose_date")),
        "fiscalYear": row.get("year") or None,
    }


def parse_date(value: str) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return datetime.min


def sort_newest_first(records: List[Dict]) -> List[Dict]:
    return sorted(
        records,
        key=lambda x: (parse_date(x.get("announce")), x.get("symbol", "")),
        reverse=True,
    )


def record_key(item: Dict) -> str:
    return "|".join(str(item.get(f) or "") for f in ["symbol", "fiscalYear", "announce", "total"])


def dedupe_records(records: List[Dict]) -> List[Dict]:
    out = []
    seen = set()
    for item in records:
        key = record_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def get_year_options(session: requests.Session) -> List[Dict]:
    html_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    res = session.get(BASE_URL, headers={**html_headers, "X-Requested-With": ""}, timeout=20)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    year_select = soup.find("select", {"id": "year"})
    if not year_select:
        raise RuntimeError("Year selector not found on proposed-dividend page.")

    years = []
    for opt in year_select.find_all("option"):
        year_id = opt.get("value", "").strip()
        label = opt.get_text(strip=True)
        if year_id:
            years.append({"id": year_id, "label": label})
    return years


def fetch_paged(session: requests.Session, params: Dict, page_size: int = 50) -> List[Dict]:
    all_rows = []
    start = 0
    draw = 1
    total = None

    while True:
        q = dict(params)
        q.update({"draw": draw, "start": start, "length": page_size})
        res = session.get(BASE_URL, params=q, timeout=25)
        res.raise_for_status()
        payload = res.json()
        rows = payload.get("data", [])
        if total is None:
            total = int(payload.get("recordsFiltered", 0))
        all_rows.extend(rows)
        if not rows or len(all_rows) >= total:
            break
        start += page_size
        draw += 1

    return all_rows


def fetch_all_years(session: requests.Session) -> List[Dict]:
    years = get_year_options(session)
    merged = []
    for y in years:
        rows = fetch_paged(
            session,
            params={"type": "YEARWISE", "year": y["id"], "sector": "0"},
        )
        normalized = [normalize_record(r) for r in rows]
        merged.extend(normalized)
        print(f"Fetched year {y['label']} ({y['id']}): {len(rows)} rows")
    return sort_newest_first(dedupe_records(merged))


def records_to_compact(records: List[Dict]) -> Tuple[List[str], List[List[Any]]]:
    """Convert dict records to compact format: (symbols_list, rows_with_symbol_index)."""
    symbols = sorted(set(r["symbol"] for r in records))
    symbol_idx = {s: i for i, s in enumerate(symbols)}

    rows = []
    for r in records:
        rows.append([
            symbol_idx[r["symbol"]],
            r.get("bonus"),
            r.get("cash"),
            r.get("total"),
            r.get("announce"),
            r.get("bookclose"),
            r.get("fiscalYear"),
        ])
    return symbols, rows


def load_compact_history(path: str) -> Optional[Dict]:
    """Load history in compact format. Returns None if file doesn't exist or is empty."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict) and "records" in data:
            return data
        return None
    except Exception:
        return None


def compact_to_records(history: Dict) -> List[Dict]:
    """Convert compact history back to dict records for merging."""
    symbols = history.get("symbols", [])
    records = []
    for row in history.get("records", []):
        if len(row) < 7:
            continue
        records.append({
            "symbol": symbols[row[0]] if row[0] < len(symbols) else None,
            "bonus": row[1],
            "cash": row[2],
            "total": row[3],
            "announce": row[4],
            "bookclose": row[5],
            "fiscalYear": row[6],
        })
    return [r for r in records if r.get("symbol")]


def save_compact_history(path: str, records: List[Dict]) -> None:
    """Save records in compact format."""
    symbols, rows = records_to_compact(records)
    output = {
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "symbols": symbols,
        "columns": COLUMNS,
        "records": rows,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)


def merge_records(existing: List[Dict], incoming: List[Dict]) -> List[Dict]:
    """Merge incoming records into existing, deduplicating."""
    seen = {record_key(r) for r in existing}
    to_add = [r for r in incoming if record_key(r) not in seen]
    if to_add:
        return sort_newest_first(existing + to_add)
    return existing


def cleanup_legacy_files(out_dir: str) -> None:
    """Remove old files that are no longer needed."""
    legacy_paths = [
        os.path.join(out_dir, "years_manifest.json"),
        os.path.join(out_dir, "latest_summary.json"),
        os.path.join(out_dir, "latest_1y.json"),
        os.path.join(out_dir, "all_years_backfill.json"),
    ]
    for p in legacy_paths:
        if os.path.exists(p):
            try:
                os.remove(p)
                print(f"Removed legacy file: {os.path.basename(p)}")
            except Exception:
                pass

    legacy_chunk_dir = os.path.join(out_dir, "latest_chunks")
    if os.path.isdir(legacy_chunk_dir):
        for name in os.listdir(legacy_chunk_dir):
            fp = os.path.join(legacy_chunk_dir, name)
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
            except Exception:
                pass
        try:
            os.rmdir(legacy_chunk_dir)
        except Exception:
            pass


def write_meta(out_dir: str, mode: str, record_count: int) -> None:
    meta_path = os.path.join(out_dir, "meta.json")
    meta = {
        "last_run_at": datetime.now().isoformat(),
        "mode": mode,
        "record_count": record_count,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sharesansar Proposed Dividend scraper (compact history format)."
    )
    parser.add_argument(
        "--mode",
        choices=["backfill", "latest", "both"],
        default="both",
        help="backfill: fetch all years, latest: fetch recent and merge, both: do both",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip smoke gate check.",
    )
    args = parser.parse_args()

    out_dir = get_data_dir()
    session = create_session()
    history_path = os.path.join(out_dir, HISTORY_FILE)

    # Load existing history
    existing_compact = load_compact_history(history_path)
    if existing_compact:
        existing_records = compact_to_records(existing_compact)
        print(f"Loaded {len(existing_records)} existing history records.")
    else:
        existing_records = []
        print("No existing history found.")

    all_records = existing_records

    if args.mode in ("backfill", "both"):
        all_year_rows = fetch_all_years(session)
        all_records = merge_records(all_records, all_year_rows)
        print(f"After backfill merge: {len(all_records)} records.")

    if args.mode in ("latest", "both"):
        # Fetch latest 1 year and merge
        latest_rows = fetch_paged(session, params={"type": "LATEST", "duration": "1_YEAR"})
        normalized = [normalize_record(r) for r in latest_rows]
        latest_deduped = sort_newest_first(dedupe_records(normalized))
        all_records = merge_records(all_records, latest_deduped)
        print(f"After latest merge: {len(all_records)} records.")

    cleanup_legacy_files(out_dir)
    save_compact_history(history_path, all_records)
    write_meta(out_dir, args.mode, len(all_records))
    print(f"Done. {history_path} ({len(all_records)} records)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Run aborted: {exc}")
        sys.exit(1)
