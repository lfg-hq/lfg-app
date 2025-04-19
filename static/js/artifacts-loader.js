/**
 * Artifacts Loader JavaScript
 * Handles loading artifact data from the server and updating the artifacts panel
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the artifact loaders
    window.ArtifactsLoader = {
        /**
         * Load features from the API for the current project
         * @param {number} projectId - The ID of the current project
         */
        loadFeatures: function(projectId) {
            console.log(`[ArtifactsLoader] loadFeatures called with project ID: ${projectId}`);
            
            if (!projectId) {
                console.warn('[ArtifactsLoader] No project ID provided for loading features');
                return;
            }
            
            // Get features tab content element
            const featuresTab = document.getElementById('features');
            if (!featuresTab) {
                console.warn('[ArtifactsLoader] Features tab element not found');
                return;
            }
            
            // Show loading state
            console.log('[ArtifactsLoader] Showing loading state');
            featuresTab.innerHTML = '<div class="loading-state"><div class="spinner"></div><div>Loading features...</div></div>';
            
            // Fetch features from API
            const url = `/projects/${projectId}/api/features/`;
            console.log(`[ArtifactsLoader] Fetching features from API: ${url}`);
            
            fetch(url)
                .then(response => {
                    console.log(`[ArtifactsLoader] API response received, status: ${response.status}`);
                    if (!response.ok) {
                        throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('[ArtifactsLoader] API data received:', data);
                    // Process features data
                    const features = data.features || [];
                    console.log(`[ArtifactsLoader] Found ${features.length} features`);
                    
                    if (features.length === 0) {
                        // Show empty state if no features found
                        console.log('[ArtifactsLoader] No features found, showing empty state');
                        featuresTab.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">
                                    <i class="fas fa-list-check"></i>
                                </div>
                                <div class="empty-state-text">
                                    No features defined yet.
                                </div>
                            </div>
                        `;
                        return;
                    }
                    
                    // Create features content
                    console.log('[ArtifactsLoader] Rendering features to UI');
                    let featuresHtml = '<div class="features-list">';
                    
                    features.forEach(feature => {
                        const priorityClass = feature.priority.toLowerCase().replace(' ', '-');
                        
                        featuresHtml += `
                            <div class="feature-item">
                                <div class="feature-header">
                                    <h3 class="feature-name">${feature.name}</h3>
                                    <span class="feature-priority ${priorityClass}">${feature.priority}</span>
                                </div>
                                <div class="feature-description">${feature.description}</div>
                                <div class="feature-details markdown-content">
                                    ${typeof marked !== 'undefined' ? marked.parse(feature.details) : feature.details}
                                </div>
                            </div>
                        `;
                    });
                    
                    featuresHtml += '</div>';
                    featuresTab.innerHTML = featuresHtml;
                    
                    // Switch to the features tab to show the newly loaded content
                    if (window.switchTab) {
                        window.switchTab('features');
                    } else if (window.ArtifactsPanel && typeof window.ArtifactsPanel.toggle === 'function') {
                        // Make the artifacts panel visible if it's not
                        window.ArtifactsPanel.toggle();
                    }
                })
                .catch(error => {
                    console.error('Error fetching features:', error);
                    featuresTab.innerHTML = `
                        <div class="error-state">
                            <div class="error-state-icon">
                                <i class="fas fa-exclamation-triangle"></i>
                            </div>
                            <div class="error-state-text">
                                Error loading features. Please try again.
                            </div>
                        </div>
                    `;
                });
        },
        
        /**
         * Load personas from the API for the current project
         * @param {number} projectId - The ID of the current project
         */
        loadPersonas: function(projectId) {
            console.log(`[ArtifactsLoader] loadPersonas called with project ID: ${projectId}`);
            
            if (!projectId) {
                console.warn('[ArtifactsLoader] No project ID provided for loading personas');
                return;
            }
            
            // Get personas tab content element
            const personasTab = document.getElementById('personas');
            if (!personasTab) {
                console.warn('[ArtifactsLoader] Personas tab element not found');
                return;
            }
            
            // Show loading state
            console.log('[ArtifactsLoader] Showing loading state for personas');
            personasTab.innerHTML = '<div class="loading-state"><div class="spinner"></div><div>Loading personas...</div></div>';
            
            // Fetch personas from API
            const url = `/projects/${projectId}/api/personas/`;
            console.log(`[ArtifactsLoader] Fetching personas from API: ${url}`);
            
            fetch(url)
                .then(response => {
                    console.log(`[ArtifactsLoader] Personas API response received, status: ${response.status}`);
                    if (!response.ok) {
                        throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('[ArtifactsLoader] Personas API data received:', data);
                    // Process personas data
                    const personas = data.personas || [];
                    console.log(`[ArtifactsLoader] Found ${personas.length} personas`);
                    
                    if (personas.length === 0) {
                        // Show empty state if no personas found
                        console.log('[ArtifactsLoader] No personas found, showing empty state');
                        personasTab.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">
                                    <i class="fas fa-users"></i>
                                </div>
                                <div class="empty-state-text">
                                    No personas defined yet.
                                </div>
                            </div>
                        `;
                        return;
                    }
                    
                    // Create personas content
                    console.log('[ArtifactsLoader] Rendering personas to UI');
                    let personasHtml = '<div class="personas-list">';
                    
                    personas.forEach(persona => {
                        personasHtml += `
                            <div class="persona-item">
                                <div class="persona-header">
                                    <h3 class="persona-name">${persona.name}</h3>
                                    <span class="persona-role">${persona.role}</span>
                                </div>
                                <div class="persona-description markdown-content">
                                    ${typeof marked !== 'undefined' ? marked.parse(persona.description) : persona.description}
                                </div>
                            </div>
                        `;
                    });
                    
                    personasHtml += '</div>';
                    personasTab.innerHTML = personasHtml;
                })
                .catch(error => {
                    console.error('Error fetching personas:', error);
                    personasTab.innerHTML = `
                        <div class="error-state">
                            <div class="error-state-icon">
                                <i class="fas fa-exclamation-triangle"></i>
                            </div>
                            <div class="error-state-text">
                                Error loading personas. Please try again.
                            </div>
                        </div>
                    `;
                });
        },
        
        /**
         * Load PRD from the API for the current project
         * @param {number} projectId - The ID of the current project
         */
        loadPRD: function(projectId) {
            console.log(`[ArtifactsLoader] loadPRD called with project ID: ${projectId}`);
            
            if (!projectId) {
                console.warn('[ArtifactsLoader] No project ID provided for loading PRD');
                return;
            }
            
            // Get PRD tab content element
            const prdTab = document.getElementById('prd');
            if (!prdTab) {
                console.warn('[ArtifactsLoader] PRD tab element not found');
                return;
            }
            
            // Show loading state
            console.log('[ArtifactsLoader] Showing loading state for PRD');
            prdTab.innerHTML = '<div class="loading-state"><div class="spinner"></div><div>Loading PRD...</div></div>';
            
            // Fetch PRD from API
            const url = `/projects/${projectId}/api/prd/`;
            console.log(`[ArtifactsLoader] Fetching PRD from API: ${url}`);
            
            fetch(url)
                .then(response => {
                    console.log(`[ArtifactsLoader] PRD API response received, status: ${response.status}`);
                    if (!response.ok) {
                        throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('[ArtifactsLoader] PRD API data received:', data);
                    // Process PRD data
                    const prdContent = data.content || '';
                    
                    if (!prdContent) {
                        // Show empty state if no PRD found
                        console.log('[ArtifactsLoader] No PRD found, showing empty state');
                        prdTab.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">
                                    <i class="fas fa-file-alt"></i>
                                </div>
                                <div class="empty-state-text">
                                    No PRD available yet.
                                </div>
                            </div>
                        `;
                        return;
                    }
                    
                    // Render PRD content with markdown
                    prdTab.innerHTML = `
                        <div class="prd-container">
                            <div class="prd-header">
                                <h2>${data.title || 'Product Requirement Document'}</h2>
                                <div class="prd-meta">
                                    ${data.updated_at ? `<span>Last updated: ${data.updated_at}</span>` : ''}
                                </div>
                            </div>
                            <div class="prd-content markdown-content">
                                ${typeof marked !== 'undefined' ? marked.parse(prdContent) : prdContent}
                            </div>
                        </div>
                    `;
                })
                .catch(error => {
                    console.error('Error fetching PRD:', error);
                    prdTab.innerHTML = `
                        <div class="error-state">
                            <div class="error-state-icon">
                                <i class="fas fa-exclamation-triangle"></i>
                            </div>
                            <div class="error-state-text">
                                Error loading PRD. Please try again.
                            </div>
                        </div>
                    `;
                });
        },
        
        /**
         * Load tickets from the API for the current project
         * @param {number} projectId - The ID of the current project
         */
        loadTickets: function(projectId) {
            console.log(`[ArtifactsLoader] loadTickets called with project ID: ${projectId}`);
            
            if (!projectId) {
                console.warn('[ArtifactsLoader] No project ID provided for loading tickets');
                return;
            }
            
            // Get tickets tab content element
            const ticketsTab = document.getElementById('tickets');
            if (!ticketsTab) {
                console.warn('[ArtifactsLoader] Tickets tab element not found');
                return;
            }
            
            // Show loading state
            console.log('[ArtifactsLoader] Showing loading state for tickets');
            ticketsTab.innerHTML = '<div class="loading-state"><div class="spinner"></div><div>Loading tickets...</div></div>';
            
            // Fetch tickets from API - updated to new endpoint in projects app
            const url = `/projects/${projectId}/api/tickets/`;
            console.log(`[ArtifactsLoader] Fetching tickets from API: ${url}`);
            
            fetch(url)
                .then(response => {
                    console.log(`[ArtifactsLoader] Tickets API response received, status: ${response.status}`);
                    if (!response.ok) {
                        throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('[ArtifactsLoader] Tickets API data received:', data);
                    // Process tickets data
                    const tickets = data.tickets || [];
                    console.log(`[ArtifactsLoader] Found ${tickets.length} tickets`);
                    
                    if (tickets.length === 0) {
                        // Show empty state if no tickets found
                        console.log('[ArtifactsLoader] No tickets found, showing empty state');
                        ticketsTab.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">
                                    <i class="fas fa-ticket"></i>
                                </div>
                                <div class="empty-state-text">
                                    No tickets created yet.
                                </div>
                            </div>
                        `;
                        return;
                    }
                    
                    // Extract unique features for filter dropdown
                    const features = [...new Set(tickets.map(ticket => 
                        ticket.feature ? ticket.feature.name : 'Unknown'
                    ))].sort();
                    
                    // Create container for tickets with filter
                    ticketsTab.innerHTML = `
                        <div class="tickets-container">
                            <div class="ticket-filters">
                                <div class="filter-options">
                                    <div class="filter-group">
                                        <select id="feature-filter" class="feature-filter-dropdown">
                                            <option value="all">All Features</option>
                                            ${features.map(feature => `<option value="${feature}">${feature}</option>`).join('')}
                                        </select>
                                        <button id="clear-filters" class="clear-filters-btn" title="Clear filters">
                                            <i class="fas fa-times"></i>
                                        </button>
                                    </div>
                                </div>
                            </div>
                            <div class="tickets-content" id="tickets-content">
                                <!-- Tickets will be loaded here -->
                            </div>
                        </div>
                        
                        <!-- Right Drawer for Ticket Details -->
                        <div class="ticket-details-drawer" id="ticket-details-drawer">
                            <div class="drawer-header">
                                <h3 class="drawer-title">Ticket Details</h3>
                                <button class="close-drawer-btn" id="close-drawer-btn">
                                    <i class="fas fa-times"></i>
                                </button>
                            </div>
                            <div class="drawer-content" id="drawer-content">
                                <!-- Ticket details will be loaded here -->
                            </div>
                        </div>
                        
                        <!-- Overlay for drawer -->
                        <div class="drawer-overlay" id="drawer-overlay"></div>
                    `;
                    
                    const ticketsContent = document.getElementById('tickets-content');
                    const featureFilter = document.getElementById('feature-filter');
                    const clearFiltersBtn = document.getElementById('clear-filters');
                    
                    // Group tickets by status for potential future use
                    const ticketsByStatus = {
                        open: [],
                        in_progress: [],
                        agent: [],
                        closed: []
                    };
                    
                    tickets.forEach(ticket => {
                        const status = ticket.status || 'open';
                        if (ticketsByStatus[status]) {
                            ticketsByStatus[status].push(ticket);
                        } else {
                            ticketsByStatus.open.push(ticket);
                        }
                    });
                    
                    // Function to render tickets based on filter
                    const renderTickets = (filterFeature = 'all') => {
                        let filteredTickets = [...tickets];
                        
                        // Apply feature filter if not 'all'
                        if (filterFeature !== 'all') {
                            filteredTickets = filteredTickets.filter(ticket => 
                                ticket.feature && ticket.feature.name === filterFeature
                            );
                        }
                        
                        // Create HTML for filtered tickets
                        let ticketsHTML = `<div class="tickets-by-status">`;
                        
                        if (filteredTickets.length === 0) {
                            ticketsHTML += `
                                <div class="no-results">
                                    <div class="empty-state-icon">
                                        <i class="fas fa-filter"></i>
                                    </div>
                                    <div class="empty-state-text">
                                        No tickets match your filter criteria.
                                    </div>
                                </div>
                            `;
                        } else {
                            filteredTickets.forEach(ticket => {
                                const featurePriority = ticket.feature ? ticket.feature.priority || 'medium' : 'medium';
                                const priorityClass = `${featurePriority}-priority`;
                                const status = ticket.status || 'open';
                                const isHighlighted = filterFeature !== 'all' && ticket.feature && ticket.feature.name === filterFeature;
                                
                                // Process description for better display
                                let displayDescription = ticket.description || '';
                                const descriptionLimit = 300; // Increased character limit
                                const isTruncated = displayDescription.length > descriptionLimit;
                                
                                if (isTruncated) {
                                    // Find the last space before the limit to avoid cutting words
                                    const lastSpaceIndex = displayDescription.lastIndexOf(' ', descriptionLimit);
                                    const truncateIndex = lastSpaceIndex > 0 ? lastSpaceIndex : descriptionLimit;
                                    displayDescription = displayDescription.substring(0, truncateIndex) + '...';
                                }
                                
                                // Replace newlines with <br> tags for proper formatting
                                displayDescription = displayDescription.replace(/\n/g, '<br>');
                                
                                ticketsHTML += `
                                    <div class="ticket-card" data-ticket-id="${ticket.id}" data-feature="${ticket.feature ? ticket.feature.name : 'Unknown'}">
                                        <div class="card-header ${status}">
                                            <h4 class="card-title">${ticket.title}</h4>
                                        </div>
                                        <div class="card-body">
                                            <div class="card-description">${displayDescription}</div>
                                            
                                            <div class="card-meta">
                                                <div class="card-tags">
                                                    <span class="feature-tag ${priorityClass} ${isHighlighted ? 'filter-active' : ''}">
                                                        <i class="fas fa-tag"></i> ${ticket.feature ? ticket.feature.name : 'Unknown Feature'}
                                                    </span>
                                                    <span class="status-tag status-${status}">
                                                        ${status.replace('_', ' ').charAt(0).toUpperCase() + status.replace('_', ' ').slice(1)}
                                                    </span>
                                                </div>
                                                <button class="view-details-btn" data-ticket-id="${ticket.id}" title="View details">
                                                    <i class="fas fa-info-circle"></i>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                `;
                            });
                        }
                        
                        ticketsHTML += `</div>`;
                        ticketsContent.innerHTML = ticketsHTML;
                        
                        // Reattach event listeners after rendering
                        attachDetailViewListeners();
                    };
                    
                    // Function to attach event listeners for detail view buttons
                    const attachDetailViewListeners = () => {
                        // Add event listeners for the details buttons
                        const detailsButtons = document.querySelectorAll('.view-details-btn');
                        const detailsDrawer = document.getElementById('ticket-details-drawer');
                        const drawerOverlay = document.getElementById('drawer-overlay');
                        const closeDrawerBtn = document.getElementById('close-drawer-btn');
                        
                        detailsButtons.forEach(button => {
                            button.addEventListener('click', function(e) {
                                const ticketId = this.getAttribute('data-ticket-id');
                                const ticket = tickets.find(t => t.id == ticketId);
                                
                                if (ticket) {
                                    // Populate drawer with ticket details
                                    const drawerContent = document.getElementById('drawer-content');
                                    drawerContent.innerHTML = `
                                        <div class="drawer-section">
                                            <h4 class="section-title">Ticket Information</h4>
                                            <p class="ticket-id"><strong>ID:</strong> ${ticket.ticket_id}</p>
                                            <p class="ticket-title"><strong>Title:</strong> ${ticket.title}</p>
                                            <p class="ticket-status"><strong>Status:</strong> ${ticket.status.replace('_', ' ').charAt(0).toUpperCase() + ticket.status.replace('_', ' ').slice(1)}</p>
                                            <p class="ticket-feature"><strong>Feature:</strong> ${ticket.feature.name}</p>
                                        </div>
                                        
                                        <div class="drawer-section">
                                            <h4 class="section-title">Description</h4>
                                            <div class="section-content description-content">
                                                ${ticket.description.replace(/\n/g, '<br>')}
                                            </div>
                                        </div>
                                        
                                        <div class="drawer-section">
                                            <h4 class="section-title">Frontend Tasks</h4>
                                            <div class="section-content">
                                                ${ticket.frontend_tasks ? ticket.frontend_tasks.replace(/\n/g, '<br>') : 'No frontend tasks specified.'}
                                            </div>
                                        </div>
                                        
                                        <div class="drawer-section">
                                            <h4 class="section-title">Backend Tasks</h4>
                                            <div class="section-content">
                                                ${ticket.backend_tasks ? ticket.backend_tasks.replace(/\n/g, '<br>') : 'No backend tasks specified.'}
                                            </div>
                                        </div>
                                        
                                        <div class="drawer-section">
                                            <h4 class="section-title">Implementation Steps</h4>
                                            <div class="section-content">
                                                ${ticket.implementation_steps ? ticket.implementation_steps.replace(/\n/g, '<br>') : 'No implementation steps specified.'}
                                            </div>
                                        </div>
                                    `;
                                    
                                    // Show the drawer
                                    detailsDrawer.classList.add('open');
                                    drawerOverlay.classList.add('active');
                                }
                            });
                        });
                        
                        // Close drawer when clicking close button or overlay
                        if (closeDrawerBtn) {
                            closeDrawerBtn.addEventListener('click', function() {
                                detailsDrawer.classList.remove('open');
                                drawerOverlay.classList.remove('active');
                            });
                        }
                        
                        if (drawerOverlay) {
                            drawerOverlay.addEventListener('click', function() {
                                detailsDrawer.classList.remove('open');
                                drawerOverlay.classList.remove('active');
                            });
                        }
                    };
                    
                    // Add event listeners for filters
                    if (featureFilter) {
                        featureFilter.addEventListener('change', function() {
                            renderTickets(this.value);
                        });
                    }
                    
                    if (clearFiltersBtn) {
                        clearFiltersBtn.addEventListener('click', function() {
                            featureFilter.value = 'all';
                            renderTickets('all');
                        });
                    }
                    
                    // Initial render with all tickets
                    renderTickets();
                })
                .catch(error => {
                    console.error('Error fetching tickets:', error);
                    ticketsTab.innerHTML = `
                        <div class="error-state">
                            <div class="error-state-icon">
                                <i class="fas fa-exclamation-triangle"></i>
                            </div>
                            <div class="error-state-text">
                                Error loading tickets. Please try again.
                            </div>
                        </div>
                    `;
                });
        },
        
        /**
         * Load design schema from the API for the current project
         * @param {number} projectId - The ID of the current project
         */
        loadDesignSchema: function(projectId) {
            console.log(`[ArtifactsLoader] loadDesignSchema called with project ID: ${projectId}`);
            
            if (!projectId) {
                console.warn('[ArtifactsLoader] No project ID provided for loading design schema');
                return;
            }
            
            // Get design schema tab content element
            const designTab = document.getElementById('design');
            if (!designTab) {
                console.warn('[ArtifactsLoader] Design tab element not found');
                return;
            }
            
            // Show loading state
            console.log('[ArtifactsLoader] Showing loading state for design schema');
            designTab.innerHTML = '<div class="loading-state"><div class="spinner"></div><div>Loading design schema...</div></div>';
            
            // Fetch design schema from API
            const url = `/projects/${projectId}/api/design-schema/`;
            console.log(`[ArtifactsLoader] Fetching design schema from API: ${url}`);
            
            fetch(url)
                .then(response => {
                    console.log(`[ArtifactsLoader] Design schema API response received, status: ${response.status}`);
                    if (!response.ok) {
                        throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('[ArtifactsLoader] Design schema API data received:', data);
                    // Process design schema data
                    const designSchemaContent = data.content || '';
                    
                    if (!designSchemaContent) {
                        // Show empty state if no design schema found
                        console.log('[ArtifactsLoader] No design schema found, showing empty state');
                        designTab.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-state-icon">
                                    <i class="fas fa-file-alt"></i>
                                </div>
                                <div class="empty-state-text">
                                    No design schema available yet.
                                </div>
                            </div>
                        `;
                        return;
                    }
                    
                    // Render design schema content with markdown
                    designTab.innerHTML = `
                        <div class="design-schema-container">
                            <div class="design-schema-header">
                                <h2>${data.title || 'Design Schema'}</h2>
                                <div class="design-schema-meta">
                                    ${data.updated_at ? `<span>Last updated: ${data.updated_at}</span>` : ''}
                                </div>
                            </div>
                            <div class="design-schema-content markdown-content">
                                ${typeof marked !== 'undefined' ? marked.parse(designSchemaContent) : designSchemaContent}
                            </div>
                        </div>
                    `;
                })
                .catch(error => {
                    console.error('Error fetching design schema:', error);
                    designTab.innerHTML = `
                        <div class="error-state">
                            <div class="error-state-icon">
                                <i class="fas fa-exclamation-triangle"></i>
                            </div>
                            <div class="error-state-text">
                                Error loading design schema. Please try again.
                            </div>
                        </div>
                    `;
                });
        }
    };
    
    // Switch tab helper function
    window.switchTab = function(tabId) {
        console.log(`[ArtifactsLoader] Switching to tab: ${tabId}`);
        
        // Get tab elements
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabPanes = document.querySelectorAll('.tab-pane');
        
        // Remove active class from all buttons and panes
        tabButtons.forEach(button => button.classList.remove('active'));
        tabPanes.forEach(pane => pane.classList.remove('active'));
        
        // Add active class to the selected tab
        const selectedButton = document.querySelector(`.tab-button[data-tab="${tabId}"]`);
        const selectedPane = document.getElementById(tabId);
        
        if (selectedButton && selectedPane) {
            selectedButton.classList.add('active');
            selectedPane.classList.add('active');
            
            // Load data for the tab if it's empty
            if (selectedPane.querySelector('.empty-state')) {
                loadTabData(tabId);
            }
        }
    };
    
    // Set up tab switching event listeners
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            window.switchTab(tabId);
        });
    });
    
    // Function to load data for a tab
    function loadTabData(tabId) {
        const projectId = getCurrentProjectId();
        if (!projectId) {
            console.warn('[ArtifactsLoader] No project ID available for loading tab data');
            return;
        }
        
        console.log(`[ArtifactsLoader] Loading data for tab: ${tabId}`);
        
        switch (tabId) {
            case 'prd':
                window.ArtifactsLoader.loadPRD(projectId);
                break;
            case 'features':
                window.ArtifactsLoader.loadFeatures(projectId);
                break;
            case 'personas':
                window.ArtifactsLoader.loadPersonas(projectId);
                break;
            case 'design':
                if (window.ArtifactsLoader.loadDesignSchema) {
                    window.ArtifactsLoader.loadDesignSchema(projectId);
                }
                break;
            case 'tickets':
                window.ArtifactsLoader.loadTickets(projectId);
                break;
            // Add more cases as needed for other tabs
        }
    }
    
    // Function to get current project ID from URL or stored value
    function getCurrentProjectId() {
        // Try to get from URL path (e.g. /chat/project/123/)
        const pathMatch = window.location.pathname.match(/\/project\/(\d+)/);
        if (pathMatch && pathMatch[1]) {
            return pathMatch[1];
        }
        
        // Try to get from URL query parameter
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('project_id')) {
            return urlParams.get('project_id');
        }
        
        // Try to get from stored value in localStorage
        return localStorage.getItem('current_project_id');
    }
});