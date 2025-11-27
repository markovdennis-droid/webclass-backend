import json
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# CORS — при желании можно сузить до конкретного домена
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика: предполагается, что teacher.html и student.html лежат в папке "static"
# Если у тебя уже есть другой mount — адаптируй этот блок под свой проект.
app.mount("/", StaticFiles(directory="static", html=True), name="static")


class Room:
    def __init__(self) -> None:
        self.teacher: Optional[WebSocket] = None
        self.student: Optional[WebSocket] = None


rooms: Dict[str, Room] = {}


async def safe_send(ws: Optional[WebSocket], data: str) -> None:
    if not ws:
        return
    try:
        await ws.send_text(data)
    except Exception:
        # В проде тут логируем ошибку
        pass


async def notify_both_ready(room_id: str) -> None:
    room = rooms.get(room_id)
    if not room:
        return
    if room.teacher and room.student:
        msg = json.dumps({"type": "both-ready"})
        await safe_send(room.teacher, msg)
        await safe_send(room.student, msg)


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    room: str = Query(...),
    role: str = Query(...),
):
    """
    WebSocket-сигналинг для WebRTC.
    Подключение:
      /ws?room=ROOM_ID&role=teacher
      /ws?room=ROOM_ID&role=student
    """
    await websocket.accept()

    if room not in rooms:
        rooms[room] = Room()
    room_obj = rooms[room]

    # Регистрируем сокет
    if role == "teacher":
        room_obj.teacher = websocket
    else:
        role = "student"
        room_obj.student = websocket

    # Если оба в комнате — шлём обоим "both-ready"
    await notify_both_ready(room)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            # Пересылаем signaling-сообщения второй стороне
            if msg_type in ("offer", "answer", "ice-candidate"):
                target_ws: Optional[WebSocket]
                if role == "teacher":
                    target_ws = room_obj.student
                else:
                    target_ws = room_obj.teacher

                if target_ws is not None:
                    await safe_send(target_ws, data)

    except WebSocketDisconnect:
        # Клиент отвалился
        if role == "teacher" and room_obj.teacher is websocket:
            room_obj.teacher = None
        elif role == "student" and room_obj.student is websocket:
            room_obj.student = None

        # Если в комнате никого не осталось — удаляем её
        if room_obj.teacher is None and room_obj.student is None:
            rooms.pop(room, None)
