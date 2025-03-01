document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const messageContainer = document.querySelector('.message-container') || createMessageContainer();
    const conversationList = document.getElementById('conversation-list');
    const newChatBtn = document.getElementById('new-chat-btn');
    const sidebar = document.getElementById('sidebar');
    const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
    const appContainer = document.querySelector('.app-container');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    
    let currentConversationId = null;
    let currentProvider = 'openai';
    
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
    
    // New chat button click handler
    newChatBtn.addEventListener('click', () => {
        currentConversationId = null;
        clearChatMessages();
        chatInput.focus();
        
        // Remove active class from all conversations
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });
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
    
    // Function to create message container if it doesn't exist
    function createMessageContainer() {
        const container = document.createElement('div');
        container.className = 'message-container';
        chatMessages.appendChild(container);
        return container;
    }
    
    // Function to send message and get response
    async function sendMessage(message) {
        // Add user message to chat
        addMessageToChat('user', message);
        
        // Show typing indicator
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'typing-indicator';
        typingIndicator.innerHTML = '<span></span><span></span><span></span>';
        messageContainer.appendChild(typingIndicator);
        
        // Scroll to bottom
        scrollToBottom();
        
        // Test artifact functionality
        if (message.toLowerCase().includes('show artifact')) {
            // Add a test artifact
            if (window.ArtifactsPanel) {
                setTimeout(() => {
                    window.ArtifactsPanel.addArtifact({
                        title: "Test Artifact",
                        description: "This is a test artifact created from your message",
                        type: "code",
                        content: "function testArtifact() {\n  console.log('This is a test artifact');\n  return 'Hello from the artifacts panel!';\n}"
                    });
                }, 1000);
            }
        }
        
        try {
            // Disable input while waiting for response
            chatInput.disabled = true;
            
            // Prepare request data
            const data = {
                message: message,
                conversation_id: currentConversationId,
                provider: currentProvider
            };
            
            // Get CSRF token
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            
            // Send request to server
            const response = await fetch('/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(data)
            });
            
            console.log('Response status:', response.status);
            console.log('Response headers:', Object.fromEntries([...response.headers.entries()]));
            
            // Check if the response is a stream
            const contentType = response.headers.get('content-type');
            console.log('Content-Type:', contentType);
            
            // Remove typing indicator
            typingIndicator.remove();
            
            if (response.ok) {
                try {
                    // Clone the response for debugging
                    const responseClone = response.clone();
                    const responseText = await responseClone.text();
                    console.log('Raw response text:', responseText);
                    
                    // Check if the response starts with "data: " which would indicate SSE format
                    if (responseText.trim().startsWith('data:')) {
                        console.log('Detected Server-Sent Events format');
                        // Handle SSE format - this is just a placeholder, you'll need to implement proper SSE handling
                        const jsonData = JSON.parse(responseText.replace(/^data: /, ''));
                        console.log('Parsed SSE data:', jsonData);
                        
                        // Process the data similar to the JSON response
                        const responseData = jsonData;
                        
                        // Update conversation ID if this is a new conversation
                        if (!currentConversationId && responseData.conversation_id) {
                            currentConversationId = responseData.conversation_id;
                            // Add the new conversation to the list
                            addConversationToList(responseData.conversation_id, message);
                        }
                        
                        // Add assistant's response to chat
                        addMessageToChat('assistant', responseData.response);
                        
                        // Handle artifacts if any
                        if (responseData.artifacts && responseData.artifacts.length > 0) {
                            responseData.artifacts.forEach(artifact => {
                                if (window.ArtifactsPanel) {
                                    window.ArtifactsPanel.addArtifact(artifact);
                                }
                            });
                        }
                    } else {
                        // Parse as regular JSON
                        const responseData = await response.json();
                        console.log('Parsed JSON response:', responseData);
                        
                        // Update conversation ID if this is a new conversation
                        if (!currentConversationId && responseData.conversation_id) {
                            currentConversationId = responseData.conversation_id;
                            // Add the new conversation to the list
                            addConversationToList(responseData.conversation_id, message);
                        }
                        
                        // Add assistant's response to chat
                        addMessageToChat('assistant', responseData.response);
                        
                        // Check if there are any artifacts in the response
                        if (responseData.artifacts && responseData.artifacts.length > 0) {
                            // Add each artifact to the panel
                            responseData.artifacts.forEach(artifact => {
                                // Check if ArtifactsPanel exists
                                if (window.ArtifactsPanel) {
                                    window.ArtifactsPanel.addArtifact(artifact);
                                }
                            });
                        }
                    }
                } catch (parseError) {
                    console.error('Error parsing response:', parseError);
                    console.error('Failed to parse response as JSON. Response might be in a different format.');
                    addMessageToChat('assistant', 'Sorry, I encountered an error processing the response.');
                }
                
                // Example of manually adding an artifact (for demonstration)
                // This would typically come from the backend response
                if (message.toLowerCase().includes('example') || message.toLowerCase().includes('artifact')) {
                    // Check if ArtifactsPanel exists
                    if (window.ArtifactsPanel) {
                        window.ArtifactsPanel.addArtifact({
                            title: "Example Artifact",
                            description: "This is an example artifact created from your message",
                            type: "code",
                            content: "function exampleCode() {\n  console.log('This is an example artifact');\n  return 'Hello from the artifacts panel!';\n}"
                        });
                    }
                }
            } else {
                // Handle error
                addMessageToChat('assistant', 'Sorry, I encountered an error processing your request.');
            }
        } catch (error) {
            console.error('Error:', error);
            // Remove typing indicator
            typingIndicator.remove();
            // Add error message
            addMessageToChat('assistant', 'Sorry, I encountered an error processing your request.');
        } finally {
            // Re-enable input
            chatInput.disabled = false;
            chatInput.focus();
            
            // Scroll to bottom
            scrollToBottom();
        }
    }
    
    // Function to add a message to the chat
    function addMessageToChat(role, content) {
        // Remove welcome message if it exists
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (role === 'assistant') {
            contentDiv.innerHTML = marked.parse(content);
        } else {
            contentDiv.textContent = content;
        }
        
        messageDiv.appendChild(contentDiv);
        messageContainer.appendChild(messageDiv);
        scrollToBottom();
    }
    
    // Function to clear chat messages
    function clearChatMessages() {
        messageContainer.innerHTML = `
            <div class="welcome-message">
                <h2>Welcome to LFG Chat</h2>
                <p>Start a conversation with the AI assistant below.</p>
            </div>
        `;
    }
    
    // Function to scroll chat to bottom
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Function to load conversations
    async function loadConversations() {
        try {
            const response = await fetch('/api/conversations/');
            const conversations = await response.json();
            
            conversationList.innerHTML = '';
            
            conversations.forEach(conversation => {
                const conversationItem = document.createElement('div');
                conversationItem.className = 'conversation-item';
                if (currentConversationId === conversation.id) {
                    conversationItem.classList.add('active');
                }
                
                conversationItem.textContent = conversation.title;
                conversationItem.dataset.id = conversation.id;
                
                conversationItem.addEventListener('click', () => {
                    loadConversation(conversation.id);
                });
                
                conversationList.appendChild(conversationItem);
            });
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    }
    
    // Function to load a specific conversation
    async function loadConversation(conversationId) {
        try {
            const response = await fetch(`/api/conversations/${conversationId}/`);
            const conversation = await response.json();
            
            currentConversationId = conversation.id;
            
            // Update active state in conversation list
            document.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.remove('active');
                if (parseInt(item.dataset.id) === conversation.id) {
                    item.classList.add('active');
                }
            });
            
            // Clear and load messages
            messageContainer.innerHTML = '';
            
            conversation.messages.forEach(message => {
                addMessageToChat(message.role, message.content);
            });
            
            scrollToBottom();
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    }

    // Function to set sidebar state
    function setSidebarState(collapsed) {
        if (collapsed) {
            appContainer.classList.add('sidebar-collapsed');
        } else {
            appContainer.classList.remove('sidebar-collapsed');
        }
        
        // Store in localStorage as a fallback
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

    // Toggle sidebar when button is clicked
    toggleSidebarBtn.addEventListener('click', () => {
        const isCurrentlyCollapsed = appContainer.classList.contains('sidebar-collapsed');
        setSidebarState(!isCurrentlyCollapsed);
    });

    // Close sidebar when overlay is clicked (mobile)
    sidebarOverlay.addEventListener('click', () => {
        appContainer.classList.remove('sidebar-open');
    });

    // Initialize sidebar state from user preference
    function initSidebarState() {
        // Check if we have a server-provided preference
        const serverPreference = document.body.dataset.sidebarCollapsed === 'true';
        
        // If not, fall back to localStorage
        const localPreference = localStorage.getItem('sidebar_collapsed') === 'true';
        
        // Apply the preference
        setSidebarState(serverPreference || localPreference);
    }

    // Add a mobile toggle button
    function addMobileToggle() {
        const mobileToggle = document.createElement('button');
        mobileToggle.className = 'mobile-sidebar-toggle';
        mobileToggle.innerHTML = '☰';
        mobileToggle.addEventListener('click', () => {
            appContainer.classList.toggle('sidebar-open');
        });
        document.body.appendChild(mobileToggle);
    }

    // Call the initialization functions
    initSidebarState();
    if (window.innerWidth <= 768) {
        addMobileToggle();
    }

    // Helper function to get CSRF token
    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }

    // Function to add a conversation to the list
    function addConversationToList(conversationId, title) {
        // Check if conversation already exists in the list
        const existingConversation = document.querySelector(`.conversation-item[data-id="${conversationId}"]`);
        if (existingConversation) {
            // If it exists, just make it active
            document.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.remove('active');
            });
            existingConversation.classList.add('active');
            return;
        }
        
        // Create a new conversation item
        const conversationItem = document.createElement('div');
        conversationItem.className = 'conversation-item active';
        conversationItem.setAttribute('data-id', conversationId);
        
        // Truncate title if it's too long
        const truncatedTitle = title.length > 30 ? title.substring(0, 27) + '...' : title;
        
        conversationItem.innerHTML = `
            <div class="conversation-title">${truncatedTitle}</div>
            <div class="conversation-actions">
                <button class="delete-conversation" data-id="${conversationId}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        
        // Add click event to load the conversation
        conversationItem.addEventListener('click', (e) => {
            // Ignore if delete button was clicked
            if (e.target.closest('.delete-conversation')) return;
            
            // Remove active class from all conversations
            document.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.remove('active');
            });
            
            // Add active class to this conversation
            conversationItem.classList.add('active');
            
            // Load the conversation
            loadConversation(conversationId);
        });
        
        // Add delete button functionality
        const deleteBtn = conversationItem.querySelector('.delete-conversation');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteConversation(conversationId);
            });
        }
        
        // Add to the beginning of the list
        if (conversationList.firstChild) {
            conversationList.insertBefore(conversationItem, conversationList.firstChild);
        } else {
            conversationList.appendChild(conversationItem);
        }
        
        // Remove active class from all other conversations
        document.querySelectorAll('.conversation-item').forEach(item => {
            if (item !== conversationItem) {
                item.classList.remove('active');
            }
        });
    }
}); 