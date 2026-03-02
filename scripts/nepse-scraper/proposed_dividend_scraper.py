import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


BASE_URL = "https://www.sharesansar.com/proposed-dividend"
LATEST_FILE = "latest_1y.json"
HISTORY_FILE = "history_all_years.json"
# Stable dedupe identity for proposed-dividend rows.
# If this tuple changes, uniqueness behavior for history/latest changes too.
DEDUPE_FIELDS = ("id", "symbol", "fiscal_year", "announcement_date", "total_dividend")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def get_data_dir() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data", "proposed_dividend")
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


def load_json_list(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_json_list(path: str, data: List[Dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean_html_anchor(value: str) -> Tuple[str, str]:
    if value is None:
        return "", ""
    soup = BeautifulSoup(value, "html.parser")
    anchor = soup.find("a")
    if anchor:
        return anchor.get_text(strip=True), anchor.get("href", "")
    return soup.get_text(strip=True), ""


def normalize_record(row: Dict) -> Dict:
    symbol_text, _ = clean_html_anchor(row.get("symbol"))
    company_text, company_url = clean_html_anchor(row.get("companyname"))
    return {
        "id": row.get("id"),
        "symbol": symbol_text,
        "company_name": company_text,
        "company_url": company_url,
        "bonus_share": row.get("bonus_share"),
        "cash_dividend": row.get("cash_dividend"),
        "total_dividend": row.get("total_dividend"),
        "announcement_date": row.get("announcement_date"),
        "bookclose_date": row.get("bookclose_date"),
        "distribution_date": row.get("distribution_date"),
        "bonus_listing_date": row.get("bonus_listing_date"),
        "fiscal_year": row.get("year"),
        "ltp": row.get("close"),
        "price_as_of": row.get("published_date"),
        "status": row.get("status"),
        "scraped_at": datetime.now().isoformat(),
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
        key=lambda x: (parse_date(x.get("announcement_date")), x.get("id") or 0),
        reverse=True,
    )


def record_key(item: Dict) -> str:
    return "|".join(str(item.get(field, "")) for field in DEDUPE_FIELDS)


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
    # Ensure this request is treated as a normal HTML page fetch, not AJAX.
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


def fetch_latest_1y(session: requests.Session) -> List[Dict]:
    rows = fetch_paged(session, params={"type": "LATEST", "duration": "1_YEAR"})
    normalized = [normalize_record(r) for r in rows]
    return sort_newest_first(dedupe_records(normalized))


def is_newest_first(records: List[Dict]) -> bool:
    if len(records) < 2:
        return True
    prev = None
    for item in records:
        cur = parse_date(item.get("announcement_date"))
        if prev is not None and cur > prev:
            return False
        prev = cur
    return True


def run_smoke_gate(session: requests.Session) -> List[Dict]:
    latest_rows = fetch_latest_1y(session)
    if not latest_rows:
        raise RuntimeError("Smoke test failed: latest fetch returned empty list.")
    if not is_newest_first(latest_rows):
        raise RuntimeError("Smoke test failed: latest list is not sorted newest-first.")
    print(f"Smoke test passed: {len(latest_rows)} latest rows, newest-first order.")
    return latest_rows


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


def merge_into_history(out_dir: str, incoming: List[Dict], incremental: bool = True) -> int:
    history_path = os.path.join(out_dir, HISTORY_FILE)
    history = load_json_list(history_path)

    # one-time migration from legacy file name
    legacy_backfill = os.path.join(out_dir, "all_years_backfill.json")
    if not history and os.path.exists(legacy_backfill):
        history = load_json_list(legacy_backfill)

    seen = {record_key(item) for item in history}
    to_add = [item for item in incoming if record_key(item) not in seen]
    if to_add:
        if incremental:
            # Incremental update: keep existing history untouched, prepend only new rows.
            new_rows = sort_newest_first(dedupe_records(to_add))
            updated_history = new_rows + history
            save_json_list(history_path, updated_history)
        else:
            # Full merge for backfill to preserve global newest-first ordering.
            updated_history = sort_newest_first(dedupe_records(history + to_add))
            save_json_list(history_path, updated_history)
    elif not os.path.exists(history_path):
        history = sort_newest_first(dedupe_records(history))
        save_json_list(history_path, history)

    return len(to_add)


def write_latest(out_dir: str, latest_rows: List[Dict]) -> None:
    latest_path = os.path.join(out_dir, LATEST_FILE)
    save_json_list(latest_path, latest_rows)


def cleanup_legacy_files(out_dir: str) -> None:
    legacy_paths = [
        os.path.join(out_dir, "years_manifest.json"),
        os.path.join(out_dir, "latest_summary.json"),
        os.path.join(out_dir, "all_years_backfill.json"),
    ]
    for p in legacy_paths:
        if os.path.exists(p):
            try:
                os.remove(p)
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


def write_meta(out_dir: str, mode: str, latest_count: int, history_count: int, smoke_passed: bool) -> None:
    meta_path = os.path.join(out_dir, "meta.json")
    meta = {
        "last_run_at": datetime.now().isoformat(),
        "mode": mode,
        "latest_count": latest_count,
        "history_count": history_count,
        "smoke_passed": smoke_passed,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def is_history_empty(out_dir: str) -> bool:
    history_path = os.path.join(out_dir, HISTORY_FILE)
    history = load_json_list(history_path)
    return len(history) == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sharesansar Proposed Dividend scraper with only latest + history files."
    )
    parser.add_argument(
        "--mode",
        choices=["backfill", "latest", "both"],
        default="both",
        help="backfill: fetch all years into history, latest: refresh 1-year latest + merge to history, both: do both",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip smoke gate check (use only for emergency/manual runs).",
    )
    args = parser.parse_args()

    out_dir = get_data_dir()
    session = create_session()
    did_full_backfill = False

    smoke_passed = False
    cached_latest_rows: List[Dict] = []
    needs_latest = args.mode in ("latest", "both")
    if needs_latest:
        if args.skip_smoke:
            print("Smoke check skipped by --skip-smoke.")
            cached_latest_rows = fetch_latest_1y(session)
        else:
            cached_latest_rows = run_smoke_gate(session)
            smoke_passed = True

    if args.mode in ("backfill", "both"):
        all_year_rows = fetch_all_years(session)
        added = merge_into_history(out_dir, all_year_rows, incremental=False)
        print(f"History merged from all years. New added: {added}")
        did_full_backfill = True

    if args.mode in ("latest", "both"):
        if not did_full_backfill and is_history_empty(out_dir):
            print("History file is empty. Running full all-years fetch before latest merge...")
            all_year_rows = fetch_all_years(session)
            added_backfill = merge_into_history(out_dir, all_year_rows, incremental=False)
            print(f"History bootstrap from all years complete. New added: {added_backfill}")
        write_latest(out_dir, cached_latest_rows)
        added = merge_into_history(out_dir, cached_latest_rows)
        print(f"Latest (1 year) saved: {len(cached_latest_rows)}")
        print(f"Latest merged into history. New added: {added}")

    cleanup_legacy_files(out_dir)
    latest_count = len(cached_latest_rows)
    history_count = len(load_json_list(os.path.join(out_dir, HISTORY_FILE)))
    write_meta(
        out_dir=out_dir,
        mode=args.mode,
        latest_count=latest_count,
        history_count=history_count,
        smoke_passed=smoke_passed,
    )
    print(
        f"Done. Files: {os.path.join(out_dir, LATEST_FILE)} and {os.path.join(out_dir, HISTORY_FILE)}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Run aborted: {exc}")
        sys.exit(1)
