from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Set

app = FastAPI()

# Разрешаем подключение с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms: Dict[str, Set[WebSocket]] = {}


@app.get("/")
async def root():
    return {"status": "ok", "service": "webclass-backend"}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """
    Простой сигнальный сервер:
    - клиент подключается ws://host/ws/room
    - отправляет JSON (offer, answer, candidate)
    - сервер пересылает остальным участникам комнаты
    """
    await websocket.accept()

    if room_id not in rooms:
        rooms[room_id] = set()
    rooms[room_id].add(websocket)

    print(f"Client connected: room={room_id}, clients={len(rooms[room_id])}")

    try:
        while True:
            data = await websocket.receive_text()
            for conn in list(rooms[room_id]):
                if conn is not websocket:
                    await conn.send_text(data)
    except WebSocketDisconnect:
        print(f"Client disconnected: room={room_id}")
        rooms[room_id].discard(websocket)
        if not rooms[room_id]:
            del rooms[room_id]
