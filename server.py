from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Разрешаем запросы с фронтенда (и вообще со всех доменов, чтобы не мучиться)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # можно сузить до "https://webclass-lx23.onrender.com"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# комнаты: room_id -> набор подключённых сокетов
rooms: Dict[str, Set[WebSocket]] = {}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """
    Простая сигнальная комната:
    - добавляем WebSocket в комнату
    - всё, что пришло от одного клиента, пересылаем всем остальным
    """
    await websocket.accept()
    print(f"✅ WebSocket подключён: room={room_id}")

    if room_id not in rooms:
        rooms[room_id] = set()
    rooms[room_id].add(websocket)

    try:
        while True:
            # ждём сообщение от клиента (offer / answer / ice в виде текста)
            data = await websocket.receive_text()
            print(f"📨 msg in room={room_id}: {data[:60]}...")

            # рассылаем всем остальным участникам этой комнаты
            for client in list(rooms[room_id]):
                if client is websocket:
                    continue
                try:
                    await client.send_text(data)
                except Exception as e:
                    print(f"⚠️ ошибка отправки клиенту: {e}")
                    rooms[room_id].discard(client)

    except WebSocketDisconnect:
        print(f"🔌 Клиент отключился: room={room_id}")
        rooms[room_id].discard(websocket)
        if not rooms[room_id]:
            del rooms[room_id]
            print(f"🧹 Комната {room_id} очищена (нет клиентов)")
    except Exception as e:
        print(f"❌ Неожиданная ошибка WebSocket: {e}")
        rooms[room_id].discard(websocket)
        if room_id in rooms and not rooms[room_id]:
            del rooms[room_id]


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=10000)
