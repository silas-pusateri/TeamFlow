let socket = io();

socket.on('connect', () => {
    console.log('Connected to WebSocket');
    // Request current user ID from server
    socket.emit('get_current_user');
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

    // Group reactions by emoji
    const reactionGroups = {};
    if (data.reactions) {
        data.reactions.forEach(reaction => {
            if (!reactionGroups[reaction.emoji]) {
                reactionGroups[reaction.emoji] = {
                    count: 0,
                    users: new Set()
                };
            }
            reactionGroups[reaction.emoji].count++;
            reactionGroups[reaction.emoji].users.add(reaction.user_id);
        });
    }

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
        <div class="reactions">
            ${Object.entries(reactionGroups).map(([emoji, {count, users}]) => `
                <span class="reaction ${users.has(currentUserId) ? 'active' : ''}" 
                      data-emoji="${emoji}" 
                      title="${count} ${count === 1 ? 'reaction' : 'reactions'}">
                    ${emoji}
                    <span class="reaction-count">${count}</span>
                </span>
            `).join('')}
        </div>
    `;

    messageContainer.appendChild(messageElement);
    messageContainer.scrollTop = messageContainer.scrollHeight;
});

socket.on('reaction_added', (data) => {
    const message = document.querySelector(`[data-message-id="${data.message_id}"]`);
    if (message) {
        const reactionsContainer = message.querySelector('.reactions');
        const existingReaction = reactionsContainer.querySelector(`[data-emoji="${data.emoji}"]`);

        if (existingReaction) {
            // Update existing reaction
            const countElement = existingReaction.querySelector('.reaction-count');
            const currentCount = parseInt(countElement.textContent);

            if (data.user_id === currentUserId) {
                if (existingReaction.classList.contains('active')) {
                    // Remove reaction
                    if (currentCount === 1) {
                        existingReaction.remove();
                    } else {
                        countElement.textContent = currentCount - 1;
                        existingReaction.classList.remove('active');
                    }
                } else {
                    // Add reaction
                    countElement.textContent = currentCount + 1;
                    existingReaction.classList.add('active');
                }
            } else {
                // Another user's reaction
                countElement.textContent = currentCount + 1;
            }
        } else {
            // Create new reaction
            const reaction = document.createElement('span');
            reaction.classList.add('reaction');
            if (data.user_id === currentUserId) {
                reaction.classList.add('active');
            }
            reaction.dataset.emoji = data.emoji;
            reaction.innerHTML = `
                ${data.emoji}
                <span class="reaction-count">1</span>
            `;
            reactionsContainer.appendChild(reaction);
        }
    }
});

// Add event handler for clicking on reactions
document.addEventListener('click', (e) => {
    const reaction = e.target.closest('.reaction');
    if (reaction) {
        const messageId = reaction.closest('.message').dataset.messageId;
        const emoji = reaction.dataset.emoji;
        socket.emit('reaction', {
            message_id: messageId,
            emoji: emoji
        });
    }
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

function updateUserStatus(data) {
    const userElement = document.querySelector(`[data-user-id="${data.user_id}"]`);
    if (userElement) {
        const statusDot = userElement.querySelector('.status-dot');
        statusDot.classList.remove('online', 'offline');
        statusDot.classList.add(data.status);
    }
}

// Add currentUserId to window scope for reaction handling
window.currentUserId = null;
socket.on('current_user', (data) => {
    window.currentUserId = data.user_id;
});