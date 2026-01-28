import os
import time
import csv
import threading
import requests
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from threading import Lock


class OFSScraper:
    def __init__(self, save_dir="data"):
        self.nseRunning = True
        self.bseRunning = True

        self.save_dir = save_dir
        self.nse_dir = os.path.join(save_dir, "nse")
        self.bse_dir = os.path.join(save_dir, "bse")

        os.makedirs(self.nse_dir, exist_ok=True)
        os.makedirs(self.bse_dir, exist_ok=True)

        self.nse_data = {}
        self.bse_data = {} 
        self.state_lock = Lock()


        
    def parse_int(self, val):
        return int(val.replace(",", "").replace('"', "").strip())



    def scrape_nse(self):
        URL = "https://www.nseindia.com/market-data/ofs-information"

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir="browser_profile",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )

            page = context.new_page()

            try:
                page.goto("https://www.nseindia.com", wait_until="domcontentloaded", timeout=60000)
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                page.click("text=General Category", timeout=15000)

                while self.nseRunning:
                    cycle_start = time.time()
                    temp_data = {}

                    page.click("a[onclick=\"refreshApi('loadOfsGeneral')\"]")
                    page.wait_for_timeout(1000)
                    page.wait_for_selector("#ofsGeneralTable tbody tr", timeout=30000)

                    rows = page.query_selector_all("#ofsGeneralTable tbody tr")
                    i = 0
                    print("1",time.time() - cycle_start)

                    while i < len(rows):
                        row = rows[i]
                        if "accordActive" in (row.get_attribute("class") or ""):
                            if i + 1 < len(rows):
                                table = rows[i + 1].query_selector("table tbody")
                                if table:
                                    for r in table.query_selector_all("tr"):
                                        try:
                                            c = r.query_selector_all("td")
                                            price = float(c[0].inner_text().strip())
                                            qty = self.parse_int(c[2].inner_text())
                                            temp_data[price] = qty
                                        except:
                                            continue
                                i += 2
                                continue
                        i += 1

                    
                    with self.state_lock:
                        self.nse_data = temp_data

                    elapsed = time.time() - cycle_start
                    time.sleep(max(0, 30 - elapsed))

            finally:
                context.close()


    def scrape_bse(self, scripcode="500188"):
        url = f"https://www.bseindia.com/markets/PublicIssues/BSEBidDetails_ofs.aspx?flag=NR&Scripcode={scripcode}"

        headers = {"User-Agent": "Mozilla/5.0"}

        while self.bseRunning:
            cycle_start = time.time()
            temp_data = []

            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                table = soup.find("table", {"cellpadding": "4", "cellspacing": "1"})
                if not table:
                    time.sleep(60)
                    continue
                temp_state = {}
                ts = time.time()

                for row in table.find_all("tr"):
                    try:
                        cells = row.find_all("td")
                        price = float(cells[0].get_text(strip=True))
                        qty = self.parse_int(cells[2].get_text())
                        temp_state[price] = qty
                    except:
                        continue

                with self.state_lock:
                    self.bse_data = temp_state


            except Exception as e:
                print("BSE error:", e)

            elapsed = time.time() - cycle_start
            
            time.sleep(max(0, 60 - elapsed))


    def run_both(self):
        threading.Thread(target=self.scrape_nse, daemon=True).start()
        threading.Thread(target=self.scrape_bse, daemon=True).start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.nseRunning = False
            self.bseRunning = False
            print("Stopped")


if __name__ == "__main__":
    OFSScraper().run_both()