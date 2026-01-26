from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
app = FastAPI()

@app.websocket("/ws")
async def server(ws: WebSocket):
    count = 0
    await ws.accept()

    try :
        while True:
            await ws.send_text(str(count))
            count += 1
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("client disconnected")

