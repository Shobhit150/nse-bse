import threading
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from nsebse import OFSScraper
import copy
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S"
)

logger = logging.getLogger("WS")

scraper = OFSScraper()
clients = set()
clients_needing_snapshot = set()

ISSUE_SIZE = 4_757_707
FLOOR_PRICE = 685

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    scraper_thread = threading.Thread(
        target=scraper.run_both,
        daemon=True
    )
    scraper_thread.start()

    broadcaster_task = asyncio.create_task(broadcaster())
    yield
    


    scraper.nseRunning = False
    scraper.bseRunning = False
    broadcaster_task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "running", "clients": len(clients)}

@app.get("/health")
async def health():
    with scraper.state_lock:
        nse_count = len(scraper.nse_data)
        bse_count = len(scraper.bse_data)
    
    return {
        "status": "ok",
        "clients": len(clients),
        "nse_data_count": nse_count,
        "bse_data_count": bse_count
    }

@app.websocket("/ws/nse")
async def nse_ws(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    clients_needing_snapshot.add(ws)
    print(f"✅ Client connected: {id(ws)}")

    try:
        while True:
            await asyncio.sleep(3600)
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)
        clients_needing_snapshot.discard(ws)
        print(f"🧹 Client removed: {id(ws)}")


def is_live(fetch_ts, max_age=120):
    return fetch_ts is not None and (time.time() - fetch_ts) <= max_age

def merge_price_qty(nse, bse):
    prices = set(nse) | set(bse)
    merged = {
        p: nse.get(p, 0) + bse.get(p, 0)
        for p in prices
    }
    nse_floor_for_retail = scraper.nse_cutoff_qty or 0
    bse_floor_for_retail = scraper.bse_cutoff_qty or 0
    floor_qty = nse_floor_for_retail + bse_floor_for_retail
    if(floor_qty>0):
        merged[FLOOR_PRICE] = merged.get(FLOOR_PRICE, 0) + floor_qty
    return merged

def cumulative_high_to_low(merged: dict, issue_size: int):
    cumulative = 0
    result = []
    cutoff_price = None

    for price in sorted(merged.keys(), reverse=True):
        cumulative += merged[price]
        result.append({
            "price": price,
            "qty": merged[price],
            "cumulative_qty": cumulative
        })

        if cutoff_price is None and cumulative >= issue_size:
            cutoff_price = price

    return result, cutoff_price

def subscription_metrics(cumulative, issue_size):
    if not cumulative:
        return {
            "total_demand": 0,
            "subscription_pct": 0.0,
            "remaining_qty": issue_size,
            "oversubscribed": False,
            "top_price": None
        }

    total_demand = cumulative[-1]["cumulative_qty"]
    subscription_pct = round((total_demand / issue_size) * 100, 2)

    return {
        "total_demand": total_demand,
        "subscription_pct": subscription_pct,
        "remaining_qty": max(0, issue_size - total_demand),
        "oversubscribed": total_demand >= issue_size,
        "top_price": cumulative[0]["price"]
    }

async def broadcaster():
    logger.info("Broadcaster loop started")
    last_sent = None
    tick = 0

    while True:
        try:
            tick += 1

            with scraper.state_lock:
                nse = copy.deepcopy(scraper.nse_data)
                bse = copy.deepcopy(scraper.bse_data)

                nse_last_updated_ts = scraper.nse_last_updated_ts
                bse_last_updated_ts = scraper.bse_last_updated_ts

            if tick % 10 == 0:
                logger.info(
                    "State snapshot | nse=%d | bse=%d | clients=%d",
                    len(nse),
                    len(bse),
                    len(clients)
                )

            merged = merge_price_qty(nse, bse)

            if not merged:
                logger.debug("No merged data yet, skipping broadcast")
                await asyncio.sleep(0.5)
                continue

            cumulative, cutoff_price = cumulative_high_to_low(
                merged, ISSUE_SIZE
            )

            metrics = subscription_metrics(cumulative, ISSUE_SIZE)

            payload = {
                "data": cumulative,
                "meta": {
                    "cutoff_price": cutoff_price,
                    "total_demand": metrics["total_demand"],
                    "subscription_pct": metrics["subscription_pct"],
                    "remaining_qty": metrics["remaining_qty"],
                    "oversubscribed": metrics["oversubscribed"],
                    "top_price": metrics["top_price"],
                    "issue_size": ISSUE_SIZE,
                    "bse_last_updated_ts": bse_last_updated_ts,
                    "nse_last_updated_ts": nse_last_updated_ts
                }
            }

            sent = 0
            skipped = 0
            dead = set()

            for ws in list(clients):
                try:
                    if cumulative != last_sent or ws in clients_needing_snapshot:
                        await ws.send_json(payload)
                        clients_needing_snapshot.discard(ws)
                        sent += 1
                    else:
                        skipped += 1

                except (WebSocketDisconnect, RuntimeError):
                    dead.add(ws)

            if dead:
                clients.difference_update(dead)
                clients_needing_snapshot.difference_update(dead)
                logger.warning("Removed %d dead clients", len(dead))

            if sent > 0:
                logger.info(
                    "Broadcast sent | sent=%d | skipped=%d | cutoff=%s",
                    sent,
                    skipped,
                    cutoff_price
                )

            last_sent = copy.deepcopy(cumulative)
            await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            logger.info("Broadcaster cancelled")
            break
        except Exception:
            logger.exception("Broadcaster error")
            await asyncio.sleep(1)
