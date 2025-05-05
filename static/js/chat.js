document.addEventListener('DOMContentLoaded', () => {
    // Check if the artifacts panel is in the DOM
    const artifactsPanel = document.getElementById('artifacts-panel');
    if (artifactsPanel) {
        console.log('✅ Artifacts panel found in DOM');
    } else {
        console.error('❌ Artifacts panel NOT found in DOM! This will cause issues with notifications.');
    }
    
    // Check if the ArtifactsPanel API is available
    if (window.ArtifactsPanel && typeof window.ArtifactsPanel.toggle === 'function') {
        console.log('✅ ArtifactsPanel API is available');
    } else {
        console.log('❌ ArtifactsPanel API is NOT available yet. This may be a timing issue.');
        // We'll check again after a delay to see if it's a timing issue
        setTimeout(() => {
            if (window.ArtifactsPanel && typeof window.ArtifactsPanel.toggle === 'function') {
                console.log('✅ ArtifactsPanel API is now available (after delay)');
            } else {
                console.error('❌ ArtifactsPanel API is still NOT available after delay. Check script loading order.');
            }
        }, 1000);
    }
    
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
            if (message || window.attachedFile) {
                sendMessage(message);
                this.value = '';
                this.style.height = 'auto';
                
                // Clear file attachment if exists
                const fileAttachmentIndicator = document.querySelector('.input-file-attachment');
                if (fileAttachmentIndicator) {
                    fileAttachmentIndicator.remove();
                }
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
        if (message || window.attachedFile) {
            sendMessage(message);
            chatInput.value = '';
            chatInput.style.height = 'auto';
            
            // Clear file attachment if exists
            const fileAttachmentIndicator = document.querySelector('.input-file-attachment');
            if (fileAttachmentIndicator) {
                fileAttachmentIndicator.remove();
            }
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
    
    // File upload functionality
    const fileUploadBtn = document.getElementById('file-upload-btn');
    const fileUploadInput = document.getElementById('file-upload-input');
    
    if (fileUploadBtn && fileUploadInput) {
        fileUploadBtn.addEventListener('click', () => {
            fileUploadInput.click();
        });
        
        fileUploadInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                console.log('%c FILE SELECTED', 'background: #44f; color: white; font-weight: bold;');
                console.log('User selected file:', file.name, 'type:', file.type, 'size:', file.size);
                
                // Create a notification about the selected file
                const fileInfo = document.createElement('div');
                fileInfo.className = 'file-info';
                fileInfo.textContent = `Selected file: ${file.name}`;
                
                // Show the selected file notification temporarily
                const inputWrapper = document.querySelector('.input-wrapper');
                inputWrapper.appendChild(fileInfo);
                
                // Simple animation to show file is ready
                setTimeout(() => {
                    fileInfo.classList.add('show');
                }, 10);
                
                // Get current conversation ID - first check currentConversationId, then URL
                let conversationId = currentConversationId;
                if (!conversationId) {
                    // Try to get it from URL
                    const urlParams = new URLSearchParams(window.location.search);
                    if (urlParams.has('conversation_id')) {
                        conversationId = urlParams.get('conversation_id');
                        console.log('Found conversation ID in URL:', conversationId);
                        // Update current conversation ID
                        currentConversationId = conversationId;
                    }
                }
                
                // File will be stored in this object until message is sent
                const fileData = {
                    file: file,
                    name: file.name,
                    type: file.type,
                    size: file.size
                };
                
                // Add a visual indicator in the input area
                const fileAttachmentIndicator = document.createElement('div');
                fileAttachmentIndicator.className = 'input-file-attachment';
                
                // Remove any existing indicators
                const existingIndicator = document.querySelector('.input-file-attachment');
                if (existingIndicator) {
                    existingIndicator.remove();
                }
                
                // IMPORTANT CHANGE: Always try to upload immediately, even without conversationId
                // Show uploading status in the file attachment indicator
                fileAttachmentIndicator.classList.add('uploading');
                fileAttachmentIndicator.innerHTML = `
                    <i class="fas fa-sync fa-spin"></i>
                    <span>Uploading ${file.name}...</span>
                `;
                
                // Add the indicator to the input area
                inputWrapper.appendChild(fileAttachmentIndicator);
                
                // If no conversation exists yet, create one first via API
                const uploadFile = async () => {
                    try {
                        // Check if we need to create a conversation first
                        if (!conversationId) {
                            console.log('%c CREATING NEW CONVERSATION', 'background: #f90; color: white; font-weight: bold;');
                            
                            // Get CSRF token
                            const csrfToken = getCsrfToken();
                            
                            // Create a new conversation
                            const createResponse = await fetch('/api/conversations/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': csrfToken,
                                    'X-Requested-With': 'XMLHttpRequest'
                                },
                                body: JSON.stringify({
                                    project_id: currentProjectId || null
                                })
                            });
                            
                            if (!createResponse.ok) {
                                throw new Error('Failed to create conversation');
                            }
                            
                            const conversationData = await createResponse.json();
                            conversationId = conversationData.id;
                            currentConversationId = conversationId;
                            
                            console.log('Created new conversation with ID:', conversationId);
                            
                            // Update URL with conversation ID
                            const url = new URL(window.location);
                            url.searchParams.set('conversation_id', conversationId);
                            window.history.pushState({}, '', url);
                        }
                        
                        // Now upload the file with the conversation ID
                        console.log('%c UPLOADING FILE IMMEDIATELY', 'background: #f50; color: white; font-weight: bold;');
                        console.log('Using conversation ID for upload:', conversationId);
                        
                        const fileResponse = await uploadFileToServer(file, conversationId);
                        console.log('File uploaded immediately after selection, file_id:', fileResponse.id);
                        
                        // Update the indicator to show success
                        fileAttachmentIndicator.classList.remove('uploading');
                        fileAttachmentIndicator.classList.add('uploaded');
                        fileAttachmentIndicator.innerHTML = `
                            <i class="fas fa-check-circle"></i>
                            <span>${file.name}</span>
                            <button type="button" id="remove-file-btn" title="Remove file">
                                <i class="fas fa-times"></i>
                            </button>
                        `;
                        
                        // Store the file with the file_id in a global variable
                        window.attachedFile = {
                            file: file,
                            name: file.name,
                            type: file.type,
                            size: file.size,
                            id: fileResponse.id
                        };
                        
                        console.log('Updated window.attachedFile with file_id:', window.attachedFile);
                        
                        // Add event listener to remove button
                        const removeFileBtn = document.getElementById('remove-file-btn');
                        if (removeFileBtn) {
                            removeFileBtn.addEventListener('click', (e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                window.attachedFile = null;
                                fileAttachmentIndicator.remove();
                            });
                        }
                    } catch (error) {
                        console.error('%c FILE UPLOAD ERROR', 'background: #f00; color: white; font-weight: bold;');
                        console.error('Error details:', error);
                        
                        // Update the indicator to show error
                        fileAttachmentIndicator.classList.remove('uploading');
                        fileAttachmentIndicator.classList.add('error');
                        fileAttachmentIndicator.innerHTML = `
                            <i class="fas fa-exclamation-circle"></i>
                            <span>Error: ${file.name}</span>
                            <button type="button" id="remove-file-btn" title="Remove file">
                                <i class="fas fa-times"></i>
                            </button>
                        `;
                        
                        // Still store the file in a global variable, but without file_id
                        window.attachedFile = fileData;
                        
                        // Add event listener to remove button
                        const removeFileBtn = document.getElementById('remove-file-btn');
                        if (removeFileBtn) {
                            removeFileBtn.addEventListener('click', (e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                window.attachedFile = null;
                                fileAttachmentIndicator.remove();
                            });
                        }
                    }
                };
                
                // Call the upload function immediately
                uploadFile();
                
                // Focus on the input so the user can type their message
                chatInput.focus();
                
                // Clear the file input to allow uploading the same file again
                fileUploadInput.value = '';
                
                // Remove the notification after a short delay
                setTimeout(() => {
                    fileInfo.classList.remove('show');
                    setTimeout(() => fileInfo.remove(), 300);
                }, 3000);
            }
        });
    }
    
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
            
            // Enhanced logging for debugging purposes
            console.log('WebSocket message received:', data);
            
            // Special handling for notifications - Use the same improved detection logic
            const isNotification = data.is_notification === true || 
                                  data.is_notification === "true" || 
                                  (data.notification_type && data.notification_type !== "");
                                  
            const isEarlyNotification = isNotification && 
                                       (data.early_notification === true || 
                                        data.early_notification === "true");
            
            if (data.type === 'ai_chunk' && isNotification) {
                console.log('%c NOTIFICATION DATA RECEIVED IN WEBSOCKET! ', 'background: #ffa500; color: #000; font-weight: bold; padding: 2px 5px;');
                console.log('Notification data:', data);
                console.log('Is early notification:', isEarlyNotification);
                
                if (isEarlyNotification) {
                    console.log('%c EARLY NOTIFICATION RECEIVED! ', 'background: #ff0000; color: #fff; font-weight: bold; padding: 2px 5px;');
                    console.log('Function name:', data.function_name);
                }
            }
            
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
        
        // Add explicit debug for notification property
        console.log('Data object type:', typeof data);
        console.log('is_notification raw value:', data.is_notification);
        console.log('is_notification type:', typeof data.is_notification);
        
        // Fix notification detection by checking for either boolean true, string "true", or existence of notification_type
        // This handles cases where is_notification is undefined but we still want to process regular chunks
        const isNotification = data.is_notification === true || 
                              data.is_notification === "true" || 
                              (data.notification_type && data.notification_type !== "");
                              
        // Check if this is an early notification
        const isEarlyNotification = isNotification && 
                                   (data.early_notification === true || 
                                    data.early_notification === "true");
        
        // Add additional debugging to see the entire data structure
        console.log("Received AI chunk data:", data);
        console.log("Is Notification (after fix):", isNotification);
        console.log("Is Early Notification:", isEarlyNotification);
        console.log("Function name (if early):", data.function_name || "none");
        
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
        
        // Handle early notifications (show a function call indicator but don't open artifacts yet)
        if (isEarlyNotification && data.function_name) {
            console.log('\n\n==========================================');
            console.log('EARLY NOTIFICATION RECEIVED:');
            console.log('Function name early notification:', data.function_name);
            console.log('Notification type:', data.notification_type);
            console.log('Is early notification:', data.early_notification);
            console.log('==========================================\n\n');
            
            // Remove any previous function call indicators
            removeFunctionCallIndicator();
            
            // Show function call indicator for the function
            showFunctionCallIndicator(data.function_name);
            
            // Add a visual "calling function" separator
            const separator = document.createElement('div');
            separator.className = 'function-call-separator';
            separator.innerHTML = `<div class="separator-line"></div>
                                  <div class="separator-text">Calling early notification function: ${data.function_name}</div>
                                  <div class="separator-line"></div>`;
            messageContainer.appendChild(separator);
            scrollToBottom();
            
            return;
        }
        
        // Handle regular (completion) notifications
        if (isNotification && !isEarlyNotification) {
            console.log('\n\n==========================================');
            console.log('COMPLETION NOTIFICATION RECEIVED - DETAILED DEBUG INFO:');
            console.log('Full data object:', data);
            console.log('Notification type:', data.notification_type);
            console.log('Current project ID:', currentProjectId);
            console.log('==========================================\n\n');
            
            // Show a function call indicator in the UI for the function that generated this notification
            const functionName = data.notification_type === 'features' ? 'extract_features' : 
                               data.notification_type === 'personas' ? 'extract_personas' : 
                               data.function_name || data.notification_type;
            
            // Remove any previous function call indicators
            removeFunctionCallIndicator();
            
            // Show success message
            showFunctionCallSuccess(functionName, data.notification_type);
            
            // Check if we have a valid project ID from somewhere
            if (!currentProjectId) {
                // Try to get project ID from URL first
                const urlParams = new URLSearchParams(window.location.search);
                const urlProjectId = urlParams.get('project_id');
                
                // Then try from path (format: /chat/project/{id}/)
                const pathProjectId = extractProjectIdFromPath();
                
                if (urlProjectId) {
                    console.log(`Using project ID from URL: ${urlProjectId}`);
                    currentProjectId = urlProjectId;
                } else if (pathProjectId) {
                    console.log(`Using project ID from path: ${pathProjectId}`);
                    currentProjectId = pathProjectId;
                }
            }
            
            // If still no project ID, we can't proceed with loading artifacts
            if (!currentProjectId) {
                console.error('Unable to determine project ID for notification! Cannot load artifacts.');
                // Try to at least open the panel even if we can't load content
                if (window.ArtifactsPanel && typeof window.ArtifactsPanel.toggle === 'function') {
                    console.log('Opening artifacts panel with forceOpen=true');
                    try {
                        window.ArtifactsPanel.toggle(true); // Use forceOpen parameter to ensure it opens
                        console.log('ArtifactsPanel.toggle called successfully');
                        
                        // Double check if panel is actually open now
                        const panel = document.getElementById('artifacts-panel');
                        if (panel) {
                            console.log('Panel element found, expanded status:', panel.classList.contains('expanded'));
                            if (!panel.classList.contains('expanded')) {
                                console.log('Panel still not expanded after toggle, forcing expanded class');
                                panel.classList.add('expanded');
                                document.querySelector('.app-container')?.classList.add('artifacts-expanded');
                                document.getElementById('artifacts-button')?.classList.add('active');
                            }
                        } else {
                            console.error('Could not find artifacts-panel element in DOM');
                        }
                    } catch (err) {
                        console.error('Error toggling artifacts panel:', err);
                    }
                } else {
                    console.error('ArtifactsPanel not available!', window.ArtifactsPanel);
                }
                return;
            }
            
            console.log('\n\nArtifacts Panel Status:');
            console.log('ArtifactsPanel available:', !!window.ArtifactsPanel);
            console.log('Toggle function available:', !!(window.ArtifactsPanel && typeof window.ArtifactsPanel.toggle === 'function'));
            
            // Make sure artifacts panel is visible
            let panelOpenSuccess = false;
            
            if (window.ArtifactsPanel && typeof window.ArtifactsPanel.toggle === 'function') {
                console.log('Opening artifacts panel with ArtifactsPanel.toggle');
                try {
                    window.ArtifactsPanel.toggle(true); // Use forceOpen parameter to ensure it opens
                    console.log('ArtifactsPanel.toggle called successfully');
                    
                    // Double check if panel is actually open now
                    const panel = document.getElementById('artifacts-panel');
                    if (panel) {
                        console.log('Panel element found, expanded status:', panel.classList.contains('expanded'));
                        panelOpenSuccess = panel.classList.contains('expanded');
                        
                        if (!panelOpenSuccess) {
                            console.log('Panel still not expanded after toggle, adding expanded class directly');
                            panel.classList.add('expanded');
                            document.querySelector('.app-container')?.classList.add('artifacts-expanded');
                            document.getElementById('artifacts-button')?.classList.add('active');
                            panelOpenSuccess = true;
                        }
                    } else {
                        console.error('Could not find artifacts-panel element in DOM');
                    }
                } catch (err) {
                    console.error('Error toggling artifacts panel:', err);
                }
            } else {
                console.error('ArtifactsPanel not available!', window.ArtifactsPanel);
            }
            
            // If the panel still isn't open, try the direct approach
            if (!panelOpenSuccess && window.forceOpenArtifactsPanel) {
                console.log('Using forceOpenArtifactsPanel as fallback');
                window.forceOpenArtifactsPanel(data.notification_type);
                panelOpenSuccess = true;
            }
            
            // Last resort - direct DOM manipulation if all else fails
            if (!panelOpenSuccess) {
                console.log('Attempting direct DOM manipulation to open panel');
                try {
                    // Try to manipulate DOM directly
                    const panel = document.getElementById('artifacts-panel');
                    const appContainer = document.querySelector('.app-container');
                    const button = document.getElementById('artifacts-button');
                    
                    if (panel && appContainer) {
                        panel.classList.add('expanded');
                        appContainer.classList.add('artifacts-expanded');
                        if (button) button.classList.add('active');
                        console.log('Panel forced open with direct DOM manipulation');
                        panelOpenSuccess = true;
                    }
                } catch (e) {
                    console.error('Error in direct DOM manipulation:', e);
                }
            }
            
            console.log('\n\nTab Switching Status:');
            console.log('switchTab available:', !!window.switchTab);
            console.log('notification_type available:', !!data.notification_type);
            
            // Switch to the appropriate tab
            if (window.switchTab && data.notification_type) {
                console.log(`Switching to tab: ${data.notification_type}`);
                
                // Try the standard tab switching first
                try {
                    window.switchTab(data.notification_type);
                    console.log('Tab switched successfully using window.switchTab');
                } catch (err) {
                    console.error('Error switching tab with window.switchTab:', err);
                    
                    // Try direct DOM manipulation as fallback
                    try {
                        const tabButtons = document.querySelectorAll('.tab-button');
                        const tabPanes = document.querySelectorAll('.tab-pane');
                        
                        // Find the right tab
                        const targetButton = document.querySelector(`.tab-button[data-tab="${data.notification_type}"]`);
                        const targetPane = document.getElementById(data.notification_type);
                        
                        if (targetButton && targetPane) {
                            // Remove active class from all tabs
                            tabButtons.forEach(btn => btn.classList.remove('active'));
                            tabPanes.forEach(pane => pane.classList.remove('active'));
                            
                            // Set active class on the target tab
                            targetButton.classList.add('active');
                            targetPane.classList.add('active');
                            console.log('Tab switched successfully using direct DOM manipulation');
                        } else {
                            console.error(`Could not find tab elements for ${data.notification_type}`);
                        }
                    } catch (domErr) {
                        console.error('Error switching tab with direct DOM manipulation:', domErr);
                    }
                }
                
                // Load the content for that tab if we have a project ID
                console.log(`Current project ID for loading: ${currentProjectId}`);
                
                console.log('\n\nLoader Status:');
                console.log('ArtifactsLoader available:', !!window.ArtifactsLoader);
                console.log(`loadFeatures function available:`, !!(window.ArtifactsLoader && typeof window.ArtifactsLoader.loadFeatures === 'function'));
                console.log(`loadPersonas function available:`, !!(window.ArtifactsLoader && typeof window.ArtifactsLoader.loadPersonas === 'function'));
                console.log(`loadPRD function available:`, !!(window.ArtifactsLoader && typeof window.ArtifactsLoader.loadPRD === 'function'));
                
                // Load the appropriate content based on notification type
                if (data.notification_type === 'features' && 
                    window.ArtifactsLoader && 
                    typeof window.ArtifactsLoader.loadFeatures === 'function') {
                    console.log(`Calling ArtifactsLoader.loadFeatures(${currentProjectId})`);
                    window.ArtifactsLoader.loadFeatures(currentProjectId);
                } else if (data.notification_type === 'personas' && 
                          window.ArtifactsLoader && 
                          typeof window.ArtifactsLoader.loadPersonas === 'function') {
                    console.log(`Calling ArtifactsLoader.loadPersonas(${currentProjectId})`);
                    window.ArtifactsLoader.loadPersonas(currentProjectId);
                } else if (data.notification_type === 'prd' && 
                          window.ArtifactsLoader && 
                          typeof window.ArtifactsLoader.loadPRD === 'function') {
                    console.log(`Calling ArtifactsLoader.loadPRD(${currentProjectId})`);
                    window.ArtifactsLoader.loadPRD(currentProjectId);
                } else {
                    console.error(`ArtifactsLoader.load${data.notification_type} not available!`, window.ArtifactsLoader);
                }
            } else {
                console.error(`switchTab not available or no notification_type provided!`);
            }
            console.log('==========================================\n\n');
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
        
        // Check for function call mentions in text
        checkForFunctionCall(chunk);
        
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
            
            // Check if this chunk seems to finalize a function call statement
            if (chunk.includes("function") && 
                (chunk.includes("extract_features") || 
                 chunk.includes("extract_personas") || 
                 chunk.includes("get_features") || 
                 chunk.includes("get_personas"))) {
                
                // Identify which function is being called
                let functionName = "";
                if (chunk.includes("extract_features")) functionName = "extract_features";
                else if (chunk.includes("extract_personas")) functionName = "extract_personas";
                else if (chunk.includes("get_features")) functionName = "get_features";
                else if (chunk.includes("get_personas")) functionName = "get_personas";
                
                if (functionName && !document.querySelector('.function-call-indicator')) {
                    // Show the function call indicator
                    showFunctionCallIndicator(functionName);
                    
                    // Add a visual "calling function" separator
                    const separator = document.createElement('div');
                    separator.className = 'function-call-separator';
                    separator.innerHTML = `<div class="separator-line"></div>
                                          <div class="separator-text">Calling function: ${functionName}</div>
                                          <div class="separator-line"></div>`;
                    messageContainer.appendChild(separator);
                    scrollToBottom();
                }
            }
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
        
        // Check if we have a message or an attached file
        if (!message && !window.attachedFile) {
            console.log('No message or file to send');
            return;
        }

        // Reset stop requested flag
        stopRequested = false;
        
        // Get file data from the attached file (which may already have a file_id if it was uploaded)
        let fileData = null;
        if (window.attachedFile) {
            console.log('Attached file found:', window.attachedFile);
            fileData = {
                name: window.attachedFile.name,
                type: window.attachedFile.type,
                size: window.attachedFile.size
            };
            
            // If the file was already uploaded, it will have an id
            if (window.attachedFile.id) {
                fileData.id = window.attachedFile.id;
            }
        }
        
        // Store a reference to the attached file and clear the global reference
        const attachedFile = window.attachedFile;
        window.attachedFile = null;
        
        // Clear the file attachment indicator
        const fileAttachmentIndicator = document.querySelector('.input-file-attachment');
        if (fileAttachmentIndicator) {
            fileAttachmentIndicator.remove();
        }
        
        // If there's an attached file that hasn't been uploaded yet, upload it first
        if (attachedFile && attachedFile.file && !attachedFile.id) {
            // Show typing indicator (shows we're doing something)
            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'typing-indicator';
            typingIndicator.innerHTML = '<span></span><span></span><span></span>';
            messageContainer.appendChild(typingIndicator);
            console.log('sendMessage: Added typing indicator for file upload');
            
            // Disable input while uploading file and waiting for response
            chatInput.disabled = true;
            
            // Check for conversation ID - first in currentConversationId, then in URL
            let conversationId = currentConversationId;
            if (!conversationId) {
                // Try to get it from URL
                const urlParams = new URLSearchParams(window.location.search);
                if (urlParams.has('conversation_id')) {
                    conversationId = urlParams.get('conversation_id');
                    console.log('Found conversation ID in URL:', conversationId);
                    // Update current conversation ID
                    currentConversationId = conversationId;
                }
            }
            
            if (conversationId) {
                // If we have a conversation ID from anywhere, upload file first
                console.log('Uploading file to conversation:', conversationId);
                uploadFileToServer(attachedFile.file, conversationId)
                    .then(fileResponse => {
                        console.log('File uploaded successfully before message, file_id:', fileResponse.id);
                        
                        // Now add the file_id to the file data
                        fileData.id = fileResponse.id;
                        
                        // Now actually add the user message to chat with file data
                        addMessageToChat('user', message, fileData);
                        
                        // Proceed with sending the message with the file_id
                        sendMessageToServer(message, fileData);
                    })
                    .catch(error => {
                        console.error('Error uploading file before message:', error);
                        
                        // If file upload failed, still send the message without file_id
                        addMessageToChat('user', message, fileData);
                        sendMessageToServer(message, fileData);
                        
                        // Re-enable input
                        chatInput.disabled = false;
                    });
            } else {
                // If we still don't have a conversation ID, just send the message with file data
                console.log('No conversation ID found. Sending message with file data.');
                
                // Add user message to chat with file data
                addMessageToChat('user', message, fileData);
                
                // For simplicity, we'll just send message without file_id
                // The server will need to handle creating both conversation and file
                sendMessageToServer(message, fileData);
                
                // Remove typing indicator for file upload
                const typingIndicator = document.querySelector('.typing-indicator');
                if (typingIndicator) {
                    typingIndicator.remove();
                }
            }
        } else {
            // Either no file is attached, or the file was already uploaded and has a file_id
            
            // Add user message to chat with file data (including file_id if available)
            addMessageToChat('user', message, fileData);
            
            // Proceed with standard message sending
            sendMessageToServer(message, fileData);
        }
    }
    
    // Function to handle the actual WebSocket message sending
    function sendMessageToServer(message, fileData = null) {
        // Show typing indicator if not already present
        if (!document.querySelector('.typing-indicator')) {
            const typingIndicator = document.createElement('div');
            typingIndicator.className = 'typing-indicator';
            typingIndicator.innerHTML = '<span></span><span></span><span></span>';
            messageContainer.appendChild(typingIndicator);
            console.log('sendMessageToServer: Added typing indicator');
        }
        
        // Scroll to bottom
        scrollToBottom();
        
        // Disable input while waiting for response (if not already disabled)
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
        
        // Add file data if provided
        if (fileData) {
            messageData.file = fileData;
        }
        
        console.log('sendMessageToServer: Message data:', messageData);
        
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
    
    // Function to upload file to server via REST API
    async function uploadFileToServer(file, conversationId = null, messageId = null) {
        try {
            console.log('%c FILE UPLOAD - Starting file upload process', 'background: #3a9; color: white; font-weight: bold;');
            console.log('File to upload:', file);
            console.log('Conversation ID:', conversationId);
            console.log('Message ID:', messageId);
            
            // Validate that we have a conversation ID if required
            if (!conversationId) {
                console.warn('No conversation ID provided for file upload');
                showFileNotification(`File upload requires a conversation ID`, 'error');
                throw new Error('Conversation ID is required');
            }
            
            // Show uploading notification
            const notification = showFileNotification(`Uploading ${file.name}...`, 'uploading');
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('conversation_id', conversationId);
            if (messageId) {
                formData.append('message_id', messageId);
            }
            
            // Get CSRF token
            const csrfToken = getCsrfToken();
            console.log('CSRF Token obtained:', csrfToken ? 'Token exists' : 'No token found');
            
            // Log request details
            console.log('%c API REQUEST - About to send file upload request', 'background: #f50; color: white; font-weight: bold;');
            console.log('Endpoint:', '/api/files/upload/');
            console.log('Method:', 'POST');
            console.log('FormData contents:', {
                file: file.name,
                conversation_id: conversationId,
                message_id: messageId || 'Not provided'
            });
            
            // Add a timestamp to force cache busting
            const timestamp = new Date().getTime();
            const apiUrl = `/api/files/upload/?_=${timestamp}`;
            
            // Force this to be a visible network call by adding headers
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                },
                body: formData,
                credentials: 'same-origin' // Include cookies
            });
            
            console.log('%c API RESPONSE - Received response from server', 'background: #0a5; color: white; font-weight: bold;');
            console.log('Response status:', response.status);
            console.log('Response OK:', response.ok);
            
            if (!response.ok) {
                console.error('Upload failed with status:', response.status);
                let errorData;
                try {
                    errorData = await response.json();
                    console.error('Error details:', errorData);
                } catch (e) {
                    const textError = await response.text();
                    console.error('Error response (text):', textError);
                    errorData = { error: 'Failed to upload file' };
                }
                throw new Error(errorData.error || `Failed to upload file: ${response.status}`);
            }
            
            // Parse response data
            let data;
            try {
                data = await response.json();
                console.log('%c SUCCESS - File uploaded successfully', 'background: #0c0; color: white; font-weight: bold;');
                console.log('Server response:', data);
            } catch (e) {
                console.error('Failed to parse JSON response:', e);
                const textResponse = await response.text();
                console.log('Raw response text:', textResponse);
                throw new Error('Invalid response format from server');
            }
            
            // Check for file_id in response
            if (!data.id) {
                console.error('Server response missing file_id:', data);
                throw new Error('Server did not return a file_id');
            }
            
            console.log('%c FILE ID - Obtained file ID from server', 'background: #00c; color: white; font-weight: bold;');
            console.log('File ID:', data.id);
            
            // Update notification to show success
            if (notification && notification.parentNode) {
                notification.className = 'file-notification success';
                notification.innerHTML = `
                    <i class="fas fa-check-circle"></i>
                    <span>File ${file.name} uploaded successfully (ID: ${data.id})</span>
                `;
                
                // Remove after a delay
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.classList.remove('show');
                        setTimeout(() => notification.remove(), 300);
                    }
                }, 5000);
            }
            
            // Return the data with file_id
            return data;
        } catch (error) {
            console.error('%c ERROR - File upload failed', 'background: #f00; color: white; font-weight: bold;');
            console.error('Error details:', error);
            console.error('Stack trace:', error.stack);
            
            // Show error notification
            showFileNotification(`Error uploading file: ${error.message}`, 'error');
            throw error;
        }
    }
    
    // Helper function to show file notifications
    function showFileNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `file-notification ${type}`;
        
        // Add icon based on type
        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle';
        if (type === 'error') icon = 'exclamation-circle';
        if (type === 'uploading') icon = 'sync fa-spin';
        
        notification.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
        `;
        
        // Add to container
        const container = document.querySelector('.chat-messages');
        container.appendChild(notification);
        
        // Show with animation
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Remove after delay unless it's an uploading notification
        if (type !== 'uploading') {
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, 5000);
        }
        
        return notification;
    }

    // Function to add a message to the chat
    function addMessageToChat(role, content, fileData = null) {
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
            
            // Add file attachment indicator if fileData is provided
            if (fileData) {
                const fileAttachment = document.createElement('div');
                fileAttachment.className = 'file-attachment';
                fileAttachment.innerHTML = `
                    <i class="fas fa-paperclip"></i>
                    <span class="file-name">${fileData.name}</span>
                    <span class="file-type">${fileData.type}</span>
                `;
                contentDiv.appendChild(document.createElement('br'));
                contentDiv.appendChild(fileAttachment);
            }
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
    
    // Function to show a function call indicator
    function showFunctionCallIndicator(functionName) {
        // Remove any existing function call indicators
        removeFunctionCallIndicator();
        
        // Get a user-friendly function description
        const functionDetails = getFunctionDetails(functionName);
        
        // Create the indicator element
        const indicator = document.createElement('div');
        indicator.className = 'function-call-indicator';
        indicator.innerHTML = `
            <div class="function-call-spinner"></div>
            <div class="function-call-text">
                <div class="function-name">${functionName}()</div>
                <div class="function-status">
                    ${functionDetails.description || 'Processing function call...'}
                </div>
            </div>
        `;
        
        // Add to message container
        messageContainer.appendChild(indicator);
        scrollToBottom();
        
        return indicator;
    }
    
    // Function to show a function call success message
    function showFunctionCallSuccess(functionName, type) {
        // Remove any existing function call indicators
        removeFunctionCallIndicator();
        
        // Get function details
        const functionDetails = getFunctionDetails(functionName);
        
        // Create the success element
        const successElement = document.createElement('div');
        successElement.className = 'function-call-success';
        
        let message = '';
        if (type === 'features') {
            message = 'Features extracted and saved successfully!';
        } else if (type === 'personas') {
            message = 'Personas extracted and saved successfully!';
        } else if (type === 'prd') {
            message = 'PRD generated and saved successfully!';
        } else {
            message = 'Function call completed successfully!';
        }
        
        successElement.innerHTML = `
            <div class="function-call-icon">✓</div>
            <div class="function-call-text">
                <div class="function-name">${functionName}()</div>
                <div class="function-result">
                    ${message}<br>
                    <small>${functionDetails.successMessage || 'Results have been processed and saved.'}</small>
                </div>
            </div>
        `;
        
        // Add to message container
        messageContainer.appendChild(successElement);
        scrollToBottom();
        
        // Also add a permanent mini indicator
        addFunctionCallMiniIndicator(functionName, type);
        
        // Remove after a delay
        setTimeout(() => {
            if (successElement.parentNode) {
                successElement.classList.add('fade-out');
                setTimeout(() => {
                    if (successElement.parentNode) {
                        successElement.remove();
                    }
                }, 500); // fade out time
            }
        }, 4000); // show for 4 seconds
    }
    
    // Function to add a permanent mini indicator of function call success
    function addFunctionCallMiniIndicator(functionName, type) {
        // Create mini indicator
        const miniIndicator = document.createElement('div');
        miniIndicator.className = 'function-mini-indicator';
        
        let icon = '';
        if (type === 'features') icon = '📋';
        else if (type === 'personas') icon = '👥';
        else if (type === 'prd') icon = '📄';
        else icon = '✓';
        
        miniIndicator.innerHTML = `
            <span class="mini-icon">${icon}</span>
            <span class="mini-name">${functionName}</span>
        `;
        
        // Add it to the message container
        messageContainer.appendChild(miniIndicator);
        
        // Add fade-in animation
        setTimeout(() => {
            miniIndicator.classList.add('show');
        }, 100);
    }
    
    // Helper function to get function details for UI display
    function getFunctionDetails(functionName) {
        const functionDetails = {
            'extract_features': {
                description: 'Extracting and processing features from the conversation...',
                successMessage: 'Features have been extracted, categorized, and saved to the project.'
            },
            'extract_personas': {
                description: 'Analyzing and extracting personas from the conversation...',
                successMessage: 'Personas have been identified and saved to the project.'
            },
            'get_features': {
                description: 'Retrieving existing features for this project...',
                successMessage: 'Existing features have been loaded from the database.'
            },
            'get_personas': {
                description: 'Retrieving existing personas for this project...',
                successMessage: 'Existing personas have been loaded from the database.'
            },
            'extract_prd': {
                description: 'Generating and processing PRD from the conversation...',
                successMessage: 'PRD has been generated and saved to the project.'
            },
            'get_prd': {
                description: 'Retrieving existing PRD for this project...',
                successMessage: 'Existing PRD has been loaded from the database.'
            }
        };
        
        return functionDetails[functionName] || {};
    }
    
    // Function to remove any function call indicators
    function removeFunctionCallIndicator() {
        const existingIndicators = document.querySelectorAll('.function-call-indicator, .function-call-success');
        existingIndicators.forEach(indicator => {
            indicator.remove();
        });
    }
    
    // Add new function to detect function calls in text and show indicators
    function checkForFunctionCall(text) {
        // More comprehensive patterns to detect function calls in the AI's text
        const patterns = [
            // Standard function call patterns
            /(?:I'll|I will|Let me|I'm going to|I am going to)\s+(?:call|use|execute|run)\s+(?:the\s+)?`?(\w+)`?\s+function/i,
            
            // Direct function mentions
            /(?:calling|executing|running|using)\s+(?:the\s+)?`?(\w+)`?\s+function/i,
            
            // Code block style mentions
            /```(?:python|js|javascript)?\s*(?:function\s+)?(\w+)\s*\(/i,
            
            // Now let's/I'm extracting patterns
            /(?:Now|I'm|I am)\s+(?:extracting|getting)\s+(?:the\s+)?(\w+)/i,
            
            // Calling with specific syntax
            /(?:extract_(\w+)|get_(\w+))\(/i
        ];
        
        // Check each pattern
        for (const pattern of patterns) {
            const match = text.match(pattern);
            if (match) {
                let functionName = '';
                
                // Special case for the last pattern with capturing groups
                if (pattern.toString().includes('extract_') && (match[1] || match[2])) {
                    functionName = match[1] ? `extract_${match[1]}` : `get_${match[2]}`;
                } else if (match[1]) {
                    functionName = match[1].toLowerCase();
                    
                    // Handle some common variations
                    if (functionName === 'extract' || functionName === 'extracting') functionName = 'extract_features';
                    if (functionName === 'features') functionName = 'extract_features';
                    if (functionName === 'personas') functionName = 'extract_personas';
                    if (functionName === 'prd') functionName = 'extract_prd';
                }
                
                // Only show for known functions to avoid false positives
                const knownFunctions = ['extract_features', 'extract_personas', 'get_features', 'get_personas', 'extract_prd', 'get_prd'];
                
                if (knownFunctions.includes(functionName)) {
                    showFunctionCallIndicator(functionName);
                    return; // Exit after finding the first match
                }
            }
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
            
            // Load files for this conversation
            loadMessageFiles(conversationId);
            
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
        // Try to get it from the meta tag first (Django's standard location)
        const metaToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (metaToken) {
            console.log('Found CSRF token in meta tag');
            return metaToken;
        }
        
        // Then try the input field (another common location)
        const inputToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (inputToken) {
            console.log('Found CSRF token in input field');
            return inputToken;
        }
        
        // Finally try to get it from cookies
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        
        if (cookieValue) {
            console.log('Found CSRF token in cookies');
            return cookieValue;
        }
        
        console.error('CSRF token not found in any location');
        return '';
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

    // Add a test function to simulate a notification for debugging purposes
    window.testNotification = function(type) {
        console.log('Manually triggering notification test...');
        const notificationType = type || 'features';
        
        // Create a fake notification data object
        const fakeNotificationData = {
            type: 'ai_chunk',
            chunk: '',
            is_final: false,
            is_notification: true,
            notification_type: notificationType
        };
        
        // Process it through the normal handler
        console.log('Simulating notification with data:', fakeNotificationData);
        handleAIChunk(fakeNotificationData);
    };

    // Add a test function to simulate function call indicators for debugging
    window.testFunctionCall = function(functionName) {
        console.log('Testing function call indicator for:', functionName);
        
        const validFunctions = ['extract_features', 'extract_personas', 'get_features', 'get_personas'];
        const fn = validFunctions.includes(functionName) ? functionName : validFunctions[0];
        
        // Add a simulated assistant message first
        if (!document.querySelector('.message.assistant:last-child')) {
            addMessageToChat('assistant', `I'll extract the key information from our conversation. Let me call the ${fn} function to process this data.`);
        }
        
        // Add the separator that would normally appear right after the function mention
        const separator = document.createElement('div');
        separator.className = 'function-call-separator';
        separator.innerHTML = `<div class="separator-line"></div>
                              <div class="separator-text">Calling function: ${fn}</div>
                              <div class="separator-line"></div>`;
        messageContainer.appendChild(separator);
        
        // Show the function call indicator
        showFunctionCallIndicator(fn);
        
        // After a delay, show the success message
        setTimeout(() => {
            const type = fn.includes('features') ? 'features' : 'personas';
            showFunctionCallSuccess(fn, type);
            
            // Add a simulated response message
            setTimeout(() => {
                if (fn === 'extract_features') {
                    addMessageToChat('assistant', 'I\'ve successfully extracted and saved the features. You can view them in the artifacts panel.');
                } else if (fn === 'extract_personas') {
                    addMessageToChat('assistant', 'I\'ve successfully identified and saved the personas. You can view them in the artifacts panel.');
                } else {
                    addMessageToChat('assistant', 'I\'ve successfully retrieved the data. You can view it in the artifacts panel.');
                }
            }, 1000);
        }, 3000);
    };

    // Add a helper function to force open the artifacts panel
    window.forceOpenArtifactsPanel = function(tabType) {
        console.log('Force opening artifacts panel with tab:', tabType);
        
        // First try using the API if available
        if (window.ArtifactsPanel && typeof window.ArtifactsPanel.toggle === 'function') {
            window.ArtifactsPanel.toggle(true);
        }
        
        // Then try direct DOM manipulation
        const panel = document.getElementById('artifacts-panel');
        const appContainer = document.querySelector('.app-container');
        const button = document.getElementById('artifacts-button');
        
        if (panel && appContainer) {
            panel.classList.add('expanded');
            appContainer.classList.add('artifacts-expanded');
            if (button) button.classList.add('active');
        }
        
        // Then try to switch to the correct tab
        if (window.switchTab && tabType) {
            setTimeout(() => {
                window.switchTab(tabType);
                
                // Try to load the content based on the tab type
                if (window.ArtifactsLoader) {
                    const projectId = currentProjectId || extractProjectIdFromPath() || 
                                    new URLSearchParams(window.location.search).get('project_id');
                    
                    if (projectId) {
                        if (tabType === 'features' && typeof window.ArtifactsLoader.loadFeatures === 'function') {
                            window.ArtifactsLoader.loadFeatures(projectId);
                        } else if (tabType === 'personas' && typeof window.ArtifactsLoader.loadPersonas === 'function') {
                            window.ArtifactsLoader.loadPersonas(projectId);
                        } else if (tabType === 'prd' && typeof window.ArtifactsLoader.loadPRD === 'function') {
                            window.ArtifactsLoader.loadPRD(projectId);
                        }
                    }
                }
            }, 100); // Small delay to ensure panel is open first
        }
    };

    /**
     * Test function to demonstrate notification styles
     * This can be called from the console with: testNotifications()
     */
    function testNotifications() {
        console.log('Testing notification indicators');
        
        // Test default function call indicator
        showFunctionCallIndicator('test_function');
        
        // Test function call for features
        setTimeout(() => {
            const featuresElement = document.createElement('div');
            featuresElement.className = 'function-features';
            document.querySelector('.messages').appendChild(featuresElement);
            
            showFunctionCallIndicator('extract_features', 'features');
        }, 1000);
        
        // Test function call for personas
        setTimeout(() => {
            const personasElement = document.createElement('div');
            personasElement.className = 'function-personas';
            document.querySelector('.messages').appendChild(personasElement);
            
            showFunctionCallIndicator('extract_personas', 'personas');
        }, 2000);
        
        // Test success notification
        setTimeout(() => {
            showFunctionCallSuccess('test_function');
        }, 3000);
        
        // Test success notification for features
        setTimeout(() => {
            showFunctionCallSuccess('extract_features', 'features');
        }, 4000);
        
        // Test success notification for personas
        setTimeout(() => {
            showFunctionCallSuccess('extract_personas', 'personas');
        }, 5000);
        
        // Test mini indicators
        setTimeout(() => {
            addFunctionCallMiniIndicator('test_function');
        }, 6000);
        
        setTimeout(() => {
            addFunctionCallMiniIndicator('extract_features', 'features');
        }, 6500);
        
        setTimeout(() => {
            addFunctionCallMiniIndicator('extract_personas', 'personas');
        }, 7000);
        
        console.log('All notification tests queued');
    }

    // Expose the test function globally
    window.testNotifications = testNotifications;

    // Function to load message files
    async function loadMessageFiles(conversationId) {
        try {
            const response = await fetch(`/api/conversations/${conversationId}/files/`);
            const files = await response.json();
            
            // Clear existing message files
            const messageFilesContainer = document.getElementById('message-files');
            messageFilesContainer.innerHTML = '';
            
            // Add message files to the container
            files.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'message-file';
                fileItem.textContent = file.name;
                
                // Add click handler to download the file
                fileItem.addEventListener('click', () => {
                    downloadFile(file.url);
                });
                
                messageFilesContainer.appendChild(fileItem);
            });
        } catch (error) {
            console.error('Error loading message files:', error);
        }
    }

    // Function to download a file
    function downloadFile(fileUrl) {
        // Implement the logic to download the file from the given URL
        console.log('Downloading file:', fileUrl);
    }

    // Add a function to test the file upload API directly for debugging
    window.testFileUpload = async function(conversationId) {
        // Create a simple test file
        const blob = new Blob(['Test file content'], { type: 'text/plain' });
        const file = new File([blob], 'test-upload.txt', { type: 'text/plain' });
        
        console.log('Starting test upload with file:', file);
        console.log('Using conversation ID:', conversationId);
        
        try {
            const result = await uploadFileToServer(file, conversationId);
            console.log('Test upload successful:', result);
            alert(`Test upload successful! File ID: ${result.id}`);
            return result;
        } catch (error) {
            console.error('Test upload failed:', error);
            alert(`Test upload failed: ${error.message}`);
        }
    };
});
