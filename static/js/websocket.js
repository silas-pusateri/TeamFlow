let socket = io();

socket.on('connect', () => {
    console.log('Connected to WebSocket');
});

socket.on('message', (data) => {
    const messageContainer = document.getElementById('message-container');
    const placeholder = messageContainer.querySelector('.no-messages-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    messageElement.dataset.messageId = data.id;

    messageElement.innerHTML = `
        <div class="message-header">
            <span class="username">${data.user}</span>
            <span class="timestamp">${new Date(data.timestamp).toLocaleString()}</span>
        </div>
        <div class="message-content">${data.content}</div>
        <div class="message-actions">
            <button class="pin-btn ${data.is_pinned ? 'active' : ''}" 
                title="${data.is_pinned ? `Pinned by ${data.pinned_by} on ${new Date(data.pinned_at).toLocaleString()}` : 'Pin message'}">
                <i class="feather-pin"></i>
            </button>
            <button class="bookmark-btn" title="Bookmark message">
                <i class="feather-bookmark"></i>
            </button>
            <button class="reaction-btn" title="Add reaction">
                <i class="feather-smile"></i>
            </button>
        </div>
        <div class="reactions"></div>
    `;

    messageContainer.appendChild(messageElement);
    messageContainer.scrollTop = messageContainer.scrollHeight;
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

socket.on('message_pinned', (data) => {
    const message = document.querySelector(`[data-message-id="${data.message_id}"]`);
    if (message) {
        const pinButton = message.querySelector('.pin-btn');
        pinButton.classList.toggle('active', data.is_pinned);
        pinButton.title = data.is_pinned ? 
            `Pinned by ${data.pinned_by} on ${new Date(data.pinned_at).toLocaleString()}` :
            'Pin message';
    }
});

socket.on('message_bookmarked', (data) => {
    const message = document.querySelector(`[data-message-id="${data.message_id}"]`);
    if (message) {
        const bookmarkButton = message.querySelector('.bookmark-btn');
        bookmarkButton.classList.toggle('active', data.is_bookmarked);
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