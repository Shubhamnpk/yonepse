import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

def scrape_sharehub_brokers():
    url = "https://sharehubnepal.com/broker/dashboard"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    print(f"Fetching {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching ShareHub broker dashboard: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    
    print("Extracting React Server Components payload...")
    rsc_payload = ""
    script_count = 0
    for script in soup.find_all("script"):
        text = script.string
        if text and "self.__next_f.push" in text:
            start = text.find(',"')
            if start != -1:
                start += 2
                end = text.rfind('"]')
                if end != -1:
                    js_str = text[start:end]
                    unescaped = js_str.replace('\\"', '"').replace('\\\\', '\\').replace('\\/', '/').replace('\\n', '\n').replace('\\t', '\t')
                    rsc_payload += unescaped
                    script_count += 1
                    
    print(f"Extracted payload from {script_count} scripts. Total length: {len(rsc_payload)} characters.")
    
    if not rsc_payload:
        print("Error: Could not extract RSC payload from the page.")
        return None

    rsc_payload_cleaned = rsc_payload.replace('\t', '\\t')

    top_brokers_data = {}
    top_brokers_meta = {}
    top_brokers_match = re.search(r'"topBrokers"\s*:\s*\{', rsc_payload_cleaned)
    if top_brokers_match:
        start_idx = top_brokers_match.end() - 1
        bracket_count = 0
        end_idx = start_idx
        while end_idx < len(rsc_payload_cleaned):
            char = rsc_payload_cleaned[end_idx]
            if char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count == 0:
                    top_brokers_str = rsc_payload_cleaned[start_idx:end_idx+1]
                    try:
                        parsed_top = json.loads(top_brokers_str)
                        top_brokers_meta = {
                            "date": parsed_top.get("date"),
                            "totalAmount": parsed_top.get("totalAmount"),
                            "totalQuantity": parsed_top.get("totalQuantity"),
                            "totalTransactions": parsed_top.get("totalTransactions")
                        }
                        for item in parsed_top.get("brokerSummaryData", []):
                            b_id = item.get("brokerId")
                            if b_id:
                                top_brokers_data[str(b_id)] = item
                        print(f"Parsed {len(top_brokers_data)} daily active brokers from topBrokers.")
                    except Exception as e:
                        print(f"Error parsing topBrokers JSON: {e}")
                    break
            end_idx += 1
    else:
        print("Warning: 'topBrokers' list not found in payload.")

    brokers_list = []
    brokers_match = re.search(r'"brokers"\s*:\s*\[', rsc_payload_cleaned)
    if brokers_match:
        start_idx = brokers_match.end() - 1
        bracket_count = 0
        end_idx = start_idx
        while end_idx < len(rsc_payload_cleaned):
            char = rsc_payload_cleaned[end_idx]
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    brokers_list_str = rsc_payload_cleaned[start_idx:end_idx+1]
                    try:
                        brokers_list = json.loads(brokers_list_str)
                        print(f"Parsed {len(brokers_list)} global brokers with rating details.")
                    except Exception as e:
                        print(f"Error parsing brokers list JSON: {e}")
                    break
            end_idx += 1
    else:
        print("Warning: 'brokers' list not found in payload.")

    if not brokers_list:
        print("Error: Could not retrieve global brokers list.")
        return None

    enrichment = {}
    for broker in brokers_list:
        code = str(broker.get("code"))
        
        entry = {
            "imageUrl": f"https://cdn.arthakendra.com/{broker.get('imageUrl')}" if broker.get("imageUrl") and not broker.get("imageUrl").startswith("http") else broker.get("imageUrl"),
            "rating": {
                "averageRating": broker.get("averageRating"),
                "totalRatings": broker.get("totalRatings"),
                "averageShareTransferDays": broker.get("averageShareTransferDays"),
                "averageCashDepositDays": broker.get("averageCashDepositDays")
            },
            "thirtyDaysTurnover": broker.get("thirtyDaysTurnover"),
            "latestTurnover": broker.get("latestTurnover"),
            "todayStats": None
        }
        
        if code in top_brokers_data:
            top_data = top_brokers_data[code]
            entry["todayStats"] = {
                "totalAmount": top_data.get("totalAmount"),
                "buyAmount": top_data.get("buyAmount"),
                "buyQuantity": top_data.get("buyQuantity"),
                "buyTransactions": top_data.get("buyTransactions"),
                "buyQuantityPercentage": top_data.get("buyQuantityPercentage"),
                "sellAmount": top_data.get("sellAmount"),
                "sellQuantity": top_data.get("sellQuantity"),
                "sellTransactions": top_data.get("sellTransactions"),
                "sellQuantityPercentage": top_data.get("sellQuantityPercentage"),
                "matchingAmount": top_data.get("matchingAmount"),
                "matchingQuantity": top_data.get("matchingQuantity"),
                "matchingTransactions": top_data.get("matchingTransactions"),
                "averageBuyRate": top_data.get("averageBuyRate"),
                "averageSellRate": top_data.get("averageSellRate"),
                "topStock": top_data.get("topStock")
            }
            
        enrichment[code] = entry

    output_data = {
        "scrapedAt": datetime.now().isoformat(),
        "marketSummaryToday": {
            "date": top_brokers_meta.get("date"),
            "totalAmount": top_brokers_meta.get("totalAmount"),
            "totalQuantity": top_brokers_meta.get("totalQuantity"),
            "totalTransactions": top_brokers_meta.get("totalTransactions")
        },
        "enrichment": enrichment
    }

    return output_data

def save_data(data):
    if not data:
        print("No data to save.")
        return
        
    os.makedirs('data', exist_ok=True)
    
    file_path = 'data/sharehub_brokers.json'
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully saved enrichment data to {file_path}")
    print(f"Enriched brokers: {len(data['enrichment'])}")

if __name__ == "__main__":
    print("Starting ShareHub Nepal Broker Enrichment Scraper...")
    scraped_data = scrape_sharehub_brokers()
    save_data(scraped_data)
