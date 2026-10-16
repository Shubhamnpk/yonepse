#!/usr/bin/env python3
"""Update OMF NAV history in LTP shards straight from AMC sources.

Single file, one worker per fund (ThreadPoolExecutor). Each fund fetches
that AMC's official daily NAVs; results are shared per source so NIC Asia
and Nabil are each hit once per run. Per-source failures never stop the
other funds.

Covered: NFCF + NI31 (Nabil), GSYM (Garima), NIBLSF (NIMB Ace),
ELIS + NADDF (NIC Asia). AMCs without a script-fetchable daily history
(CSBY, KSLY, MSIP, NMBSBFE, PSIS, SFF, SLK, SSIS) are not covered.

Behavior: append-only by default (fills dates missing from the shards,
never touches existing points). Pass --correct to also overwrite points
that differ from the AMC value. The market scraper owns date creation
and the manifest; this script only writes month files it actually changes.

Usage:
  python scripts/nepse-scraper/omf_nav_history.py --dry-run
  python scripts/nepse-scraper/omf_nav_history.py --funds NFCF,GSYM
  python scripts/nepse-scraper/omf_nav_history.py --correct
"""

import argparse
import glob
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ltp_history.build_ltp_shards import (
    ensure_month_shape,
    load_json,
    npt_now,
    upsert_month,
    write_json,
)

NPT = timezone(timedelta(hours=5, minutes=45))
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

MONTHS = {
    "January": "01", "February": "02", "March": "03", "April": "04", "May": "05",
    "June": "06", "July": "07", "August": "08", "September": "09", "October": "10",
    "November": "11", "December": "12",
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}


def make_session(referer=None):
    session = requests.Session()
    session.headers.update({
        "User-Agent": BROWSER_UA,
        "Accept-Language": "en-US,en;q=0.9",
    })
    if referer:
        session.headers["Referer"] = referer
    return session


# ---------------------------------------------------------------- Nabil ---
NABIL_PAGES = {
    "NFCF": "https://nabilinvest.com.np/investment-banking/mutual-funds/nabil-flexi-cap-fund/",
    "NI31": "https://nabilinvest.com.np/investment-banking/mutual-funds/ni-31/",
}
NABIL_SCHEMES = {"NFCF": "Nabil Flexi Cap Fund", "NI31": "NI 31"}
NABIL_NAV_RE = re.compile(r"NAV as on (\d{4}-\d{2}-\d{2}).*?NAV\s+([\d.]+)")
NABIL_LOOKBACK_DAYS = 14
NABIL_SLEEP_SECONDS = 0.6


def _nabil_nav_on(nonce, ajax_url, referer, scheme, date, retries=2):
    """Single by-date NAV lookup with one retry (WAF rate-limits bursts)."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                ajax_url,
                data=urllib.parse.urlencode(
                    {"action": "ni_mf_get_by_date", "nonce": nonce,
                     "scheme": scheme, "date": date}).encode(),
                headers={"User-Agent": BROWSER_UA, "Referer": referer,
                         "X-Requested-With": "XMLHttpRequest",
                         "Accept": "application/json, text/javascript, */*; q=0.01",
                         "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            )
            payload = json.loads(_nabil_urlopen(req).read().decode("utf-8"))
            if not payload.get("success"):
                return None
            text = re.sub(r"\s+", " ",
                          re.sub(r"<[^>]+>", " ", payload["data"].get("nav", "")))
            m = NABIL_NAV_RE.search(text)
            if m and m.group(1) == date:
                return float(m.group(2))
            return None
        except Exception:
            time.sleep(NABIL_SLEEP_SECONDS * (attempt + 1))
    return None


def _nabil_urlopen(req, timeout=30):
    # NOTE: urllib (not requests) — Nabil's WAF currently 403s requests'
    # TLS fingerprint but lets stdlib urllib through.
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_nabil():
    """Per-date NAV viewer, one endpoint page per fund of the same company.

    Returns {symbol: [(date, nav)]} newest first. Each fund is fetched from
    its own page (own nonce + referer).
    """
    today = datetime.now(NPT).date()
    out = {symbol: [] for symbol in NABIL_SCHEMES}
    for symbol, scheme in NABIL_SCHEMES.items():
        page_url = NABIL_PAGES[symbol]
        try:
            page_req = urllib.request.Request(
                page_url, headers={"User-Agent": BROWSER_UA, "Accept": "text/html"})
            cfg = json.loads(
                re.search(r"niMfDateFilter['\"]?\s*[:=]\s*(\{[^}]+\})",
                          _nabil_urlopen(page_req).read().decode("utf-8", "ignore")).group(1)
            )
            nonce, ajax_url = cfg["nonce"], cfg["ajaxUrl"]
        except Exception:
            continue
        for back in range(NABIL_LOOKBACK_DAYS):
            date = (today - timedelta(days=back)).isoformat()
            nav = _nabil_nav_on(nonce, ajax_url, page_url, scheme, date)
            time.sleep(NABIL_SLEEP_SECONDS)
            if nav is not None:
                out[symbol].append((date, nav))
    if not any(out.values()):
        raise RuntimeError("by-date endpoint returned no NAVs (WAF block?)")
    return out


# --------------------------------------------------------------- Garima ---
GARIMA_API = "https://www.garimacapital.com/nav/category-data"
GARIMA_CATEGORIES = {10: "GSYM"}


def fetch_garima():
    """Garima Capital NAV JSON API. Returns {symbol: [(date, nav)]}."""
    session = make_session(referer="https://www.garimacapital.com/")
    session.headers.update({"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
    out = {}
    for category_id, symbol in GARIMA_CATEGORIES.items():
        points, page = [], 1
        while True:
            resp = session.get(
                f"{GARIMA_API}/{category_id}?daily_page={page}&weekly_page=1&monthly_page=1",
                timeout=30,
            )
            resp.raise_for_status()
            daily = resp.json().get("tables", {}).get("daily", {})
            for item in daily.get("data", []):
                if item.get("publish_at") is not None and item.get("value") is not None:
                    points.append((item["publish_at"], float(item["value"])))
            if not daily.get("pagination", {}).get("next_page_url"):
                break
            page += 1
        out[symbol] = points
    return out


# ------------------------------------------------------------- NIMB Ace ---
NIMB_PAGE = "https://nimbacecapital.com/nav-nibl-sahabhagita"
NIMB_AJAX = "https://nimbacecapital.com/wp-admin/admin-ajax.php"
NIMB_FUND = "nibl-sahabhagita-fund-nav"
NIMB_MAX_PAGES = 3


def fetch_nimb():
    """NIMB Ace Capital WP-AJAX daily NAV table. Returns {symbol: [...]}."""
    session = make_session(referer=NIMB_PAGE)
    page = session.get(NIMB_PAGE, headers={"Accept": "text/html"}, timeout=30)
    page.raise_for_status()
    nonce = re.search(r"nonce:\s*'([0-9a-f]+)'", page.text).group(1)
    points = []
    for page_no in range(1, NIMB_MAX_PAGES + 1):
        resp = session.post(
            NIMB_AJAX,
            data={"action": "load_mutual_fund_table", "nonce": nonce,
                  "mutual_fund": NIMB_FUND, "type": "daily",
                  "page": page_no, "search": "", "entries": 50},
            headers={"X-Requested-With": "XMLHttpRequest",
                     "Accept": "application/json, text/javascript, */*; q=0.01"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            break
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>",
                          payload.get("data", {}).get("html", ""), re.S | re.I)
        if not rows:
            break
        for row in rows:
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)]
            if len(cells) < 3:
                continue
            m = re.fullmatch(r"(\d{2})/([A-Za-z]+)/(\d{4})", cells[0])
            if not m:
                continue
            try:
                points.append((f"{m.group(3)}-{MONTHS[m.group(2)]}-{m.group(1)}",
                               float(cells[2].replace(",", ""))))
            except (KeyError, TypeError, ValueError):
                continue
    return {"NIBLSF": points}


# ------------------------------------------------------------- NIC Asia ---
NIC_API = "https://www.nicasiacapital.com/nav-details/daily-data"
NIC_REFERER = "https://www.nicasiacapital.com/nav-details"
NIC_CATEGORIES = {"ELIS": 11, "NADDF": 5}
NIC_DATE_RE = re.compile(r"([A-Za-z]+) (\d{1,2}), (\d{4})")


def fetch_nic_asia():
    """NIC Asia Capital NAV JSON API (current year). Returns {symbol: [...]}."""
    session = make_session(referer=NIC_REFERER)
    session.headers.update({"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
    year = datetime.now(NPT).year
    out = {}
    for symbol, category in NIC_CATEGORIES.items():
        points, page = [], 1
        while True:
            resp = session.get(NIC_API, params={"page": page, "year": year, "category": category},
                               timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("data", [])
            if not rows:
                break
            for row in rows:
                m = NIC_DATE_RE.fullmatch((row.get("publish_at") or "").strip())
                if not m or row.get("value") is None:
                    continue
                try:
                    points.append((f"{m.group(3)}-{MONTHS[m.group(1)]}-{int(m.group(2)):02d}",
                                   float(row["value"])))
                except (KeyError, TypeError, ValueError):
                    continue
            if page >= payload.get("last_page", 1):
                break
            page += 1
        out[symbol] = points
    return out


SOURCE_FETCHERS = {
    "nabil": fetch_nabil,
    "garima": fetch_garima,
    "nimb": fetch_nimb,
    "nicasia": fetch_nic_asia,
}
SYMBOL_SOURCE = {
    "NFCF": "nabil", "NI31": "nabil",
    "GSYM": "garima",
    "NIBLSF": "nimb",
    "ELIS": "nicasia", "NADDF": "nicasia",
}

_cache = {}
_cache_lock = threading.Lock()


def points_for(symbol):
    """Shared per-source fetch so one source is hit once per run."""
    source = SYMBOL_SOURCE[symbol]
    with _cache_lock:
        if source not in _cache:
            _cache[source] = SOURCE_FETCHERS[source]()
        return _cache[source].get(symbol, [])


def update_symbol(symbol, output_dir, dry_run, correct):
    stats = {"symbol": symbol, "inserted": 0, "corrected": 0, "error": None}
    try:
        points = {date: nav for date, nav in points_for(symbol)}
    except Exception as exc:
        stats["error"] = str(exc)[:200]
        return stats
    if not points:
        stats["error"] = "source returned no points"
        return stats

    updated_at = npt_now().isoformat(timespec="seconds")
    for path in sorted(glob.glob(os.path.join(output_dir, "monthly", "*.json"))):
        month_data = load_json(path, {})
        if symbol not in month_data.get("series", {}):
            continue
        month, series = month_data.get("month"), {r[0]: r[1] for r in month_data["series"][symbol]}
        touched = False
        for idx, date in enumerate(month_data["dates"]):
            if date not in points:
                continue
            if idx not in series:
                month_data = upsert_month(month_data, date, {symbol: [points[date]]}, updated_at)
                stats["inserted"] += 1
                touched = True
            elif correct and series[idx] != points[date]:
                month_data = upsert_month(month_data, date, {symbol: [points[date]]}, updated_at)
                stats["corrected"] += 1
                touched = True
        if touched and not dry_run:
            write_json(path, month_data)
            ensure_month_shape(load_json(path, {}), month)  # re-validate written file
    return stats


def run(symbols=None, output_dir=None, dry_run=False, correct=False, workers=6):
    """Run per-fund workers; returns list of stats dicts. Import-safe."""
    if output_dir is None:
        output_dir = os.path.join("data", "ltp")
    if symbols is None:
        symbols = list(SYMBOL_SOURCE)
    unknown = [s for s in symbols if s not in SYMBOL_SOURCE]
    if unknown:
        raise ValueError(f"No AMC worker for: {', '.join(unknown)}")

    results = []
    with ThreadPoolExecutor(max_workers=min(workers, len(symbols))) as pool:
        futures = {pool.submit(update_symbol, s, output_dir, dry_run, correct): s
                   for s in symbols}
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda x: x["symbol"])


def main():
    parser = argparse.ArgumentParser(description="Update OMF NAV history from AMC sources.")
    parser.add_argument("--funds", help="Comma-separated symbols (default: all).")
    parser.add_argument("--output", default=os.path.join("data", "ltp"),
                        help="LTP output directory. Defaults to data/ltp.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report without writing.")
    parser.add_argument("--correct", action="store_true",
                        help="Also overwrite points that differ (default: append new only).")
    parser.add_argument("--workers", type=int, default=6, help="Parallel per-fund workers.")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.funds.split(",")] if args.funds else None
    try:
        results = run(symbols, args.output, args.dry_run, args.correct, args.workers)
    except ValueError as exc:
        raise SystemExit(str(exc))

    for r in results:
        suffix = " (dry-run)" if args.dry_run else ""
        if r["error"]:
            print(f"- {r['symbol']}: FAILED ({r['error']})")
        elif args.correct:
            print(f"- {r['symbol']}: +{r['inserted']} new, ~{r['corrected']} corrected{suffix}")
        else:
            print(f"- {r['symbol']}: +{r['inserted']} new{suffix}")


if __name__ == "__main__":
    main()
