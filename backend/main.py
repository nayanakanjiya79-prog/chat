import json
import time
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
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
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat Room</title>
    <style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; height: 100vh; display: flex; justify-content: center; align-items: center; }
.container { width: 100%; max-width: 500px; height: 90vh; max-height: 800px; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); display: flex; flex-direction: column; }
.header { background: #0084ff; color: white; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
.header h1 { font-size: 18px; font-weight: 600; }
.users-count { font-size: 12px; opacity: 0.9; margin-top: 4px; }
.leave-btn { background: rgba(255,255,255,0.2); color: white; border: none; padding: 8px 15px; border-radius: 20px; cursor: pointer; font-size: 14px; }
.leave-btn:hover { background: rgba(255,255,255,0.3); }
.chat-area { flex: 1; overflow-y: auto; padding: 15px; background: #f0f2f5; display: flex; flex-direction: column; }
.message { margin-bottom: 10px; display: flex; flex-direction: column; animation: fadeIn 0.3s ease; max-width: 80%; }
.message.sent { align-self: flex-end; align-items: flex-end; }
.message.received { align-self: flex-start; align-items: flex-start; }
.message-info { font-size: 11px; color: #999; margin-bottom: 4px; }
.message-bubble { max-width: 100%; padding: 10px 15px; border-radius: 18px; word-wrap: break-word; line-height: 1.4; }
.message.sent .message-bubble { background: #0084ff; color: white; border-bottom-right-radius: 4px; }
.message.received .message-bubble { background: white; color: #333; border-bottom-left-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
.system-message { text-align: center; font-size: 12px; color: #666; padding: 8px 15px; background: rgba(0,0,0,0.05); border-radius: 10px; margin: 5px auto; align-self: center; }
.input-area { padding: 15px; background: white; border-top: 1px solid #eee; display: flex; gap: 10px; align-items: center; }
.input-area input { flex: 1; padding: 12px 15px; border: 1px solid #ddd; border-radius: 25px; outline: none; font-size: 14px; }
.input-area input:focus { border-color: #0084ff; }
.input-area button { background: #0084ff; color: white; border: none; padding: 12px 20px; border-radius: 25px; cursor: pointer; font-size: 14px; font-weight: 600; }
.input-area button:hover { background: #0073e6; }
.login-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); display: flex; justify-content: center; align-items: center; z-index: 100; }
.login-box { background: white; padding: 30px; border-radius: 15px; width: 90%; max-width: 350px; text-align: center; }
.login-box h2 { margin-bottom: 20px; color: #333; font-size: 24px; }
.login-box input { width: 100%; padding: 12px 15px; margin-bottom: 15px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; }
.login-box button { width: 100%; padding: 12px; background: #0084ff; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 600; }
.login-box .error { color: #e74c3c; font-size: 14px; margin-top: 10px; }
.hidden { display: none !important; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@media (max-width: 480px) { .container { height: 100vh; max-height: none; border-radius: 0; } .message { max-width: 85%; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div><h1>Chat Room</h1><div class="users-count">Online: <span id="userCount">0</span>/3</div></div>
            <button class="leave-btn" onclick="leaveChat()">Leave</button>
        </div>
        <div class="chat-area" id="chatArea"></div>
        <div class="input-area">
            <input type="text" id="messageInput" placeholder="Type a message..." onkeypress="handleKeyPress(event)">
            <button id="sendBtn" onclick="sendMessage()">Send</button>
        </div>
    </div>
    <div class="login-overlay" id="loginOverlay">
        <div class="login-box">
            <h2>Join Chat</h2>
            <input type="text" id="usernameInput" placeholder="Enter username" maxlength="20">
            <button onclick="joinChat()">Join</button>
            <div class="error" id="loginError"></div>
        </div>
    </div>
    <script>
let ws = null;
let username = '';
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 3000;
function joinChat() {
    const input = document.getElementById('usernameInput');
    const error = document.getElementById('loginError');
    const name = input.value.trim();
    if (!name) { error.textContent = 'Please enter a username'; return; }
    if (name.length < 3) { error.textContent = 'Username must be at least 3 characters'; return; }
    if (!/^[a-zA-Z0-9_]+$/.test(name)) { error.textContent = 'Only letters, numbers, underscores allowed'; return; }
    username = name;
    connectWebSocket();
}
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws?username=${encodeURIComponent(username)}`);
    ws.onopen = () => { reconnectAttempts = 0; document.getElementById('loginOverlay').classList.add('hidden'); loadChatHistory(); };
    ws.onerror = () => { console.error('WebSocket error'); };
    ws.onmessage = (event) => { try { handleMessage(JSON.parse(event.data)); } catch(e) { console.error(e); } };
    ws.onclose = (event) => { if(event.code !== 4000 && event.code !== 4001 && event.code !== 4002) { handleDisconnect(event.code); } else if(event.code === 4002) { showError('Chat is full'); } else if(event.code === 4001) { showError('Invalid username'); } else { addSystemMessage('Disconnected'); } };
}
function handleDisconnect(code) {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS && code !== 4001 && code !== 4002) {
        reconnectAttempts++;
        addSystemMessage('Reconnecting... (' + reconnectAttempts + '/' + MAX_RECONNECT_ATTEMPTS + ')');
        setTimeout(connectWebSocket, RECONNECT_DELAY);
    } else {
        addSystemMessage('Connection lost. Refresh to rejoin.');
    }
}
function showError(text) { document.getElementById('loginError').textContent = text; }
function leaveChat() { if(ws) { ws.send(JSON.stringify({type:'leave'})); ws.close(4000,'User left'); } document.getElementById('loginOverlay').classList.remove('hidden'); }
function sendMessage() { const input = document.getElementById('messageInput'); const text = input.value.trim(); if(!text || !ws || ws.readyState !== WebSocket.OPEN) return; ws.send(JSON.stringify({type:'message',message:text})); input.value = ''; }
function handleKeyPress(e) { if(e.key === 'Enter') sendMessage(); }
function handleMessage(data) {
    if(data.type === 'message') { addMessage(data.username, data.message, data.timestamp, data.username === username); }
    else if(data.type === 'system') { addSystemMessage(data.message); }
    else if(data.type === 'users') { document.getElementById('userCount').textContent = data.users.length; }
}
function addMessage(sender, text, timestamp, isSent) {
    const div = document.createElement('div');
    div.className = 'message ' + (isSent ? 'sent' : 'received');
    const time = new Date(timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
    const senderInfo = !isSent ? '<div class="message-info">' + sender + '</div>' : '';
    div.innerHTML = senderInfo + '<div class="message-bubble">' + text + '</div><div class="message-info">' + time + '</div>';
    document.getElementById('chatArea').appendChild(div);
    document.getElementById('chatArea').scrollTop = document.getElementById('chatArea').scrollHeight;
}
function addSystemMessage(text) {
    const div = document.createElement('div');
    div.className = 'system-message';
    div.textContent = text;
    document.getElementById('chatArea').appendChild(div);
    document.getElementById('chatArea').scrollTop = document.getElementById('chatArea').scrollHeight;
}
async function loadChatHistory() {
    try {
        const r = await fetch('/messages');
        if(r.ok) {
            const messages = await r.json();
            const chatArea = document.getElementById('chatArea');
            chatArea.innerHTML = '';
            messages.forEach(m => addMessage(m.sender, m.message, m.timestamp, username && m.sender === username));
        }
    } catch(e) { console.error('Failed to load chat history:', e); }
}
    </script>
</body>
</html>"""
    return HTMLResponse(html)


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