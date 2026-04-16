let ws = null;
let username = '';
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 3000;

function joinChat() {
    const input = document.getElementById('usernameInput');
    const error = document.getElementById('loginError');
    const name = input.value.trim();

    if (!name) {
        error.textContent = 'Please enter a username';
        return;
    }
    if (name.length < 3) {
        error.textContent = 'Username must be at least 3 characters';
        return;
    }
    if (!/^[a-zA-Z0-9_]+$/.test(name)) {
        error.textContent = 'Only letters, numbers, and underscores allowed';
        return;
    }

    username = name;
    connectWebSocket();
}

function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws?username=${encodeURIComponent(username)}`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        reconnectAttempts = 0;
        document.getElementById('loginOverlay').classList.add('hidden');
        loadChatHistory();
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (e) {
            console.error('Failed to parse message:', e);
        }
    };

    ws.onclose = (event) => {
        if (event.code !== 4000 && event.code !== 4001 && event.code !== 4002) {
            handleDisconnect(event.code, event.reason);
        } else if (event.code === 4002) {
            showError('Chat is full. Try again later.');
            document.getElementById('loginOverlay').classList.remove('hidden');
        } else if (event.code === 4001) {
            showError('Invalid username');
            document.getElementById('loginOverlay').classList.remove('hidden');
        } else {
            addSystemMessage('Disconnected from chat');
        }
    };
}

function handleDisconnect(code, reason) {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS && code !== 4001 && code !== 4002) {
        reconnectAttempts++;
        addSystemMessage(`Reconnecting... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
        setTimeout(connectWebSocket, RECONNECT_DELAY);
    } else {
        addSystemMessage('Connection lost. Please refresh to rejoin.');
        document.getElementById('loginOverlay').classList.remove('hidden');
    }
}

function showError(text) {
    const error = document.getElementById('loginError');
    error.textContent = text;
}

function leaveChat() {
    if (ws) {
        ws.send(JSON.stringify({ type: 'leave' }));
        ws.close(4000, 'User left');
    }
    document.getElementById('loginOverlay').classList.remove('hidden');
}

function sendMessage() {
    const input = document.getElementById('messageInput');
    const text = input.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(JSON.stringify({ type: 'message', message: text }));
    input.value = '';
    input.focus();
}

function handleKeyPress(e) {
    if (e.key === 'Enter') sendMessage();
}

function handleMessage(data) {
    switch (data.type) {
        case 'message':
            addMessage(data.username, data.message, data.timestamp, data.username === username);
            break;
        case 'system':
            addSystemMessage(data.message);
            break;
        case 'users':
            document.getElementById('userCount').textContent = data.users.length;
            break;
    }
}

function addMessage(sender, text, timestamp, isSent) {
    const chatArea = document.getElementById('chatArea');
    const div = document.createElement('div');
    div.className = `message ${isSent ? 'sent' : 'received'}`;

    const time = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const senderInfo = !isSent ? `<div class="message-info">${sender}</div>` : '';

    div.innerHTML = `
        ${senderInfo}
        <div class="message-bubble">${text}</div>
        <div class="message-info">${time}</div>
    `;
    chatArea.appendChild(div);
    scrollToBottom();
}

function addSystemMessage(text) {
    const chatArea = document.getElementById('chatArea');
    const div = document.createElement('div');
    div.className = 'system-message';
    div.textContent = text;
    chatArea.appendChild(div);
    scrollToBottom();
}

function scrollToBottom() {
    const chatArea = document.getElementById('chatArea');
    chatArea.scrollTop = chatArea.scrollHeight;
}

async function loadChatHistory() {
    try {
        const response = await fetch('/messages');
        if (response.ok) {
            const messages = await response.json();
            const chatArea = document.getElementById('chatArea');
            chatArea.innerHTML = '';
            messages.forEach(m => {
                const isSent = username && m.sender === username;
                addMessage(m.sender, m.message, m.timestamp, isSent);
            });
        }
    } catch (e) {
        console.error('Failed to load chat history:', e);
    }
}