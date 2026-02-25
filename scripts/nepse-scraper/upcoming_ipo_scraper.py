import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

def extract_company_from_text(text):
    if not text:
        return ""

    cleaned = text.strip()
    # Most IPO notices start with company name and end with Limited/Ltd.
    patterns = [
        r"^\s*(.+?\b(?:Limited|Ltd\.?))\b",
        r"^\s*(.+?)\s+(?:is\s+going\s+to\s+issue|has\s+published)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return match.group(1).strip(" -,:")
    return ""

def parse_ipo_text(full_text):
    company = full_text.strip() if full_text else ""
    units = ""
    date_range = ""

    pattern_main = re.compile(
        r"^\s*(?P<company>.+?)\s+is\s+going\s+to\s+issue\s+its\s+(?P<units>[\d,]+(?:\.\d+)?)\s+units.*?starting\s+from\s+(?P<date>.+?)\s*$",
        flags=re.IGNORECASE,
    )
    match = pattern_main.search(full_text)
    if match:
        return (
            match.group("company").strip(),
            match.group("units").strip(),
            match.group("date").strip(),
        )

    # Fallback: parse each piece independently if sentence wording changes.
    company_match = re.search(r"^\s*(.+?)\s+is\s+going\s+to\s+issue\s+its\s+", full_text, re.IGNORECASE)
    units_match = re.search(r"\b([\d,]+(?:\.\d+)?)\s+units?\b", full_text, re.IGNORECASE)
    date_match = re.search(r"\b(?:starting\s+from|open(?:ing)?\s+from|from)\s+(.+)$", full_text, re.IGNORECASE)

    if company_match:
        company = company_match.group(1).strip()
    if units_match:
        units = units_match.group(1).strip()
    if date_match:
        date_range = date_match.group(1).strip()

    # Final fallback for invalid/placeholder units values.
    units_candidate_match = re.search(r"(\d[\d,]*(?:\.\d+)?)\s+units?\b", full_text, re.IGNORECASE)
    units_candidate = units_candidate_match.group(1).strip() if units_candidate_match else ""
    normalized_units = units.replace(",", "").strip() if units else ""
    invalid_units = {"", "0", "00", "000", "0.0", "0.00", "00.0", "00.00"}
    if normalized_units in invalid_units and units_candidate:
        units = units_candidate

    extracted_company = extract_company_from_text(full_text)
    if extracted_company:
        company = extracted_company

    return company, units, date_range

def backfill_units_from_text(item):
    units = str(item.get("units", "")).strip()
    normalized_units = units.replace(",", "")
    invalid_units = {"", "Unknown", "0", "00", "000", "0.0", "0.00", "00.0", "00.00"}
    if normalized_units not in invalid_units:
        return item

    full_text = str(item.get("full_text", ""))
    if not full_text:
        return item

    match = re.search(r"(\d[\d,]*(?:\.\d+)?)\s+units?\b", full_text, re.IGNORECASE)
    if match:
        item["units"] = match.group(1)
    return item

def backfill_date_range_from_text(item):
    date_range = str(item.get("date_range", "")).strip()
    if date_range and date_range.lower() != "unknown":
        return item

    full_text = str(item.get("full_text", ""))
    if not full_text:
        return item

    match = re.search(r"\b(?:starting\s+from|open(?:ing)?\s+from|from)\s+(.+)$", full_text, re.IGNORECASE)
    if match:
        item["date_range"] = match.group(1).strip()
    return item

def backfill_company_from_text(item):
    company = str(item.get("company", "")).strip()
    if company and company.lower() != "unknown":
        return item

    full_text = str(item.get("full_text", ""))
    if not full_text:
        return item

    extracted = extract_company_from_text(full_text)
    if extracted:
        item["company"] = extracted
    return item

def scrape_upcoming_ipo():
    url = "https://merolagani.com/Ipo.aspx?type=upcoming"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print(f"Fetching {url}...")
        response = requests.get(url, headers=headers, timeout=(10, 30))
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        announcements_div = soup.find('div', class_='announcement-list')
        if not announcements_div:
            print("No announcement list found.")
            return []
            
        items = announcements_div.find_all('div', class_='media')
        print(f"Found {len(items)} announcements.")
        
        data = []
        
        for item in items:
            try:
                # Extract Announcement Date
                date_elem = item.find('small', class_='text-muted')
                announcement_date = date_elem.get_text(strip=True) if date_elem else ""
                
                # Extract Body Text and Link
                body_div = item.find('div', class_='media-body')
                if not body_div:
                    continue
                    
                link_elem = body_div.find('a')
                if not link_elem:
                    continue
                    
                full_text = link_elem.get_text(strip=True)
                link = link_elem.get('href')
                if not link:
                    continue
                if not link.startswith('http'):
                    link = "https://merolagani.com" + link
                is_reserved_share = "nepalese citizens working abroad" in full_text.lower()
                
                # Parse text
                company, units, date_range = parse_ipo_text(full_text)

                entry = {
                    "company": company,
                    "units": units,
                    "date_range": date_range,
                    "announcement_date": announcement_date,
                    "full_text": full_text,
                    "url": link,
                    "is_reserved_share": is_reserved_share,
                    "reserved_for": "Nepalese citizens working abroad" if is_reserved_share else "",
                    "scraped_at": datetime.now().isoformat()
                }
                data.append(entry)
                
            except Exception as e:
                fallback_text = item.get_text(" ", strip=True)
                fallback_date_elem = item.find('small', class_='text-muted')
                fallback_date = fallback_date_elem.get_text(strip=True) if fallback_date_elem else ""
                fallback_company = extract_company_from_text(fallback_text) or fallback_text
                data.append({
                    "company": fallback_company,
                    "units": "",
                    "date_range": "",
                    "announcement_date": fallback_date,
                    "full_text": fallback_text,
                    "url": "",
                    "is_reserved_share": "nepalese citizens working abroad" in fallback_text.lower(),
                    "reserved_for": "Nepalese citizens working abroad" if "nepalese citizens working abroad" in fallback_text.lower() else "",
                    "scraped_at": datetime.now().isoformat(),
                    "parse_error": str(e),
                })
                print(f"Error parsing item: {e}")
                
        return data

    except Exception as e:
        print(f"Error occurred: {e}")
        return None

if __name__ == "__main__":
    from datetime import timedelta
    import os

    new_data = scrape_upcoming_ipo()
    output_file = "data/upcoming_ipo.json"
    history_file = "data/oldipo.json"
    os.makedirs("data", exist_ok=True)

    # 1. Load existing data
    existing_items = {}
    history_items = {}
    try:
        if os.path.exists(output_file):
            with open(output_file, "r", encoding='utf-8') as f:
                old_data = json.load(f)
                # Map by URL for easy lookup
                existing_items = {item.get('url'): item for item in old_data if item.get('url')}
    except Exception as e:
        print(f"Error loading existing data: {e}")

    try:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding='utf-8') as f:
                old_history = json.load(f)
                history_items = {item.get('url'): item for item in old_history if item.get('url')}
    except Exception as e:
        print(f"Error loading IPO history data: {e}")

    # 2. Add/Update with new data
    if new_data:
        for item in new_data:
            url = item.get('url')
            if url:
                # Update existing or add new
                existing_items[url] = item

    # 3. Split items:
    # - Keep recent items in upcoming_ipo.json (within last 10 days by scraped_at)
    # - Move older items into data/oldipo.json history archive
    now = datetime.now()
    cutoff_date = now - timedelta(days=10)
    
    final_data = []
    archived_data = []
    for item in existing_items.values():
        item = backfill_company_from_text(item)
        item = backfill_units_from_text(item)
        item = backfill_date_range_from_text(item)
        try:
            scraped_at = item.get('scraped_at')
            if scraped_at:
                item_date = datetime.fromisoformat(scraped_at)
                if item_date > cutoff_date:
                    final_data.append(item)
                else:
                    archived_data.append(item)
            else:
                # If no timestamp, keep it for now but add one
                item['scraped_at'] = now.isoformat()
                final_data.append(item)
        except (ValueError, TypeError):
            # If date parsing fails, keep it
            final_data.append(item)

    # Merge archived entries into history (dedupe by URL)
    for item in archived_data:
        url = item.get('url')
        if url:
            history_items[url] = item

    history_list = list(history_items.values())
    history_list.sort(key=lambda x: x.get('scraped_at', ''), reverse=True)

    # 4. Save results
    # Intentionally preserve the previous upcoming_ipo.json snapshot when
    # final_data is empty, so the last known upcoming IPO list remains available.
    if final_data:
        # Sort by scraped_at descending so newest are first
        final_data.sort(key=lambda x: x.get('scraped_at', ''), reverse=True)
        
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"Successfully processed {len(final_data)} upcoming items (New: {len(new_data) if new_data else 0}). Saved to {output_file}")
    else:
        print("No data to save.")

    with open(history_file, "w", encoding='utf-8') as f:
        json.dump(history_list, f, indent=4, ensure_ascii=False)
    print(f"Archived IPO history count: {len(history_list)}. Saved to {history_file}")
