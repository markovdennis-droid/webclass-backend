from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, Dict

app = FastAPI()

# --- CORS (на один домен можно оставить *, ошибок не будет)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Монтируем папку /static
app.mount("/static", StaticFiles(directory="main/static"), name="static")

# --- Маршруты для teacher и student
@app.get("/teacher")
async def serve_teacher():
    return FileResponse("static/teacher.html")

@app.get("/student")
async def serve_student():
    return FileResponse("static/student.html")


# --- Класс комнаты
class Room:
    def __init__(self):
        self.teacher: Optional[WebSocket] = None
        self.student: Optional[WebSocket] = None


rooms: Dict[str, Room] = {}


async def safe_send(ws: Optional[WebSocket], msg: str):
    if ws:
        try:
            await ws.send_text(msg)
        except:
            pass


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    # Получаем параметры room & role
    params = ws.query_params
    room_id = params.get("room")
    role = params.get("role")  # teacher | student

    if not room_id or not role:
        await ws.close()
        return

    if room_id not in rooms:
        rooms[room_id] = Room()

    room = rooms[room_id]

    # Регистрируем сокет
    if role == "teacher":
        room.teacher = ws
        # сообщаем студенту что учитель подключился
        await safe_send(room.student, "teacher_connected")
    else:
        room.student = ws
        # сообщаем учителю что студент подключился
        await safe_send(room.teacher, "student_connected")

    try:
        while True:
            data = await ws.receive_text()

            # видео / rtc
            if role == "teacher":
                await safe_send(room.student, data)
            else:
                await safe_send(room.teacher, data)

    except WebSocketDisconnect:
        if role == "teacher":
            room.teacher = None
            await safe_send(room.student, "teacher_left")
        else:
            room.student = None
            await safe_send(room.teacher, "student_left")
