let socket = io();

socket.on('connect', () => {
    console.log('Connected to WebSocket');
});

socket.on('message', (data) => {
    renderMessage(data);
});

socket.on('status_change', (data) => {
    updateUserStatus(data);
});

socket.on('thread_message', (data) => {
    const parentMessage = document.querySelector(`[data-message-id="${data.parent_id}"]`);
    if (parentMessage) {
        const threadContainer = parentMessage.querySelector('.thread-container');
        const threadMessage = document.createElement('div');
        threadMessage.classList.add('thread-message');
        threadMessage.innerHTML = `
            <span class="username">${data.user}</span>
            <span class="timestamp">${new Date(data.timestamp).toLocaleString()}</span>
            <div class="content">${data.content}</div>
        `;
        threadContainer.appendChild(threadMessage);
    }
});

socket.on('reaction_added', (data) => {
    const message = document.querySelector(`[data-message-id="${data.message_id}"]`);
    if (message) {
        const reactionsContainer = message.querySelector('.reactions');
        const reaction = document.createElement('span');
        reaction.classList.add('reaction');
        reaction.textContent = data.emoji;
        reactionsContainer.appendChild(reaction);
    }
});

function updateUserStatus(data) {
    const userElement = document.querySelector(`[data-user-id="${data.user_id}"]`);
    if (userElement) {
        const statusDot = userElement.querySelector('.status-dot');
        statusDot.classList.remove('online', 'offline');
        statusDot.classList.add(data.status);
    }
}