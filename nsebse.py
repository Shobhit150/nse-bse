import os
import time
import csv
import threading
import requests
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from threading import Lock
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
    datefmt="%H:%M:%S"
)



logger = logging.getLogger("OFS")

class OFSScraper:
    def __init__(self):
        self.nse_cutoff_qty = None
        self.bse_cutoff_qty = None
        self.nseRunning = True
        self.bseRunning = True

        self.scrapTime = 10

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
            context = p.chromium.launch_persistent_context(
                user_data_dir="browser_profile",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )

            page = context.new_page()

            try:
                page.goto("https://www.nseindia.com", wait_until="domcontentloaded", timeout=60000)
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                page.click("text=Retail Category", timeout=15000)

                while self.nseRunning:
                    cycle_start = time.time()
                    temp_data = {}

                    logger.info("NSE cycle started")

                    try:
                        page.click("a[onclick=\"refreshApi('loadOfsRetail')\"]")
                        page.wait_for_timeout(1000)

                        page.wait_for_selector("#ofsRetailTable tbody tr", timeout=30000)

                        with self.state_lock:
                            self.nse_last_updated_ts = time.time()

                        rows = page.query_selector_all("#ofsRetailTable tbody tr")
                        i = 0

                        while i < len(rows):
                            row = rows[i]
                            if "accordActive" in (row.get_attribute("class") or ""):
                                if i + 1 < len(rows):
                                    table = rows[i + 1].query_selector("table tbody")
                                    if table:
                                        for r in table.query_selector_all("tr"):
                                            try:
                                                c = r.query_selector_all("td")
                                                raw_price = c[0].inner_text().strip()
                                                if raw_price.lower().startswith("cut"):
                                                    if self.nse_cutoff_qty is None:
                                                        with self.state_lock:
                                                            self.nse_cutoff_qty = self.parse_int(c[2].inner_text())
                                                    continue
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
                        logger.info(
                            "NSE cycle done | rows=%d | time=%.2fs",
                            len(temp_data),
                            elapsed
                        )

                    except Exception as e:
                        logger.exception("NSE cycle failed")

                    time.sleep(max(0, self.scrapTime - (time.time() - cycle_start)))

            finally:
                context.close()


    def scrape_bse(self, scripcode="500188"):
        url = f"https://www.bseindia.com/markets/PublicIssues/BSEBidDetails_ofs.aspx?flag=R&Scripcode={scripcode}"

        headers = {"User-Agent": "Mozilla/5.0"}

        while self.bseRunning:
            cycle_start = time.time()
            temp_state = {}

            logger.info("BSE cycle started")

            try:
                response = requests.get(url, headers=headers, timeout=30)

                with self.state_lock:
                    self.bse_last_updated_ts = time.time()

                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                table = soup.find("table", {"cellpadding": "4", "cellspacing": "1"})
                if not table:
                    logger.warning("BSE table not found")
                    time.sleep(60)
                    continue

                for row in table.find_all("tr"):
                    try:
                        cells = row.find_all("td")

                        raw_price = cells[0].get_text(strip=True)
                        if raw_price.lower().startswith("cut"):
                            if self.bse_cutoff_qty is None:
                                with self.state_lock:
                                    self.bse_cutoff_qty = self.parse_int(cells[2].get_text())
                            continue
                        price = float(raw_price)
                        qty = self.parse_int(cells[2].get_text())
                        temp_state[price] = qty
                    except:
                        continue

                with self.state_lock:
                    self.bse_data = temp_state
                     

                elapsed = time.time() - cycle_start
                logger.info(
                    "BSE cycle done | rows=%d | time=%.2fs",
                    len(temp_state),
                    elapsed
                )

            except Exception:
                logger.exception("BSE cycle failed")

            time.sleep(max(0, self.scrapTime - (time.time() - cycle_start)))


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