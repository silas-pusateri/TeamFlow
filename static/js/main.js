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

    // Add click handler to existing send button
    const sendButton = document.querySelector('.send-button');
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }

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

    // User Status Popup handling
    let currentPopup = null;

    function createUserStatusPopup(userData) {
        const popup = document.createElement('div');
        popup.className = 'user-status-popup';

        const initials = userData.username.slice(0, 2).toUpperCase();
        const timeAgo = getTimeAgo(new Date(userData.last_seen));

        popup.innerHTML = `
            <div class="user-status-header">
                <div class="user-avatar">${initials}</div>
                <div class="user-info">
                    <div class="user-status-name">${userData.username}</div>
                    <div class="user-role">${userData.role || 'Member'}</div>
                    <div class="user-custom-status">
                        ${userData.status_emoji ? `<span class="status-emoji">${userData.status_emoji}</span>` : ''}
                        <span>${userData.custom_status || 'No status set'}</span>
                    </div>
                </div>
            </div>
            <div class="activity-section">
                <div class="activity-header">Activity Stats</div>
                <div class="activity-stats">
                    <div class="stat-item">
                        <div class="stat-value">${userData.stats.total_messages}</div>
                        <div class="stat-label">Messages</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${userData.stats.reactions_given}</div>
                        <div class="stat-label">Reactions</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${userData.stats.threads_participated}</div>
                        <div class="stat-label">Threads</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${userData.stats.bookmarks_count}</div>
                        <div class="stat-label">Bookmarks</div>
                    </div>
                </div>

                ${userData.recent_activity.length ? `
                    <div class="recent-activity">
                        <div class="activity-header">Recent Activity</div>
                        ${userData.recent_activity.map(activity => `
                            <div class="activity-item">
                                <div>${activity.content}</div>
                                <div class="activity-timestamp">${new Date(activity.timestamp).toLocaleString()}</div>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>

            <div class="user-presence">
                <span class="status-dot ${userData.is_online ? 'online' : 'offline'}"></span>
                ${userData.is_online ? 'Online' : `Last seen ${timeAgo}`}
            </div>
        `;

        return popup;
    }

    function getTimeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);

        const intervals = {
            year: 31536000,
            month: 2592000,
            week: 604800,
            day: 86400,
            hour: 3600,
            minute: 60
        };

        for (const [unit, secondsInUnit] of Object.entries(intervals)) {
            const interval = Math.floor(seconds / secondsInUnit);
            if (interval >= 1) {
                return `${interval} ${unit}${interval === 1 ? '' : 's'} ago`;
            }
        }

        return 'just now';
    }

    function showUserStatusPopup(event, userData) {
        // Remove any existing popup
        hideUserStatusPopup();

        const popup = createUserStatusPopup(userData);

        // Position the popup
        const rect = event.target.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const popupHeight = 400; // Approximate height of the popup

        // Calculate position
        let top = rect.bottom + 5;
        if (top + popupHeight > viewportHeight) {
            top = rect.top - popupHeight - 5;
        }

        popup.style.left = `${rect.left}px`;
        popup.style.top = `${top}px`;

        // Add to document
        document.body.appendChild(popup);
        currentPopup = popup;

        // Show with animation
        requestAnimationFrame(() => {
            popup.classList.add('active');
        });
    }

    function hideUserStatusPopup() {
        if (currentPopup) {
            currentPopup.remove();
            currentPopup = null;
        }
    }

    // Add hover handlers for usernames
    document.addEventListener('mouseover', (e) => {
        const usernameElement = e.target.closest('.username');
        if (usernameElement) {
            const username = usernameElement.textContent;
            // Emit socket event to get user status
            socket.emit('get_user_status', { username });
        }
    });

    document.addEventListener('mouseout', (e) => {
        const usernameElement = e.target.closest('.username');
        if (usernameElement) {
            hideUserStatusPopup();
        }
    });

    // Handle user status updates from server
    socket.on('user_status', (userData) => {
        const usernameElement = document.querySelector('.username:hover');
        if (usernameElement) {
            showUserStatusPopup({ target: usernameElement }, userData); // Fixed: Passing proper event object
        }
    });

    // Add status modal handling after the existing handlers
    const statusModal = document.getElementById('statusModal');
    const statusText = document.getElementById('statusText');
    const updateStatusBtn = document.getElementById('updateStatusBtn');
    let selectedEmoji = '';
    let currentUserId; // Declare currentUserId

    if (statusModal) {
        // Populate form with current status when modal opens
        statusModal.addEventListener('show.bs.modal', () => {
            const statusBtn = document.querySelector('[data-bs-target="#statusModal"]');
            if (statusBtn) {
                // Get current status text (remove emoji if present)
                const currentStatusText = statusBtn.textContent.trim();
                const statusMatch = currentStatusText.match(/(?:^|\s)([^📱💻🎯🏃🎮☕🎧🤔].*)$/);
                if (statusMatch) {
                    statusText.value = statusMatch[1].trim();
                }

                // Find and select current emoji if present
                const emojiMatch = currentStatusText.match(/([📱💻🎯🏃🎮☕🎧🤔])/);
                if (emojiMatch) {
                    selectedEmoji = emojiMatch[1];
                    document.querySelectorAll('.emoji-option').forEach(option => {
                        if (option.dataset.emoji === selectedEmoji) {
                            option.classList.add('selected');
                        }
                    });
                }
            }
        });

        // Reset form when modal is hidden
        statusModal.addEventListener('hidden.bs.modal', () => {
            statusText.value = '';
            selectedEmoji = '';
            document.querySelectorAll('.emoji-option').forEach(option => {
                option.classList.remove('selected');
            });
        });

        // Handle emoji selection
        statusModal.addEventListener('click', (e) => {
            const emojiOption = e.target.closest('.emoji-option');
            if (emojiOption) {
                // Remove previous selection
                document.querySelectorAll('.emoji-option').forEach(option => {
                    option.classList.remove('selected');
                });
                // Select new emoji
                emojiOption.classList.add('selected');
                selectedEmoji = emojiOption.dataset.emoji;
            }
        });

        // Handle status update
        updateStatusBtn.addEventListener('click', () => {
            const status = statusText.value.trim();
            socket.emit('update_custom_status', {
                status: status,
                emoji: selectedEmoji
            });

            // Close modal
            bootstrap.Modal.getInstance(statusModal).hide();
        });
    }

    // Handle status updates from server
    socket.on('user_status_updated', (data) => {
        // Update status button if it's the current user
        if (data.user_id === currentUserId) {
            const statusBtn = document.querySelector('[data-bs-target="#statusModal"]');
            if (statusBtn) {
                statusBtn.innerHTML = `
                    <span class="status-dot ${data.is_online ? 'online' : 'offline'}"></span>
                    ${data.status_emoji || ''} ${data.custom_status || 'Set status'}
                `;
            }
        }
    });

    // Update currentUserId when received from server
    socket.on('current_user', (data) => {
        currentUserId = data.user_id;
    });

    // Add these event handlers at the end of the DOMContentLoaded event listener
    // Search functionality
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const searchResultsModal = new bootstrap.Modal(document.getElementById('searchResultsModal'));
    const searchResults = document.getElementById('searchResults');
    const applyFilters = document.getElementById('applyFilters');
    const clearFilters = document.getElementById('clearFilters');
    const searchUserFilter = document.getElementById('searchUserFilter');
    const searchChannelFilter = document.getElementById('searchChannelFilter');
    const searchDateFrom = document.getElementById('searchDateFrom');
    const searchDateTo = document.getElementById('searchDateTo');
    const includeThreads = document.getElementById('includeThreads');

    // Populate channel filter dropdown
    socket.on('channel_list', (data) => {
        const channelFilter = document.getElementById('searchChannelFilter');
        if (channelFilter) {
            channelFilter.innerHTML = '<option value="">All Channels</option>' +
                data.channels.map(channel => 
                    `<option value="${channel.id}">${channel.name}</option>`
                ).join('');
        }
    });

    function performSearch() {
        const keyword = searchInput.value.trim();
        if (keyword) {
            const searchData = {
                keyword: keyword,
                username: searchUserFilter.value.trim(),
                channel_id: searchChannelFilter.value,
                date_from: searchDateFrom.value,
                date_to: searchDateTo.value,
                include_threads: includeThreads.checked
            };
            socket.emit('search_messages', searchData);
        }
    }

    if (searchBtn) {
        searchBtn.addEventListener('click', performSearch);
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    }

    if (applyFilters) {
        applyFilters.addEventListener('click', performSearch);
    }

    if (clearFilters) {
        clearFilters.addEventListener('click', () => {
            searchUserFilter.value = '';
            searchChannelFilter.value = '';
            searchDateFrom.value = '';
            searchDateTo.value = '';
            includeThreads.checked = true;  // Reset to true as it's the default
            performSearch();
        });
    }

    // Sync search input with modal
    searchBtn.addEventListener('click', () => {
        document.getElementById('modalSearchInput').value = searchInput.value;
    });

    // Update search when modal keywords change
    const modalSearchInput = document.getElementById('modalSearchInput');
    modalSearchInput.addEventListener('input', () => {
        searchInput.value = modalSearchInput.value;
    });
    
    modalSearchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            performSearch();
        }
    });

    socket.on('search_results', (data) => {
        if (searchResults) {
            if (data.results.length === 0) {
                searchResults.innerHTML = `
                    <div class="p-4 text-center">
                        <p>No messages found matching your search.</p>
                    </div>
                `;
            } else {
                searchResults.innerHTML = data.results.map(result => `
                    <div class="search-result-item">
                        <div class="search-result-header">
                            <span class="search-result-channel"># ${result.channel}</span>
                            <span class="search-result-timestamp">${new Date(result.timestamp).toLocaleString()}</span>
                        </div>
                        <div class="search-result-content">${result.content}</div>
                        <div class="search-result-user">
                            <span class="username" data-user-id="${result.user_id}">${result.user}</span>
                        </div>
                    </div>
                `).join('');
            }
            searchResultsModal.show();
        }
    });
});