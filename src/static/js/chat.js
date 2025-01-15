// Add file upload handling
const fileInput = document.getElementById('file-upload');
const messageInput = document.getElementById('message-input');
const sendButton = document.querySelector('.send-button');
let selectedFile = null;
let currentChannelId = null;
let processedMessageIds = new Set(); // Track processed message IDs

// Update file input event listener
fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (file) {
        if (file.size > 16 * 1024 * 1024) { // 16MB limit
            alert('File size must be less than 16MB');
            fileInput.value = '';
            selectedFile = null;
            return;
        }
        selectedFile = file;
        
        // If a file is selected without a message, send it immediately
        if (!messageInput.value.trim()) {
            await sendMessage('', currentChannelId);
        }
    }
});

// Handle sending messages
sendButton.addEventListener('click', () => {
    const content = messageInput.value.trim();
    if (content || selectedFile) {
        sendMessage(content, currentChannelId);
        messageInput.value = '';
    }
});

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const content = messageInput.value.trim();
        if (content || selectedFile) {
            sendMessage(content, currentChannelId);
            messageInput.value = '';
        }
    }
});

// Update send message function
async function sendMessage(content, channelId) {
    if (!channelId) {
        console.error('No channel selected');
        return;
    }

    let messageData = {
        content: content,
        channel_id: channelId
    };

    if (selectedFile) {
        try {
            // Convert file to base64
            const base64Data = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = () => reject(reader.error);
                reader.readAsDataURL(selectedFile);
            });

            messageData.file = {
                name: selectedFile.name,
                type: selectedFile.type,
                data: base64Data
            };
        } catch (error) {
            console.error('Error processing file:', error);
            alert('Failed to process file');
            return;
        }
    }

    try {
        // Emit the message through socket.io
        socket.emit('message', messageData);
        
        // Clear the file input and selected file
        if (selectedFile) {
            fileInput.value = '';
            selectedFile = null;
        }
    } catch (error) {
        console.error('Error sending message:', error);
        alert('Failed to send message');
    }
}

// Update the channel switching function to store current channel
function switchChannel(channelId) {
    if (currentChannelId) {
        socket.emit('leave', { channel: currentChannelId });
    }
    currentChannelId = channelId;
    socket.emit('join', { channel: channelId });
    // Clear processed message IDs when switching channels
    processedMessageIds.clear();
}

// Export the message display function for use in websocket.js
window.displayMessage = function(message) {
    // Check if message has already been processed
    if (processedMessageIds.has(message.id)) {
        return null;
    }
    processedMessageIds.add(message.id);

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message';
    messageDiv.id = `message-${message.id}`;

    let messageContent = `
        <div class="message-header">
            <span class="username">${escapeHtml(message.user)}</span>
            <span class="timestamp">${formatTimestamp(message.timestamp)}</span>
        </div>
        <div class="message-content">
    `;

    // Add file attachment if present
    if (message.file) {
        const fileType = message.file.type ? message.file.type.toLowerCase() : '';
        const isImage = ['jpg', 'jpeg', 'png', 'gif'].some(ext => fileType.includes(ext));
        
        messageContent += `
            <div class="file-attachment">
                <div class="file-info">
                    <i class="fas fa-${isImage ? 'image' : 'file'}"></i>
                    <span class="file-name">${escapeHtml(message.file.name)}</span>
                    ${fileType ? `<span class="file-type">${escapeHtml(fileType)}</span>` : ''}
                </div>
                ${isImage ? `
                    <div class="image-preview">
                        <a href="${message.file.path}" target="_blank">
                            <img src="${message.file.path}" alt="${escapeHtml(message.file.name)}" class="attachment-preview">
                        </a>
                    </div>
                ` : `
                    <a href="${message.file.path}" target="_blank" class="file-link">
                        Download File
                    </a>
                `}
            </div>
        `;
    }

    // Add message content after file attachment if present
    if (message.content) {
        messageContent += `<p class="message-text">${escapeHtml(message.content)}</p>`;
    }

    messageContent += '</div>';
    messageDiv.innerHTML = messageContent;
    
    return messageDiv;
}

// Helper function to escape HTML
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Helper function to format timestamp
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

// Add socket error handler
socket.on('error', (error) => {
    console.error('Socket error:', error);
    alert(error.message || 'An error occurred');
}); 