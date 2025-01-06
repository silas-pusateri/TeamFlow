let socket = io();
let currentUserId = null;

socket.on('connect', () => {
    console.log('Connected to WebSocket');
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
                    users: new Set(),
                    usernames: []
                };
            }
            reactionGroups[reaction.emoji].count++;
            reactionGroups[reaction.emoji].users.add(reaction.user_id);
            reactionGroups[reaction.emoji].usernames.push(reaction.user);
        });
    }

    messageElement.innerHTML = createMessageHTML(data, reactionGroups);
    messageContainer.appendChild(messageElement);
    messageContainer.scrollTop = messageContainer.scrollHeight;
});

function createMessageHTML(data, reactionGroups) {
    return `
        <div class="message-header">
            <span class="username">${data.user}</span>
            <span class="timestamp">${new Date(data.timestamp).toLocaleString()}</span>
        </div>
        <div class="message-content">${data.content}</div>
        <div class="message-hover-actions">
            <button class="hover-action-btn reaction-btn" title="Add reaction">
                <i class="feather-smile"></i>
                React
            </button>
            <button class="hover-action-btn reply-btn" title="Reply to message">
                <i class="feather-message-square"></i>
                Reply
            </button>
        </div>
        <div class="reactions">
            ${Object.entries(reactionGroups).map(([emoji, {count, users, usernames}]) => `
                <span class="reaction ${users.has(currentUserId) ? 'active' : ''}" 
                      data-emoji="${emoji}" 
                      title="${usernames.join(', ')}">
                    ${emoji}
                    <span class="reaction-count">${count}</span>
                </span>
            `).join('')}
        </div>
        <div class="thread-container" data-message-id="${data.id}">
            ${(data.threads || []).map(thread => createThreadMessageHTML(thread)).join('')}
        </div>
    `;
}

function createThreadMessageHTML(thread) {
    return `
        <div class="thread-message" data-thread-id="${thread.id}">
            <div class="message-header">
                <span class="username">${thread.user}</span>
                <span class="timestamp">${new Date(thread.timestamp).toLocaleString()}</span>
            </div>
            <div class="message-content">${thread.content}</div>
            <div class="message-hover-actions">
                <button class="hover-action-btn reaction-btn" title="Add reaction">
                    <i class="feather-smile"></i>
                    React
                </button>
            </div>
            <div class="reactions"></div>
        </div>
    `;
}

socket.on('thread_message', (data) => {
    console.log('Received thread message:', data);
    const threadContainer = document.querySelector(`.thread-container[data-message-id="${data.parent_id}"]`);
    if (threadContainer) {
        threadContainer.style.display = 'block';
        const threadMessage = document.createElement('div');
        threadMessage.classList.add('thread-message');
        threadMessage.dataset.threadId = data.id;
        threadMessage.innerHTML = createThreadMessageHTML(data);
        threadContainer.appendChild(threadMessage);
        threadContainer.scrollTop = threadContainer.scrollHeight;
    } else {
        console.error('Thread container not found for parent message:', data.parent_id);
    }
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

            // Update title with usernames
            const currentTitle = existingReaction.title.split(', ');
            if (existingReaction.classList.contains('active')) {
                if (!currentTitle.includes(data.user)) {
                    currentTitle.push(data.user);
                }
            } else {
                const index = currentTitle.indexOf(data.user);
                if (index > -1) {
                    currentTitle.splice(index, 1);
                }
            }
            existingReaction.title = currentTitle.join(', ');
        } else {
            // Create new reaction
            const reaction = document.createElement('span');
            reaction.classList.add('reaction');
            if (data.user_id === currentUserId) {
                reaction.classList.add('active');
            }
            reaction.dataset.emoji = data.emoji;
            reaction.title = data.user;
            reaction.innerHTML = `
                ${data.emoji}
                <span class="reaction-count">1</span>
            `;
            reactionsContainer.appendChild(reaction);
        }
    }
});

// Add event handler for clicking on reactions and replies
document.addEventListener('click', (e) => {
    const reaction = e.target.closest('.reaction');
    const replyBtn = e.target.closest('.reply-btn');

    if (reaction) {
        const messageId = reaction.closest('.message').dataset.messageId;
        const emoji = reaction.dataset.emoji;
        socket.emit('reaction', {
            message_id: messageId,
            emoji: emoji
        });
    } else if (replyBtn) {
        const messageElement = replyBtn.closest('.message');
        const threadContainer = messageElement.querySelector('.thread-container');
        const messageId = messageElement.dataset.messageId;

        // Show reply input
        const replyInput = document.createElement('div');
        replyInput.className = 'reply-input';
        replyInput.innerHTML = `
            <textarea class="form-control" placeholder="Type your reply..."></textarea>
            <button class="btn btn-primary mt-2">Send Reply</button>
        `;

        // Add the reply input if it doesn't exist
        if (!threadContainer.querySelector('.reply-input')) {
            threadContainer.appendChild(replyInput);
        }

        // Show the thread container
        threadContainer.style.display = 'block';

        // Handle reply submission
        const sendButton = replyInput.querySelector('button');
        const textarea = replyInput.querySelector('textarea');

        sendButton.onclick = () => {
            const content = textarea.value.trim();
            if (content) {
                socket.emit('thread_reply', {
                    content: content,
                    parent_id: messageId,
                    channel_id: currentChannel // This is defined in main.js
                });
                textarea.value = '';
            }
        };
    }
});

socket.on('status_change', (data) => {
    updateUserStatus(data);
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
    currentUserId = data.user_id;
});