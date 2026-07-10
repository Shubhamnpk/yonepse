import sys
import os
import json
import argparse
import subprocess
from datetime import date, datetime, timedelta, timezone
import urllib.parse
import re
import requests
from bs4 import BeautifulSoup

# Add the current directory to path to find official_api
sys.path.append(os.path.dirname(__file__))

from official_api import NepseScraper
from open_ended_mutual_fund_scraper import scrape_and_save_open_ended_navs
from ltp_history.build_ltp_intraday import build_intraday_shard
from ltp_history.build_ltp_shards import build_shards

NPT = timezone(timedelta(hours=5, minutes=45))
LTP_HISTORY_CLOSE_HOUR = 16
LTP_HISTORY_CLOSE_MINUTE = 0
LEGACY_ENDPOINT_SUPPORT_END = date(2026, 11, 18)


def should_write_legacy_aliases():
    return datetime.now(NPT).date() <= LEGACY_ENDPOINT_SUPPORT_END


def remove_file_if_exists(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

def get_file_last_commit_date(filepath):
    """Get the datetime of the last git commit for a specific file."""
    try:
        # Use git log to get the Unix timestamp of the last commit for the file
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ct', filepath],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return datetime.fromtimestamp(int(result.stdout.strip()))
    except Exception:
        pass
    return None

def load_json_list(filepath):
    """Load a JSON file and return a list, defaulting to an empty list."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def load_json_object(filepath):
    """Load a JSON file and return an object, defaulting to None."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def today_npt_string():
    return datetime.now(NPT).date().isoformat()

def update_company_run_metadata(company_dir, key):
    metadata_path = os.path.join(company_dir, 'run_metadata.json')
    metadata = load_json_object(metadata_path)
    if not isinstance(metadata, dict):
        metadata = {}
    now_npt = datetime.now(NPT).isoformat(timespec='seconds')
    metadata[key] = today_npt_string()
    metadata[f"{key}_at"] = now_npt
    write_json_if_changed(metadata_path, metadata)

def should_run_daily_company_dataset(company_dir, key, label, force=False):
    if force:
        return True
    metadata = load_json_object(os.path.join(company_dir, 'run_metadata.json'))
    last_checked = metadata.get(key) if isinstance(metadata, dict) else None
    today = today_npt_string()
    if last_checked == today:
        print(f"Skipping {label}; already checked today ({today} NPT). Use force flag to run again.")
        return False
    return True

def snapshot_complete_enough(filepath, data, min_existing_ratio=0.8):
    if not data:
        return False
    existing = load_json_object(filepath)
    if isinstance(existing, list) and isinstance(data, list) and existing:
        return len(data) >= int(len(existing) * min_existing_ratio)
    return True

def _prev_day_ltp_from_history(data_dir, symbol, current_date):
    """Get LTP from most recent trading day before current_date in LTP history."""
    if not symbol or not current_date:
        return None
    month = current_date[:7]
    months_to_try = [month]
    try:
        dt = datetime.strptime(current_date, "%Y-%m-%d").date()
        months_to_try.append((dt.replace(day=1) - timedelta(days=1)).strftime("%Y-%m"))
    except ValueError:
        pass
    for m in months_to_try:
        path = os.path.join(data_dir, "ltp", "monthly", f"{m}.json")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        dates = data.get("dates", [])
        rows = data.get("series", {}).get(symbol, [])
        if not dates or not rows:
            continue
        date_to_idx = {d: i for i, d in enumerate(dates)}
        for pd in sorted([d for d in dates if d < current_date], reverse=True):
            idx = date_to_idx[pd]
            for row in rows:
                if row[0] == idx:
                    return row[1]
    return None


def build_omf_rows_for_nepse_data(data_dir, omf_items=None):
    """
    Load open-ended mutual funds from OMF.json and map them into nepse_data schema.
    """
    if omf_items is None:
        omf_path = os.path.join(data_dir, 'OMF.json')
        omf_items = load_json_list(omf_path)
    if not omf_items:
        return []

    mapped = []
    for item in omf_items:
        if not isinstance(item, dict):
            continue

        symbol = item.get('symbol')
        name = item.get('fund_name')
        if not symbol or not name:
            continue

        ltp = item.get('daily_nav')
        daily_nav_date = item.get('daily_nav_date')
        previous_close = _prev_day_ltp_from_history(data_dir, symbol, daily_nav_date)
        if previous_close is None:
            previous_close = item.get('weekly_nav')
        change = (
            round(ltp - previous_close, 2)
            if isinstance(ltp, (int, float)) and isinstance(previous_close, (int, float))
            else 0
        )
        percent_change = (
            round((change / previous_close) * 100, 2)
            if isinstance(previous_close, (int, float)) and previous_close != 0
            else 0
        )

        mapped.append({
            "symbol": symbol,
            "name": name,
            "ltp": ltp,
            "previous_close": previous_close,
            "change": change,
            "percent_change": percent_change,
            "high": None,
            "low": None,
            "volume": None,
            "turnover": None,
            "trades": None,
            "last_updated": item.get('daily_nav_date') or item.get('scraped_at'),
            "market_cap": item.get('fund_size'),
            "asset_type": "open_ended_mutual_fund"
        })

    return mapped

def refresh_omf_data(data_dir):
    """
    Refresh OMF.json from Sharesansar. If refresh fails, keep existing OMF.json.
    """
    omf_path = os.path.join(data_dir, 'OMF.json')
    try:
        rows = scrape_and_save_open_ended_navs(output_path=omf_path)
        print(f"Refreshed OMF.json with {len(rows)} open-ended mutual fund rows.")
        return rows
    except Exception as exc:
        print(f"OMF refresh failed, falling back to existing OMF.json: {exc}")
        return load_json_list(omf_path)

def unique_text_values(values):
    seen = set()
    out = []
    for value in values:
        text = str(value or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out

def compact_broker_record(broker):
    """Keep only public broker-directory fields used by the site/API."""
    if not isinstance(broker, dict):
        return {}

    membership = broker.get('membershipTypeMaster') or {}
    tms_mapping = broker.get('memberTMSLinkMapping') or {}
    branches = broker.get('memberBranchMappings')
    raw_provinces = list(unique_text_values(
        (item or {}).get('description') or (item or {}).get('name')
        for item in broker.get('provinceList') or []
    ))
    provinces = raw_provinces[0] if raw_provinces else None
    if provinces and provinces.startswith('Province '):
        provinces = provinces.replace('Province ', '')
    districts = unique_text_values(
        (item or {}).get('districtName')
        for item in broker.get('districtList') or []
    )

    compact = {
        "id": broker.get('id'),
        "memberCode": broker.get('memberCode'),
        "memberName": broker.get('memberName'),
        "membershipType": membership.get('membershipType'),
        "phone": broker.get('authorizedContactPersonNumber'),
        "provinces": provinces,
        "districts": districts,
        "tmsLink": tms_mapping.get('tmsLink'),
        "branchCount": len(branches) if isinstance(branches, list) else 0,
        "activeStatus": broker.get('activeStatus'),
        "isDealer": broker.get('isDealer'),
    }
    return {
        key: value
        for key, value in compact.items()
        if value not in (None, "", [], {})
    }

def compact_broker_records(brokers):
    if not isinstance(brokers, list):
        return []
    compact = [compact_broker_record(item) for item in brokers]
    compact = [item for item in compact if item.get('memberCode') or item.get('memberName')]
    return sorted(compact, key=lambda item: int(item.get('memberCode') or 0))

def compact_financial_report_record(record):
    """Return the useful public fields from a NEPSE fiscal report application."""
    if not isinstance(record, dict):
        return {}

    fiscal_report = record.get('fiscalReport') or {}
    report_type = fiscal_report.get('reportTypeMaster') or {}
    quarter = fiscal_report.get('quarterMaster') or {}
    financial_year = fiscal_report.get('financialYear') or {}

    documents = []
    raw_documents = record.get('applicationDocumentDetailsList')
    if isinstance(raw_documents, list):
        for doc in raw_documents:
            if not isinstance(doc, dict):
                continue
            compact_doc = {
                "submitted_date": doc.get('submittedDate'),
                "path": doc.get('filePath'),
            }
            compact_doc = {
                key: value
                for key, value in compact_doc.items()
                if value not in (None, "", [], {})
            }
            if compact_doc:
                documents.append(compact_doc)

    compact = {
        "type": report_type.get('reportName'),
        "quarter": quarter.get('quarterName'),
        "fy": financial_year.get('fyName'),
        "fy_nepali": financial_year.get('fyNameNepali'),
        "pe": fiscal_report.get('peValue'),
        "eps": fiscal_report.get('epsValue'),
        "paid_up_capital": fiscal_report.get('paidUpCapital'),
        "profit": fiscal_report.get('profitAmount'),
        "net_worth_per_share": fiscal_report.get('netWorthPerShare'),
        "remarks": fiscal_report.get('remarks'),
        "documents": documents,
    }
    return {
        key: value
        for key, value in compact.items()
        if value not in (None, "", [], {})
    }

def compact_financial_report_records(records):
    if not isinstance(records, list):
        return []
    compact = [compact_financial_report_record(item) for item in records]
    return [item for item in compact if item]

def compact_company_profile_record(profile, security):
    """Return the brief company profile and contact facts from NEPSE."""
    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(security, dict):
        security = {}

    address_parts = [
        profile.get('addressField'),
        profile.get('town'),
    ]
    address = ', '.join(str(part).strip() for part in address_parts if str(part or '').strip())

    compact = {
        "id": security.get('id'),
        "symbol": security.get('symbol'),
        "profile": profile.get('companyProfile'),
        "email": profile.get('companyEmail') or security.get('companyEmail'),
        "phone": profile.get('phoneNumber'),
        "fax": profile.get('fax'),
        "contact_person": profile.get('companyContactPerson'),
        "address_type": profile.get('addressType'),
        "address": address,
        "logo_path": profile.get('logoFilePath'),
    }
    return {
        key: value
        for key, value in compact.items()
        if value not in (None, "", [], {})
    }

def build_company_profiles_snapshot(scraper, securities):
    """Fetch brief company profile data for every security ID."""
    snapshot = []
    if not isinstance(securities, list):
        return snapshot

    total = len(securities)
    for index, security in enumerate(securities, start=1):
        if not isinstance(security, dict):
            continue

        company_id = security.get('id')
        if company_id is None:
            continue

        symbol = security.get('symbol') or str(company_id)
        try:
            profile = compact_company_profile_record(
                scraper.get_company_profile(int(company_id)),
                security
            )
            if profile.get('profile') or profile.get('email') or profile.get('phone') or profile.get('address'):
                snapshot.append(profile)
            if index % 25 == 0 or index == total:
                print(f"Fetched company profiles for {index}/{total} securities...")
        except Exception as exc:
            print(f"Failed to fetch company profile for {symbol} ({company_id}): {exc}")

    return sorted(snapshot, key=lambda item: str(item.get('symbol') or item.get('id') or ''))

def build_company_financials_snapshot(scraper, securities):
    """Fetch financial reports for every security ID from the company detail endpoint."""
    snapshot = []
    if not isinstance(securities, list):
        return snapshot

    total = len(securities)
    for index, security in enumerate(securities, start=1):
        if not isinstance(security, dict):
            continue

        company_id = security.get('id')
        if company_id is None:
            continue

        symbol = security.get('symbol') or str(company_id)
        try:
            reports = compact_financial_report_records(
                scraper.get_company_financials(int(company_id))
            )
            if not reports:
                continue
            snapshot.append({
                "id": company_id,
                "symbol": security.get('symbol'),
                "reports": reports,
            })
            if index % 25 == 0 or index == total:
                print(f"Fetched company financials for {index}/{total} securities...")
        except Exception as exc:
            print(f"Failed to fetch financials for {symbol} ({company_id}): {exc}")

    return sorted(snapshot, key=lambda item: str(item.get('symbol') or item.get('id') or ''))

def should_update_ltp_history(mode, market_is_open=False):
    """Decide when daily LTP history should be updated."""
    if mode == 'always':
        return True
    if mode == 'skip':
        return False

    now_npt = datetime.now(NPT)
    close_cutoff = now_npt.replace(
        hour=LTP_HISTORY_CLOSE_HOUR,
        minute=LTP_HISTORY_CLOSE_MINUTE,
        second=0,
        microsecond=0
    )
    after_close = now_npt >= close_cutoff
    if mode == 'live-close':
        return bool(market_is_open) or after_close
    return after_close

def ltp_history_latest_status():
    """Mark intraday LTP history as provisional until the close-time run finalizes it."""
    now_npt = datetime.now(NPT)
    close_cutoff = now_npt.replace(
        hour=LTP_HISTORY_CLOSE_HOUR,
        minute=LTP_HISTORY_CLOSE_MINUTE,
        second=0,
        microsecond=0
    )
    return 'final' if now_npt >= close_cutoff else 'provisional'

def write_json_if_changed(filepath, data):
    """Write JSON only if content differs or file does not exist."""
    existing = load_json_object(filepath)
    if existing == data:
        return False
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return True

def write_snapshot_if_changed(filepath, data, label, min_existing_ratio=0.8):
    """Write a fetched snapshot only when it is non-empty, complete enough, and changed."""
    if not data:
        print(f"No {label} data fetched. Keeping existing file unchanged.")
        return False

    existing = load_json_object(filepath)
    if isinstance(existing, list) and isinstance(data, list) and existing:
        minimum_count = int(len(existing) * min_existing_ratio)
        if len(data) < minimum_count:
            print(
                f"Fetched only {len(data)} {label} rows; existing file has {len(existing)}. "
                "Keeping existing file unchanged to avoid a partial overwrite."
            )
            return False

    if existing == data:
        print(f"{label.capitalize()} unchanged. Keeping existing file.")
        return False

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    print(f"Updated {label} with {len(data) if isinstance(data, list) else 'new'} rows.")
    return True

def financial_report_key(report):
    """Build a stable identity for append-only financial reports."""
    if not isinstance(report, dict):
        return json.dumps(report, sort_keys=True)
    documents = report.get('documents') if isinstance(report.get('documents'), list) else []
    document_keys = tuple(
        (
            str((doc or {}).get('path') or ''),
            str((doc or {}).get('submitted_date') or ''),
        )
        for doc in documents
        if isinstance(doc, dict)
    )
    return (
        str(report.get('type') or ''),
        str(report.get('quarter') or ''),
        str(report.get('fy') or ''),
        str(report.get('fy_nepali') or ''),
        document_keys,
    )

def company_financial_key(company):
    if not isinstance(company, dict):
        return ''
    symbol = company.get('symbol')
    if symbol:
        return f"symbol:{str(symbol).upper()}"
    company_id = company.get('id')
    return f"id:{company_id}" if company_id is not None else ''

def merge_append_only_financials(existing_records, incoming_records):
    """
    Preserve stored financial reports and append only reports/companies not seen before.
    Existing report values are not overwritten because historical financial filings should
    remain stable once captured.
    """
    existing = existing_records if isinstance(existing_records, list) else []
    incoming = incoming_records if isinstance(incoming_records, list) else []
    merged = []
    company_index = {}
    added_reports = 0
    added_companies = 0

    for company in existing:
        if not isinstance(company, dict):
            continue
        cloned = {**company}
        reports = company.get('reports')
        cloned['reports'] = reports[:] if isinstance(reports, list) else []
        key = company_financial_key(cloned)
        if key:
            company_index[key] = cloned
        merged.append(cloned)

    for company in incoming:
        if not isinstance(company, dict):
            continue
        reports = company.get('reports') if isinstance(company.get('reports'), list) else []
        key = company_financial_key(company)
        if not key or key not in company_index:
            cloned = {**company, "reports": reports[:]}
            merged.append(cloned)
            if key:
                company_index[key] = cloned
            added_companies += 1
            added_reports += len(reports)
            continue

        target = company_index[key]
        target_reports = target.get('reports') if isinstance(target.get('reports'), list) else []
        seen_reports = {financial_report_key(report) for report in target_reports}
        for report in reports:
            report_key = financial_report_key(report)
            if report_key in seen_reports:
                continue
            target_reports.append(report)
            seen_reports.add(report_key)
            added_reports += 1
        target['reports'] = target_reports

    return merged, added_companies, added_reports

def write_financials_append_only(filepath, incoming_records, min_existing_ratio=0.8):
    """Append new financial report records without replacing existing historical rows."""
    if not incoming_records:
        print("No company financial report data fetched. Keeping existing file unchanged.")
        return False, load_json_list(filepath)

    existing = load_json_list(filepath)
    if existing:
        minimum_count = int(len(existing) * min_existing_ratio)
        if len(incoming_records) < minimum_count:
            print(
                f"Fetched only {len(incoming_records)} company financial rows; existing file has {len(existing)}. "
                "Keeping existing file unchanged to avoid a partial append run."
            )
            return False, existing

    merged, added_companies, added_reports = merge_append_only_financials(existing, incoming_records)
    if not existing:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=4)
        print(f"Created company financial reports with {len(merged)} companies.")
        return True, merged

    if added_reports == 0 and added_companies == 0:
        print("No new company financial reports found. Keeping existing financials file.")
        return False, existing

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=4)
    print(f"Appended {added_reports} new financial reports across {added_companies} new companies.")
    return True, merged

def merge_records_by_id(existing_records, incoming_records):
    """
    Merge two record lists using `id` as the primary key.
    - Existing records are preserved.
    - Incoming records update matching IDs.
    - Incoming records with new IDs are appended.
    """
    merged_by_id = {}
    order = []
    fallback_counter = 0

    def record_key(record):
        nonlocal fallback_counter
        if isinstance(record, dict) and record.get('id') is not None:
            return f"id:{record.get('id')}"
        fallback_counter += 1
        return f"fallback:{fallback_counter}"

    def merge_record(existing, incoming):
        merged = dict(existing)
        for key, value in incoming.items():
            if value in (None, "", [], {}) and merged.get(key) not in (None, "", [], {}):
                continue
            merged[key] = value
        return merged

    for record in existing_records:
        key = record_key(record)
        if key not in merged_by_id:
            order.append(key)
            merged_by_id[key] = record

    for record in incoming_records:
        key = record_key(record)
        if key in merged_by_id and isinstance(merged_by_id[key], dict) and isinstance(record, dict):
            merged_by_id[key] = merge_record(merged_by_id[key], record)
        else:
            merged_by_id[key] = record
            if key not in order:
                order.append(key)

    return [merged_by_id[key] for key in order]

def load_records_from_paths(*paths):
    """Load and merge records from multiple JSON list files without dropping older IDs."""
    merged = []
    for path in paths:
        records = load_json_list(path)
        if records:
            merged = merge_records_by_id(merged, records)
    return merged

def _normalize_text(value):
    """Normalize text for safe duplicate comparisons."""
    return ' '.join(str(value or '').split()).strip().lower()

def strip_html_text(value):
    if not value:
        return ""
    return BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)

def build_file_url(file_path):
    """Construct the full, valid download URL for a NEPSE attachment path."""
    if not file_path:
        return None
    file_path = str(file_path)
    if file_path.startswith('http://') or file_path.startswith('https://'):
        return file_path
    base_url = "https://www.nepalstock.com.np/api/nots/security/fetchFiles?fileLocation="
    encoded_path = urllib.parse.quote(file_path, safe="/%")
    return base_url + encoded_path

def add_file_urls_to_company_disclosures(records):
    """Attach fileUrl to each document entry in company disclosures."""
    if not isinstance(records, list):
        return records
    for record in records:
        if not isinstance(record, dict):
            continue
        documents = record.get('applicationDocumentDetailsList')
        if not isinstance(documents, list):
            continue
        for doc in documents:
            if not isinstance(doc, dict):
                continue
            file_url = build_file_url(doc.get('filePath'))
            if file_url:
                doc['fileUrl'] = file_url
    return records

def compact_company_disclosure_record(record):
    """Return a compact public-facing company disclosure record."""
    if not isinstance(record, dict):
        return {}

    raw_title = record.get('title') or record.get('newsHeadline') or ''
    symbol = record.get('symbol') or extract_symbol_from_title(raw_title)
    title = re.sub(r'\s*[\[\(][A-Za-z0-9]+[\]\)]\s*$', '', str(raw_title)).strip()
    body = record.get('body') or strip_html_text(record.get('newsBody'))
    source = record.get('source') or record.get('newsSource')
    if not title:
        title = (
            strip_html_text(body)
            or strip_html_text(source)
            or f"Disclosure {record.get('id')}"
        )
    raw_documents = record.get('documents')
    if not isinstance(raw_documents, list):
        raw_documents = record.get('applicationDocumentDetailsList')

    documents = []
    if isinstance(raw_documents, list):
        for doc in raw_documents:
            if not isinstance(doc, dict):
                continue
            compact_doc = {
                "id": doc.get('id'),
                "submittedDate": doc.get('submittedDate'),
                "fileUrl": doc.get('fileUrl') or build_file_url(doc.get('filePath')),
            }
            compact_doc = {
                key: value
                for key, value in compact_doc.items()
                if value not in (None, "", [], {})
            }
            if compact_doc:
                documents.append(compact_doc)

    compact = {
        "id": record.get('id'),
        "symbol": symbol,
        "title": title,
        "body": body,
        "source": source,
        "publishedAt": record.get('publishedAt') or record.get('addedDate'),
        "documents": documents,
    }
    return {
        key: value
        for key, value in compact.items()
        if value not in (None, "", [], {})
    }

def compact_company_disclosure_records(records):
    if not isinstance(records, list):
        return []
    compact = [compact_company_disclosure_record(item) for item in records]
    return [item for item in compact if item.get('id') is not None]

def compact_exchange_message_record(record):
    """Return a compact public-facing exchange message record."""
    if not isinstance(record, dict):
        return {}

    raw_title = record.get('title') or record.get('messageTitle') or record.get('newsHeadline') or ''
    symbol = record.get('symbol') or extract_symbol_from_title(raw_title)
    title = re.sub(r'\s*[\[\(][A-Za-z0-9]+[\]\)]\s*$', '', str(raw_title)).strip()

    compact = {
        "id": record.get('id'),
        "symbol": symbol,
        "title": title,
        "body": record.get('body') or strip_html_text(record.get('messageBody')),
        "publishedAt": record.get('publishedAt') or record.get('addedDate'),
        "expiresAt": record.get('expiresAt') or record.get('expiryDate'),
        "fileUrl": record.get('fileUrl') or build_file_url(record.get('filePath')),
    }
    return {
        key: value
        for key, value in compact.items()
        if value not in (None, "", [], {})
    }

def compact_exchange_message_records(records):
    if not isinstance(records, list):
        return []
    compact = [compact_exchange_message_record(item) for item in records]
    return [item for item in compact if item.get('id') is not None]

def compact_notice_record(record):
    """Return a compact public-facing general notice record."""
    if not isinstance(record, dict):
        return {}

    notice_type = record.get('type')
    raw_notice_type = record.get('noticeTypeId')
    if not notice_type and isinstance(raw_notice_type, dict):
        notice_type = raw_notice_type.get('noticeType')

    compact = {
        "id": record.get('id'),
        "title": record.get('title') or record.get('noticeHeading'),
        "body": record.get('body') or strip_html_text(record.get('noticeBody')),
        "expiresAt": record.get('expiresAt') or record.get('noticeExpiryDate'),
        "type": notice_type,
        "featured": record.get('featured') if 'featured' in record else record.get('feature'),
        "filePath": record.get('filePath') or record.get('noticeFilePath'),
    }
    return {
        key: value
        for key, value in compact.items()
        if value not in (None, "", [], {})
    }

def compact_notice_records(records):
    if not isinstance(records, list):
        return []
    compact = [compact_notice_record(item) for item in records]
    return [item for item in compact if item.get('id') is not None]

def add_file_urls_to_exchange_messages(records):
    """Attach fileUrl to each exchange message when filePath is present."""
    if not isinstance(records, list):
        return records
    for record in records:
        if not isinstance(record, dict):
            continue
        file_url = build_file_url(record.get('filePath'))
        if file_url:
            record['fileUrl'] = file_url
    return records

def _parse_datetime(value):
    """Parse a date/time string to a datetime; fallback to datetime.min."""
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return datetime.min

def sort_disclosures_latest_first(records, date_keys):
    """Sort disclosures so newest entries appear first."""
    if not isinstance(records, list):
        return records
    def sort_key(item):
        if not isinstance(item, dict):
            return datetime.min
        for key in date_keys:
            value = item.get(key)
            if value:
                return _parse_datetime(value)
        return datetime.min
    records.sort(key=sort_key, reverse=True)
    return records

def sort_notices_latest_first(records):
    """Sort notices so newest entries appear first (date, then id fallback)."""
    if not isinstance(records, list):
        return records
    def sort_key(item):
        if not isinstance(item, dict):
            return (datetime.min, 0)
        for key in ('publishedAt', 'modifiedDate', 'expiresAt', 'noticeExpiryDate'):
            value = item.get(key)
            if value:
                return (_parse_datetime(value), 0)
        notice_id = item.get('id')
        try:
            return (datetime.min, int(notice_id))
        except Exception:
            return (datetime.min, 0)
    records.sort(key=sort_key, reverse=True)
    return records

def _collect_record_ids(records):
    """Collect numeric/string IDs from a list of records."""
    if not isinstance(records, list):
        return set()
    return {
        str(item.get('id'))
        for item in records
        if isinstance(item, dict) and item.get('id') is not None
    }

def filter_new_records(existing_records, incoming_records):
    """Return only incoming records whose IDs are not in existing records."""
    existing_ids = _collect_record_ids(existing_records)
    if not isinstance(incoming_records, list):
        return []
    return [
        item for item in incoming_records
        if isinstance(item, dict)
        and item.get('id') is not None
        and str(item.get('id')) not in existing_ids
    ]

def extract_symbol_from_title(title):
    """Extract ticker symbol from a title like '[SYMBOL]' or '(SYMBOL)'."""
    if not title:
        return ""
    match = re.search(r'\[([A-Za-z0-9]+)\]', str(title))
    if match:
        return match.group(1).upper()
    match = re.search(r'\(([A-Za-z0-9]+)\)', str(title))
    if match:
        return match.group(1).upper()
    return ""

def add_symbols_to_company_disclosures(records):
    """Add `symbol` field to company disclosures for easier filtering."""
    if not isinstance(records, list):
        return records
    for record in records:
        if not isinstance(record, dict):
            continue
        title = record.get('newsHeadline') or record.get('messageTitle') or ""
        symbol = extract_symbol_from_title(title)
        if symbol:
            record['symbol'] = symbol
    return records

def add_symbols_to_exchange_messages(records):
    """Add `symbol` field to exchange messages for easier filtering."""
    if not isinstance(records, list):
        return records
    for record in records:
        if not isinstance(record, dict):
            continue
        title = record.get('messageTitle') or record.get('newsHeadline') or ""
        symbol = extract_symbol_from_title(title)
        if symbol:
            record['symbol'] = symbol
    return records

def filter_general_notices(general_notices, exchange_messages):
    """
    Remove exchange-message entries from general notices.
    Matching strategy:
    1) Same numeric/string id
    2) Same normalized title + body
    """
    notices = general_notices if isinstance(general_notices, list) else []
    exchanges = exchange_messages if isinstance(exchange_messages, list) else []

    exchange_ids = {
        str(item.get('id'))
        for item in exchanges
        if isinstance(item, dict) and item.get('id') is not None
    }
    exchange_title_body = {
        (
            _normalize_text(item.get('title') or item.get('messageTitle')),
            _normalize_text(item.get('body') or item.get('messageBody'))
        )
        for item in exchanges
        if isinstance(item, dict)
    }

    filtered = []
    removed_count = 0
    for notice in notices:
        if not isinstance(notice, dict):
            filtered.append(notice)
            continue

        notice_id = notice.get('id')
        notice_key = (
            _normalize_text(notice.get('title') or notice.get('noticeHeading')),
            _normalize_text(notice.get('body') or notice.get('noticeBody'))
        )

        is_exchange_duplicate = (
            (notice_id is not None and str(notice_id) in exchange_ids)
            or notice_key in exchange_title_body
        )

        if is_exchange_duplicate:
            removed_count += 1
            continue

        filtered.append(notice)

    if removed_count:
        print(f"Filtered out {removed_count} exchange-derived records from notices.")
    return filtered

def get_sector_wise_codes():
    """Scrape sector-wise company codes from MeroLagani."""
    url = "https://merolagani.com/CompanyList.aspx"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        sectors = {}
        accordion_toggles = soup.find_all('a', href=re.compile(r'#collapse_\d+'))

        for toggle in accordion_toggles:
            sector_name = toggle.get_text(strip=True)
            target_id = toggle['href'].replace('#', '')
            content_div = soup.find(id=target_id)

            if not content_div:
                continue

            table = content_div.find('table')
            companies = []

            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        symbol_link = cols[0].find('a')
                        symbol = symbol_link.get_text(strip=True) if symbol_link else cols[0].get_text(strip=True)

                        name = cols[1].get_text(strip=True)
                        name = " ".join(name.split())

                        if symbol and name:
                            companies.append({
                                "symbol": symbol,
                                "name": name
                            })
            else:
                company_links = content_div.find_all('a', href=re.compile(r'CompanyDetail\.aspx\?symbol='))
                for link in company_links:
                    href = link.get('href', '')
                    match = re.search(r'symbol=([a-zA-Z0-9.]+)', href, re.IGNORECASE)
                    if match:
                        symbol = match.group(1)
                        companies.append({
                            "symbol": symbol,
                            "name": symbol
                        })

            if companies:
                sectors[sector_name] = companies

        return sectors

    except Exception as e:
        print(f"Error fetching sector-wise codes: {e}")
        return None

def scrape_all_official_data(
    include_brokers=False,
    include_financials=False,
    include_profiles=False,
    force_financials=False,
    force_profiles=False,
    ltp_history_mode='live-close',
    include_market=True,
    include_notifications=True
):
    print(f"Starting Comprehensive Official NEPSE Scraper at {datetime.now().isoformat()}...")
    
    try:
        # 1. Initialize Scraper
        scraper = NepseScraper(verify_ssl=False)
        
        # Data directory
        # Use absolute path of this file to find the data directory
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.path.join(base_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        market_dir = os.path.join(data_dir, 'market')
        os.makedirs(market_dir, exist_ok=True)
        notify_dir = os.path.join(data_dir, 'notify')
        os.makedirs(notify_dir, exist_ok=True)
        other_dir = os.path.join(data_dir, 'other')
        os.makedirs(other_dir, exist_ok=True)
        write_legacy = should_write_legacy_aliases()

        def write_json(path, data):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)

        if not write_legacy:
            for legacy_name in (
                'market_status.json',
                'indices.json',
                'sector_indices.json',
                'top_stocks.json',
                'market_summary.json',
                'market_summary_history.json',
                'disclosures.json',
                'exchange_messages.json',
                'notices.json',
                'brokers.json',
                'all_securities.json',
                'nepse_sector_wise_codes.json',
                'supply_demand.json',
            ):
                remove_file_if_exists(os.path.join(data_dir, legacy_name))
            remove_file_if_exists(os.path.join(data_dir, 'brokers', 'list.json'))
        
        if include_market:
            # 2. Market Status
            print("Checking market status...")
            is_open = scraper.is_market_open()
            market_status = {
                "is_open": is_open,
                "last_checked": datetime.now().isoformat()
            }
            write_json(os.path.join(market_dir, 'status.json'), market_status)
            if write_legacy:
                write_json(os.path.join(data_dir, 'market_status.json'), market_status)

            # 3. Refresh open-ended mutual funds (OMF.json)
            print("Refreshing open-ended mutual fund data...")
            omf_snapshot = refresh_omf_data(data_dir)

            # 4. Today's Prices
            print("Fetching today's prices...")
            raw_prices = scraper.get_today_price()

            mapped_prices = []
            for item in raw_prices:
                symbol = item.get('symbol')
                ltp = item.get('lastUpdatedPrice', 0)
                prev_close = item.get('previousDayClosePrice', 0)
                change = round(ltp - prev_close, 2) if ltp and prev_close else 0
                p_change = round((change / prev_close) * 100, 2) if prev_close != 0 else 0

                mapped_prices.append({
                    "symbol": symbol,
                    "name": item.get('securityName'),
                    "ltp": ltp,
                    "previous_close": prev_close,
                    "change": change,
                    "percent_change": p_change,
                    "high": item.get('highPrice'),
                    "low": item.get('lowPrice'),
                    "volume": item.get('totalTradedQuantity'),
                    "turnover": item.get('totalTradedValue'),
                    "trades": item.get('totalTrades'),
                    "last_updated": item.get('lastUpdatedTime'),
                    "market_cap": item.get('marketCapitalization')
                })

            # Include open-ended mutual funds collected from Sharesansar OMF.json.
            # Use fresh in-memory snapshot when available.
            omf_rows = build_omf_rows_for_nepse_data(data_dir, omf_items=omf_snapshot)
            if omf_rows:
                seen_symbols = {row.get('symbol') for row in mapped_prices if isinstance(row, dict)}
                appended = 0
                for row in omf_rows:
                    symbol = row.get('symbol')
                    if symbol in seen_symbols:
                        continue
                    mapped_prices.append(row)
                    seen_symbols.add(symbol)
                    appended += 1
                print(f"Added {appended} open-ended mutual fund rows to nepse_data.json.")
            else:
                print("No OMF rows found. nepse_data.json will include only NEPSE official price rows.")

            mapped_prices.sort(key=lambda x: str(x.get('symbol', '')))

            write_json(os.path.join(data_dir, 'nepse_data.json'), mapped_prices)
            write_json(os.path.join(market_dir, 'live.json'), mapped_prices)

            if should_update_ltp_history(ltp_history_mode, market_is_open=is_open):
                latest_status = ltp_history_latest_status()
                print(f"Updating daily intraday LTP shard ({ltp_history_mode}, {latest_status}).")
                build_intraday_shard(
                    source_path=os.path.join(data_dir, 'nepse_data.json'),
                    output_dir=os.path.join(data_dir, 'ltp')
                )

                print(f"Updating monthly LTP history shards ({ltp_history_mode}, {latest_status}).")
                build_shards(
                    source_path=os.path.join(data_dir, 'nepse_data.json'),
                    output_dir=os.path.join(data_dir, 'ltp'),
                    latest_status=latest_status
                )
            else:
                now_npt = datetime.now(NPT).isoformat(timespec='minutes')
                print(
                    "Skipping monthly LTP history shards "
                    f"({ltp_history_mode}, current NPT time {now_npt})."
                )

            # 4. Indices (Live & All Sectoral)
            print("Fetching indices...")
            indices = scraper.get_nepse_index()
            sector_indices = scraper.get_sector_indices()
            write_json(os.path.join(market_dir, 'indices.json'), indices)
            write_json(os.path.join(market_dir, 'sector_indices.json'), sector_indices)
            if write_legacy:
                write_json(os.path.join(data_dir, 'indices.json'), indices)
                write_json(os.path.join(data_dir, 'sector_indices.json'), sector_indices)

            # 4b. Sector-wise Company Codes
            print("Fetching sector-wise company codes...")
            sector_wise_codes = get_sector_wise_codes()
            sector_codes_path = os.path.join(other_dir, 'sector_codes.json')
            if isinstance(sector_wise_codes, dict) and sector_wise_codes:
                if write_json_if_changed(sector_codes_path, sector_wise_codes):
                    print("Updated sector-wise codes.")
                else:
                    print("Sector-wise codes unchanged. Keeping existing file.")
                if write_legacy:
                    write_json_if_changed(os.path.join(data_dir, 'nepse_sector_wise_codes.json'), sector_wise_codes)
            else:
                print("No sector-wise data found or error. Keeping existing file unchanged.")

            # 5. Top Stocks (Full Categories)
            print("Fetching top gainers, losers, turnover, trades, and transactions...")
            categories = ['top_gainer', 'top_loser', 'top_turnover', 'top_trade', 'top_transaction']
            top_stocks = {}
            for cat in categories:
                try:
                    top_stocks[cat] = scraper.get_top_stocks(cat, show_all=True)
                except:
                    top_stocks[cat] = []
            write_json(os.path.join(market_dir, 'top_stocks.json'), top_stocks)
            if write_legacy:
                write_json(os.path.join(data_dir, 'top_stocks.json'), top_stocks)

            # 6. Market Summary & History
            print("Fetching market summaries...")
            summary = scraper.get_market_summary()
            summary_history = scraper.get_market_summary_history()
            write_json(os.path.join(market_dir, 'summary.json'), summary)
            write_json(os.path.join(market_dir, 'history.json'), summary_history)
            if write_legacy:
                write_json(os.path.join(data_dir, 'market_summary.json'), summary)
                write_json(os.path.join(data_dir, 'market_summary_history.json'), summary_history)
        else:
            print("Skipping market data refresh.")

        # 7. Notices & News (Restored Disclosures)
        print("Fetching company disclosures...")
        disclosure_data = scraper.get_company_disclosures()
        company_disclosures = disclosure_data.get('companyNews', [])
        exchange_messages = disclosure_data.get('exchangeMessages', [])

        disclosures_path = os.path.join(notify_dir, 'disclosures.json')
        exchange_messages_path = os.path.join(notify_dir, 'exchange_messages.json')
        legacy_disclosures_path = os.path.join(data_dir, 'disclosures.json')
        legacy_exchange_messages_path = os.path.join(data_dir, 'exchange_messages.json')

        existing_company_disclosures = load_records_from_paths(
            disclosures_path,
            legacy_disclosures_path
        )
        existing_exchange_messages = load_records_from_paths(
            exchange_messages_path,
            legacy_exchange_messages_path
        )

        incoming_company_disclosures = company_disclosures if isinstance(company_disclosures, list) else []
        incoming_exchange_messages = exchange_messages if isinstance(exchange_messages, list) else []

        new_company_disclosures = filter_new_records(
            existing_company_disclosures,
            incoming_company_disclosures
        )
        new_exchange_messages = filter_new_records(
            existing_exchange_messages,
            incoming_exchange_messages
        )

        if new_company_disclosures or new_exchange_messages:
            merged_company_disclosures = merge_records_by_id(
                existing_company_disclosures,
                incoming_company_disclosures
            )
            merged_exchange_messages = merge_records_by_id(
                existing_exchange_messages,
                incoming_exchange_messages
            )

            merged_company_disclosures = add_file_urls_to_company_disclosures(merged_company_disclosures)
            merged_exchange_messages = add_file_urls_to_exchange_messages(merged_exchange_messages)

            merged_company_disclosures = add_symbols_to_company_disclosures(merged_company_disclosures)
            merged_exchange_messages = add_symbols_to_exchange_messages(merged_exchange_messages)

            merged_company_disclosures = compact_company_disclosure_records(merged_company_disclosures)
            merged_exchange_messages = compact_exchange_message_records(merged_exchange_messages)

            merged_company_disclosures = sort_disclosures_latest_first(
                merged_company_disclosures,
                date_keys=('publishedAt', 'addedDate', 'modifiedDate', 'approvedDate')
            )
            merged_exchange_messages = sort_disclosures_latest_first(
                merged_exchange_messages,
                date_keys=('publishedAt', 'addedDate', 'modifiedDate', 'approvedDate', 'expiresAt', 'expiryDate')
            )
            
            write_json(disclosures_path, merged_company_disclosures)
            write_json(exchange_messages_path, merged_exchange_messages)
            if write_legacy:
                write_json(legacy_disclosures_path, merged_company_disclosures)
                write_json(legacy_exchange_messages_path, merged_exchange_messages)

            print(
                "New disclosures found: "
                f"{len(new_company_disclosures)} company disclosures, "
                f"{len(new_exchange_messages)} exchange messages."
            )
        else:
            merged_company_disclosures = compact_company_disclosure_records(existing_company_disclosures)
            merged_company_disclosures = sort_disclosures_latest_first(
                merged_company_disclosures,
                date_keys=('publishedAt', 'addedDate', 'modifiedDate', 'approvedDate')
            )
            merged_exchange_messages = compact_exchange_message_records(existing_exchange_messages)
            merged_exchange_messages = sort_disclosures_latest_first(
                merged_exchange_messages,
                date_keys=('publishedAt', 'addedDate', 'modifiedDate', 'approvedDate', 'expiresAt', 'expiryDate')
            )
            disclosures_changed = merged_company_disclosures != existing_company_disclosures
            exchange_messages_changed = merged_exchange_messages != existing_exchange_messages
            if disclosures_changed or exchange_messages_changed:
                if disclosures_changed:
                    write_json(disclosures_path, merged_company_disclosures)
                    if write_legacy:
                        write_json(legacy_disclosures_path, merged_company_disclosures)
                if exchange_messages_changed:
                    write_json(exchange_messages_path, merged_exchange_messages)
                    if write_legacy:
                        write_json(legacy_exchange_messages_path, merged_exchange_messages)
                print("No new disclosures found. Compacted existing disclosure files.")
            else:
                print("No new disclosures found. Keeping existing disclosure files unchanged.")

        print("Fetching notices...")
        general_notices = scraper.get_notices()
        filtered_general_notices = filter_general_notices(general_notices, merged_exchange_messages)
        notices_path = os.path.join(notify_dir, 'notices.json')

        existing_notices = {}
        if os.path.exists(notices_path):
            try:
                with open(notices_path, 'r', encoding='utf-8') as f:
                    loaded_notices = json.load(f)
                if isinstance(loaded_notices, dict):
                    existing_notices = loaded_notices
            except Exception:
                existing_notices = {}

        existing_general_notices = existing_notices.get('general', [])
        incoming_general_notices = filtered_general_notices if isinstance(filtered_general_notices, list) else []
        new_general_notices = filter_new_records(
            existing_general_notices if isinstance(existing_general_notices, list) else [],
            incoming_general_notices
        )

        if new_general_notices:
            merged_general_notices = merge_records_by_id(
                existing_general_notices if isinstance(existing_general_notices, list) else [],
                incoming_general_notices
            )
            merged_general_notices = compact_notice_records(merged_general_notices)
            merged_general_notices = sort_notices_latest_first(merged_general_notices)

            notices_payload = {
                "general": merged_general_notices,
                "last_updated": datetime.now().isoformat()
            }
            # Keep notices file dedicated to general notices only.
            write_json(notices_path, notices_payload)
            if write_legacy:
                write_json(os.path.join(data_dir, 'notices.json'), notices_payload)
            print(f"New notices found: {len(new_general_notices)}.")
        else:
            merged_general_notices = compact_notice_records(
                existing_general_notices if isinstance(existing_general_notices, list) else []
            )
            merged_general_notices = sort_notices_latest_first(merged_general_notices)
            notices_payload = {
                "general": merged_general_notices,
                "last_updated": existing_notices.get('last_updated') or datetime.now().isoformat()
            }
            if notices_payload != existing_notices:
                write_json(notices_path, notices_payload)
                if write_legacy:
                    write_json(os.path.join(data_dir, 'notices.json'), notices_payload)
                print("No new notices found. Compacted existing notices file.")
            else:
                print("No new notices found. Keeping existing notices file unchanged.")

        # 8. Brokers
        if include_brokers:
            print("Fetching broker list...")
            brokers = scraper.get_brokers()
            brokers = compact_broker_records(brokers)
            brokers_path = os.path.join(other_dir, 'brokers.json')
            if isinstance(brokers, list) and brokers:
                if write_json_if_changed(brokers_path, brokers):
                    print("Updated broker list.")
                else:
                    print("Broker list unchanged. Keeping existing file.")
                if write_legacy:
                    write_json_if_changed(os.path.join(data_dir, 'brokers.json'), brokers)
            else:
                print("No broker data found or error. Keeping existing file unchanged.")
        else:
            print("Skipping broker list (not requested or recently updated).")

        # 9. Securities metadata and optional company financial reports
        print("Fetching all securities for company IDs...")
        all_securities = scraper.get_all_securities()
        securities_path = os.path.join(other_dir, 'securities.json')
        if isinstance(all_securities, list) and all_securities:
            if write_json_if_changed(securities_path, all_securities):
                print(f"Updated securities list with {len(all_securities)} company IDs.")
            else:
                print(f"Securities list unchanged ({len(all_securities)} company IDs).")
            if write_legacy:
                write_json_if_changed(os.path.join(data_dir, 'all_securities.json'), all_securities)
        else:
            print("No securities data found or error. Keeping existing securities file unchanged.")
            all_securities = load_json_list(securities_path)

        if include_financials:
            company_dir = os.path.join(data_dir, 'company')
            os.makedirs(company_dir, exist_ok=True)
            financials_path = os.path.join(company_dir, 'financials.json')
            metadata_path = os.path.join(company_dir, 'metadata.json')
            if should_run_daily_company_dataset(
                company_dir,
                'financials_last_checked',
                'company financial reports',
                force_financials
            ):
                print("Fetching company financial reports from company detail pages...")
                financials = build_company_financials_snapshot(scraper, all_securities)
                financials_changed, merged_financials = write_financials_append_only(
                    financials_path,
                    financials
                )
                if financials_changed or not os.path.exists(metadata_path):
                    metadata_payload = {
                        "last_updated": datetime.now().isoformat(),
                        "source": "https://nepalstock.com/company/detail/{company_id}",
                        "document_base_url": "https://www.nepalstock.com.np/api/nots/security/fetchFiles?fileLocation=",
                        "count": len(merged_financials),
                    }
                    write_json_if_changed(metadata_path, metadata_payload)
                    print("Updated company financial metadata.")
                if snapshot_complete_enough(financials_path, financials):
                    update_company_run_metadata(company_dir, 'financials_last_checked')
        else:
            print("Skipping company financial reports (use --financials to fetch them).")

        if include_profiles:
            company_dir = os.path.join(data_dir, 'company')
            os.makedirs(company_dir, exist_ok=True)
            profiles_path = os.path.join(company_dir, 'profiles.json')
            if should_run_daily_company_dataset(
                company_dir,
                'profiles_last_checked',
                'company profiles',
                force_profiles
            ):
                print("Fetching company profiles from company detail pages...")
                profiles = build_company_profiles_snapshot(scraper, all_securities)
                write_snapshot_if_changed(
                    profiles_path,
                    profiles,
                    'company profiles'
                )
                if snapshot_complete_enough(profiles_path, profiles):
                    update_company_run_metadata(company_dir, 'profiles_last_checked')
        else:
            print("Skipping company profiles (use --profiles to fetch them).")

        # 10. Supply & Demand
        if include_market:
            print("Fetching supply and demand...")
            try:
                supply_demand = scraper.get_supply_demand(show_all=True)
                write_json(os.path.join(market_dir, 'supply_demand.json'), supply_demand)
                if write_legacy:
                    write_json(os.path.join(data_dir, 'supply_demand.json'), supply_demand)
            except requests.HTTPError as exc:
                print(f"Failed to fetch supply and demand ({exc}). Keeping existing supply_demand.json unchanged.")
        else:
            print("Skipping supply and demand refresh.")

        print(f"Successfully completed comprehensive official scraping.")
        return True

    except Exception as e:
        print(f"Error in comprehensive official scraping: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NEPSE Official Data Scraper')
    parser.add_argument('--brokers', action='store_true', help='Force update broker list')
    parser.add_argument(
        '--financials',
        action='store_true',
        help='Fetch financial reports for all company IDs from /company/detail/{company_id}'
    )
    parser.add_argument(
        '--profiles',
        action='store_true',
        help='Fetch brief company profiles for all company IDs from /company/detail/{company_id}'
    )
    parser.add_argument(
        '--force-financials',
        action='store_true',
        help='Run company financial fetching even if it already ran today'
    )
    parser.add_argument(
        '--force-profiles',
        action='store_true',
        help='Run company profile fetching even if it already ran today'
    )
    parser.add_argument(
        '--ltp-history',
        choices=('live-close', 'close-only', 'always', 'skip'),
        default='live-close',
        help='Control monthly LTP history shard updates. Defaults to live-close.'
    )
    parser.add_argument(
        '--skip-market',
        action='store_true',
        help='Skip market price, index, summary, OMF, top-stock, LTP, and supply/demand refreshes.'
    )
    args = parser.parse_args()
    
    # Use absolute path of this file to find the data directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, 'data')
    
    # helper for age check
    def should_update(filename, force_flag):
        if force_flag:
            return True
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            print(f"{filename} not found, performing initial fetch...")
            return True
        
        file_time = get_file_last_commit_date(filepath)
        if not file_time:
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
        
        age = datetime.now() - file_time
        if age > timedelta(days=60):
            print(f"{filename} is {age.days} days old, updating...")
            return True
        print(f"{filename} is {age.days} days old (limit 60). Skipping update.")
        return False

    include_brokers = should_update(os.path.join('other', 'brokers.json'), args.brokers)
            
    success = scrape_all_official_data(
        include_brokers=include_brokers,
        include_financials=args.financials,
        include_profiles=args.profiles,
        force_financials=args.force_financials,
        force_profiles=args.force_profiles,
        ltp_history_mode=args.ltp_history,
        include_market=not args.skip_market
    )
    sys.exit(0 if success else 1)
