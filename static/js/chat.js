document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const messageContainer = document.querySelector('.message-container') || createMessageContainer();
    const conversationList = document.getElementById('conversation-list');
    const newChatBtn = document.getElementById('new-chat-btn');
    const backBtn = document.getElementById('back-btn');
    const sidebar = document.getElementById('sidebar');
    const appContainer = document.querySelector('.app-container');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    
    let currentConversationId = null;
    let currentProvider = 'openai';
    let currentProjectId = null;
    let socket = null;
    let isSocketConnected = false;
    let messageQueue = [];
    let isStreaming = false; // Track whether we're currently streaming a response
    let stopRequested = false; // Track if user has already requested to stop generation
    
    // Get or create the send button
    const sendBtn = document.getElementById('send-btn') || createSendButton();
    let stopBtn = null; // Will be created when needed
    
    // Extract project ID from path if in format /chat/project/{id}/
    function extractProjectIdFromPath() {
        const pathParts = window.location.pathname.split('/').filter(part => part);
        if (pathParts.length >= 3 && pathParts[0] === 'chat' && pathParts[1] === 'project') {
            return pathParts[2];
        }
        return null;
    }
    
    // Check for conversation ID in the URL or from Django template
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('conversation_id')) {
        currentConversationId = urlParams.get('conversation_id');
    } else if (typeof initialConversationId !== 'undefined' && initialConversationId) {
        currentConversationId = initialConversationId;
    }
    
    // Check for project ID from different sources
    if (urlParams.has('project_id')) {
        currentProjectId = urlParams.get('project_id');
    } else if (typeof initialProjectId !== 'undefined' && initialProjectId) {
        currentProjectId = initialProjectId;
    } else {
        // Try to extract from path
        const pathProjectId = extractProjectIdFromPath();
        if (pathProjectId) {
            currentProjectId = pathProjectId;
            console.log('Extracted project ID from path:', currentProjectId);
        }
    }
    
    // Initialize WebSocket connection
    connectWebSocket();
    
    // Auto-resize the text area based on content
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
    
    // Handle Enter key press in the textarea
    chatInput.addEventListener('keydown', function(e) {
        // Check if Enter was pressed without Shift key (Shift+Enter allows for new lines)
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Prevent the default behavior (new line)
            const message = this.value.trim();
            if (message) {
                sendMessage(message);
                this.value = '';
                this.style.height = 'auto';
            }
        }
    });
    
    // Load conversation history on page load
    loadConversations();
    
    // If we have a conversation ID, load that conversation
    if (currentConversationId) {
        loadConversation(currentConversationId);
    }
    
    // New chat button click handler
    newChatBtn.addEventListener('click', () => {
        // Reset conversation ID but keep project ID if it's from URL
        currentConversationId = null;
        
        // Check if we should maintain the project ID
        const urlParams = new URLSearchParams(window.location.search);
        console.log('Url Params:', urlParams);
        const urlProjectId = urlParams.get('project_id');
        const pathProjectId = extractProjectIdFromPath();
        
        // Only reset project ID if it's not specified in URL or path
        if (!urlProjectId && !pathProjectId) {
            currentProjectId = null;
        } else if (pathProjectId && !currentProjectId) {
            // Update currentProjectId if it was found in the path but wasn't set
            currentProjectId = pathProjectId;
        }
        
        // Clear chat messages and show welcome message
        clearChatMessages();
        
        // Add welcome message
        const welcomeMessage = document.createElement('div');
        welcomeMessage.className = 'welcome-message';
        welcomeMessage.innerHTML = '<h2>LFG 🚀🚀</h2><p>Start a conversation with the AI assistant below.</p>';
        messageContainer.appendChild(welcomeMessage);
        
        // Reset WebSocket connection to ensure clean session
        connectWebSocket();
        
        // Update URL handling
        if (pathProjectId) {
            // If we're in path format, keep the same URL format but remove conversation_id param
            const url = new URL(window.location);
            url.searchParams.delete('conversation_id');
            window.history.pushState({}, '', url);
        } else {
            // Normal handling for query param style URLs
            const url = new URL(window.location);
            url.searchParams.delete('conversation_id');
            // Only remove project_id from URL if it's not specified
            if (!urlProjectId) {
                url.searchParams.delete('project_id');
            }
            window.history.pushState({}, '', url);
        }
        
        // Remove active class from all conversations in sidebar
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Focus on input for immediate typing
        chatInput.focus();
        
        console.log('New chat session started with project ID:', currentProjectId);
    });
    
    // Submit message when form is submitted
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (message) {
            sendMessage(message);
            chatInput.value = '';
            chatInput.style.height = 'auto';
        }
    });
    
    // Set up provider selection
    const providerOptions = document.querySelectorAll('input[name="ai-provider"]');
    providerOptions.forEach(option => {
        option.addEventListener('change', function() {
            if (this.checked) {
                currentProvider = this.value;
                console.log(`Switched to ${currentProvider} provider`);
            }
        });
    });
    
    // Back button click handler
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            window.location.href = '/projects/';
        });
    }
    
    // Window event listeners for WebSocket
    window.addEventListener('beforeunload', () => {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.close();
        }
    });
    
    // Function to connect WebSocket and receive messages
    function connectWebSocket() {
        // Determine if we're on HTTPS or HTTP
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat/`;

        console.log('Current Project ID:', currentProjectId);
        console.log('URL path:', window.location.pathname);
        console.log('URL params:', window.location.search);
        
        // Add conversation ID and project ID as query parameters if available
        let wsUrlWithParams = wsUrl;
        const urlParams = [];
        
        if (currentConversationId) {
            urlParams.push(`conversation_id=${currentConversationId}`);
        }
        
        if (currentProjectId) {
            urlParams.push(`project_id=${currentProjectId}`);
            console.log('Adding project_id to WebSocket URL:', currentProjectId);
        } else {
            console.warn('No project_id available for WebSocket connection!');
            // Try once more to get project ID from path as a fallback
            const pathProjectId = extractProjectIdFromPath();
            if (pathProjectId) {
                currentProjectId = pathProjectId;
                urlParams.push(`project_id=${currentProjectId}`);
                console.log('Found and added project_id from path:', currentProjectId);
            }
        }
        
        if (urlParams.length > 0) {
            wsUrlWithParams = `${wsUrl}?${urlParams.join('&')}`;
        }
        
        console.log('Connecting to WebSocket:', wsUrlWithParams);
        
        // Close existing socket if it exists
        if (socket) {
            socket.close();
        }
        
        socket = new WebSocket(wsUrlWithParams);
        
        socket.onopen = function(e) {
            console.log('WebSocket connection established');
            isSocketConnected = true;
            
            // Send any queued messages
            while (messageQueue.length > 0) {
                const queuedMessage = messageQueue.shift();
                socket.send(JSON.stringify(queuedMessage));
            }
        };
        
        socket.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);
            
            // Log message content for troubleshooting empty messages
            if (data.type === 'ai_chunk' && data.is_final) {
                console.log('Final AI chunk received - conversation saved');
            } else if (data.type === 'ai_chunk' && data.chunk === '') {
                console.log('Empty AI chunk received - this may be a typing indicator');
            } else if (data.type === 'message' && (!data.message || data.message.trim() === '')) {
                console.warn('Empty message content received in message event:', data);
            }
            
            switch (data.type) {
                case 'chat_history':
                    // Handle chat history
                    clearChatMessages();
                    data.messages.forEach(msg => {
                        // Skip empty messages
                        if (msg.content && msg.content.trim() !== '') {
                            addMessageToChat(msg.role, msg.content);
                        }
                    });
                    scrollToBottom();
                    break;
                    
                case 'message':
                    // Handle complete message
                    addMessageToChat(data.sender, data.message);
                    scrollToBottom();
                    break;
                    
                case 'ai_chunk':
                    // Handle AI response chunk for streaming
                    // Skip entirely empty chunks that aren't typing indicators or final messages
                    if (data.chunk === '' && !data.is_final && document.querySelector('.message.assistant:last-child')) {
                        console.log('Skipping empty non-final chunk');
                        break;
                    }
                    
                    handleAIChunk(data);
                    break;
                
                case 'stop_confirmed':
                    // Handle confirmation that generation was stopped
                    console.log('Generation stopped by server');
                    
                    // If the user has already processed the stop locally, don't do anything
                    if (!stopRequested) {
                        // Remove typing indicator if it exists
                        const typingIndicator = document.querySelector('.typing-indicator');
                        if (typingIndicator) {
                            typingIndicator.remove();
                        }
                        
                        // Check if there's an assistant message, if not add one
                        const assistantMessage = document.querySelector('.message.assistant:last-child');
                        if (!assistantMessage) {
                            // No message was created yet, so create one with the stopped message
                            addMessageToChat('system', '*Generation stopped by server*');
                        }
                        
                        // Re-enable input and restore send button
                        chatInput.disabled = false;
                        hideStopButton();
                    }
                    
                    // Reset the flag
                    stopRequested = false;
                    break;
                    
                case 'error':
                    console.error('WebSocket error:', data.message);
                    // Display error message to user
                    const errorMsg = document.createElement('div');
                    errorMsg.className = 'error-message';
                    errorMsg.textContent = data.message;
                    messageContainer.appendChild(errorMsg);
                    scrollToBottom();
                    
                    // In case of error, restore UI
                    chatInput.disabled = false;
                    hideStopButton();
                    break;
                    
                default:
                    console.log('Unknown message type:', data.type);
            }
        };
        
        socket.onclose = function(event) {
            if (event.wasClean) {
                console.log(`WebSocket connection closed cleanly, code=${event.code}, reason=${event.reason}`);
            } else {
                console.error('WebSocket connection died');
                
                // Attempt to reconnect after a delay
                setTimeout(() => {
                    isSocketConnected = false;
                    console.log('Attempting to reconnect...');
                    connectWebSocket();
                }, 3000);
            }
        };
        
        socket.onerror = function(error) {
            console.error('WebSocket error:', error);
            isSocketConnected = false;
        };
    }
    
    // Function to handle AI response chunks
    function handleAIChunk(data) {
        const chunk = data.chunk;
        const isFinal = data.is_final;
        const isNotification = data.is_notification;
        
        if (isFinal) {
            // Final chunk with metadata
            console.log('AI response complete');
            
            // Skip creating a message if it's empty (likely just the final signal after a stop)
            if (chunk === '' && document.querySelector('.message.system:last-child')) {
                console.log('Skipping empty final chunk after stopped generation');
            }
            
            // Update conversation ID and other metadata if provided
            if (data.conversation_id) {
                currentConversationId = data.conversation_id;
                
                // Update URL with conversation ID
                const url = new URL(window.location);
                url.searchParams.set('conversation_id', currentConversationId);
                window.history.pushState({}, '', url);
            }
            
            if (data.provider) {
                currentProvider = data.provider;
            }
            
            if (data.project_id) {
                currentProjectId = data.project_id;
            }
            
            // Re-enable the input
            chatInput.disabled = false;
            chatInput.focus();
            
            // Restore send button
            hideStopButton();
            
            // Reset the stop requested flag
            stopRequested = false;
            
            // Reload the conversations list to include the new one
            loadConversations();
            return;
        }
        
        // Handle notifications
        if (isNotification) {
            console.log('Received notification:', data);
            
            // Make sure artifacts panel is visible
            if (window.ArtifactsPanel && typeof window.ArtifactsPanel.toggle === 'function') {
                window.ArtifactsPanel.toggle();
            }
            
            // Switch to the appropriate tab
            if (window.switchTab && data.notification_type) {
                window.switchTab(data.notification_type);
                
                // Load the content for that tab if we have a project ID
                if (currentProjectId) {
                    if (data.notification_type === 'features' && 
                        window.ArtifactsLoader && 
                        typeof window.ArtifactsLoader.loadFeatures === 'function') {
                        window.ArtifactsLoader.loadFeatures(currentProjectId);
                    } else if (data.notification_type === 'personas' && 
                              window.ArtifactsLoader && 
                              typeof window.ArtifactsLoader.loadPersonas === 'function') {
                        window.ArtifactsLoader.loadPersonas(currentProjectId);
                    }
                }
            }
            return;
        }
        
        if (!chunk) {
            // This is just a typing indicator
            const typingIndicator = document.querySelector('.typing-indicator');
            if (!typingIndicator) {
                const indicator = document.createElement('div');
                indicator.className = 'typing-indicator';
                indicator.innerHTML = '<span></span><span></span><span></span>';
                messageContainer.appendChild(indicator);
                scrollToBottom();
            }
            return;
        }
        
        // Get or create the assistant message
        const assistantMessage = document.querySelector('.message.assistant:last-child');
        if (assistantMessage) {
            // Add to existing message
            const existingContent = assistantMessage.querySelector('.message-content');
            const currentContent = existingContent.getAttribute('data-raw-content') || '';
            const newContent = currentContent + chunk;
            
            // Store raw content and render with markdown
            existingContent.setAttribute('data-raw-content', newContent);
            existingContent.innerHTML = marked.parse(newContent);
        } else {
            // Remove typing indicator if present
            const typingIndicator = document.querySelector('.typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
            
            // Create new message
            addMessageToChat('assistant', chunk);
        }
        
        scrollToBottom();
    }
    
    // Function to create message container if it doesn't exist
    function createMessageContainer() {
        const container = document.createElement('div');
        container.className = 'message-container';
        chatMessages.appendChild(container);
        return container;
    }
    
    // Function to create send button if it doesn't exist
    function createSendButton() {
        const btn = document.createElement('button');
        btn.id = 'send-btn';
        btn.type = 'submit';
        btn.className = 'send-btn';
        btn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        btn.title = 'Send message';
        chatForm.appendChild(btn);
        return btn;
    }
    
    // Function to create and show stop button
    function showStopButton() {
        // Create stop button if it doesn't exist
        if (!stopBtn) {
            stopBtn = document.createElement('button');
            stopBtn.id = 'stop-btn';
            stopBtn.type = 'button';
            stopBtn.className = 'stop-btn';
            stopBtn.innerHTML = '<i class="fas fa-stop"></i>';
            stopBtn.title = 'Stop generating';
            
            // Add event listener to stop button
            stopBtn.addEventListener('click', stopGeneration);
            
            // Insert after (or in place of) the send button
            chatForm.appendChild(stopBtn);
        }
        
        // Show stop button, hide send button
        sendBtn.style.display = 'none';
        stopBtn.style.display = 'block';
        isStreaming = true;
    }
    
    // Function to hide stop button and show send button
    function hideStopButton() {
        if (stopBtn) {
            stopBtn.style.display = 'none';
        }
        sendBtn.style.display = 'block';
        isStreaming = false;
    }
    
    // Function to stop the generation
    function stopGeneration() {
        if (socket && socket.readyState === WebSocket.OPEN && !stopRequested) {
            // Set flag to indicate stop has been requested
            stopRequested = true;
            
            const stopMessage = {
                type: 'stop_generation',
                conversation_id: currentConversationId,
                project_id: currentProjectId
            };
            socket.send(JSON.stringify(stopMessage));
            console.log('Stop generation message sent');
            
            // Remove typing indicator if it exists
            const typingIndicator = document.querySelector('.typing-indicator');
            if (typingIndicator) {
                typingIndicator.remove();
            }
            
            // Add a note that generation was stopped
            const assistantMessage = document.querySelector('.message.assistant:last-child');
            if (assistantMessage) {
                const contentDiv = assistantMessage.querySelector('.message-content');
                const currentContent = contentDiv.getAttribute('data-raw-content') || '';
                const newContent = currentContent + '\n\n*Generation stopped by user*';
                
                contentDiv.setAttribute('data-raw-content', newContent);
                contentDiv.innerHTML = marked.parse(newContent);
            } else {
                // If there's no assistant message yet, create one with the stopped message
                addMessageToChat('system', '*Generation stopped by user*');
            }
            
            // Reset UI - enable input and restore send button
            chatInput.disabled = false;
            hideStopButton();
        }
    }
    
    // Function to send message using WebSocket
    function sendMessage(message) {
        console.log('sendMessage: Starting to send message:', message);
        
        // Reset stop requested flag
        stopRequested = false;
        
        // Add user message to chat
        addMessageToChat('user', message);
        
        // Show typing indicator
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'typing-indicator';
        typingIndicator.innerHTML = '<span></span><span></span><span></span>';
        messageContainer.appendChild(typingIndicator);
        console.log('sendMessage: Added typing indicator');
        
        // Scroll to bottom
        scrollToBottom();
        
        // Disable input while waiting for response
        chatInput.disabled = true;
        
        // Show stop button since we're about to start streaming
        showStopButton();
        
        // Prepare message data
        const messageData = {
            type: 'message',
            message: message,
            conversation_id: currentConversationId,
            provider: currentProvider,
            project_id: currentProjectId
        };
        
        // Add project_id if available
        if (currentProjectId) {
            messageData.project_id = currentProjectId;
        }
        
        console.log('sendMessage: Message data:', messageData);
        
        // Send via WebSocket if connected, otherwise queue
        if (isSocketConnected && socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(messageData));
        } else {
            console.log('WebSocket not connected, queueing message');
            messageQueue.push(messageData);
            
            // Try to reconnect
            if (!isSocketConnected) {
                connectWebSocket();
            }
        }
    }
    
    // Function to add a message to the chat
    function addMessageToChat(role, content) {
        // Skip adding empty messages
        if (!content || content.trim() === '') {
            console.log(`Skipping empty ${role} message`);
            return;
        }
        
        // Create message element
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        // Create message content
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.setAttribute('data-raw-content', content);
        
        // Use marked.js to render markdown for assistant messages
        if (role === 'assistant' || role === 'system') {
            contentDiv.innerHTML = marked.parse(content);
        } else {
            // For user messages, just escape HTML and replace newlines with <br>
            contentDiv.textContent = content;
        }
        
        // Append elements
        messageDiv.appendChild(contentDiv);
        messageContainer.appendChild(messageDiv);
        
        // Remove typing indicator if it exists
        const typingIndicator = document.querySelector('.typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }
    
    // Function to clear all messages from the chat
    function clearChatMessages() {
        messageContainer.innerHTML = '';
    }
    
    // Function to scroll to the bottom of the chat
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Function to load conversation list
    async function loadConversations() {
        try {
            // First check path for project ID since we're in project context
            const pathProjectId = extractProjectIdFromPath();
            
            if (!pathProjectId) {
                throw new Error('No project ID found in path. Expected format: /chat/project/{id}/');
            }
            
            // Build the URL with project_id
            const url = `/api/projects/${pathProjectId}/conversations/`;
            console.log('Loading conversations for project:', pathProjectId);
            
            const response = await fetch(url);
            const conversations = await response.json();
            
            // Clear the conversation list
            conversationList.innerHTML = '';
            
            // Add conversations to the list
            conversations.forEach(conversation => {
                const conversationItem = createCompactConversationItem(conversation);
                
                // Add active class if this is the current conversation
                if (conversation.id === currentConversationId) {
                    conversationItem.classList.add('active');
                }
                
                // Add click handler
                conversationItem.addEventListener('click', () => {
                    loadConversation(conversation.id);
                });
                
                // Add delete handler
                const deleteBtn = conversationItem.querySelector('.delete-conversation-btn');
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteConversation(conversation.id);
                });
                
                conversationList.appendChild(conversationItem);
            });
            
            // If sidebar is empty, add a message
            if (conversations.length === 0) {
                const emptyMessage = document.createElement('div');
                emptyMessage.className = 'empty-conversations-message';
                emptyMessage.textContent = 'No conversations yet. Start chatting!';
                conversationList.appendChild(emptyMessage);
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    }
    
    // Function to load a specific conversation
    async function loadConversation(conversationId) {
        try {
            const response = await fetch(`/api/conversations/${conversationId}/`);
            const data = await response.json();
            
            // Set current conversation ID
            currentConversationId = conversationId;
            
            // Clear chat
            clearChatMessages();
            
            // Set project ID if this conversation is linked to a project
            if (data.project) {
                currentProjectId = data.project.id;
            }
            
            // Add each message to the chat
            data.messages.forEach(message => {
                // Skip empty messages and show all non-empty messages
                if (message.content && message.content.trim() !== '') {
                    addMessageToChat(message.role, message.content);
                }
            });
            
            // Mark this conversation as active in the sidebar
            document.querySelectorAll('.conversation-item').forEach(item => {
                if (item.dataset.id === conversationId) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
            
            // Check if we're in project path format
            const pathProjectId = extractProjectIdFromPath();
            
            // Update URL appropriately based on format
            if (pathProjectId) {
                // If we're already in path format, just add conversation_id as query param
                const url = new URL(window.location);
                url.searchParams.set('conversation_id', conversationId);
                window.history.pushState({}, '', url);
            } else {
                // Standard query param format
                const url = new URL(window.location);
                url.searchParams.set('conversation_id', conversationId);
                if (currentProjectId) {
                    url.searchParams.set('project_id', currentProjectId);
                }
                window.history.pushState({}, '', url);
            }
            
            // Scroll to bottom
            scrollToBottom();
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    }

    // Function to set sidebar state
    function setSidebarState(collapsed) {
        const sidebar = document.getElementById('sidebar');
        
        if (collapsed) {
            sidebar.classList.remove('expanded');
            appContainer.classList.remove('sidebar-expanded');
        } else {
            sidebar.classList.add('expanded');
            appContainer.classList.add('sidebar-expanded');
        }
        
        // Store in localStorage
        localStorage.setItem('sidebar_collapsed', collapsed);
        
        // Save to server if user is logged in
        if (document.body.dataset.userAuthenticated === 'true') {
            fetch('/api/toggle-sidebar/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({ collapsed: collapsed }),
            });
        }
    }

    // Close sidebar when overlay is clicked (mobile)
    sidebarOverlay.addEventListener('click', () => {
        setSidebarState(true); // Collapse sidebar
    });

    // Add a mobile toggle button
    function addMobileToggle() {
        const mobileToggle = document.createElement('button');
        mobileToggle.className = 'mobile-sidebar-toggle';
        mobileToggle.innerHTML = '☰';
        mobileToggle.addEventListener('click', () => {
            const sidebar = document.getElementById('sidebar');
            const isCurrentlyExpanded = sidebar.classList.contains('expanded');
            setSidebarState(isCurrentlyExpanded); // Toggle sidebar state
        });
        document.body.appendChild(mobileToggle);
    }

    // Call the initialization functions
    if (window.innerWidth <= 768) {
        addMobileToggle();
    }

    // Helper function to get CSRF token
    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    // Function to delete a conversation
    async function deleteConversation(conversationId) {
        if (!confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
            return;
        }
        
        try {
            // Get CSRF token
            const csrfToken = getCsrfToken();
            
            // Send delete request
            const response = await fetch(`/api/conversations/${conversationId}/`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            });
            
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }
            
            // Remove from DOM
            const conversationItem = document.querySelector(`.conversation-item[data-id="${conversationId}"]`);
            if (conversationItem) {
                conversationItem.remove();
            }
            
            // If this was the active conversation, clear the chat
            if (currentConversationId === conversationId) {
                currentConversationId = null;
                clearChatMessages();
                chatInput.focus();
                
                // Clear URL parameter
                const url = new URL(window.location);
                url.searchParams.delete('conversation_id');
                window.history.pushState({}, '', url);
            }
            
            // Refresh conversation list
            loadConversations();
            
        } catch (error) {
            console.error('Error deleting conversation:', error);
            alert('Failed to delete conversation. Please try again.');
        }
    }

    // Modify the function that creates conversation items to be even more compact
    function createCompactConversationItem(conversation) {
        const conversationItem = document.createElement('div');
        conversationItem.className = 'conversation-item';
        conversationItem.dataset.id = conversation.id;
        
        // Truncate title to be compact
        let title = conversation.title || `Chat ${conversation.id}`;
        if (title.length > 20) { // Allow slightly longer titles since we don't show project badges
            title = title.substring(0, 20) + '...';
        }
        
        // Create minimal HTML structure without project badges
        conversationItem.innerHTML = `
            <div class="conversation-title" title="${conversation.title}">${title}</div>
            <button class="delete-conversation-btn" title="Delete">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        return conversationItem;
    }
});
