
import requests
from bs4 import BeautifulSoup
import re
import json

def get_sector_wise_codes():
    url = "https://merolagani.com/CompanyList.aspx"
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # The structure is likely an accordion.
        # Based on markdown view: links to #collapse_X are headers.
        # The content is in the element with id collapse_X.
        
        sectors = {}
        
        # Find all elements that link to a collapse section
        # Trying a generic approach: look for 'a' tags with href starting with #collapse or matching pattern
        accordion_toggles = soup.find_all('a', href=re.compile(r'#collapse_\d+'))
        
        print(f"Found {len(accordion_toggles)} sector groupings.")
        
        for toggle in accordion_toggles:
            sector_name = toggle.get_text(strip=True)
            target_id = toggle['href'].replace('#', '')
            
            # Find the content div
            content_div = soup.find(id=target_id)
            
            if content_div:
                # Find the table in the content div
                table = content_div.find('table')
                companies = []
                
                if table:
                    rows = table.find_all('tr')
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 2:
                            symbol_link = cols[0].find('a')
                            symbol = symbol_link.get_text(strip=True) if symbol_link else cols[0].get_text(strip=True)
                            
                            # Company Name is usually in the second column
                            name = cols[1].get_text(strip=True)
                            # Clean up name (remove extra whitespace/newlines)
                            name = " ".join(name.split())
                            
                            if symbol and name:
                                companies.append({
                                    "symbol": symbol,
                                    "name": name
                                })
                else:
                    # Fallback to the old method if table is missing for some reason
                    company_links = content_div.find_all('a', href=re.compile(r'CompanyDetail\.aspx\?symbol='))
                    for link in company_links:
                        href = link['href']
                        match = re.search(r'symbol=([a-zA-Z0-9.]+)', href, re.IGNORECASE)
                        if match:
                            symbol = match.group(1)
                            companies.append({
                                "symbol": symbol,
                                "name": symbol # Fallback name to symbol
                            })

                if companies:
                    sectors[sector_name] = companies
                    print(f"Sector: {sector_name}, Count: {len(companies)}")
                
        return sectors

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

import os

if __name__ == "__main__":
    data = get_sector_wise_codes()
    if data:
        # Use absolute path relative to the script to find the project root's data directory
        # scripts/nepse-scraper/sectors.py -> scripts/nepse-scraper -> scripts -> root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.path.join(base_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        output_file = os.path.join(data_dir, "nepse_sector_wise_codes.json")
        
        with open(output_file, "w") as f:
            json.dump(data, f, indent=4)
        print(f"Successfully saved sector-wise codes to {output_file}")
