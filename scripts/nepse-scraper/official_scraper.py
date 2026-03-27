import sys
import os
import json
import argparse
import subprocess
from datetime import datetime, timedelta
import urllib.parse
import re
import requests
from bs4 import BeautifulSoup

# Add the current directory to path to find official_api
sys.path.append(os.path.dirname(__file__))

from official_api import NepseScraper
from open_ended_mutual_fund_scraper import scrape_and_save_open_ended_navs

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

def write_json_if_changed(filepath, data):
    """Write JSON only if content differs or file does not exist."""
    existing = load_json_object(filepath)
    if existing == data:
        return False
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    return True

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

    for record in existing_records:
        key = record_key(record)
        if key not in merged_by_id:
            order.append(key)
            merged_by_id[key] = record

    for record in incoming_records:
        key = record_key(record)
        if key in merged_by_id and isinstance(merged_by_id[key], dict) and isinstance(record, dict):
            merged_by_id[key] = {**merged_by_id[key], **record}
        else:
            merged_by_id[key] = record
            if key not in order:
                order.append(key)

    return [merged_by_id[key] for key in order]

def _normalize_text(value):
    """Normalize text for safe duplicate comparisons."""
    return ' '.join(str(value or '').split()).strip().lower()

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
        for key in ('modifiedDate', 'noticeExpiryDate'):
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
            _normalize_text(item.get('messageTitle')),
            _normalize_text(item.get('messageBody'))
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
            _normalize_text(notice.get('noticeHeading')),
            _normalize_text(notice.get('noticeBody'))
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

def scrape_all_official_data(include_brokers=False):
    print(f"Starting Comprehensive Official NEPSE Scraper at {datetime.now().isoformat()}...")
    
    try:
        # 1. Initialize Scraper
        scraper = NepseScraper(verify_ssl=False)
        
        # Data directory
        # Use absolute path of this file to find the data directory
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.path.join(base_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # 2. Market Status
        print("Checking market status...")
        is_open = scraper.is_market_open()
        market_status = {
            "is_open": is_open,
            "last_checked": datetime.now().isoformat()
        }
        with open(os.path.join(data_dir, 'market_status.json'), 'w') as f:
            json.dump(market_status, f, indent=4)
        
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

        with open(os.path.join(data_dir, 'nepse_data.json'), 'w') as f:
            json.dump(mapped_prices, f, indent=4)
        
        # 4. Indices (Live & All Sectoral)
        print("Fetching indices...")
        indices = scraper.get_nepse_index()
        sector_indices = scraper.get_sector_indices()
        with open(os.path.join(data_dir, 'indices.json'), 'w') as f:
            json.dump(indices, f, indent=4)
        with open(os.path.join(data_dir, 'sector_indices.json'), 'w') as f:
            json.dump(sector_indices, f, indent=4)

        # 4b. Sector-wise Company Codes
        print("Fetching sector-wise company codes...")
        sector_wise_codes = get_sector_wise_codes()
        sector_codes_path = os.path.join(data_dir, 'nepse_sector_wise_codes.json')
        if isinstance(sector_wise_codes, dict) and sector_wise_codes:
            if write_json_if_changed(sector_codes_path, sector_wise_codes):
                print("Updated sector-wise codes.")
            else:
                print("Sector-wise codes unchanged. Keeping existing file.")
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
        with open(os.path.join(data_dir, 'top_stocks.json'), 'w') as f:
            json.dump(top_stocks, f, indent=4)

        # 6. Market Summary & History
        print("Fetching market summaries...")
        summary = scraper.get_market_summary()
        summary_history = scraper.get_market_summary_history()
        with open(os.path.join(data_dir, 'market_summary.json'), 'w') as f:
            json.dump(summary, f, indent=4)
        with open(os.path.join(data_dir, 'market_summary_history.json'), 'w') as f:
            json.dump(summary_history, f, indent=4)

        # 7. Notices & News (Restored Disclosures)
        print("Fetching company disclosures...")
        disclosure_data = scraper.get_company_disclosures()
        company_disclosures = disclosure_data.get('companyNews', [])
        exchange_messages = disclosure_data.get('exchangeMessages', [])

        disclosures_path = os.path.join(data_dir, 'disclosures.json')
        exchange_messages_path = os.path.join(data_dir, 'exchange_messages.json')

        existing_company_disclosures = load_json_list(disclosures_path)
        existing_exchange_messages = load_json_list(exchange_messages_path)

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

            merged_company_disclosures = sort_disclosures_latest_first(
                merged_company_disclosures,
                date_keys=('addedDate', 'modifiedDate', 'approvedDate')
            )
            merged_exchange_messages = sort_disclosures_latest_first(
                merged_exchange_messages,
                date_keys=('addedDate', 'modifiedDate', 'approvedDate', 'expiryDate')
            )
            
            with open(disclosures_path, 'w', encoding='utf-8') as f:
                json.dump(merged_company_disclosures, f, indent=4)
            
            with open(exchange_messages_path, 'w', encoding='utf-8') as f:
                json.dump(merged_exchange_messages, f, indent=4)

            print(
                "New disclosures found: "
                f"{len(new_company_disclosures)} company disclosures, "
                f"{len(new_exchange_messages)} exchange messages."
            )
        else:
            merged_company_disclosures = existing_company_disclosures
            merged_exchange_messages = existing_exchange_messages
            print("No new disclosures found. Keeping existing disclosure files unchanged.")

        print("Fetching notices...")
        general_notices = scraper.get_notices()
        filtered_general_notices = filter_general_notices(general_notices, merged_exchange_messages)
        notices_path = os.path.join(data_dir, 'notices.json')

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
            merged_general_notices = sort_notices_latest_first(merged_general_notices)

            with open(os.path.join(data_dir, 'notices.json'), 'w') as f:
                # Keep notices file dedicated to general notices only.
                json.dump({
                    "general": merged_general_notices,
                    "last_updated": datetime.now().isoformat()
                }, f, indent=4)
            print(f"New notices found: {len(new_general_notices)}.")
        else:
            print("No new notices found. Keeping existing notices file unchanged.")

        # 8. Brokers
        if include_brokers:
            print("Fetching broker list...")
            brokers = scraper.get_brokers()
            brokers_path = os.path.join(data_dir, 'brokers.json')
            if isinstance(brokers, list) and brokers:
                if write_json_if_changed(brokers_path, brokers):
                    print("Updated broker list.")
                else:
                    print("Broker list unchanged. Keeping existing file.")
            else:
                print("No broker data found or error. Keeping existing file unchanged.")
        else:
            print("Skipping broker list (not requested or recently updated).")

        # 9. Supply & Demand (Disabled)
        print("Fetching supply and demand...")
        supply_demand = scraper.get_supply_demand(show_all=True)
        with open(os.path.join(data_dir, 'supply_demand.json'), 'w') as f:
            json.dump(supply_demand, f, indent=4)

        # 10. Live Trades (Only if market open)
        if is_open:
            print("Fetching live trades...")
            live_trades = scraper.get_live_trades()
            with open(os.path.join(data_dir, 'live_trades.json'), 'w') as f:
                json.dump(live_trades, f, indent=4)

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

    include_brokers = should_update('brokers.json', args.brokers)
            
    scrape_all_official_data(include_brokers=include_brokers)
