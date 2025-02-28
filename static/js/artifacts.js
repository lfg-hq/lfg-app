/**
 * Artifacts Panel JavaScript
 * Handles the functionality for the resizable and collapsible artifacts panel
 */
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const appContainer = document.querySelector('.app-container');
    const artifactsPanel = document.getElementById('artifacts-panel');
    const artifactsToggle = document.getElementById('artifacts-toggle');
    const resizeHandle = document.getElementById('resize-handle');
    const chatContainer = document.querySelector('.chat-container');
    
    // Create floating button if it doesn't exist
    let artifactsButton = document.getElementById('artifacts-button');
    if (!artifactsButton) {
        artifactsButton = document.createElement('button');
        artifactsButton.id = 'artifacts-button';
        artifactsButton.className = 'artifacts-button';
        artifactsButton.innerHTML = '<i class="fas fa-cube"></i>';
        document.body.appendChild(artifactsButton);
    }
    
    // If elements don't exist, exit early
    if (!artifactsPanel || !artifactsToggle || !resizeHandle) {
        console.warn('Artifacts panel elements not found');
        return;
    }
    
    // Initialize state
    let isResizing = false;
    let lastDownX = 0;
    let panelWidth = parseInt(getComputedStyle(artifactsPanel).width) || 350;
    
    // Check if panel should start expanded (from localStorage)
    const shouldBeExpanded = localStorage.getItem('artifacts_expanded') === 'true';
    if (shouldBeExpanded) {
        artifactsPanel.classList.add('expanded');
        appContainer.classList.add('artifacts-expanded');
        artifactsButton.classList.add('active');
        updateChatContainerPosition(true);
    }
    
    // Toggle panel visibility when floating button is clicked
    artifactsButton.addEventListener('click', function() {
        const isExpanded = artifactsPanel.classList.toggle('expanded');
        artifactsButton.classList.toggle('active');
        
        // Update app container class to adjust chat container
        if (isExpanded) {
            appContainer.classList.add('artifacts-expanded');
        } else {
            appContainer.classList.remove('artifacts-expanded');
        }
        
        // Store state in localStorage
        localStorage.setItem('artifacts_expanded', isExpanded);
        
        // Update chat container position
        updateChatContainerPosition(isExpanded);
    });
    
    // Close panel when toggle button inside panel is clicked
    artifactsToggle.addEventListener('click', function() {
        artifactsPanel.classList.remove('expanded');
        artifactsButton.classList.remove('active');
        appContainer.classList.remove('artifacts-expanded');
        
        // Store state in localStorage
        localStorage.setItem('artifacts_expanded', false);
        
        // Update chat container position
        updateChatContainerPosition(false);
    });
    
    // Resize functionality
    resizeHandle.addEventListener('mousedown', function(e) {
        // Only allow resizing when panel is expanded
        if (!artifactsPanel.classList.contains('expanded')) {
            return;
        }
        
        isResizing = true;
        lastDownX = e.clientX;
        resizeHandle.classList.add('active');
        
        // Prevent text selection during resize
        document.body.style.userSelect = 'none';
        
        // Add event listeners for mouse movement and release
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
        
        e.preventDefault();
    });
    
    function handleMouseMove(e) {
        if (!isResizing) return;
        
        // Calculate new width (right panel, so we subtract)
        const offsetX = lastDownX - e.clientX;
        const newWidth = panelWidth + offsetX;
        
        // Calculate maximum width (75% of window width)
        const maxWidth = window.innerWidth * 0.75;
        
        // Limit minimum and maximum width
        if (newWidth >= 250 && newWidth <= maxWidth) {
            artifactsPanel.style.width = newWidth + 'px';
            
            // Update chat container position
            updateChatContainerPosition(true, newWidth);
        }
    }
    
    function handleMouseUp() {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('active');
            
            // Update stored width
            panelWidth = parseInt(getComputedStyle(artifactsPanel).width);
            
            // Store width in localStorage
            localStorage.setItem('artifacts_width', panelWidth);
            
            // Re-enable text selection
            document.body.style.userSelect = '';
            
            // Remove event listeners
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        }
    }
    
    // Touch support for mobile
    resizeHandle.addEventListener('touchstart', function(e) {
        // Only allow resizing when panel is expanded
        if (!artifactsPanel.classList.contains('expanded')) {
            return;
        }
        
        isResizing = true;
        lastDownX = e.touches[0].clientX;
        resizeHandle.classList.add('active');
        
        document.addEventListener('touchmove', handleTouchMove);
        document.addEventListener('touchend', handleTouchEnd);
        e.preventDefault();
    });
    
    function handleTouchMove(e) {
        if (!isResizing) return;
        
        const offsetX = lastDownX - e.touches[0].clientX;
        const newWidth = panelWidth + offsetX;
        const maxWidth = window.innerWidth * 0.75;
        
        if (newWidth >= 250 && newWidth <= maxWidth) {
            artifactsPanel.style.width = newWidth + 'px';
            updateChatContainerPosition(true, newWidth);
        }
        
        e.preventDefault();
    }
    
    function handleTouchEnd() {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('active');
            
            panelWidth = parseInt(getComputedStyle(artifactsPanel).width);
            localStorage.setItem('artifacts_width', panelWidth);
            
            document.removeEventListener('touchmove', handleTouchMove);
            document.removeEventListener('touchend', handleTouchEnd);
        }
    }
    
    // Function to update chat container position based on artifacts panel
    function updateChatContainerPosition(isExpanded, width) {
        if (!chatContainer) return;
        
        if (isExpanded) {
            const panelWidth = width || parseInt(getComputedStyle(artifactsPanel).width);
            chatContainer.style.right = panelWidth + 'px';
        } else {
            chatContainer.style.right = '0'; // Full width when panel is hidden
        }
    }
    
    // Load saved width from localStorage if available
    const savedWidth = localStorage.getItem('artifacts_width');
    if (savedWidth && !isNaN(parseInt(savedWidth))) {
        panelWidth = parseInt(savedWidth);
        artifactsPanel.style.width = panelWidth + 'px';
        
        // Only update chat container if panel is expanded
        if (artifactsPanel.classList.contains('expanded')) {
            updateChatContainerPosition(true, panelWidth);
        }
    }
    
    // Window resize handler
    window.addEventListener('resize', function() {
        const maxWidth = window.innerWidth * 0.75;
        
        // On mobile, reset panel width to full width
        if (window.innerWidth <= 768) {
            artifactsPanel.style.width = '100%';
            panelWidth = window.innerWidth;
        } else if (!isResizing) {
            // On desktop, ensure panel width is within bounds
            if (panelWidth > maxWidth) {
                panelWidth = maxWidth;
                artifactsPanel.style.width = maxWidth + 'px';
            }
        }
        
        // Update chat container position based on current state
        updateChatContainerPosition(artifactsPanel.classList.contains('expanded'), panelWidth);
    });
    
    // Public API for artifacts panel
    window.ArtifactsPanel = {
        /**
         * Add a new artifact to the panel
         * @param {Object} artifact - The artifact to add
         * @param {string} artifact.title - The title of the artifact
         * @param {string} artifact.description - The description of the artifact
         * @param {string} artifact.type - The type of artifact (image, code, etc.)
         * @param {string} artifact.content - The content or URL of the artifact
         */
        addArtifact: function(artifact) {
            const artifactsContent = document.querySelector('.artifacts-content');
            const emptyState = document.querySelector('.empty-state');
            
            if (!artifactsContent) return;
            
            // Hide empty state if it exists
            if (emptyState) {
                emptyState.style.display = 'none';
            }
            
            // Create artifact item
            const artifactItem = document.createElement('div');
            artifactItem.className = 'artifact-item';
            
            // Create title
            const title = document.createElement('div');
            title.className = 'artifact-title';
            title.textContent = artifact.title;
            
            // Create description
            const description = document.createElement('div');
            description.className = 'artifact-description';
            description.textContent = artifact.description;
            
            // Add to DOM
            artifactItem.appendChild(title);
            artifactItem.appendChild(description);
            
            // Add content based on type
            if (artifact.type === 'image' && artifact.content) {
                const img = document.createElement('img');
                img.src = artifact.content;
                img.alt = artifact.title;
                img.style.width = '100%';
                img.style.marginTop = '10px';
                img.style.borderRadius = '4px';
                artifactItem.appendChild(img);
            } else if (artifact.type === 'code' && artifact.content) {
                const pre = document.createElement('pre');
                pre.style.marginTop = '10px';
                pre.style.padding = '10px';
                pre.style.backgroundColor = 'rgba(0, 0, 0, 0.2)';
                pre.style.borderRadius = '4px';
                pre.style.overflow = 'auto';
                pre.style.fontSize = '0.85rem';
                
                const code = document.createElement('code');
                code.textContent = artifact.content;
                
                pre.appendChild(code);
                artifactItem.appendChild(pre);
            }
            
            // Add to the beginning of the list
            if (artifactsContent.firstChild) {
                artifactsContent.insertBefore(artifactItem, artifactsContent.firstChild);
            } else {
                artifactsContent.appendChild(artifactItem);
            }
            
            // Show panel if not expanded
            if (!artifactsPanel.classList.contains('expanded')) {
                artifactsButton.click();
            }
            
            return artifactItem;
        },
        
        /**
         * Clear all artifacts from the panel
         */
        clearArtifacts: function() {
            const artifactsContent = document.querySelector('.artifacts-content');
            const emptyState = document.querySelector('.empty-state');
            
            if (!artifactsContent) return;
            
            // Remove all artifact items
            const items = artifactsContent.querySelectorAll('.artifact-item');
            items.forEach(item => item.remove());
            
            // Show empty state if it exists
            if (emptyState) {
                emptyState.style.display = 'flex';
            }
        },
        
        /**
         * Toggle the artifacts panel visibility
         */
        toggle: function() {
            if (artifactsButton) {
                artifactsButton.click();
            }
        }
    };
}); 