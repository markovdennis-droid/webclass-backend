import os
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Разрешаем запросы с фронта
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# room -> {"teacher": WebSocket | None, "student": WebSocket | None}
rooms: Dict[str, Dict[str, WebSocket]] = {}

# Сюда будем складывать offer, если второй ещё не подключился
pending_offers: Dict[str, Dict[str, Any]] = {}


def get_other_role(role: str) -> str:
    return "student" if role == "teacher" else "teacher"


@app.get("/")
async def root():
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

    rooms[room][role] = websocket

    print(f"[WS] {role} '{name}' connected to room '{room}'")

    # Сообщаем подключившемуся, что он в комнате
    await websocket.send_json(
        {
            "type": "joined",
            "room": room,
            "role": role,
            "name": name,
        }
    )

    # Если до этого в комнате уже был сохранён offer от другой стороны —
    # сразу отправляем его вновь подключившемуся
    pending = pending_offers.get(room)
    if pending and pending.get("role") != role:
        try:
            await websocket.send_json(pending)
            print(f"[WS] sent pending offer to {role} in room {room}")
        except Exception as e:
            print(f"[WS] error sending pending offer: {e}")
        else:
            del pending_offers[room]

    # Сообщаем второй стороне (если есть), что кто-то подключился
    other_role = get_other_role(role)
    other_ws = rooms[room].get(other_role)
    if other_ws is not None:
        try:
            await other_ws.send_json(
                {
                    "type": "info",
                    "text": f"{role} {name} подключился",
                    "room": room,
                    "from_role": role,
                }
            )
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            other_role = get_other_role(role)
            other_ws = rooms[room].get(other_role)

            # Сигнальные сообщения WebRTC
            if msg_type in ("offer", "answer", "ice-candidate"):
                # Если вторая сторона уже в комнате — просто пересылаем
                if other_ws is not None:
                    try:
                        await other_ws.send_json(data)
                    except Exception as e:
                        print(f"[WS] error sending {msg_type} to {other_role}: {e}")
                else:
                    # Если ОФФЕР пришёл, а второй ещё не подключился —
                    # сохраняем его, чтобы отправить, когда тот зайдёт
                    if msg_type == "offer":
                        pending_offers[room] = data
                        print(f"[WS] stored pending offer in room {room}")
                continue

            # Остальные типы при необходимости можно обработать тут

    except WebSocketDisconnect:
        print(f"[WS] {role} '{name}' disconnected from room '{room}'")
    finally:
        try:
            if room in rooms and rooms[room].get(role) is websocket:
                rooms[room][role] = None

            other_role = get_other_role(role)
            other_ws = rooms[room].get(other_role) if room in rooms else None
            if other_ws is not None:
                try:
                    await other_ws.send_json(
                        {
                            "type": "info",
                            "text": f"{role} {name} отключился",
                            "room": room,
                            "from_role": role,
                        }
                    )
                except Exception:
                    pass

            # Если отключился тот, кто присылал pending-offer — можно его сбросить
            pending = pending_offers.get(room)
            if pending and pending.get("role") == role:
                del pending_offers[room]

        except Exception as e:
            print(f"[WS] cleanup error: {e}")


# Локальный запуск (на Render используется команда uvicorn server:app ...)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
