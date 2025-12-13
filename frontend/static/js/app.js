/**
 * Info-Agent Application JavaScript
 *
 * Main application logic for the Info-Agent dashboard.
 */

(function() {
    'use strict';

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        console.log('[Info-Agent] Application initialized');
        initializeApp();
    });

    /**
     * Initialize the application.
     */
    function initializeApp() {
        // Set up HTMX event handlers
        setupHTMXHandlers();

        // Check for workflow container and connect to SSE
        const workflowContainer = document.getElementById('workflow-container');
        if (workflowContainer) {
            const workflowId = workflowContainer.dataset.workflowId;
            if (workflowId && typeof InfoAgentSSE !== 'undefined') {
                console.log(`[Info-Agent] Auto-connecting to workflow: ${workflowId}`);
                // Connection is handled by the page-specific script
            }
        }

        // Load initial stats if on dashboard
        loadDashboardStats();
    }

    /**
     * Set up HTMX event handlers.
     */
    function setupHTMXHandlers() {
        // Handle HTMX load events
        document.body.addEventListener('htmx:afterSwap', function(event) {
            console.log('[Info-Agent] HTMX content swapped:', event.detail.target.id);
        });

        // Handle HTMX errors
        document.body.addEventListener('htmx:responseError', function(event) {
            console.error('[Info-Agent] HTMX error:', event.detail.xhr.status);
            if (typeof InfoAgentSSE !== 'undefined') {
                InfoAgentSSE.showNotification('Failed to load content', 'error');
            }
        });
    }

    /**
     * Load dashboard statistics.
     */
    async function loadDashboardStats() {
        const statTotal = document.getElementById('stat-total');
        const statCompleted = document.getElementById('stat-completed');
        const statInProgress = document.getElementById('stat-in-progress');

        if (!statTotal) return; // Not on dashboard

        try {
            const response = await fetch('/api/workflows?limit=1000');
            if (!response.ok) return;

            const data = await response.json();
            const workflows = data.workflows || [];

            statTotal.textContent = workflows.length;
            statCompleted.textContent = workflows.filter(w => w.status === 'completed').length;
            statInProgress.textContent = workflows.filter(w =>
                ['executing', 'awaiting_approval', 'planning', 'waiting_for_response'].includes(w.status)
            ).length;

        } catch (error) {
            console.error('[Info-Agent] Failed to load stats:', error);
        }
    }

    /**
     * Format a timestamp for display.
     * @param {string} timestamp - ISO timestamp string
     * @returns {string} Formatted date string
     */
    function formatTimestamp(timestamp) {
        if (!timestamp) return 'Unknown';
        const date = new Date(timestamp);
        return date.toLocaleString();
    }

    /**
     * Format a relative time.
     * @param {string} timestamp - ISO timestamp string
     * @returns {string} Relative time string
     */
    function formatRelativeTime(timestamp) {
        if (!timestamp) return 'Unknown';

        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    }

    /**
     * Copy text to clipboard.
     * @param {string} text - Text to copy
     */
    async function copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            if (typeof InfoAgentSSE !== 'undefined') {
                InfoAgentSSE.showNotification('Copied to clipboard', 'success');
            }
        } catch (error) {
            console.error('[Info-Agent] Failed to copy:', error);
        }
    }

    /**
     * Confirm an action with the user.
     * @param {string} message - Confirmation message
     * @returns {Promise<boolean>} Whether confirmed
     */
    function confirmAction(message) {
        return new Promise(function(resolve) {
            const result = confirm(message);
            resolve(result);
        });
    }

    /**
     * Debounce a function.
     * @param {function} func - Function to debounce
     * @param {number} wait - Wait time in ms
     * @returns {function} Debounced function
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = function() {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Expose utilities globally
    window.InfoAgent = {
        formatTimestamp: formatTimestamp,
        formatRelativeTime: formatRelativeTime,
        copyToClipboard: copyToClipboard,
        confirmAction: confirmAction,
        debounce: debounce,
        loadDashboardStats: loadDashboardStats,
    };

})();
