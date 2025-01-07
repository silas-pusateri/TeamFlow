document.addEventListener('DOMContentLoaded', function() {
    const messageContainer = document.getElementById('message-container');
    const messageInput = document.getElementById('message-input');
    const channelList = document.getElementById('channel-list');
    let currentChannel = null;
    let replyingTo = null;

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

    // Create reply context container
    const replyContext = document.createElement('div');
    replyContext.className = 'reply-context';
    replyContext.style.display = 'none';
    messageInput.parentElement.insertBefore(replyContext, messageInput);

    // Create cancel reply button
    const cancelReplyButton = document.createElement('button');
    cancelReplyButton.className = 'cancel-reply-btn';
    cancelReplyButton.innerHTML = '×';
    cancelReplyButton.addEventListener('click', cancelReply);
    replyContext.appendChild(cancelReplyButton);

    // Channel creation
    const createChannelBtn = document.getElementById('createChannelBtn');
    const channelNameInput = document.getElementById('channelName');
    const channelDescriptionInput = document.getElementById('channelDescription');
    const newChannelModal = document.getElementById('newChannelModal');
    const modal = new bootstrap.Modal(newChannelModal);

    createChannelBtn.addEventListener('click', () => {
        const name = channelNameInput.value.trim();
        const description = channelDescriptionInput.value.trim();

        if (name && description) {
            socket.emit('create_channel', { name, description });
            channelNameInput.value = '';
            channelDescriptionInput.value = '';
            modal.hide();
        }
    });

    socket.on('channel_created', (data) => {
        const channelList = document.getElementById('channel-list');
        const channelItem = document.createElement('li');
        channelItem.className = 'channel-item';
        channelItem.dataset.channelId = data.id;
        channelItem.textContent = `# ${data.name}`;
        channelList.appendChild(channelItem);
    });


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

    // Create send button
    const sendButton = document.createElement('button');
    sendButton.className = 'send-button';
    sendButton.innerHTML = '<i class="feather-send"></i>';
    sendButton.addEventListener('click', sendMessage);
    messageInput.parentElement.appendChild(sendButton);

    // Select first channel by default
    const firstChannel = channelList.querySelector('.channel-item');
    if (firstChannel) {
        const channelId = firstChannel.dataset.channelId;
        switchChannel(channelId);
    }

    function sendMessage() {
        const content = messageInput.value.trim();
        if (content && currentChannel) {
            const messageData = {
                content: content,
                channel_id: currentChannel
            };

            if (replyingTo) {
                messageData.parent_id = replyingTo.messageId;
            }

            socket.emit(replyingTo ? 'thread_reply' : 'message', messageData);
            messageInput.value = '';
            cancelReply();
        }
    }

    function switchChannel(channelId) {
        if (currentChannel) {
            socket.emit('leave', { channel: currentChannel });
        }

        // Clear messages before joining new channel
        messageContainer.innerHTML = `
            <div class="no-messages-placeholder">
                <p>No messages yet in this channel. Be the first to start a conversation! 💬</p>
            </div>
        `;

        currentChannel = channelId;
        socket.emit('join', { channel: channelId });

        // Reset reply state when switching channels
        cancelReply();

        // Highlight selected channel
        document.querySelectorAll('.channel-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.channelId === channelId) {
                item.classList.add('active');
            }
        });
    }

    // Message actions (Pin, Bookmark, Reaction)
    messageContainer.addEventListener('click', (e) => {
        const messageElement = e.target.closest('.message');
        if (!messageElement) return;

        const messageId = messageElement.dataset.messageId;

        if (e.target.classList.contains('reaction-btn')) {
            showEmojiPicker(messageId, e.target.getBoundingClientRect());
        } else if (e.target.classList.contains('reply-btn')) {
            const username = messageElement.querySelector('.username').textContent;
            const content = messageElement.querySelector('.message-content').textContent;
            setReplyContext(messageId, username, content);
        }
    });

    function setReplyContext(messageId, username, content) {
        replyingTo = { messageId, username, content };
        replyContext.style.display = 'flex';
        replyContext.innerHTML = `
            <div class="reply-info">
                <span class="reply-label">Replying to ${username}</span>
                <span class="reply-preview">${content.substring(0, 50)}${content.length > 50 ? '...' : ''}</span>
            </div>
            <button class="cancel-reply-btn" onclick="cancelReply()">×</button>
        `;
        messageInput.focus();
    }

    function cancelReply() {
        replyingTo = null;
        replyContext.style.display = 'none';
    }

    window.cancelReply = cancelReply;  // Make it accessible globally for the onclick handler

    // Create emoji picker element
    const emojiPicker = document.createElement('div');
    emojiPicker.className = 'emoji-picker';
    emojiPicker.style.display = 'none';
    document.body.appendChild(emojiPicker);

    const commonEmojis = ['👍', '❤️', '😊', '🎉', '👏', '🚀', '👌', '🔥', '✨', '😄', '🤔', '👀',
                         '😂', '🙌', '💯', '🎨', '💪', '🌟', '💡', '🎵', '🎮', '🍕', '☕', '🌈'];

    function showEmojiPicker(messageId, buttonRect) {
        emojiPicker.innerHTML = commonEmojis.map(emoji =>
            `<span class="emoji-option" data-emoji="${emoji}">${emoji}</span>`
        ).join('');

        emojiPicker.style.display = 'flex';

        // Position the picker near the reaction button
        const pickerRect = emojiPicker.getBoundingClientRect();
        const windowHeight = window.innerHeight;
        const windowWidth = window.innerWidth;

        // Calculate position to ensure the picker stays within viewport
        let top = buttonRect.top - pickerRect.height;
        let left = buttonRect.left;

        // Adjust if too close to top
        if (top < 10) {
            top = buttonRect.bottom + 5;
        }

        // Adjust if too close to right edge
        if (left + pickerRect.width > windowWidth - 10) {
            left = windowWidth - pickerRect.width - 10;
        }

        emojiPicker.style.top = `${top}px`;
        emojiPicker.style.left = `${left}px`;

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
});