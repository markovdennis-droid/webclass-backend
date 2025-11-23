from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

origins = [
    "https://webclass-lx23.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms: dict[str, set[WebSocket]] = {}

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()

    if room_id not in rooms:
        rooms[room_id] = set()
    rooms[room_id].add(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            for client in list(rooms[room_id]):
                if client is not websocket:
                    try:
                        await client.send_text(data)
                    except:
                        rooms[room_id].discard(client)

    except WebSocketDisconnect:
        rooms[room_id].discard(websocket)
        if not rooms[room_id]:
            del rooms[room_id]


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=10000)
