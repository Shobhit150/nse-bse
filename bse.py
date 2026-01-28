import os
import csv
from datetime import datetime
import requests
from bs4 import BeautifulSoup

def save_html_and_csv(url, save_dir="data/html"):
    """
    Save HTML and extract table to CSV
    """
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"📡 Fetching: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        domain = url.split('/')[2].replace('www.', '')
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        csv_filename = f"{save_dir}/{domain}_{timestamp}.csv"
        

        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the data table (the one with bid details)
        table = soup.find('table', {'cellpadding': '4', 'cellspacing': '1'})
        
        if table:
            with open(csv_filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                
                # Extract all rows
                rows = table.find_all('tr')
                
                for row in rows:
                    cells = row.find_all('td')
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    if row_data:  # Only write non-empty rows
                        writer.writerow(row_data)
            
            print(f"✅ Saved CSV: {csv_filename}")
        else:
            print("⚠️  Table not found")
        
        return csv_filename
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

if __name__ == "__main__":
    print("\n🔹 Save BSE page and extract table")
    save_html_and_csv(
        "https://www.bseindia.com/markets/PublicIssues/BSEBidDetails_ofs.aspx?flag=NR&Scripcode=500188",
        save_dir="data/bse"
    )