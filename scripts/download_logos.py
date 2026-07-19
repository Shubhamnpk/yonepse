import json
import os
import sys
import urllib.parse
import requests
import mimetypes

NEPSE_FILE_URL = "https://www.nepalstock.com.np/api/nots/security/fetchFiles?fileLocation="
LOGO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'assets', 'img', 'logos'
)
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data'
)
RELATIVE_LOGO_PATH = 'assets/img/logos'

# Symbols that contain '/' need to be mapped to a safe filename
# We store the safe filename in the JSON but keep the original symbol
SAFE_SYMBOL_MAP = {}


def safe_filename(symbol, ext):
    safe = symbol.replace('/', '_')
    SAFE_SYMBOL_MAP[symbol] = safe
    return f"{safe}{ext}"


def build_file_url(file_path):
    if not file_path:
        return None
    file_path = str(file_path)
    if file_path.startswith('http://') or file_path.startswith('https://'):
        return file_path
    encoded = urllib.parse.quote(file_path, safe='/%')
    return NEPSE_FILE_URL + encoded


def extension_for_content_type(content_type, url):
    if not content_type:
        _, ext = os.path.splitext(url.split('?')[0])
        return ext if ext else '.jpg'
    mapping = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/svg+xml': '.svg',
        'image/bmp': '.bmp',
    }
    for ct, ext in mapping.items():
        if ct in content_type:
            return ext
    return '.jpg'


def main():
    profiles_path = os.path.join(DATA_DIR, 'company', 'profiles.json')
    securities_path = os.path.join(DATA_DIR, 'other', 'securities.json')

    profiles = json.load(open(profiles_path, 'r', encoding='utf-8'))
    securities = json.load(open(securities_path, 'r', encoding='utf-8'))

    sec_by_symbol = {s['symbol']: s for s in securities if s.get('symbol')}

    candidates = [
        p for p in profiles
        if p.get('logo_path') and p.get('symbol') in sec_by_symbol
    ]

    print(f"Found {len(candidates)} securities with logo_path in profiles.json")
    os.makedirs(LOGO_DIR, exist_ok=True)

    downloaded = 0
    skipped = 0
    failed = 0
    updated_securities = 0

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    for profile in candidates:
        symbol = profile['symbol']
        logo_path = profile['logo_path']
        url = build_file_url(logo_path)

        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                print(f"  {symbol}: HTTP {resp.status_code}, skipping")
                skipped += 1
                continue

            content_type = resp.headers.get('Content-Type', '')
            if 'image' not in content_type:
                print(f"  {symbol}: not an image ({content_type}), skipping")
                skipped += 1
                continue

            ext = extension_for_content_type(content_type, logo_path)
            filename = safe_filename(symbol, ext)
            filepath = os.path.join(LOGO_DIR, filename)

            with open(filepath, 'wb') as f:
                f.write(resp.content)

            image_url = f"{RELATIVE_LOGO_PATH}/{filename}"
            sec_by_symbol[symbol]['imageUrl'] = image_url
            updated_securities += 1
            downloaded += 1

            if downloaded % 25 == 0:
                print(f"  Progress: {downloaded} downloaded, {failed} failed, {skipped} skipped")

        except Exception as e:
            print(f"  {symbol}: error - {e}")
            failed += 1

    print(f"\nDownload complete: {downloaded} images, {failed} failed, {skipped} skipped (non-image)")

    with open(securities_path, 'w', encoding='utf-8') as f:
        json.dump(securities, f, indent=4)
    print(f"Updated {securities_path}")

    print(f"\nTotal securities with imageUrl: {updated_securities}")
    print(f"Logos saved to: {LOGO_DIR}")


if __name__ == '__main__':
    main()
