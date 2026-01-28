import os
import json
import csv
from datetime import datetime
from playwright.sync_api import sync_playwright

URL = "https://www.nseindia.com/market-data/ofs-information"
SAVE_DIR = "data/nse"

os.makedirs(SAVE_DIR, exist_ok=True)

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir="browser_profile",
        headless=False,
        viewport={"width": 1280, "height": 800},
        args=["--disable-blink-features=AutomationControlled"]
    )

    page = context.new_page()

    print("Opening NSE homepage...")
    page.goto("https://www.nseindia.com", timeout=60000)
    page.wait_for_timeout(3000)

    print("Opening OFS page...")
    page.goto(URL, timeout=60000)
    page.wait_for_timeout(5000)

    print("Clicking General Category...")
    page.click("text=General Category", timeout=15000)
    page.wait_for_timeout(2000)

    print("Clicking Refresh...")
    page.click("a[onclick=\"refreshApi('loadOfsGeneral')\"]", timeout=15000)

    print("Waiting for table data...")
    try:
        page.wait_for_selector("#ofsGeneralTable tbody tr", timeout=30000)
        page.wait_for_timeout(3000)
        row_count = page.locator("#ofsGeneralTable tbody tr").count()
        print(f"Found {row_count} rows in table")
    except Exception as e:
        print(f"Warning: Table selector wait failed: {e}")
        page.wait_for_timeout(10000)

    # ✅ EXTRACT DATA
    print("\n--- Extracting OFS Data ---")
    
    # Get timestamp
    timestamp_elem = page.query_selector(".asondate span")
    data_timestamp = timestamp_elem.inner_text().strip() if timestamp_elem else "Unknown"
    
    ofs_data = {
        "timestamp": data_timestamp,
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "companies": []
    }
    
    # Get all rows (both main and detail rows)
    all_rows = page.query_selector_all("#ofsGeneralTable tbody tr")
    
    i = 0
    while i < len(all_rows):
        row = all_rows[i]
        
        # Check if this is a main row (has class accordActive)
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
                
                # Check if next row is the detail row (has accordTD class)
                if i + 1 < len(all_rows):
                    next_row = all_rows[i + 1]
                    detail_td = next_row.query_selector("td.accordTD")
                    
                    if detail_td:
                        # Find the nested table inside this detail row
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
                        
                        # Skip the detail row in next iteration
                        i += 1
                
                ofs_data["companies"].append(company_data)
                print(f"✓ {company_data['company_name']} - {len(company_data['bid_details'])} bid details")
        
        i += 1

    # ✅ SAVE AS JSON
    timestamp_file = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    json_filename = f"{SAVE_DIR}/ofs_data_{timestamp_file}.json"
    
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(ofs_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ JSON saved to: {json_filename}")
    
    # ✅ SAVE SUMMARY CSV (main data)
    csv_filename = f"{SAVE_DIR}/ofs_summary_{timestamp_file}.csv"
    
    with open(csv_filename, "w", encoding="utf-8") as f:
        f.write("Company,LTP,Floor Price,Indicative Price,Base Issue Size,Total Issue Size,")
        f.write("Cumulative 100%,Cumulative 0%,Total Qty,Times Base,Times Total,NSE Demand\n")
        
        for company in ofs_data["companies"]:
            f.write(f'"{company["company_name"]}",')
            f.write(f'{company["ltp"]},{company["floor_price"]},{company["indicative_price"]},')
            f.write(f'{company["base_issue_size"]},{company["total_issue_size"]},')
            f.write(f'{company["cumulative_qty_100pc"]},{company["cumulative_qty_0pc"]},')
            f.write(f'{company["total_qty"]},{company["times_base"]},{company["times_total"]},')
            f.write(f'{company["nse_demand"]}\n')
    
    print(f"✅ Summary CSV saved to: {csv_filename}")
    
    # ✅ SAVE BID DETAILS CSV (all bid details for all companies)
    bid_csv_filename = f"{SAVE_DIR}/ofs_bid_details_{timestamp_file}.csv"
    
    with open(bid_csv_filename, "w", encoding="utf-8", newline='') as f:
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
    
    print(f"✅ Bid Details CSV saved to: {bid_csv_filename}")
    print(f"\nTotal companies scraped: {len(ofs_data['companies'])}")
    
    for company in ofs_data["companies"]:
        print(f"  • {company['company_name']}: {len(company['bid_details'])} price intervals")
    
    page.wait_for_timeout(5000)
    context.close()