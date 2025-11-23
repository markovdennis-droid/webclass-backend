import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Разрешаем фронту с Render обращаться к бекенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# room -> {"teacher": WebSocket | None, "student": WebSocket | None}
rooms: dict[str, dict[str, WebSocket | None]] = {}


async def safe_send(ws: WebSocket | None, message: dict):
    """Отправка сообщения с защитой от разорванного соединения."""
    if ws is None:
        return
    try:
        await ws.send_text(json.dumps(message))
    except Exception:
        # на продакшене тут лучше логировать
        pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    role: str | None = None
    room: str | None = None

    try:
        while True:
            text = await websocket.receive_text()
            data = json.loads(text)
            msg_type = data.get("type")

            # ---- JOIN ----
            if msg_type == "join":
                room = data.get("room") or "default"
                role = data.get("role") or "guest"

                if room not in rooms:
                    rooms[room] = {"teacher": None, "student": None}

                if role == "teacher":
                    rooms[room]["teacher"] = websocket
                else:
                    # всё, что не teacher, считаем учеником
                    role = "student"
                    rooms[room]["student"] = websocket

                # если оба уже в комнате — уведомляем
                teacher_ws = rooms[room]["teacher"]
                student_ws = rooms[room]["student"]

                if teacher_ws and student_ws:
                    # учителю говорим, что пришёл студент
                    await safe_send(
                        teacher_ws,
                        {
                            "type": "joined",
                            "room": room,
                            "role": "student",
                            "name": data.get("name", ""),
                        },
                    )
                    # студенту говорим, что есть учитель
                    await safe_send(
                        student_ws,
                        {
                            "type": "joined",
                            "room": room,
                            "role": "teacher",
                            "name": data.get("name", ""),
                        },
                    )

                continue  # ждём следующее сообщение

            # если join ещё не был — игнор
            if room is None or role is None:
                continue

            # ---- РОУТИНГ offer / answer / ice-candidate ----
            other_role = "student" if role == "teacher" else "teacher"
            dest_ws = rooms.get(room, {}).get(other_role)

            if dest_ws is None:
                # второй участник ещё не в комнате
                continue

            # просто пересылаем сообщение как есть
            await safe_send(dest_ws, data)

    except WebSocketDisconnect:
        # клиент отключился — убираем его из комнаты
        if room and room in rooms and role:
            if rooms[room].get(role) is websocket:
                rooms[room][role] = None

            other_role = "student" if role == "teacher" else "teacher"
            other_ws = rooms[room].get(other_role)
            # уведомим второго, что этот вышел
            await safe_send(
                other_ws,
                {"type": "info", "text": f"{role} отключился"},
            )

    except Exception:
        # здесь можно логировать исключение
        pass


if __name__ == "__main__":
    # Render сам подставит PORT, но локально можно запускать так:
    uvicorn.run(app, host="0.0.0.0", port=10000)
