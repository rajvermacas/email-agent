# Info-Agent Phase 4: Full UI Architecture

## Executive Summary

This document describes the **Full UI** for the Info-Agent system. Building on all previous phases, this final phase adds real-time AG-UI integration, detailed validation results, audit log viewing, and completes the three-tab demo setup.

### Phase 4 Goals

1. Implement AG-UI real-time streaming in the frontend
2. Replace polling with SSE for instant updates
3. Build detailed validation results view
4. Create filterable audit log viewer
5. Add email thread visualization
6. Implement countdown timers for timeouts
7. Build agent activity log display
8. Add plan iteration UI with feedback
9. Complete the three-tab demo setup

### What This Phase Delivers

- A complete real-time dashboard that can:
  - Stream live updates via AG-UI protocol (SSE)
  - Display agent activity in real-time
  - Show detailed validation results with criteria breakdown
  - View and filter complete audit history
  - Visualize email conversation threads
  - Display countdown timers for pending responses
  - Support plan iteration with user feedback
  - Run the complete three-tab demo scenario

### Prerequisites

- Phases 1, 2, and 3 fully implemented and working
- All backend and UI tests passing
- AG-UI streaming endpoint functional (Phase 2)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER                                         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Real-Time Dashboard (AG-UI)                         │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │                     AG-UI Event Handler                          │   │ │
│  │  │                     (ag-ui.js via SSE)                           │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │                              │                                          │ │
│  │              ┌───────────────┼───────────────┐                         │ │
│  │              │               │               │                         │ │
│  │              ▼               ▼               ▼                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │ │
│  │  │ Execution    │  │ Agent        │  │ Countdown    │                 │ │
│  │  │ Status       │  │ Activity     │  │ Timer        │                 │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                 │ │
│  │                                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │ │
│  │  │ Email Thread │  │ Validation   │  │ Audit Log    │                 │ │
│  │  │ Viewer       │  │ Results      │  │ Viewer       │                 │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                          SSE Connection                                      │
│                                    │                                         │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI GATEWAY (Port 8000)                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    AG-UI SSE Streaming Endpoint                         ││
│  │                    POST /api/workflows/{id}/stream                      ││
│  │                                                                         ││
│  │    Events: RUN_STARTED, TEXT_MESSAGE_CONTENT, TOOL_CALL_START,         ││
│  │            STATE_DELTA, PLAN_GENERATED, EMAIL_SENT, EMAIL_RECEIVED,    ││
│  │            CLARIFICATION_NEEDED, VALIDATION_COMPLETE, RUN_FINISHED     ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                    Template Routes (Enhanced)                           ││
│  │    GET  /workflows/{id}/execute  → Real-time execution view            ││
│  │    GET  /workflows/{id}/results  → Validation results view             ││
│  │    GET  /workflows/{id}/audit    → Audit log viewer                    ││
│  │    GET  /workflows/{id}/emails   → Email thread viewer                 ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### Three-Tab Demo Setup

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DEMO BROWSER SETUP                              │
│                                                                              │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │      TAB 1          │  │      TAB 2          │  │      TAB 3          │ │
│  │                     │  │                     │  │                     │ │
│  │  System Dashboard   │  │  raj@gmail.com      │  │  mrinal@gmail.com   │ │
│  │  localhost:8000     │  │  localhost:8025     │  │  localhost:8025     │ │
│  │                     │  │                     │  │                     │ │
│  │  • Create workflow  │  │  • Receive requests │  │  • Receive          │ │
│  │  • Approve plan     │  │  • Ask questions    │  │    escalations      │ │
│  │  • Watch execution  │  │  • Send replies     │  │  • Answer questions │ │
│  │  • View results     │  │  • Upload files     │  │  • Provide answers  │ │
│  │                     │  │                     │  │                     │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│                                                                              │
│                           END USER              TARGET        ESCALATION    │
│                           (mrinal)              PERSON        CONTACT       │
│                                                 (raj)         (mrinal)      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## AG-UI Frontend Integration

### AG-UI Event Handler (`ag-ui.js`)

```javascript
/**
 * AG-UI Event Handler for Info-Agent Dashboard
 * Handles real-time streaming of workflow events via SSE
 */

class AGUIEventHandler {
    constructor(workflowId, options = {}) {
        this.workflowId = workflowId;
        this.eventSource = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
        this.reconnectDelay = options.reconnectDelay || 1000;

        // UI element references
        this.elements = {
            statusBadge: document.getElementById('status-badge'),
            activityLog: document.getElementById('activity-log'),
            agentOutput: document.getElementById('agent-output'),
            countdownTimer: document.getElementById('countdown-timer'),
            emailThread: document.getElementById('email-thread'),
            currentStep: document.getElementById('current-step'),
            progressBar: document.getElementById('progress-bar'),
            alertContainer: document.getElementById('alert-container')
        };

        // Event handlers map
        this.handlers = {
            'RUN_STARTED': this.handleRunStarted.bind(this),
            'RUN_FINISHED': this.handleRunFinished.bind(this),
            'RUN_ERROR': this.handleRunError.bind(this),
            'TEXT_MESSAGE_START': this.handleTextMessageStart.bind(this),
            'TEXT_MESSAGE_CONTENT': this.handleTextMessageContent.bind(this),
            'TEXT_MESSAGE_END': this.handleTextMessageEnd.bind(this),
            'TOOL_CALL_START': this.handleToolCallStart.bind(this),
            'TOOL_CALL_ARGS': this.handleToolCallArgs.bind(this),
            'TOOL_CALL_END': this.handleToolCallEnd.bind(this),
            'STATE_SNAPSHOT': this.handleStateSnapshot.bind(this),
            'STATE_DELTA': this.handleStateDelta.bind(this),
            'PLAN_GENERATED': this.handlePlanGenerated.bind(this),
            'PLAN_APPROVED': this.handlePlanApproved.bind(this),
            'EMAIL_SENT': this.handleEmailSent.bind(this),
            'EMAIL_RECEIVED': this.handleEmailReceived.bind(this),
            'CLARIFICATION_NEEDED': this.handleClarificationNeeded.bind(this),
            'VALIDATION_STARTED': this.handleValidationStarted.bind(this),
            'VALIDATION_COMPLETE': this.handleValidationComplete.bind(this),
            'ESCALATION_TRIGGERED': this.handleEscalationTriggered.bind(this),
            'TIMEOUT_WARNING': this.handleTimeoutWarning.bind(this)
        };
    }

    /**
     * Connect to the AG-UI SSE stream
     */
    connect() {
        console.log(`Connecting to AG-UI stream for workflow ${this.workflowId}`);

        this.eventSource = new EventSource(
            `/api/workflows/${this.workflowId}/stream`
        );

        this.eventSource.onopen = () => {
            console.log('AG-UI connection established');
            this.reconnectAttempts = 0;
            this.showConnectionStatus('connected');
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleEvent(data);
            } catch (error) {
                console.error('Failed to parse AG-UI event:', error);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('AG-UI connection error:', error);
            this.showConnectionStatus('disconnected');
            this.attemptReconnect();
        };
    }

    /**
     * Disconnect from the AG-UI stream
     */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
            console.log('AG-UI connection closed');
        }
    }

    /**
     * Attempt to reconnect after connection loss
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.showAlert('Connection lost. Please refresh the page.', 'error');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`Attempting reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
        this.showConnectionStatus('reconnecting');

        setTimeout(() => {
            this.disconnect();
            this.connect();
        }, delay);
    }

    /**
     * Route event to appropriate handler
     */
    handleEvent(event) {
        console.log('AG-UI Event:', event.type, event.data);

        const handler = this.handlers[event.type];
        if (handler) {
            handler(event);
        } else {
            console.warn('Unknown event type:', event.type);
        }

        // Always log to activity
        this.logActivity(event);
    }

    // ==================== Lifecycle Event Handlers ====================

    handleRunStarted(event) {
        this.updateStatusBadge('executing', 'Executing');
        this.showAlert('Workflow execution started', 'info');
        this.clearAgentOutput();
    }

    handleRunFinished(event) {
        const passed = event.data.validation_passed;
        const status = passed ? 'completed' : 'completed';
        const label = passed ? 'Completed (Passed)' : 'Completed (Failed)';

        this.updateStatusBadge(status, label);
        this.showAlert(
            passed ? 'Workflow completed successfully!' : 'Workflow completed with validation failure',
            passed ? 'success' : 'warning'
        );

        // Redirect to results after delay
        setTimeout(() => {
            window.location.href = `/workflows/${this.workflowId}/results`;
        }, 2000);
    }

    handleRunError(event) {
        this.updateStatusBadge('failed', 'Failed');
        this.showAlert(`Error: ${event.data.error || 'Unknown error'}`, 'error');
    }

    // ==================== Content Event Handlers ====================

    handleTextMessageStart(event) {
        // Prepare for incoming text
        this.appendAgentOutput('<div class="agent-message" id="current-message">');
    }

    handleTextMessageContent(event) {
        const content = event.data.content || '';
        const messageEl = document.getElementById('current-message');
        if (messageEl) {
            messageEl.innerHTML += this.escapeHtml(content);
        }
    }

    handleTextMessageEnd(event) {
        const messageEl = document.getElementById('current-message');
        if (messageEl) {
            messageEl.removeAttribute('id');
            messageEl.innerHTML += '</div>';
        }
    }

    // ==================== Tool Event Handlers ====================

    handleToolCallStart(event) {
        const tool = event.data.tool || 'Unknown tool';
        const description = event.data.description || '';

        this.appendAgentOutput(`
            <div class="tool-call" id="tool-${event.data.tool_call_id || 'current'}">
                <div class="flex items-center gap-2 text-sm text-gray-600">
                    <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    <span class="font-medium">${this.escapeHtml(tool)}</span>
                    <span class="text-gray-400">${this.escapeHtml(description)}</span>
                </div>
            </div>
        `);
    }

    handleToolCallArgs(event) {
        // Optional: Display tool arguments if needed
    }

    handleToolCallEnd(event) {
        const toolId = event.data.tool_call_id || 'current';
        const toolEl = document.getElementById(`tool-${toolId}`);

        if (toolEl) {
            // Replace spinner with checkmark
            toolEl.querySelector('svg').outerHTML = `
                <svg class="h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
            `;
        }
    }

    // ==================== State Event Handlers ====================

    handleStateSnapshot(event) {
        this.updateWorkflowState(event.data);
    }

    handleStateDelta(event) {
        this.updateWorkflowState(event.data);
    }

    // ==================== Custom Event Handlers ====================

    handlePlanGenerated(event) {
        this.updateStatusBadge('awaiting_approval', 'Awaiting Approval');
        this.showAlert('Execution plan generated. Please review and approve.', 'info');

        // Show approval button
        const approveBtn = document.getElementById('approve-plan-btn');
        if (approveBtn) {
            approveBtn.classList.remove('hidden');
        }
    }

    handlePlanApproved(event) {
        this.updateStatusBadge('executing', 'Executing');
        this.showAlert('Plan approved. Execution starting...', 'success');
    }

    handleEmailSent(event) {
        const to = event.data.to || 'recipient';
        this.showAlert(`Email sent to ${to}`, 'info');
        this.addEmailToThread(event.data, 'sent');
    }

    handleEmailReceived(event) {
        const from = event.data.from || 'sender';
        this.showAlert(`Email received from ${from}`, 'info');
        this.addEmailToThread(event.data, 'received');
    }

    handleClarificationNeeded(event) {
        const question = event.data.question || 'Unknown question';
        this.updateStatusBadge('escalated', 'Escalated');
        this.showAlert(`Clarification needed: ${question}`, 'warning');
    }

    handleValidationStarted(event) {
        this.updateStatusBadge('validating', 'Validating');
        this.showAlert('Document validation in progress...', 'info');
    }

    handleValidationComplete(event) {
        const passed = event.data.passed;
        const score = event.data.score || 0;

        this.showAlert(
            `Validation ${passed ? 'passed' : 'failed'} (Score: ${(score * 100).toFixed(0)}%)`,
            passed ? 'success' : 'warning'
        );
    }

    handleEscalationTriggered(event) {
        const reason = event.data.reason || 'Unknown';
        this.updateStatusBadge('escalated', 'Escalated');
        this.showAlert(`Escalation triggered: ${reason}`, 'warning');
    }

    handleTimeoutWarning(event) {
        const retryCount = event.data.retry_count || 0;
        const maxRetries = event.data.max_retries || 3;

        this.showAlert(
            `Timeout reached. Retry ${retryCount + 1} of ${maxRetries}`,
            'warning'
        );

        // Update countdown timer if present
        this.updateCountdownTimer(event.data.timeout_check);
    }

    // ==================== UI Update Methods ====================

    updateStatusBadge(status, label) {
        if (!this.elements.statusBadge) return;

        const statusConfig = {
            'created': { bg: 'bg-gray-100', text: 'text-gray-800' },
            'planning': { bg: 'bg-blue-100', text: 'text-blue-800' },
            'awaiting_approval': { bg: 'bg-yellow-100', text: 'text-yellow-800' },
            'executing': { bg: 'bg-blue-100', text: 'text-blue-800' },
            'waiting_for_response': { bg: 'bg-purple-100', text: 'text-purple-800' },
            'escalated': { bg: 'bg-orange-100', text: 'text-orange-800' },
            'validating': { bg: 'bg-indigo-100', text: 'text-indigo-800' },
            'completed': { bg: 'bg-green-100', text: 'text-green-800' },
            'failed': { bg: 'bg-red-100', text: 'text-red-800' }
        };

        const config = statusConfig[status] || statusConfig.created;

        this.elements.statusBadge.className = `inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${config.bg} ${config.text}`;
        this.elements.statusBadge.textContent = label;
    }

    appendAgentOutput(html) {
        if (!this.elements.agentOutput) return;

        this.elements.agentOutput.insertAdjacentHTML('beforeend', html);
        this.elements.agentOutput.scrollTop = this.elements.agentOutput.scrollHeight;
    }

    clearAgentOutput() {
        if (!this.elements.agentOutput) return;
        this.elements.agentOutput.innerHTML = '';
    }

    logActivity(event) {
        if (!this.elements.activityLog) return;

        const timestamp = new Date(event.timestamp).toLocaleTimeString();
        const entry = document.createElement('div');
        entry.className = 'flex gap-x-3 text-sm py-2 border-b border-gray-100';
        entry.innerHTML = `
            <span class="text-gray-400 w-20 flex-shrink-0">${timestamp}</span>
            <span class="font-medium text-gray-700">${this.escapeHtml(event.type)}</span>
        `;

        this.elements.activityLog.insertBefore(entry, this.elements.activityLog.firstChild);

        // Limit entries
        while (this.elements.activityLog.children.length > 50) {
            this.elements.activityLog.removeChild(this.elements.activityLog.lastChild);
        }
    }

    addEmailToThread(emailData, direction) {
        if (!this.elements.emailThread) return;

        const isOutgoing = direction === 'sent';
        const entry = document.createElement('div');
        entry.className = `flex ${isOutgoing ? 'justify-end' : 'justify-start'} mb-4`;
        entry.innerHTML = `
            <div class="max-w-md ${isOutgoing ? 'bg-primary-100' : 'bg-gray-100'} rounded-lg p-4">
                <div class="flex items-center gap-2 mb-2">
                    <span class="text-xs font-medium ${isOutgoing ? 'text-primary-700' : 'text-gray-700'}">
                        ${isOutgoing ? 'To: ' : 'From: '}${this.escapeHtml(isOutgoing ? emailData.to : emailData.from)}
                    </span>
                </div>
                <p class="text-sm font-medium text-gray-900">${this.escapeHtml(emailData.subject || 'No subject')}</p>
                <p class="text-sm text-gray-600 mt-1">${this.escapeHtml((emailData.body || '').substring(0, 200))}...</p>
                ${emailData.attachments?.length ? `
                    <div class="mt-2 text-xs text-gray-500">
                        <svg class="inline h-3 w-3" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
                        </svg>
                        ${emailData.attachments.length} attachment(s)
                    </div>
                ` : ''}
            </div>
        `;

        this.elements.emailThread.appendChild(entry);
        this.elements.emailThread.scrollTop = this.elements.emailThread.scrollHeight;
    }

    updateCountdownTimer(timeoutData) {
        if (!this.elements.countdownTimer || !timeoutData) return;

        const remaining = timeoutData.time_remaining_seconds || 0;

        if (remaining <= 0) {
            this.elements.countdownTimer.innerHTML = `
                <span class="text-red-600 font-medium">Timeout reached</span>
            `;
        } else {
            const hours = Math.floor(remaining / 3600);
            const minutes = Math.floor((remaining % 3600) / 60);
            const seconds = Math.floor(remaining % 60);

            this.elements.countdownTimer.innerHTML = `
                <span class="font-mono text-lg">
                    ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}
                </span>
                <span class="text-sm text-gray-500 ml-2">remaining</span>
            `;
        }
    }

    updateWorkflowState(stateData) {
        // Update current step indicator
        if (stateData.current_step !== undefined && this.elements.currentStep) {
            this.elements.currentStep.textContent = `Step ${stateData.current_step + 1}`;
        }

        // Update progress bar
        if (stateData.plan && stateData.current_step !== undefined && this.elements.progressBar) {
            const progress = ((stateData.current_step + 1) / stateData.plan.length) * 100;
            this.elements.progressBar.style.width = `${progress}%`;
        }

        // Update status if changed
        if (stateData.status) {
            this.updateStatusBadge(stateData.status, this.formatStatus(stateData.status));
        }
    }

    showAlert(message, type = 'info') {
        if (!this.elements.alertContainer) return;

        const alertConfig = {
            'info': { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', icon: 'text-blue-400' },
            'success': { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-800', icon: 'text-green-400' },
            'warning': { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-800', icon: 'text-yellow-400' },
            'error': { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800', icon: 'text-red-400' }
        };

        const config = alertConfig[type] || alertConfig.info;

        const alert = document.createElement('div');
        alert.className = `${config.bg} ${config.border} border rounded-md p-4 mb-4 animate-fade-in`;
        alert.innerHTML = `
            <div class="flex">
                <div class="flex-shrink-0">
                    <svg class="h-5 w-5 ${config.icon}" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clip-rule="evenodd" />
                    </svg>
                </div>
                <div class="ml-3">
                    <p class="text-sm font-medium ${config.text}">${this.escapeHtml(message)}</p>
                </div>
                <div class="ml-auto pl-3">
                    <button type="button" class="inline-flex ${config.text} hover:opacity-75" onclick="this.closest('div').parentElement.remove()">
                        <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                        </svg>
                    </button>
                </div>
            </div>
        `;

        this.elements.alertContainer.insertBefore(alert, this.elements.alertContainer.firstChild);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 5000);
    }

    showConnectionStatus(status) {
        const indicator = document.getElementById('connection-status');
        if (!indicator) return;

        const statusConfig = {
            'connected': { color: 'bg-green-400', text: 'Connected' },
            'disconnected': { color: 'bg-red-400', text: 'Disconnected' },
            'reconnecting': { color: 'bg-yellow-400', text: 'Reconnecting...' }
        };

        const config = statusConfig[status] || statusConfig.disconnected;

        indicator.innerHTML = `
            <span class="flex items-center gap-2 text-xs text-gray-500">
                <span class="h-2 w-2 rounded-full ${config.color}"></span>
                ${config.text}
            </span>
        `;
    }

    // ==================== Utility Methods ====================

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatStatus(status) {
        return status
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    const workflowId = document.body.dataset.workflowId;

    if (workflowId) {
        window.aguiHandler = new AGUIEventHandler(workflowId);
        window.aguiHandler.connect();

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            window.aguiHandler.disconnect();
        });
    }
});
```

---

## Template Specifications

### 1. Real-Time Execution View (`workflow/execute.html`)

```html
{% extends "base.html" %}

{% block title %}Executing - {{ workflow.name }}{% endblock %}

{% block head %}
<style>
    @keyframes fade-in {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-fade-in {
        animation: fade-in 0.3s ease-out;
    }
</style>
{% endblock %}

{% block content %}
<div class="space-y-6" data-workflow-id="{{ workflow.id }}">
    <!-- Alert Container -->
    <div id="alert-container"></div>

    <!-- Header -->
    <div class="sm:flex sm:items-center sm:justify-between">
        <div>
            <div class="flex items-center gap-x-3">
                <h1 class="text-2xl font-bold text-gray-900">{{ workflow.name }}</h1>
                <span id="status-badge" class="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                    {{ workflow.status | title | replace('_', ' ') }}
                </span>
            </div>
            <p class="mt-1 text-sm text-gray-500">
                Real-time execution monitoring
            </p>
        </div>
        <div class="mt-4 sm:mt-0 flex items-center gap-x-4">
            <!-- Connection Status -->
            <div id="connection-status">
                <span class="flex items-center gap-2 text-xs text-gray-500">
                    <span class="h-2 w-2 rounded-full bg-yellow-400 animate-pulse"></span>
                    Connecting...
                </span>
            </div>
        </div>
    </div>

    <!-- Progress Bar -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-4">
        <div class="flex items-center justify-between mb-2">
            <span id="current-step" class="text-sm font-medium text-gray-900">
                Step {{ workflow.current_step + 1 }} of {{ workflow.plan | length }}
            </span>
            <span class="text-sm text-gray-500">
                {{ ((workflow.current_step + 1) / workflow.plan | length * 100) | round }}%
            </span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-2">
            <div id="progress-bar"
                 class="bg-primary-600 h-2 rounded-full transition-all duration-500"
                 style="width: {{ ((workflow.current_step + 1) / workflow.plan | length * 100) }}%">
            </div>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Main Content (2 columns) -->
        <div class="lg:col-span-2 space-y-6">
            <!-- Agent Output -->
            <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg">
                <div class="px-4 py-3 border-b border-gray-200">
                    <h2 class="text-lg font-semibold text-gray-900">Agent Activity</h2>
                </div>
                <div id="agent-output"
                     class="p-4 h-80 overflow-y-auto font-mono text-sm bg-gray-50 space-y-2">
                    <div class="text-gray-500">Waiting for agent output...</div>
                </div>
            </div>

            <!-- Email Thread -->
            <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg">
                <div class="px-4 py-3 border-b border-gray-200">
                    <h2 class="text-lg font-semibold text-gray-900">Email Thread</h2>
                </div>
                <div id="email-thread" class="p-4 h-64 overflow-y-auto">
                    <div class="text-gray-500 text-sm text-center">
                        Email conversation will appear here...
                    </div>
                </div>
            </div>
        </div>

        <!-- Sidebar (1 column) -->
        <div class="space-y-6">
            <!-- Countdown Timer -->
            <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-4">
                <h3 class="text-sm font-medium text-gray-900 mb-3">Response Timeout</h3>
                <div id="countdown-timer" class="text-center">
                    <span class="font-mono text-2xl text-gray-900">
                        {{ "%02d" | format(workflow.timeout_hours) }}:00:00
                    </span>
                    <span class="text-sm text-gray-500 block mt-1">remaining</span>
                </div>
            </div>

            <!-- Execution Plan -->
            <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-4">
                <h3 class="text-sm font-medium text-gray-900 mb-3">Execution Plan</h3>
                <ol class="relative border-l border-gray-200 ml-3 space-y-4">
                    {% for step in workflow.plan %}
                    <li class="ml-4">
                        <span class="absolute flex items-center justify-center w-6 h-6 rounded-full -left-3
                            {% if loop.index0 < workflow.current_step %}bg-green-100 text-green-800
                            {% elif loop.index0 == workflow.current_step %}bg-blue-100 text-blue-800 ring-2 ring-blue-400
                            {% else %}bg-gray-100 text-gray-800{% endif %}
                            text-xs font-medium">
                            {% if loop.index0 < workflow.current_step %}
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                            </svg>
                            {% else %}
                            {{ loop.index }}
                            {% endif %}
                        </span>
                        <p class="text-sm {% if loop.index0 == workflow.current_step %}font-medium text-gray-900{% else %}text-gray-500{% endif %}">
                            {{ step.action | title | replace('_', ' ') }}
                        </p>
                    </li>
                    {% endfor %}
                </ol>
            </div>

            <!-- Activity Log -->
            <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-4">
                <h3 class="text-sm font-medium text-gray-900 mb-3">Recent Activity</h3>
                <div id="activity-log" class="h-48 overflow-y-auto text-xs">
                    <div class="text-gray-500">Activity will appear here...</div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/ag-ui.js"></script>
<script>
    document.body.dataset.workflowId = "{{ workflow.id }}";
</script>
{% endblock %}
```

### 2. Validation Results View (`workflow/results.html`)

```html
{% extends "base.html" %}

{% block title %}Results - {{ workflow.name }}{% endblock %}

{% block content %}
<div class="space-y-6">
    <!-- Header -->
    <div class="sm:flex sm:items-center sm:justify-between">
        <div>
            <a href="/workflows/{{ workflow.id }}" class="text-sm text-gray-500 hover:text-gray-700">
                ← Back to workflow
            </a>
            <h1 class="mt-2 text-2xl font-bold text-gray-900">Validation Results</h1>
            <p class="mt-1 text-sm text-gray-500">
                {{ workflow.name }}
            </p>
        </div>
    </div>

    {% set result = workflow.validation_result %}

    <!-- Overall Result -->
    <div class="{% if result.passed %}bg-green-50 border-green-200{% else %}bg-red-50 border-red-200{% endif %} border rounded-lg p-6">
        <div class="flex items-center">
            <div class="flex-shrink-0">
                {% if result.passed %}
                <svg class="h-12 w-12 text-green-400" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {% else %}
                <svg class="h-12 w-12 text-red-400" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {% endif %}
            </div>
            <div class="ml-4">
                <h2 class="text-xl font-bold {% if result.passed %}text-green-800{% else %}text-red-800{% endif %}">
                    Validation {{ 'Passed' if result.passed else 'Failed' }}
                </h2>
                <p class="mt-1 text-sm {% if result.passed %}text-green-700{% else %}text-red-700{% endif %}">
                    Score: {{ (result.score * 100) | round }}%
                </p>
            </div>
            <div class="ml-auto">
                <div class="text-right">
                    <p class="text-sm {% if result.passed %}text-green-700{% else %}text-red-700{% endif %}">
                        {{ result.document_name }}
                    </p>
                    <p class="text-xs {% if result.passed %}text-green-600{% else %}text-red-600{% endif %}">
                        Validated at {{ result.validated_at | format_time }}
                    </p>
                </div>
            </div>
        </div>
    </div>

    <!-- Criteria Results -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg">
        <div class="px-4 py-3 border-b border-gray-200">
            <h2 class="text-lg font-semibold text-gray-900">Validation Criteria</h2>
        </div>
        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Criterion
                        </th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Expected
                        </th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Actual
                        </th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Status
                        </th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {% for criterion in result.criteria_results %}
                    <tr>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <div class="text-sm font-medium text-gray-900">
                                {{ criterion.description }}
                            </div>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <div class="text-sm text-gray-500">
                                {{ criterion.expected }}
                            </div>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <div class="text-sm text-gray-500">
                                {{ criterion.actual }}
                            </div>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            {% if criterion.passed %}
                            <span class="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
                                <svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                                </svg>
                                Pass
                            </span>
                            {% else %}
                            <span class="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800">
                                <svg class="mr-1 h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                                </svg>
                                Fail
                            </span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    {% if result.issues %}
    <!-- Issues -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Issues Found</h2>
        <ul class="space-y-2">
            {% for issue in result.issues %}
            <li class="flex items-start gap-x-3">
                <svg class="h-5 w-5 text-red-500 mt-0.5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <span class="text-sm text-gray-700">{{ issue }}</span>
            </li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}

    {% if result.recommendations %}
    <!-- Recommendations -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Recommendations</h2>
        <ul class="space-y-2">
            {% for rec in result.recommendations %}
            <li class="flex items-start gap-x-3">
                <svg class="h-5 w-5 text-blue-500 mt-0.5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
                </svg>
                <span class="text-sm text-gray-700">{{ rec }}</span>
            </li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}

    <!-- Actions -->
    <div class="flex items-center justify-end gap-x-4">
        <a href="/workflows/{{ workflow.id }}/audit"
           class="text-sm font-semibold text-gray-900">
            View Audit Log
        </a>
        <a href="/"
           class="rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500">
            Back to Dashboard
        </a>
    </div>
</div>
{% endblock %}
```

### 3. Audit Log Viewer (`audit/log.html`)

```html
{% extends "base.html" %}

{% block title %}Audit Log - {{ workflow.name }}{% endblock %}

{% block content %}
<div class="space-y-6">
    <!-- Header -->
    <div class="sm:flex sm:items-center sm:justify-between">
        <div>
            <a href="/workflows/{{ workflow.id }}" class="text-sm text-gray-500 hover:text-gray-700">
                ← Back to workflow
            </a>
            <h1 class="mt-2 text-2xl font-bold text-gray-900">Audit Log</h1>
            <p class="mt-1 text-sm text-gray-500">
                Complete history for {{ workflow.name }}
            </p>
        </div>
        <div class="mt-4 sm:mt-0">
            <button onclick="exportAuditLog()"
                    class="inline-flex items-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50">
                <svg class="-ml-0.5 mr-1.5 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                Export CSV
            </button>
        </div>
    </div>

    <!-- Filters -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-4">
        <div class="flex flex-wrap items-center gap-4">
            <!-- Action Filter -->
            <div>
                <label for="filter-action" class="block text-xs font-medium text-gray-700 mb-1">Action</label>
                <select id="filter-action"
                        onchange="filterAuditLog()"
                        class="rounded-md border-gray-300 text-sm focus:border-primary-500 focus:ring-primary-500">
                    <option value="">All Actions</option>
                    <option value="parse_inputs">Parse Inputs</option>
                    <option value="generate_plan">Generate Plan</option>
                    <option value="send_email">Send Email</option>
                    <option value="clarification_handled">Clarification</option>
                    <option value="escalated">Escalation</option>
                    <option value="validation_complete">Validation</option>
                </select>
            </div>

            <!-- Date Range -->
            <div>
                <label for="filter-date" class="block text-xs font-medium text-gray-700 mb-1">Date</label>
                <input type="date"
                       id="filter-date"
                       onchange="filterAuditLog()"
                       class="rounded-md border-gray-300 text-sm focus:border-primary-500 focus:ring-primary-500">
            </div>

            <!-- Search -->
            <div class="flex-1">
                <label for="filter-search" class="block text-xs font-medium text-gray-700 mb-1">Search</label>
                <input type="text"
                       id="filter-search"
                       placeholder="Search details..."
                       onkeyup="filterAuditLog()"
                       class="w-full rounded-md border-gray-300 text-sm focus:border-primary-500 focus:ring-primary-500">
            </div>

            <!-- Clear Filters -->
            <div class="self-end">
                <button onclick="clearFilters()"
                        class="text-sm text-primary-600 hover:text-primary-500">
                    Clear filters
                </button>
            </div>
        </div>
    </div>

    <!-- Audit Log Table -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200" id="audit-table">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Timestamp
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Action
                    </th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Details
                    </th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {% for entry in workflow.audit_log | reverse %}
                <tr class="audit-row" data-action="{{ entry.action }}" data-timestamp="{{ entry.timestamp }}">
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {{ entry.timestamp | format_time }}
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium
                            {% if 'error' in entry.action or 'fail' in entry.action %}
                            bg-red-100 text-red-800
                            {% elif 'complete' in entry.action or 'success' in entry.action %}
                            bg-green-100 text-green-800
                            {% elif 'escalat' in entry.action %}
                            bg-orange-100 text-orange-800
                            {% else %}
                            bg-gray-100 text-gray-800
                            {% endif %}">
                            {{ entry.action | replace('_', ' ') | title }}
                        </span>
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-500 audit-details">
                        {{ entry.details }}
                    </td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="3" class="px-6 py-12 text-center text-sm text-gray-500">
                        No audit entries found.
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Pagination (if needed) -->
    {% if workflow.audit_log | length > 50 %}
    <div class="flex items-center justify-between">
        <p class="text-sm text-gray-700">
            Showing <span class="font-medium">{{ workflow.audit_log | length }}</span> entries
        </p>
    </div>
    {% endif %}
</div>
{% endblock %}

{% block scripts %}
<script>
function filterAuditLog() {
    const actionFilter = document.getElementById('filter-action').value.toLowerCase();
    const dateFilter = document.getElementById('filter-date').value;
    const searchFilter = document.getElementById('filter-search').value.toLowerCase();

    const rows = document.querySelectorAll('.audit-row');

    rows.forEach(row => {
        const action = row.dataset.action.toLowerCase();
        const timestamp = row.dataset.timestamp;
        const details = row.querySelector('.audit-details').textContent.toLowerCase();

        let show = true;

        if (actionFilter && !action.includes(actionFilter)) {
            show = false;
        }

        if (dateFilter && !timestamp.startsWith(dateFilter)) {
            show = false;
        }

        if (searchFilter && !details.includes(searchFilter) && !action.includes(searchFilter)) {
            show = false;
        }

        row.style.display = show ? '' : 'none';
    });
}

function clearFilters() {
    document.getElementById('filter-action').value = '';
    document.getElementById('filter-date').value = '';
    document.getElementById('filter-search').value = '';
    filterAuditLog();
}

function exportAuditLog() {
    const rows = document.querySelectorAll('.audit-row');
    let csv = 'Timestamp,Action,Details\n';

    rows.forEach(row => {
        if (row.style.display !== 'none') {
            const timestamp = row.dataset.timestamp;
            const action = row.dataset.action;
            const details = row.querySelector('.audit-details').textContent.trim().replace(/"/g, '""');
            csv += `"${timestamp}","${action}","${details}"\n`;
        }
    });

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'audit_log_{{ workflow.id }}.csv';
    a.click();
    window.URL.revokeObjectURL(url);
}
</script>
{% endblock %}
```

### 4. Email Thread Viewer Component (`components/email_thread.html`)

```html
<div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg">
    <div class="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-gray-900">Email Conversation</h2>
        <span class="text-sm text-gray-500">
            {{ emails | length }} message{% if emails | length != 1 %}s{% endif %}
        </span>
    </div>

    <div class="p-4 space-y-4 max-h-96 overflow-y-auto" id="email-thread-container">
        {% for email in emails %}
        <div class="flex {% if email.direction == 'outgoing' %}justify-end{% else %}justify-start{% endif %}">
            <div class="max-w-lg {% if email.direction == 'outgoing' %}bg-primary-50{% else %}bg-gray-50{% endif %} rounded-lg p-4 shadow-sm">
                <!-- Header -->
                <div class="flex items-center gap-2 mb-2">
                    {% if email.direction == 'outgoing' %}
                    <svg class="h-4 w-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                    </svg>
                    {% else %}
                    <svg class="h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                    </svg>
                    {% endif %}
                    <span class="text-xs font-medium {% if email.direction == 'outgoing' %}text-primary-700{% else %}text-gray-700{% endif %}">
                        {% if email.direction == 'outgoing' %}
                        To: {{ email.to_address }}
                        {% else %}
                        From: {{ email.from_address }}
                        {% endif %}
                    </span>
                    <span class="text-xs text-gray-400">
                        {{ email.timestamp | format_time }}
                    </span>
                </div>

                <!-- Subject -->
                <p class="text-sm font-medium text-gray-900 mb-2">
                    {{ email.subject }}
                </p>

                <!-- Body Preview -->
                <p class="text-sm text-gray-600 whitespace-pre-line">
                    {{ email.body[:300] }}{% if email.body | length > 300 %}...{% endif %}
                </p>

                <!-- Attachments -->
                {% if email.attachments %}
                <div class="mt-3 pt-3 border-t border-gray-200">
                    <div class="flex items-center gap-2 text-xs text-gray-500">
                        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
                        </svg>
                        {% for attachment in email.attachments %}
                        <a href="/attachments/{{ attachment.id }}" class="text-primary-600 hover:underline">
                            {{ attachment.filename }}
                        </a>
                        {% if not loop.last %}, {% endif %}
                        {% endfor %}
                    </div>
                </div>
                {% endif %}
            </div>
        </div>
        {% else %}
        <div class="text-center py-8 text-gray-500">
            <svg class="mx-auto h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <p class="mt-2 text-sm">No emails yet</p>
        </div>
        {% endfor %}
    </div>
</div>
```

### 5. Countdown Timer Component (`components/countdown_timer.html`)

```html
<div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-4">
    <h3 class="text-sm font-medium text-gray-900 mb-3 flex items-center gap-2">
        <svg class="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Response Timeout
    </h3>

    <div id="countdown-display" class="text-center py-4">
        {% if timeout_remaining > 0 %}
        <div class="font-mono text-3xl text-gray-900" id="countdown-value">
            {{ "%02d" | format(timeout_remaining // 3600) }}:{{ "%02d" | format((timeout_remaining % 3600) // 60) }}:{{ "%02d" | format(timeout_remaining % 60) }}
        </div>
        <p class="text-sm text-gray-500 mt-1">remaining</p>

        <!-- Progress ring -->
        <div class="mt-4 flex justify-center">
            <svg class="h-16 w-16 transform -rotate-90">
                <circle cx="32" cy="32" r="28" stroke="#e5e7eb" stroke-width="4" fill="none" />
                <circle cx="32" cy="32" r="28"
                        stroke="{{ '#22c55e' if timeout_percent > 50 else '#f59e0b' if timeout_percent > 20 else '#ef4444' }}"
                        stroke-width="4"
                        fill="none"
                        stroke-dasharray="175.93"
                        stroke-dashoffset="{{ 175.93 * (1 - timeout_percent / 100) }}"
                        stroke-linecap="round" />
            </svg>
        </div>
        {% else %}
        <div class="text-red-600 font-medium">
            Timeout Reached
        </div>
        <p class="text-sm text-red-500 mt-1">
            Retry {{ retry_count }} of {{ max_retries }}
        </p>
        {% endif %}
    </div>
</div>

<script>
// Countdown timer logic
(function() {
    let remainingSeconds = {{ timeout_remaining }};
    const countdownEl = document.getElementById('countdown-value');

    if (remainingSeconds > 0 && countdownEl) {
        const interval = setInterval(() => {
            remainingSeconds--;

            if (remainingSeconds <= 0) {
                clearInterval(interval);
                countdownEl.textContent = '00:00:00';
                countdownEl.classList.add('text-red-600');
                return;
            }

            const hours = Math.floor(remainingSeconds / 3600);
            const minutes = Math.floor((remainingSeconds % 3600) / 60);
            const seconds = remainingSeconds % 60;

            countdownEl.textContent =
                String(hours).padStart(2, '0') + ':' +
                String(minutes).padStart(2, '0') + ':' +
                String(seconds).padStart(2, '0');

            // Change color as time runs out
            if (remainingSeconds < 300) { // Less than 5 minutes
                countdownEl.classList.add('text-red-600');
            } else if (remainingSeconds < 1800) { // Less than 30 minutes
                countdownEl.classList.add('text-yellow-600');
            }
        }, 1000);
    }
})();
</script>
```

---

## Enhanced Plan Approval with Feedback

### Plan Approval with Iteration (`workflow/approve.html` - Enhanced)

```html
{% extends "base.html" %}

{% block title %}Approve Plan - {{ workflow.name }}{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto space-y-6">
    <!-- Header -->
    <div>
        <a href="/workflows/{{ workflow.id }}" class="text-sm text-gray-500 hover:text-gray-700">
            ← Back to workflow
        </a>
        <h1 class="mt-2 text-2xl font-bold text-gray-900">Review Execution Plan</h1>
        <p class="mt-1 text-sm text-gray-500">
            Review the generated plan before execution begins.
        </p>
    </div>

    <!-- Iteration History (if any) -->
    {% if workflow.plan_iterations and workflow.plan_iterations | length > 1 %}
    <div class="bg-gray-50 rounded-lg p-4">
        <h3 class="text-sm font-medium text-gray-900 mb-3">Plan Iterations</h3>
        <div class="space-y-2">
            {% for iteration in workflow.plan_iterations %}
            <div class="flex items-center gap-x-3 text-sm">
                <span class="text-gray-400">v{{ loop.index }}</span>
                <span class="text-gray-600">{{ iteration.timestamp | format_time }}</span>
                {% if iteration.feedback %}
                <span class="text-gray-500">- {{ iteration.feedback[:50] }}{% if iteration.feedback | length > 50 %}...{% endif %}</span>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    <!-- Parsed Requirements -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Understood Requirements</h2>
        <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
                <dt class="text-sm font-medium text-gray-500">Target Person</dt>
                <dd class="mt-1 text-sm text-gray-900">
                    {{ workflow.target_name or 'N/A' }}
                    {% if workflow.target_email %}
                    <span class="text-gray-500">({{ workflow.target_email }})</span>
                    {% endif %}
                </dd>
            </div>
            <div>
                <dt class="text-sm font-medium text-gray-500">Requested Information</dt>
                <dd class="mt-1 text-sm text-gray-900">{{ workflow.requested_info or 'N/A' }}</dd>
            </div>
        </dl>
    </div>

    <!-- Execution Plan -->
    <div class="bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Execution Plan</h2>
        <ol class="relative border-l border-gray-200 ml-3">
            {% for step in workflow.plan %}
            <li class="mb-6 ml-6">
                <span class="absolute flex items-center justify-center w-8 h-8 bg-primary-100 text-primary-800 rounded-full -left-4 text-sm font-medium">
                    {{ loop.index }}
                </span>
                <h3 class="font-medium text-gray-900">{{ step.action | title | replace('_', ' ') }}</h3>
                <p class="text-sm text-gray-500">{{ step.description }}</p>
            </li>
            {% endfor %}
        </ol>
    </div>

    <!-- Approval Warning -->
    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
        <div class="flex">
            <div class="flex-shrink-0">
                <svg class="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
                </svg>
            </div>
            <div class="ml-3">
                <h3 class="text-sm font-medium text-yellow-800">Approval Required</h3>
                <p class="mt-2 text-sm text-yellow-700">
                    Once approved, the workflow will begin executing and emails will be sent.
                    Please review the plan carefully before approving.
                </p>
            </div>
        </div>
    </div>

    <!-- Feedback Form (for rejection) -->
    <div id="feedback-section" class="hidden bg-white shadow-sm ring-1 ring-gray-900/5 rounded-lg p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">Provide Feedback</h3>
        <p class="text-sm text-gray-500 mb-4">
            Please describe what changes you'd like to see in the plan.
            The system will regenerate the plan based on your feedback.
        </p>
        <textarea id="rejection-feedback"
                  rows="4"
                  placeholder="e.g., 'Please add a step to verify the email address first' or 'The request should be more formal'"
                  class="w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 text-sm"></textarea>
    </div>

    <!-- Action Buttons -->
    <div class="flex items-center justify-end gap-x-4">
        <button type="button"
                onclick="toggleFeedback()"
                id="reject-toggle-btn"
                class="rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50">
            Request Changes
        </button>

        <form id="reject-form"
              hx-post="/api/workflows/{{ workflow.id }}/approve"
              hx-target="#result"
              hx-swap="innerHTML"
              class="hidden">
            <input type="hidden" name="approved" value="false">
            <input type="hidden" name="feedback" id="feedback-input">
            <button type="submit"
                    onclick="document.getElementById('feedback-input').value = document.getElementById('rejection-feedback').value"
                    class="rounded-md bg-yellow-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-yellow-500">
                Submit Feedback & Regenerate
            </button>
        </form>

        <form id="approve-form"
              hx-post="/api/workflows/{{ workflow.id }}/approve"
              hx-target="#result"
              hx-swap="innerHTML">
            <input type="hidden" name="approved" value="true">
            <button type="submit"
                    class="rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600">
                Approve & Execute
            </button>
        </form>
    </div>

    <div id="result"></div>
</div>

<script>
function toggleFeedback() {
    const feedbackSection = document.getElementById('feedback-section');
    const rejectForm = document.getElementById('reject-form');
    const approveForm = document.getElementById('approve-form');
    const toggleBtn = document.getElementById('reject-toggle-btn');

    if (feedbackSection.classList.contains('hidden')) {
        feedbackSection.classList.remove('hidden');
        rejectForm.classList.remove('hidden');
        approveForm.classList.add('hidden');
        toggleBtn.textContent = 'Cancel';
    } else {
        feedbackSection.classList.add('hidden');
        rejectForm.classList.add('hidden');
        approveForm.classList.remove('hidden');
        toggleBtn.textContent = 'Request Changes';
    }
}
</script>
{% endblock %}
```

---

## Directory Structure (Phase 4 Final)

```
info-agent/
├── src/info_agent/
│   ├── ... (all from Phase 1-3)
│   │
│   └── api/
│       └── routes/
│           └── templates.py         # Enhanced with new views
│
├── frontend/
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   │
│   │   ├── workflow/
│   │   │   ├── create.html
│   │   │   ├── detail.html
│   │   │   ├── approve.html         # ENHANCED: Iteration support
│   │   │   ├── execute.html         # NEW: Real-time execution
│   │   │   ├── results.html         # NEW: Validation results
│   │   │   ├── list.html
│   │   │   └── status_card.html
│   │   │
│   │   ├── audit/
│   │   │   └── log.html             # NEW: Audit log viewer
│   │   │
│   │   ├── email/
│   │   │   └── ... (from Phase 3)
│   │   │
│   │   └── components/
│   │       ├── header.html
│   │       ├── sidebar.html
│   │       ├── status_badge.html
│   │       ├── file_upload.html
│   │       ├── plan_step.html
│   │       ├── email_row.html
│   │       ├── alert.html
│   │       ├── agent_activity.html  # NEW
│   │       ├── countdown_timer.html # NEW
│   │       ├── email_thread.html    # NEW
│   │       └── validation_results.html # NEW
│   │
│   └── static/
│       ├── css/
│       │   └── app.css              # ENHANCED: Animations
│       │
│       └── js/
│           ├── app.js
│           ├── htmx-config.js
│           ├── ag-ui.js             # NEW: AG-UI handler
│           └── countdown.js         # NEW: Timer logic
│
├── tests/
│   └── e2e/
│       ├── test_ui_workflow.py
│       ├── test_realtime_updates.py # NEW
│       └── test_demo_scenario.py    # NEW
│
└── ... (rest from Phase 1-3)
```

---

## Demo Scenario Script

### Complete Three-Tab Demo Flow

```markdown
## Demo Setup

1. Start all services:
   ```bash
   # Terminal 1: Gateway + Supervisor
   python scripts/run_gateway.py

   # Terminal 2: Mail Agent
   python scripts/run_mail_agent.py

   # Terminal 3: Validation Agent
   python scripts/run_validation_agent.py

   # Terminal 4: Mock Email Server
   python scripts/run_email_server.py
   ```

2. Open three browser tabs:
   - Tab 1: http://localhost:8000/ (System Dashboard)
   - Tab 2: http://localhost:8025/inbox/raj@gmail.com (Target Person)
   - Tab 3: http://localhost:8025/inbox/mrinal@gmail.com (End User)

## Demo Steps

### Step 1: Create Workflow (Tab 1)
1. Click "New Workflow"
2. Enter name: "Recipe Collection from Raj"
3. Upload 4 files:
   - instructions.txt
   - faq.txt
   - escalation.txt
   - validation.txt
4. Click "Create Workflow"

### Step 2: Review and Approve Plan (Tab 1)
1. System generates plan (watch real-time updates)
2. Review parsed requirements
3. Review execution steps
4. Click "Approve & Execute"

### Step 3: Watch Email Sent (Tab 1 & Tab 2)
1. Tab 1: See "Email Sent" event in activity log
2. Tab 2: Refresh raj@gmail.com inbox
3. Tab 2: See incoming email request

### Step 4: Simulate Clarification (Tab 2)
1. Tab 2: Click "Reply" on the email
2. Tab 2: Type: "What format should the recipes be in?"
3. Tab 2: Click "Send"

### Step 5: Watch Clarification Handling (Tab 1)
1. Tab 1: See "Clarification Needed" event
2. Tab 1: System checks FAQ
3. Tab 1: FAQ match found → automatic reply

### Step 6: Check Automatic Reply (Tab 2)
1. Tab 2: Refresh inbox
2. Tab 2: See automatic reply with FAQ answer

### Step 7: Send Document (Tab 2)
1. Tab 2: Click "Reply"
2. Tab 2: Type: "Here is the Excel file with 10 recipes"
3. Tab 2: Attach valid_excel.xlsx
4. Tab 2: Click "Send"

### Step 8: Watch Validation (Tab 1)
1. Tab 1: See "Email Received" event
2. Tab 1: See "Validation Started" event
3. Tab 1: Watch validation progress
4. Tab 1: See "Validation Complete" event

### Step 9: View Results (Tab 1)
1. Tab 1: Automatically redirected to Results page
2. Tab 1: See "Validation Passed"
3. Tab 1: Review criteria breakdown
4. Tab 1: Click "View Audit Log" for complete history

## Alternative Flow: Escalation Demo

### Step 4b: Unknown Question (Tab 2)
1. Tab 2: Reply with: "Can I send PDF instead?"
2. Tab 2: Click "Send"

### Step 5b: Escalation (Tab 1 & Tab 3)
1. Tab 1: See "Clarification Needed" - not in FAQ
2. Tab 1: See "Escalation Triggered"
3. Tab 3: Refresh mrinal@gmail.com inbox
4. Tab 3: See escalation email asking for answer

### Step 6b: Provide Answer (Tab 3)
1. Tab 3: Reply with the answer
2. Tab 3: Click "Send"

### Step 7b: Answer Forwarded (Tab 1 & Tab 2)
1. Tab 1: See answer received from mrinal
2. Tab 1: See answer forwarded to raj
3. Tab 2: Refresh inbox, see the answer
```

---

## Phase 4 Completion Criteria

- [ ] AG-UI SSE connection working in frontend
- [ ] Real-time status updates displaying
- [ ] Agent activity log updating live
- [ ] Email thread visualization working
- [ ] Countdown timer counting down
- [ ] Validation results view complete
- [ ] Audit log viewer with filtering
- [ ] Plan iteration with feedback working
- [ ] Export audit log to CSV working
- [ ] All animations smooth
- [ ] Three-tab demo scenario completing successfully
- [ ] All e2e tests passing
- [ ] No polling - all updates via SSE

---

## Final System Summary

### Complete Feature List

| Feature | Phase | Status |
|---------|-------|--------|
| FastAPI Gateway | 1 | Core |
| Supervisor Agent | 1 | Core |
| Mail Agent | 1 | Core |
| Mock Email Server | 1 | Core |
| A2A Registry | 1 | Core |
| Gemini LLM Integration | 1 | Core |
| SQLite Checkpointing | 1 | Core |
| Validation Agent | 2 | Full |
| Clarification Flow | 2 | Full |
| Escalation Flow | 2 | Full |
| AG-UI Backend | 2 | Full |
| Multi-Provider LLM | 2 | Full |
| Basic Dashboard | 3 | MVP UI |
| Workflow Creation | 3 | MVP UI |
| File Upload | 3 | MVP UI |
| Email Web UI | 3 | MVP UI |
| Real-Time Updates | 4 | Full UI |
| Validation Results | 4 | Full UI |
| Audit Log Viewer | 4 | Full UI |
| Email Thread View | 4 | Full UI |
| Countdown Timer | 4 | Full UI |
| Plan Iteration | 4 | Full UI |

### Port Summary

| Service | Port |
|---------|------|
| FastAPI Gateway | 8000 |
| Mail Agent | 8001 |
| Validation Agent | 8002 |
| Mock Email Server (REST) | 8025 |
| Mock Email Server (SMTP) | 1025 |

### Demo URLs

| Purpose | URL |
|---------|-----|
| System Dashboard | http://localhost:8000/ |
| raj's Inbox | http://localhost:8025/inbox/raj@gmail.com |
| mrinal's Inbox | http://localhost:8025/inbox/mrinal@gmail.com |
| vishal's Inbox | http://localhost:8025/inbox/vishal@gmail.com |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-13 | Claude | Initial Phase 4 architecture document |
