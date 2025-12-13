/**
 * AG-UI Event Handler for Info-Agent
 *
 * This module handles Server-Sent Events (SSE) for real-time
 * workflow updates following the AG-UI protocol.
 */

const InfoAgentSSE = (function() {
    'use strict';

    // Private state
    let eventSource = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 5;
    const RECONNECT_DELAY_MS = 2000;

    /**
     * Connect to the SSE stream for a workflow.
     * @param {string} workflowId - The workflow identifier
     * @param {function} onEvent - Callback for received events
     * @returns {EventSource} The event source connection
     */
    function connect(workflowId, onEvent) {
        if (eventSource) {
            disconnect();
        }

        const url = `/api/workflows/${workflowId}/stream`;
        console.log(`[AG-UI] Connecting to SSE stream: ${url}`);

        eventSource = new EventSource(url);

        eventSource.onopen = function() {
            console.log('[AG-UI] SSE connection opened');
            reconnectAttempts = 0;
            updateConnectionStatus('connected');
        };

        eventSource.onerror = function(error) {
            console.error('[AG-UI] SSE connection error:', error);
            updateConnectionStatus('error');

            if (eventSource.readyState === EventSource.CLOSED) {
                handleReconnect(workflowId, onEvent);
            }
        };

        // Handle named events
        const eventTypes = [
            'RUN_STARTED',
            'RUN_FINISHED',
            'RUN_ERROR',
            'TEXT_MESSAGE_START',
            'TEXT_MESSAGE_CONTENT',
            'TEXT_MESSAGE_END',
            'TOOL_CALL_START',
            'TOOL_CALL_ARGS',
            'TOOL_CALL_END',
            'STATE_SNAPSHOT',
            'STATE_DELTA',
            'PLAN_GENERATED',
            'PLAN_APPROVED',
            'PLAN_REJECTED',
            'STEP_STARTED',
            'STEP_COMPLETED',
            'STEP_FAILED',
            'EMAIL_SENT',
            'EMAIL_RECEIVED',
            'CLARIFICATION_NEEDED',
            'CLARIFICATION_RESOLVED',
            'ESCALATION_TRIGGERED',
            'VALIDATION_STARTED',
            'VALIDATION_COMPLETE',
            'TIMEOUT_WARNING',
        ];

        eventTypes.forEach(function(eventType) {
            eventSource.addEventListener(eventType, function(event) {
                handleEvent(eventType, event, onEvent);
            });
        });

        // Handle generic messages
        eventSource.onmessage = function(event) {
            handleEvent('message', event, onEvent);
        };

        return eventSource;
    }

    /**
     * Disconnect from the SSE stream.
     */
    function disconnect() {
        if (eventSource) {
            console.log('[AG-UI] Disconnecting SSE stream');
            eventSource.close();
            eventSource = null;
            updateConnectionStatus('disconnected');
        }
    }

    /**
     * Handle incoming SSE event.
     * @param {string} eventType - The event type
     * @param {MessageEvent} event - The raw SSE event
     * @param {function} callback - User callback
     */
    function handleEvent(eventType, event, callback) {
        try {
            const data = JSON.parse(event.data);
            console.log(`[AG-UI] Received event: ${eventType}`, data);

            // Dispatch to UI handlers
            dispatchToUI(eventType, data);

            // Call user callback
            if (typeof callback === 'function') {
                callback(data);
            }
        } catch (error) {
            console.error('[AG-UI] Error parsing event:', error);
        }
    }

    /**
     * Dispatch event to UI components.
     * @param {string} eventType - The event type
     * @param {object} data - The event data
     */
    function dispatchToUI(eventType, data) {
        switch (eventType) {
            case 'RUN_STARTED':
                showNotification('Workflow started', 'info');
                break;

            case 'RUN_FINISHED':
                showNotification('Workflow completed', 'success');
                updateConnectionStatus('completed');
                break;

            case 'RUN_ERROR':
                showNotification(`Error: ${data.error}`, 'error');
                updateConnectionStatus('error');
                break;

            case 'PLAN_GENERATED':
                showNotification('Execution plan ready for approval', 'info');
                break;

            case 'PLAN_APPROVED':
                showNotification('Plan approved - execution starting', 'success');
                break;

            case 'EMAIL_SENT':
                showNotification(`Email sent to ${data.to_address}`, 'info');
                break;

            case 'EMAIL_RECEIVED':
                showNotification(`Email received from ${data.from_address}`, 'info');
                break;

            case 'VALIDATION_STARTED':
                showNotification('Document validation started', 'info');
                break;

            case 'VALIDATION_COMPLETE':
                const status = data.passed ? 'passed' : 'failed';
                showNotification(`Validation ${status}`, data.passed ? 'success' : 'error');
                break;

            case 'ESCALATION_TRIGGERED':
                showNotification('Escalation triggered', 'warning');
                break;

            case 'TIMEOUT_WARNING':
                showNotification('Approaching timeout', 'warning');
                break;
        }
    }

    /**
     * Handle reconnection attempts.
     * @param {string} workflowId - The workflow identifier
     * @param {function} onEvent - Callback for received events
     */
    function handleReconnect(workflowId, onEvent) {
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            console.error('[AG-UI] Max reconnect attempts reached');
            showNotification('Connection lost. Please refresh the page.', 'error');
            return;
        }

        reconnectAttempts++;
        const delay = RECONNECT_DELAY_MS * reconnectAttempts;

        console.log(`[AG-UI] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
        updateConnectionStatus('reconnecting');

        setTimeout(function() {
            connect(workflowId, onEvent);
        }, delay);
    }

    /**
     * Update the connection status indicator.
     * @param {string} status - The connection status
     */
    function updateConnectionStatus(status) {
        const statusEl = document.getElementById('connection-status');
        if (!statusEl) return;

        const statusConfig = {
            'connected': {
                text: 'Connected',
                class: 'bg-green-100 text-green-800',
            },
            'disconnected': {
                text: 'Disconnected',
                class: 'bg-gray-100 text-gray-800',
            },
            'reconnecting': {
                text: 'Reconnecting...',
                class: 'bg-yellow-100 text-yellow-800',
            },
            'error': {
                text: 'Error',
                class: 'bg-red-100 text-red-800',
            },
            'completed': {
                text: 'Completed',
                class: 'bg-green-100 text-green-800',
            },
        };

        const config = statusConfig[status] || statusConfig['disconnected'];
        statusEl.textContent = config.text;
        statusEl.className = `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.class}`;
    }

    /**
     * Show a notification toast.
     * @param {string} message - The notification message
     * @param {string} type - The notification type (info, success, warning, error)
     */
    function showNotification(message, type) {
        // Check if notification container exists
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'fixed top-4 right-4 z-50 space-y-2';
            document.body.appendChild(container);
        }

        const colors = {
            'info': 'bg-blue-500',
            'success': 'bg-green-500',
            'warning': 'bg-yellow-500',
            'error': 'bg-red-500',
        };

        const notification = document.createElement('div');
        notification.className = `${colors[type] || colors['info']} text-white px-4 py-2 rounded-lg shadow-lg transform transition-all duration-300 translate-x-full`;
        notification.textContent = message;

        container.appendChild(notification);

        // Animate in
        requestAnimationFrame(function() {
            notification.classList.remove('translate-x-full');
        });

        // Auto-remove after 5 seconds
        setTimeout(function() {
            notification.classList.add('translate-x-full');
            setTimeout(function() {
                notification.remove();
            }, 300);
        }, 5000);
    }

    /**
     * Get connection status.
     * @returns {boolean} Whether connected
     */
    function isConnected() {
        return eventSource !== null && eventSource.readyState === EventSource.OPEN;
    }

    // Public API
    return {
        connect: connect,
        disconnect: disconnect,
        isConnected: isConnected,
        showNotification: showNotification,
    };
})();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = InfoAgentSSE;
}
