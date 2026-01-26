from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import httpx
from services.scrap import scrap_page
app = FastAPI()

client = httpx.AsyncClient(timeout=10)

@app.websocket("/ws")
async def server(ws: WebSocket):
    
    await ws.accept()

    try :
        while True:
            res = await scrap_page("https://www.bseindia.com/markets/PublicIssues/OFSIssuse_new.aspx?expandable=0", client)
            await asyncio.sleep(5)

    except WebSocketDisconnect:
        print("client disconnected")

