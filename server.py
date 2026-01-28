import threading
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from nsebse import OFSScraper
import copy
import traceback

scraper = OFSScraper()
clients = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("🚀 Starting server...")
    
    scraper_thread = threading.Thread(
        target=scraper.run_both,
        daemon=True
    )
    scraper_thread.start()
    print("✅ Scraper thread started")

    broadcaster_task = asyncio.create_task(broadcaster())
    print("✅ Broadcaster task started")

    print("=" * 50)
    yield
    
    print("=" * 50)
    print("🛑 Server stopping...")
    scraper.nseRunning = False
    scraper.bseRunning = False
    broadcaster_task.cancel()
    print("=" * 50)

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
    client_id = id(ws)
    print(f"\n{'='*50}")
    print(f"➡️  NEW CONNECTION (ID: {client_id})")
    
    try:
        await ws.accept()
        print(f"✅ WebSocket ACCEPTED (ID: {client_id})")
        
        clients.add(ws)
        print(f"👥 Total clients: {len(clients)}")
        
        with scraper.state_lock:
            nse = dict(scraper.nse_data)
            bse = dict(scraper.bse_data)
        
        merged = merge_price_qty(nse, bse)
        if merged:
            payload = [
                {"price": p, "qty": q}
                for p, q in sorted(merged.items())
            ]
            print(f"📤 Sending initial data to new client: {len(payload)} items")
            try:
                await ws.send_json(payload)
                print(f"✅ Initial data sent successfully")
            except Exception as e:
                print(f"❌ Failed to send initial data: {e}")
        else:
            print("⚠️  No initial data to send (scraper has no data yet)")
        
        print(f"{'='*50}\n")
        
        while True:
            await asyncio.sleep(10)
            await ws.send_json({"type": "ping"})
                
    except WebSocketDisconnect:
        print(f"\n❌ CLIENT DISCONNECTED (ID: {client_id})")
    except Exception as e:
        print(f"\n❌ ERROR in WebSocket (ID: {client_id}): {e}")
        traceback.print_exc()
    finally:
        clients.discard(ws)
        print(f"🔌 Client removed. Remaining: {len(clients)}\n")


def merge_price_qty(nse, bse):
    prices = set(nse) | set(bse)
    return {
        p: nse.get(p, 0) + bse.get(p, 0)
        for p in prices
    }

async def broadcaster():
    last_sent = None
    iteration = 0
    print("\n📡 BROADCASTER STARTED\n")

    while True:
        try:
            iteration += 1
            
            with scraper.state_lock:
                nse = copy.deepcopy(scraper.nse_data)
                bse = copy.deepcopy(scraper.bse_data)

            merged = merge_price_qty(nse, bse)

            if iteration % 20 == 0:
                print(f"📊 Stats: NSE={len(nse)}, BSE={len(bse)}, Merged={len(merged)}, Clients={len(clients)}")

            if merged and merged != last_sent:
                payload = [
                    {"price": p, "qty": q}
                    for p, q in sorted(merged.items())
                ]

                print(f"\n📤 BROADCASTING:")
                print(f"   Items: {len(payload)}")
                print(f"   Clients: {len(clients)}")
                
                if len(payload) <= 5:  # Show sample if small
                    print(f"   Sample: {payload}")

                disconnected = set()
                for ws in list(clients):
                    try:
                        await ws.send_json(payload)
                    except Exception as e:
                        print(f"   ❌ Failed to send to client: {e}")
                        disconnected.add(ws)

                clients.difference_update(disconnected)
                if disconnected:
                    print(f"   🗑️  Removed {len(disconnected)} disconnected clients")

                last_sent = copy.deepcopy(merged)
                print()

            await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            print("📡 Broadcaster cancelled")
            break
        except Exception as e:
            print(f"❌ Broadcaster error: {e}")
            traceback.print_exc()
            await asyncio.sleep(1)