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

    // Pin and Bookmark handling
    messageContainer.addEventListener('click', (e) => {
        const messageElement = e.target.closest('.message');
        if (!messageElement) return;

        const messageId = messageElement.dataset.messageId;

        if (e.target.classList.contains('pin-btn')) {
            socket.emit('pin_message', {
                message_id: messageId
            });
        } else if (e.target.classList.contains('bookmark-btn')) {
            socket.emit('bookmark_message', {
                message_id: messageId,
                note: '' // Optional note feature can be added later
            });
        } else if (e.target.classList.contains('reaction-btn')) {
            showEmojiPicker(messageId, e.target.getBoundingClientRect());
        }
    });

    // Create emoji picker element
    const emojiPicker = document.createElement('div');
    emojiPicker.className = 'emoji-picker';
    emojiPicker.style.display = 'none';
    document.body.appendChild(emojiPicker);

    const commonEmojis = ['👍', '❤️', '😊', '🎉', '👏', '🚀', '👌', '🔥', '✨', '😄', '🤔', '👀'];

    function showEmojiPicker(messageId, buttonRect) {
        emojiPicker.innerHTML = commonEmojis.map(emoji => 
            `<span class="emoji-option" data-emoji="${emoji}">${emoji}</span>`
        ).join('');

        emojiPicker.style.display = 'flex';
        const pickerRect = emojiPicker.getBoundingClientRect();

        // Position the picker near the reaction button
        emojiPicker.style.top = `${buttonRect.top - pickerRect.height}px`;
        emojiPicker.style.left = `${buttonRect.left}px`;

        // Store the message ID for the reaction handler
        emojiPicker.dataset.messageId = messageId;

        // Add click handlers for emoji selection
        const emojiOptions = emojiPicker.querySelectorAll('.emoji-option');
        emojiOptions.forEach(option => {
            option.addEventListener('click', handleEmojiSelect);
        });

        // Close picker when clicking outside
        document.addEventListener('click', handleClickOutside);
    }

    function handleEmojiSelect(e) {
        const emoji = e.target.dataset.emoji;
        const messageId = emojiPicker.dataset.messageId;
        socket.emit('reaction', {
            message_id: messageId,
            emoji: emoji
        });
        hideEmojiPicker();
    }

    function handleClickOutside(e) {
        if (!emojiPicker.contains(e.target) && !e.target.classList.contains('reaction-btn')) {
            hideEmojiPicker();
        }
    }

    function hideEmojiPicker() {
        emojiPicker.style.display = 'none';
        document.removeEventListener('click', handleClickOutside);
    }

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
                <button class="pin-btn ${message.is_pinned ? 'active' : ''}" title="${message.is_pinned ? `Pinned by ${message.pinned_by}` : 'Pin message'}">
                    <i class="feather-pin"></i>
                </button>
                <button class="bookmark-btn ${message.is_bookmarked ? 'active' : ''}" title="Bookmark message">
                    <i class="feather-bookmark"></i>
                </button>
                <button class="reaction-btn" title="Add reaction">
                    <i class="feather-smile"></i>
                </button>
            </div>
            <div class="reactions"></div>
            <div class="thread-container" style="display: none;"></div>
        `;
        messageContainer.appendChild(messageElement);
    }

    // Thread view toggle
    messageContainer.addEventListener('click', (e) => {
        if (e.target.classList.contains('thread-toggle')) {
            const messageId = e.target.closest('.message').dataset.messageId;
            toggleThread(messageId);
        }
    });

    function toggleThread(messageId) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        const threadContainer = messageElement.querySelector('.thread-container');
        threadContainer.style.display = threadContainer.style.display === 'none' ? 'block' : 'none';
    }
});