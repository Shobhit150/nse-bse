import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import threading
import csv



class OFSScraper:
    """Unified OFS data scraper for NSE and BSE"""
    
    def __init__(self, save_dir="data"):
        self.bseRunning = True
        self.nseRunning = True

        self.save_dir = save_dir
        self.nse_dir = os.path.join(save_dir, "nse")
        self.bse_dir = os.path.join(save_dir, "bse")
        
        os.makedirs(self.nse_dir, exist_ok=True)
        os.makedirs(self.bse_dir, exist_ok=True)
    
    def scrape_nse(self):
        URL = "https://www.nseindia.com/market-data/ofs-information"
        SAVE_DIR = "data/nse"
        with sync_playwright() as p:
            
            context = p.chromium.launch_persistent_context(
                user_data_dir="browser_profile",
                headless=False, 
                viewport={"width": 1920, "height": 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials"
                ]
            )
            
            page = context.new_page()
            
            
            page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            })
            
            try:
                print("📡 Connecting to NSE...")
                
               
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        page.goto("https://www.nseindia.com", 
                                wait_until="domcontentloaded", 
                                timeout=60000)
                        print("✓ Homepage loaded")
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            print(f"⚠️  Attempt {attempt + 1} failed, retrying...")
                            time.sleep(2)
                        else:
                            raise e
                
                page.wait_for_timeout(5000)  
                
               
                print("🔄 Loading OFS page...")
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)
                
               
                print("📊 Opening General Category...")
                page.click("text=General Category", timeout=15000)
                page.wait_for_timeout(3000)
                
               
                print("🔄 Refreshing data...")
                while self.bseRunning :
                    page.click("a[onclick=\"refreshApi('loadOfsGeneral')\"]", timeout=15000)
                    
                   
                    print("⏳ Waiting for data to load...")
                    page.wait_for_selector("#ofsGeneralTable tbody tr", timeout=30000)
                    page.wait_for_timeout(3000)
                    
                    
                    timestamp_elem = page.query_selector(".asondate span")
                    data_timestamp = timestamp_elem.inner_text().strip() if timestamp_elem else "Unknown"
                    
                    print(f"📅 Data timestamp: {data_timestamp}")
                    
                    ofs_data = {
                        "timestamp": data_timestamp,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "companies": []
                    }
                    
                    
                    all_rows = page.query_selector_all("#ofsGeneralTable tbody tr")
                    
                    i = 0
                    while i < len(all_rows):
                        row = all_rows[i]
                        
                        if "accordActive" in row.get_attribute("class"):
                            cells = row.query_selector_all("td")
                            
                            if len(cells) > 1:
                                company_data = {
                                    "company_name": cells[1].inner_text().strip(),
                                    "ltp": cells[2].inner_text().strip(),
                                    "floor_price": cells[3].inner_text().strip(),
                                    "indicative_price": cells[4].inner_text().strip(),
                                    "base_issue_size": cells[5].inner_text().strip(),
                                    "total_issue_size": cells[6].inner_text().strip(),
                                    "cumulative_qty_100pc": cells[7].inner_text().strip(),
                                    "cumulative_qty_0pc": cells[8].inner_text().strip(),
                                    "total_qty": cells[9].inner_text().strip(),
                                    "times_base": cells[10].inner_text().strip(),
                                    "times_total": cells[11].inner_text().strip(),
                                    "nse_demand": cells[12].inner_text().strip(),
                                    "bid_details": []
                                }
                                
                                if i + 1 < len(all_rows):
                                    next_row = all_rows[i + 1]
                                    detail_td = next_row.query_selector("td.accordTD")
                                    
                                    if detail_td:
                                        detail_table = detail_td.query_selector("table tbody")
                                        
                                        if detail_table:
                                            detail_rows = detail_table.query_selector_all("tr")
                                            
                                            for detail_row in detail_rows:
                                                detail_cells = detail_row.query_selector_all("td")
                                                
                                                if len(detail_cells) >= 8:
                                                    bid_detail = {
                                                        "price_interval": detail_cells[0].inner_text().strip(),
                                                        "no_of_bids": detail_cells[1].inner_text().strip(),
                                                        "qty_confirmed": detail_cells[2].inner_text().strip(),
                                                        "qty_yet_to_confirm": detail_cells[3].inner_text().strip(),
                                                        "qty_total": detail_cells[4].inner_text().strip(),
                                                        "cumulative_confirmed": detail_cells[5].inner_text().strip(),
                                                        "cumulative_yet_to_confirm": detail_cells[6].inner_text().strip(),
                                                        "cumulative_total": detail_cells[7].inner_text().strip()
                                                    }
                                                    company_data["bid_details"].append(bid_detail)
                                        
                                        i += 1
                                
                                ofs_data["companies"].append(company_data)
                                print(f"  ✓ {company_data['company_name']}: {len(company_data['bid_details'])} bids")
                        
                        i += 1
                    
                    # Save files with FIXED NAMES for easy access
                    timestamp_file = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    
                    # JSON - both timestamped and latest
                    # json_filename = f"{SAVE_DIR}/ofs_data_{timestamp_file}.json"
                    # json_latest = f"{SAVE_DIR}/ofs_data_latest.json"
                    
                    # with open(json_filename, "w", encoding="utf-8") as f:
                    #     json.dump(ofs_data, f, indent=2, ensure_ascii=False)
                    # with open(json_latest, "w", encoding="utf-8") as f:
                    #     json.dump(ofs_data, f, indent=2, ensure_ascii=False)
                    
                    # Summary CSV
                    # csv_filename = f"{SAVE_DIR}/ofs_summary_{timestamp_file}.csv"
                    # csv_latest = f"{SAVE_DIR}/ofs_summary_latest.csv"
                    
                    # for filename in [csv_filename, csv_latest]:
                    #     with open(filename, "w", encoding="utf-8") as f:
                    #         f.write("Company,LTP,Floor Price,Indicative Price,Base Issue Size,Total Issue Size,")
                    #         f.write("Cumulative 100%,Cumulative 0%,Total Qty,Times Base,Times Total,NSE Demand\n")
                            
                    #         for company in ofs_data["companies"]:
                    #             f.write(f'"{company["company_name"]}",')
                    #             f.write(f'{company["ltp"]},{company["floor_price"]},{company["indicative_price"]},')
                    #             f.write(f'{company["base_issue_size"]},{company["total_issue_size"]},')
                    #             f.write(f'{company["cumulative_qty_100pc"]},{company["cumulative_qty_0pc"]},')
                    #             f.write(f'{company["total_qty"]},{company["times_base"]},{company["times_total"]},')
                    #             f.write(f'{company["nse_demand"]}\n')
                    
                    # Bid Details CSV
                    bid_csv_filename = f"{SAVE_DIR}/ofs_bid_details_{timestamp_file}.csv"
                    bid_csv_latest = f"{SAVE_DIR}/ofs_bid_details_latest.csv"
                    
                    for filename in [bid_csv_filename, bid_csv_latest]:
                        with open(filename, "w", encoding="utf-8", newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow([
                                "Company", "Price Interval", "No. of Bids",
                                "Qty Confirmed", "Qty Yet to Confirm", "Qty Total",
                                "Cumulative Confirmed", "Cumulative Yet to Confirm", "Cumulative Total"
                            ])
                            
                            for company in ofs_data["companies"]:
                                for bid in company["bid_details"]:
                                    writer.writerow([
                                        company["company_name"],
                                        bid["price_interval"],
                                        bid["no_of_bids"],
                                        bid["qty_confirmed"],
                                        bid["qty_yet_to_confirm"],
                                        bid["qty_total"],
                                        bid["cumulative_confirmed"],
                                        bid["cumulative_yet_to_confirm"],
                                        bid["cumulative_total"]
                                    ])
                    
                    print(f"\n✅ Files saved:")
                    # print(f"   📄 {json_latest} (latest)")
                    # print(f"   📊 {csv_latest} (latest)")
                    print(f"   📈 {bid_csv_latest} (latest)")
                    print(f"\n💼 Scraped {len(ofs_data['companies'])} companies")
                    time.sleep(60)
                
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
                return False
                
            finally:
                page.wait_for_timeout(2000)
                context.close()

    
    
    def scrape_bse(self, scripcode="500188"):
        save_dir="data/bse"
        url = "https://www.bseindia.com/markets/PublicIssues/BSEBidDetails_ofs.aspx?flag=NR&Scripcode=500188"
        print(f"📡 Fetching: {url}")
    
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            while self.bseRunning:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                domain = url.split('/')[2].replace('www.', '')
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

                csv_filename = f"{save_dir}/{domain}_{timestamp}.csv"
                

                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                table = soup.find('table', {'cellpadding': '4', 'cellspacing': '1'})
                
                if table:
                    with open(csv_filename, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.writer(f)
                        
                        # Extract all rows
                        rows = table.find_all('tr')
                        
                        for row in rows:
                            cells = row.find_all('td')
                            row_data = [cell.get_text(strip=True) for cell in cells]
                            if row_data: 
                                writer.writerow(row_data)
                    
                    print(f"✅ Saved CSV: {csv_filename}")
                else:
                    print("⚠️  Table not found")  

                time.sleep(60) 
            
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return None, None
    def run_both(self):
        nse_thread = threading.Thread(
            target=self.scrape_nse,
            daemon=True
        )

        bse_thread = threading.Thread(
            target=self.scrape_bse,
            daemon=True
        )

        nse_thread.start()
        bse_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping all scrapers...")
            self.nseRunning = False
            self.bseRunning = False

        

        


if __name__ == "__main__":
    
    scraper = OFSScraper(save_dir="data")
    
    
    # scraper.run_continuous(interval=20, bse_scripcode="500188")
    # scraper.scrape_nse()
    scraper.run_both()
