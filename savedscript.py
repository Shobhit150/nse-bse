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
    def __init__(self):
        self.nse_cutoff_qty = None
        self.bse_cutoff_qty = None
        self.nseRunning = True
        self.bseRunning = True

        self.scrapTime = 30

        self.nse_last_updated_ts = None
        self.bse_last_updated_ts = None

        self.nse_data = {}
        self.bse_data = {} 
        self.state_lock = Lock()
        
    def parse_int(self, val):
        return int(val.replace(",", "").replace('"', "").strip())

    def scrape_nse(self):
        URL = "https://www.nseindia.com/market-data/ofs-information"


        with sync_playwright() as p:
            t0 = time.time()
            context = p.chromium.launch_persistent_context(
                user_data_dir="browser_profile",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            print("Time here 1 : ", time.time() - t0)

            page = context.new_page()

            try:
                t = time.time()
                page.goto("https://www.nseindia.com", wait_until="domcontentloaded", timeout=60000)
                print("Time here 2 : ", time.time() - t)

                t = time.time()
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                print("Time here 3 : ", time.time() - t)

                t = time.time()
                page.click("text=Retail Category", timeout=15000)
                print("Time here 4 : ", time.time() - t)

                while self.nseRunning:
                    cycle_start = time.time()
                    
                    try:
                        page.click("a[onclick=\"refreshApi('loadOfsRetail')\"]")
                                            
                        page.wait_for_timeout(700)


    
                        with self.state_lock:
                            self.nse_last_updated_ts = time.time()

                        print(page.querySelectorAll("#ofsRetailTable tbody tr:nth-child(2) table tbody tr"))

                        temp_data = page.evaluate("""() => {
                            const data = {};
                            const rows = document.querySelectorAll("#ofsRetailTable tbody tr:nth-child(2) table tbody tr");
                            
                            rows.forEach(row => {
                                const cells = row.querySelectorAll("td");
                                
                                    const price = cells[0].innerHTML;
                                    const qty = cells[2].innerHTML;
                                    data[price] = qty;
                                                  
                                                  price = float(c[0].inner_text().strip())
                                                qty = self.parse_int(c[2].inner_text())
                            });
                            
                            return data;
                        }""")

                        with self.state_lock:
                            self.nse_data = temp_data

                        elapsed = time.time() - cycle_start
                        print("Time here 10 : ", elapsed)
                        print(temp_data)
                        

                    except Exception:
                        print("NSE cycle failed")

                    sleep_time = max(0, self.scrapTime - (time.time() - cycle_start))
                    time.sleep(sleep_time)

            finally:
                context.close()

   
    def run_both(self):
        threading.Thread(target=self.scrape_nse, daemon=True).start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.nseRunning = False
            print("Stopped")


if __name__ == "__main__":
    OFSScraper().run_both()