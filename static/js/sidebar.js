document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('sidebar');
    const appContainer = document.querySelector('.app-container');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    
    // Function to determine if mouse is in the left 10% of screen
    function isInLeftZone(e) {
        const screenWidth = window.innerWidth;
        const hoverZoneWidth = screenWidth * 0.1; // 10% of screen width
        return e.clientX <= hoverZoneWidth;
    }
    
    // Expand sidebar when mouse enters the left zone
    document.addEventListener('mousemove', (e) => {
        if (isInLeftZone(e)) {
            sidebar.classList.add('expanded');
            appContainer.classList.add('sidebar-expanded');
        } else {
            sidebar.classList.remove('expanded');
            appContainer.classList.remove('sidebar-expanded');
        }
    });
    
    // Handle touch devices - toggle on sidebar touch
    sidebar.addEventListener('touchstart', (e) => {
        if (!sidebar.classList.contains('expanded')) {
            e.preventDefault();
            sidebar.classList.add('expanded');
            appContainer.classList.add('sidebar-expanded');
        }
    });
    
    // Close on touch outside sidebar
    document.addEventListener('touchstart', (e) => {
        if (sidebar.classList.contains('expanded') && !sidebar.contains(e.target)) {
            sidebar.classList.remove('expanded');
            appContainer.classList.remove('sidebar-expanded');
        }
    });
    
    // Close sidebar when clicking on overlay
    sidebarOverlay.addEventListener('click', () => {
        sidebar.classList.remove('expanded');
        appContainer.classList.remove('sidebar-expanded');
    });
}); 