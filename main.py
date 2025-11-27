from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

app = FastAPI()

# ТВОИ HTML лежат в ПАПКЕ static/, НЕ В main/static
app.mount("/static", StaticFiles(directory="static"), name="static")

rooms = {}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, room: str, role: str):
    await websocket.accept()

    if room not in rooms:
        rooms[room] = {}

    rooms[room][role] = websocket

    other = "teacher" if role == "student" else "student"

    try:
        while True:
            data = await websocket.receive_text()
            if other in rooms[room]:
                await rooms[room][other].send_text(data)

    except WebSocketDisconnect:
        pass
