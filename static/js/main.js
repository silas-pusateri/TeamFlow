document.addEventListener('DOMContentLoaded', function() {
    const messageContainer = document.getElementById('message-container');
    const messageInput = document.getElementById('message-input');
    const channelList = document.getElementById('channel-list');
    let currentChannel = null;

    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-theme');
        localStorage.setItem('theme', document.body.classList.contains('dark-theme') ? 'dark' : 'light');
    });

    // Load saved theme
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark-theme');
    }

    // Channel selection
    channelList.addEventListener('click', (e) => {
        if (e.target.classList.contains('channel-item')) {
            const channelId = e.target.dataset.channelId;
            switchChannel(channelId);
        }
    });

    // Message sending
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Reaction handling
    messageContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('reaction-btn')) {
            const messageId = e.target.closest('.message').dataset.messageId;
            const emoji = e.target.dataset.emoji;
            socket.emit('reaction', {
                message_id: messageId,
                emoji: emoji
            });
        }
    });

    // Thread view toggle
    messageContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('thread-toggle')) {
            const messageId = e.target.closest('.message').dataset.messageId;
            toggleThread(messageId);
        }
    });

    function sendMessage() {
        const content = messageInput.value.trim();
        if (content && currentChannel) {
            socket.emit('message', {
                content: content,
                channel_id: currentChannel
            });
            messageInput.value = '';
        }
    }

    function switchChannel(channelId) {
        if (currentChannel) {
            socket.emit('leave', { channel: currentChannel });
        }
        currentChannel = channelId;
        socket.emit('join', { channel: channelId });
        loadChannelMessages(channelId);
    }

    function loadChannelMessages(channelId) {
        fetch(`/api/channels/${channelId}/messages`)
            .then(response => response.json())
            .then(messages => {
                messageContainer.innerHTML = '';
                messages.forEach(message => renderMessage(message));
            });
    }

    function renderMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');
        messageElement.dataset.messageId = message.id;
        messageElement.innerHTML = `
            <div class="message-header">
                <span class="username">${message.user}</span>
                <span class="timestamp">${new Date(message.timestamp).toLocaleString()}</span>
            </div>
            <div class="message-content">${message.content}</div>
            <div class="message-actions">
                <button class="reaction-btn" data-emoji="👍">👍</button>
                <button class="reaction-btn" data-emoji="❤️">❤️</button>
                <button class="thread-toggle">Thread</button>
            </div>
            <div class="reactions"></div>
            <div class="thread-container" style="display: none;"></div>
        `;
        messageContainer.appendChild(messageElement);
    }

    function toggleThread(messageId) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        const threadContainer = messageElement.querySelector('.thread-container');
        threadContainer.style.display = threadContainer.style.display === 'none' ? 'block' : 'none';
    }
});
