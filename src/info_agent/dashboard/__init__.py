"""
AG-UI Dashboard Integration for Info-Agent.

This module provides the AG-UI event streaming and dashboard
integration components for real-time workflow visibility.

Components:
- EventEmitter: Emits AG-UI events to connected clients
- EventStream: Manages SSE connections for streaming events
- AGUIEvent: Event data models for AG-UI protocol
"""

from info_agent.dashboard.events import (
    AGUIEvent,
    AGUIEventType,
    create_run_started_event,
    create_run_finished_event,
    create_run_error_event,
    create_text_message_event,
    create_tool_call_event,
    create_state_delta_event,
    create_plan_event,
    create_step_event,
    create_email_event,
    create_validation_event,
)
from info_agent.dashboard.stream import (
    EventEmitter,
    EventStream,
)

__all__ = [
    "AGUIEvent",
    "AGUIEventType",
    "EventEmitter",
    "EventStream",
    "create_run_started_event",
    "create_run_finished_event",
    "create_run_error_event",
    "create_text_message_event",
    "create_tool_call_event",
    "create_state_delta_event",
    "create_plan_event",
    "create_step_event",
    "create_email_event",
    "create_validation_event",
]
