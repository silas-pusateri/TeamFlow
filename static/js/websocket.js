let socket = io({
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000
});
let currentUserId = null;

socket.on('connect', () => {
    console.log('Connected to WebSocket');
    socket.emit('get_current_user');
});

socket.on('disconnect', () => {
    console.log('Disconnected from WebSocket');
});

socket.on('reconnect', (attemptNumber) => {
    console.log('Reconnected to WebSocket after ' + attemptNumber + ' attempts');
    if (currentChannel) {
        socket.emit('join', { channel: currentChannel });
    }
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

    data.content = parseChannelReferences(data.content);
    messageElement.innerHTML = createMessageHTML(data, reactionGroups);
    messageContainer.appendChild(messageElement);
    messageContainer.scrollTop = messageContainer.scrollHeight;
});

function createMessageHTML(data, reactionGroups) {
    return `
        <div class="message-header">
            <span class="username">${data.user}</span>
            <div class="message-actions">
                <span class="timestamp">${new Date(data.timestamp).toLocaleString()}</span>
                <button class="message-menu-btn" onclick="toggleMessageMenu(event, '${data.id}')">⋮</button>
                <div class="message-menu" id="menu-${data.id}">
                    <div class="menu-item" onclick="copyMessageContent('${data.id}')">Copy message</div>
                <div class="menu-item" onclick="copyMessageLink('${data.id}')">Copy link</div>
                <div class="menu-item delete-option" onclick="showDeleteConfirmation('${data.id}')">Delete message</div>
                </div>
            </div>
        </div>
        <div class="message-content">${data.content}</div>
        <div class="message-hover-actions">
            <button class="hover-action-btn reaction-btn" title="Add reaction" data-message-id="${data.id}">
                <i class="feather-smile"></i>
                React
            </button>
            <button class="hover-action-btn reply-btn" title="Reply in thread">
                <i class="feather-message-square"></i>
                Reply
            </button>
        </div>
        <div class="reactions" data-message-id="${data.id}">
            ${Object.entries(reactionGroups).map(([emoji, {count, users, usernames}]) => `
                <span class="reaction ${users.has(currentUserId) ? 'active' : ''}" 
                      data-emoji="${emoji}"
                      data-message-id="${data.id}" 
                      title="${usernames.join(', ')}">
                    ${emoji}
                    <span class="reaction-count">${count}</span>
                </span>
            `).join('')}
        </div>
        <div class="thread-container ${data.threads && data.threads.length > 0 ? 'active' : ''}">
            ${(data.threads || []).map(thread => createThreadMessageHTML(thread)).join('')}
        </div>
    `;
}

function createThreadMessageHTML(thread) {
    const threadReactions = thread.reactions || [];
    const reactionGroups = {};
    threadReactions.forEach(reaction => {
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

    return `
        <div class="thread-message" data-message-id="${thread.id}">
            <div class="message-header">
                <span class="username">${thread.user}</span>
                <span class="timestamp">${new Date(thread.timestamp).toLocaleString()}</span>
            </div>
            <div class="message-content">${thread.content}</div>
            <div class="message-hover-actions">
                <button class="hover-action-btn reaction-btn" title="Add reaction" data-message-id="${thread.id}">
                    <i class="feather-smile"></i>
                    React
                </button>
                <button class="hover-action-btn reply-btn" title="Reply in thread">
                    <i class="feather-message-square"></i>
                    Reply
                </button>
            </div>
            <div class="reactions" data-message-id="${thread.id}">
                ${Object.entries(reactionGroups).map(([emoji, {count, users, usernames}]) => `
                    <span class="reaction ${users.has(currentUserId) ? 'active' : ''}" 
                          data-emoji="${emoji}"
                          data-message-id="${thread.id}"
                          title="${usernames.join(', ')}">
                        ${emoji}
                        <span class="reaction-count">${count}</span>
                    </span>
                `).join('')}
            </div>
        </div>
    `;
}

socket.on('thread_message', (data) => {
    const parentMessage = document.querySelector(`[data-message-id="${data.parent_id}"]`);
    if (parentMessage) {
        const threadContainer = parentMessage.querySelector('.thread-container');
        threadContainer.classList.add('active');

        const threadMessage = document.createElement('div');
        threadMessage.classList.add('thread-message');
        threadMessage.dataset.messageId = data.id;
        threadMessage.innerHTML = createThreadMessageHTML(data);

        threadContainer.appendChild(threadMessage);
        threadContainer.scrollTop = threadContainer.scrollHeight;
    }
});

socket.on('reaction_added', (data) => {
    const selector = data.is_thread ? '.thread-message' : '.message';
    const message = document.querySelector(`${selector}[data-message-id="${data.message_id}"]`);
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

// Add event handlers for message actions
document.addEventListener('click', (e) => {
    const messageElement = e.target.closest('.message, .thread-message');
    if (!messageElement) return;

    if (e.target.closest('.reaction-btn')) {
        const messageId = messageElement.dataset.messageId;
        const rect = e.target.closest('.reaction-btn').getBoundingClientRect();
        showEmojiPicker(messageId, rect);
    } else if (e.target.closest('.reply-btn')) {
        const username = messageElement.querySelector('.username').textContent;
        const content = messageElement.querySelector('.message-content').textContent;
        const messageId = messageElement.dataset.messageId;
        setReplyContext(messageId, username, content);
    }

    const reaction = e.target.closest('.reaction');
    if (reaction) {
        const messageElement = reaction.closest('.message, .thread-message');
        if (messageElement) {
            const messageId = messageElement.dataset.messageId;
            const emoji = reaction.dataset.emoji;
            socket.emit('reaction', {
                message_id: messageId,
                emoji: emoji,
                is_thread: messageElement.classList.contains('thread-message')
            });
        }
    }
});

socket.on('status_change', (data) => {
    updateUserStatus(data);
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

socket.on('channel_info', (data) => {
    const header = document.getElementById('channel-header');
    if (header) {
        header.querySelector('.channel-name').textContent = `# ${data.name}`;
        header.querySelector('.channel-description').textContent = data.description;
        header.querySelector('.channel-owner').textContent = `Created by ${data.creator}`;
        header.querySelector('.message-count').textContent = `${data.message_count} messages`;
        header.querySelector('.reply-count').textContent = `${data.reply_count} replies`;
    }
});


function parseChannelReferences(content) {
    const channelRegex = /\#([a-zA-Z0-9_-]+)/g;
    return content.replace(channelRegex, (match, channelName) => {
        const channelList = document.getElementById('channel-list');
        const channels = Array.from(channelList.getElementsByClassName('channel-item'));
        const channel = channels.find(ch => ch.textContent.trim().substring(2) === channelName);
        
        if (channel) {
            const channelId = channel.dataset.channelId;
            return `<a href="#" class="channel-reference" onclick="window.switchChannel('${channelId}'); return false;">#${channelName}</a>`;
        }
        return match;
    });
}