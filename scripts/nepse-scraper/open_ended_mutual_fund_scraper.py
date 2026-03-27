import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


BASE_URL = "https://www.sharesansar.com/mutual-fund-navs"
OUTPUT_FILE = "OMF.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


def get_output_path() -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(repo_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, OUTPUT_FILE)


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


def to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def clean_date(value: Any) -> Optional[str]:
    if value in (None, "", "0000-00-00"):
        return None
    return str(value).strip()


def build_datatable_params(start: int, length: int) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "type": 2,
        "draw": 1,
        "start": start,
        "length": length,
        "search[value]": "",
        "search[regex]": "false",
        "order[0][column]": 1,
        "order[0][dir]": "asc",
    }
    column_names = [
        "DT_Row_Index",
        "symbol",
        "companyname",
        "fund_size",
        "maturity_date",
        "maturity_period",
        "daily_nav_price",
        "daily_date",
        "weekly_nav_price",
        "weekly_date",
        "monthly_nav_price",
        "monthly_date",
        "close",
        "published_date",
        "prem_dis",
        "refund_nav",
    ]
    for index, name in enumerate(column_names):
        params[f"columns[{index}][data]"] = name
        params[f"columns[{index}][name]"] = ""
        params[f"columns[{index}][searchable]"] = "true"
        params[f"columns[{index}][orderable]"] = "true"
        params[f"columns[{index}][search][value]"] = ""
        params[f"columns[{index}][search][regex]"] = "false"
    return params


def fetch_page(session: requests.Session, start: int, length: int) -> Dict[str, Any]:
    params = build_datatable_params(start=start, length=length)
    response = session.get(
        BASE_URL,
        params=params,
        headers={
            **HEADERS,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": BASE_URL,
        },
        timeout=25,
    )
    response.raise_for_status()
    return response.json()


def fetch_open_ended_navs(session: requests.Session) -> List[Dict[str, Any]]:
    # Sharesansar expects an initial HTML request so the AJAX call includes
    # a valid session cookie set by the site.
    session.get(
        BASE_URL,
        headers={
            **HEADERS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=20,
    ).raise_for_status()

    page_size = 20
    payload = fetch_page(session, start=0, length=page_size)
    rows = list(payload.get("data", []))
    total = int(payload.get("recordsFiltered", len(rows)) or 0)

    while len(rows) < total:
        payload = fetch_page(session, start=len(rows), length=page_size)
        next_rows = payload.get("data", [])
        if not next_rows:
            break
        rows.extend(next_rows)

    return rows


def normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scraped_at = datetime.now().isoformat()
    normalized: List[Dict[str, Any]] = []

    for row in rows:
        normalized.append(
            {
                "company_id": row.get("companyid"),
                "symbol": row.get("symbol"),
                "fund_name": row.get("companyname"),
                "fund_size": to_int(row.get("fund_size")),
                "daily_nav": to_float(row.get("daily_nav_price")),
                "daily_nav_date": clean_date(row.get("daily_date")),
                "weekly_nav": to_float(row.get("weekly_nav_price")),
                "weekly_nav_date": clean_date(row.get("weekly_date")),
                "monthly_nav": to_float(row.get("monthly_nav_price")),
                "monthly_nav_date": clean_date(row.get("monthly_date")),
                "ltp": to_float(row.get("close")),
                "price_as_of": clean_date(row.get("published_date")),
                "premium_discount_percent": to_float(row.get("prem_dis")),
                "refund_nav": to_float(row.get("refund_nav")),
                "source_url": BASE_URL,
                "scraped_at": scraped_at,
            }
        )

    normalized.sort(key=lambda item: ((item.get("symbol") or ""), (item.get("fund_name") or "")))
    return normalized


def save_json(path: str, data: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def scrape_and_save_open_ended_navs(output_path: Optional[str] = None) -> List[Dict[str, Any]]:
    session = create_session()
    rows = fetch_open_ended_navs(session)
    data = normalize_rows(rows)

    if not data:
        raise RuntimeError("Open-ended mutual fund fetch returned no rows.")

    final_path = output_path or get_output_path()
    save_json(final_path, data)
    print(f"Saved {len(data)} open-ended mutual fund rows to {final_path}")
    return data


def main() -> None:
    scrape_and_save_open_ended_navs()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Run aborted: {exc}")
        sys.exit(1)
