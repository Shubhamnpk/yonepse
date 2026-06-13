import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def merge_brokers():
    nepse_path = os.path.join(ROOT, 'data', 'other', 'brokers.json')
    sharehub_path = os.path.join(ROOT, 'data', 'sharehub_brokers.json')

    nepse_data = load_json(nepse_path)
    sharehub_data = load_json(sharehub_path)

    if not nepse_data or not isinstance(nepse_data, list):
        print("Error: NEPSE broker data not found or invalid.")
        return False

    enrichment = {}
    if sharehub_data and isinstance(sharehub_data, dict):
        enrichment = sharehub_data.get('enrichment', {})
        print(f"Loaded enrichment for {len(enrichment)} brokers from ShareHub.")
    else:
        print("Warning: No ShareHub enrichment data found.")

    merged = []
    for broker in nepse_data:
        code = str(broker.get('memberCode', ''))
        enrich = enrichment.get(code, {})

        provinces = broker.get('provinces')
        if isinstance(provinces, list):
            provinces = provinces[0] if provinces else None
        if provinces and isinstance(provinces, str) and provinces.startswith('Province '):
            provinces = provinces.replace('Province ', '')

        merged_broker = {
            "id": broker.get("id"),
            "memberCode": broker.get("memberCode"),
            "memberName": broker.get("memberName"),
            "membershipType": broker.get("membershipType"),
            "phone": broker.get("phone"),
            "provinces": provinces,
            "districts": broker.get("districts", []),
            "tmsLink": broker.get("tmsLink"),
            "branchCount": broker.get("branchCount", 0),
            "activeStatus": broker.get("activeStatus"),
            "isDealer": broker.get("isDealer"),
            "imageUrl": enrich.get("imageUrl"),
            "rating": enrich.get("rating"),
            "thirtyDaysTurnover": enrich.get("thirtyDaysTurnover"),
            "latestTurnover": enrich.get("latestTurnover"),
            "todayStats": enrich.get("todayStats"),
        }
        merged.append(merged_broker)

    save_json(nepse_path, merged)
    print(f"Merged enrichment into {nepse_path} ({len(merged)} brokers)")
    return True

if __name__ == "__main__":
    print("Merging ShareHub enrichment into NEPSE broker data...")
    merge_brokers()
