import json
import time
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Dict

from models import Message, SystemMessage, UserListMessage
from database import save_message, get_messages, add_user, remove_user

MAX_USERS = 3

app = FastAPI(title="Real-Time Chat")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.username_socket_map: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[username] = websocket
        self.username_socket_map[websocket] = username

    def disconnect(self, websocket: WebSocket):
        username = self.username_socket_map.pop(websocket, None)
        if username:
            self.active_connections.pop(username, None)
        return username

    async def broadcast(self, message: dict):
        disconnected = []
        for username, conn in self.active_connections.items():
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.append(username)
        for username in disconnected:
            self.active_connections.pop(username, None)

    def get_active_users(self) -> list[str]:
        return list(self.active_connections.keys())

    def is_full(self) -> bool:
        return len(self.active_connections) >= MAX_USERS


manager = ConnectionManager()

user_message_timestamps: Dict[str, float] = {}
RATE_LIMIT = 1.0


def sanitize_input(text: str) -> str:
    import html
    text = text.strip()
    text = html.escape(text)
    return text[:500]


def check_rate_limit(username: str) -> bool:
    now = time.time()
    if username in user_message_timestamps:
        if now - user_message_timestamps[username] < RATE_LIMIT:
            return False
    user_message_timestamps[username] = now
    return True


@app.get("/")
async def get_frontend():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text())
    return HTMLResponse("<h1>Frontend not found</h1>")


@app.get("/messages")
async def get_chat_history():
    return get_messages()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, username: str = None):
    username_param = username

    if not username_param:
        await websocket.close(code=4000, reason="Username required")
        return

    username_param = sanitize_input(username_param)

    if len(username_param) < 3 or len(username_param) > 20:
        await websocket.close(code=4001, reason="Invalid username")
        return

    if manager.is_full():
        await websocket.close(code=4002, reason="Chat is full")
        return

    await manager.connect(websocket, username_param)
    add_user(username_param)

    users = manager.get_active_users()
    await manager.broadcast({
        "type": "system",
        "message": f"{username_param} joined the chat",
        "timestamp": datetime.now().isoformat()
    })
    await manager.broadcast({
        "type": "users",
        "users": users
    })

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "leave":
                break

            if message_data.get("type") == "message":
                if not check_rate_limit(username_param):
                    await websocket.send_json({
                        "type": "system",
                        "message": "Too fast! Please wait.",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                message_text = sanitize_input(message_data.get("message", ""))
                if not message_text:
                    continue

                save_message(username_param, message_text)

                await manager.broadcast({
                    "type": "message",
                    "username": username_param,
                    "message": message_text,
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        disconnected_username = manager.disconnect(websocket)
        if disconnected_username:
            remove_user(disconnected_username)
            users = manager.get_active_users()
            await manager.broadcast({
                "type": "system",
                "message": f"{disconnected_username} left the chat",
                "timestamp": datetime.now().isoformat()
            })
            await manager.broadcast({
                "type": "users",
                "users": users
            })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)