import os
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Разрешаем запросы с фронта (любой домен — для простоты)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# room -> {"teacher": WebSocket | None, "student": WebSocket | None}
rooms: Dict[str, Dict[str, WebSocket]] = {}


def get_other_role(role: str) -> str:
    return "student" if role == "teacher" else "teacher"


@app.get("/")
async def root():
    # Просто чтобы было что открыть по корню
    return {"status": "ok", "message": "webclass backend is running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket-подключение:
    wss://webclass-backend-g3uh.onrender.com/ws?room=english12&role=teacher&name=Денис
    """
    await websocket.accept()

    params = websocket.query_params
    room = params.get("room") or "default"
    role = params.get("role") or "guest"
    name = params.get("name") or ""

    if room not in rooms:
        rooms[room] = {"teacher": None, "student": None}

    # Запоминаем подключение в комнате
    rooms[room][role] = websocket

    print(f"[WS] {role} '{name}' connected to room '{room}'")

    # Отправляем самому подключившемуся
    await websocket.send_json(
        {
            "type": "joined",
            "room": room,
            "role": role,
            "name": name,
        }
    )

    # Пишем второму участнику (если уже есть)
    other_role = get_other_role(role)
    other_ws = rooms[room].get(other_role)
    if other_ws is not None:
        try:
            await other_ws.send_json(
                {
                    "type": "info",
                    "text": f"{role} {name} подключился",
                    "room": room,
                }
            )
        except Exception:
            # если второй уже отвалился — просто игнорируем
            pass

    try:
        while True:
            # Ждём сообщения от клиента
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # Кому пересылать
            other_role = get_other_role(role)
            other_ws = rooms[room].get(other_role)

            # Если в комнате ещё нет второго участника — просто ждём
            if other_ws is None:
                continue

            # Пробрасываем сигнальные сообщения WebRTC
            if msg_type in ("offer", "answer", "ice-candidate"):
                try:
                    await other_ws.send_json(data)
                except Exception as e:
                    print(f"[WS] error sending to {other_role} in room {room}: {e}")

    except WebSocketDisconnect:
        print(f"[WS] {role} '{name}' disconnected from room '{room}'")
    finally:
        # Убираем сокет из комнаты
        try:
            if room in rooms and rooms[room].get(role) is websocket:
                rooms[room][role] = None

            # Уведомим второго участника, что этот ушёл
            other_role = get_other_role(role)
            other_ws = rooms[room].get(other_role) if room in rooms else None
            if other_ws is not None:
                try:
                    await other_ws.send_json(
                        {
                            "type": "info",
                            "text": f"{role} {name} отключился",
                            "room": room,
                        }
                    )
                except Exception:
                    pass
        except Exception as e:
            print(f"[WS] cleanup error: {e}")


# Локальный запуск (Render использует свою команду uvicorn server:app ...)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
