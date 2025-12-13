"""
AG-UI Event streaming infrastructure for Info-Agent.

This module provides the event emission and streaming infrastructure
for real-time dashboard updates using Server-Sent Events (SSE).
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable

from info_agent.dashboard.events import (
    AGUIEvent,
    AGUIEventType,
    create_run_started_event,
    create_run_finished_event,
    create_run_error_event,
    create_state_delta_event,
)

logger = logging.getLogger(__name__)


class EventStream:
    """
    Event stream for a single workflow.

    Manages a queue of events for streaming to connected clients.
    """

    def __init__(self, workflow_id: str) -> None:
        """
        Initialize the event stream.

        Args:
            workflow_id: Workflow identifier.
        """
        logger.debug("Creating EventStream for workflow: %s", workflow_id)

        self._workflow_id = workflow_id
        self._queue: asyncio.Queue[AGUIEvent] = asyncio.Queue()
        self._closed = False
        self._created_at = datetime.now(timezone.utc)

    @property
    def workflow_id(self) -> str:
        """Get the workflow ID."""
        return self._workflow_id

    @property
    def is_closed(self) -> bool:
        """Check if the stream is closed."""
        return self._closed

    async def put(self, event: AGUIEvent) -> None:
        """
        Add an event to the stream.

        Args:
            event: Event to add.

        Raises:
            RuntimeError: If the stream is closed.
        """
        if self._closed:
            raise RuntimeError(f"Stream for {self._workflow_id} is closed")

        logger.debug(
            "Adding event to stream: workflow=%s, type=%s",
            self._workflow_id,
            event.type.value,
        )

        await self._queue.put(event)

    async def get(self, timeout: float | None = None) -> AGUIEvent | None:
        """
        Get the next event from the stream.

        Args:
            timeout: Optional timeout in seconds.

        Returns:
            Next event, or None if timeout reached.

        Raises:
            RuntimeError: If the stream is closed.
        """
        if self._closed:
            raise RuntimeError(f"Stream for {self._workflow_id} is closed")

        try:
            if timeout is not None:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout,
                )
            else:
                event = await self._queue.get()

            logger.debug(
                "Got event from stream: workflow=%s, type=%s",
                self._workflow_id,
                event.type.value,
            )

            return event

        except asyncio.TimeoutError:
            return None

    async def stream(
        self,
        timeout: float = 30.0,
    ) -> AsyncGenerator[AGUIEvent, None]:
        """
        Stream events from the queue.

        Args:
            timeout: Timeout between events in seconds.

        Yields:
            Events from the stream.
        """
        logger.info("Starting event stream for workflow: %s", self._workflow_id)

        while not self._closed:
            try:
                event = await self.get(timeout=timeout)

                if event is None:
                    # Timeout - send heartbeat
                    logger.debug("Stream heartbeat for workflow: %s", self._workflow_id)
                    continue

                yield event

                # Check for terminal events
                if event.type in (
                    AGUIEventType.RUN_FINISHED,
                    AGUIEventType.RUN_ERROR,
                ):
                    logger.info(
                        "Terminal event received, closing stream: workflow=%s",
                        self._workflow_id,
                    )
                    break

            except RuntimeError:
                # Stream closed
                break

        logger.info("Event stream ended for workflow: %s", self._workflow_id)

    def close(self) -> None:
        """Close the stream."""
        logger.debug("Closing EventStream for workflow: %s", self._workflow_id)
        self._closed = True

    def qsize(self) -> int:
        """Get the current queue size."""
        return self._queue.qsize()


class EventEmitter:
    """
    Central event emitter for AG-UI events.

    Manages event streams for multiple workflows and provides
    methods for emitting events to connected clients.
    """

    def __init__(self) -> None:
        """Initialize the event emitter."""
        logger.info("Initializing EventEmitter")

        self._streams: dict[str, list[EventStream]] = defaultdict(list)
        self._handlers: dict[AGUIEventType, list[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def create_stream(self, workflow_id: str) -> EventStream:
        """
        Create a new event stream for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            New EventStream instance.
        """
        logger.info("Creating new stream for workflow: %s", workflow_id)

        async with self._lock:
            stream = EventStream(workflow_id)
            self._streams[workflow_id].append(stream)

            logger.debug(
                "Active streams for workflow %s: %d",
                workflow_id,
                len(self._streams[workflow_id]),
            )

            return stream

    async def remove_stream(self, stream: EventStream) -> None:
        """
        Remove an event stream.

        Args:
            stream: Stream to remove.
        """
        workflow_id = stream.workflow_id

        logger.info("Removing stream for workflow: %s", workflow_id)

        async with self._lock:
            stream.close()
            if workflow_id in self._streams:
                if stream in self._streams[workflow_id]:
                    self._streams[workflow_id].remove(stream)

                if not self._streams[workflow_id]:
                    del self._streams[workflow_id]

    async def emit(self, event: AGUIEvent) -> int:
        """
        Emit an event to all connected streams for a workflow.

        Args:
            event: Event to emit.

        Returns:
            Number of streams that received the event.
        """
        workflow_id = event.workflow_id

        logger.debug(
            "Emitting event: workflow=%s, type=%s",
            workflow_id,
            event.type.value,
        )

        # Call registered handlers
        await self._call_handlers(event)

        # Send to streams
        async with self._lock:
            streams = self._streams.get(workflow_id, [])
            count = 0

            for stream in streams:
                if not stream.is_closed:
                    try:
                        await stream.put(event)
                        count += 1
                    except RuntimeError:
                        logger.warning(
                            "Failed to emit to closed stream: %s",
                            workflow_id,
                        )

            logger.debug(
                "Event emitted to %d streams: workflow=%s",
                count,
                workflow_id,
            )

            return count

    async def emit_run_started(
        self,
        workflow_id: str,
        run_id: str | None = None,
        status: str = "executing",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Emit a RUN_STARTED event.

        Args:
            workflow_id: Workflow identifier.
            run_id: Optional run identifier.
            status: Initial status.
            metadata: Optional metadata.

        Returns:
            Number of streams that received the event.
        """
        event = create_run_started_event(
            workflow_id=workflow_id,
            run_id=run_id,
            status=status,
            metadata=metadata,
        )
        return await self.emit(event)

    async def emit_run_finished(
        self,
        workflow_id: str,
        run_id: str | None = None,
        status: str = "completed",
        result: dict[str, Any] | None = None,
    ) -> int:
        """
        Emit a RUN_FINISHED event.

        Args:
            workflow_id: Workflow identifier.
            run_id: Optional run identifier.
            status: Final status.
            result: Optional result data.

        Returns:
            Number of streams that received the event.
        """
        event = create_run_finished_event(
            workflow_id=workflow_id,
            run_id=run_id,
            status=status,
            result=result,
        )
        return await self.emit(event)

    async def emit_run_error(
        self,
        workflow_id: str,
        error: str,
        run_id: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        """
        Emit a RUN_ERROR event.

        Args:
            workflow_id: Workflow identifier.
            error: Error message.
            run_id: Optional run identifier.
            error_code: Optional error code.
            details: Optional error details.

        Returns:
            Number of streams that received the event.
        """
        event = create_run_error_event(
            workflow_id=workflow_id,
            error=error,
            run_id=run_id,
            error_code=error_code,
            details=details,
        )
        return await self.emit(event)

    async def emit_state_delta(
        self,
        workflow_id: str,
        delta: dict[str, Any],
        path: str | None = None,
    ) -> int:
        """
        Emit a STATE_DELTA event.

        Args:
            workflow_id: Workflow identifier.
            delta: State changes.
            path: Optional path to changed state.

        Returns:
            Number of streams that received the event.
        """
        event = create_state_delta_event(
            workflow_id=workflow_id,
            delta=delta,
            path=path,
        )
        return await self.emit(event)

    def register_handler(
        self,
        event_type: AGUIEventType,
        handler: Callable,
    ) -> None:
        """
        Register a handler for an event type.

        Args:
            event_type: Event type to handle.
            handler: Handler function (sync or async).
        """
        logger.debug("Registering handler for event type: %s", event_type.value)
        self._handlers[event_type].append(handler)

    def unregister_handler(
        self,
        event_type: AGUIEventType,
        handler: Callable,
    ) -> None:
        """
        Unregister a handler for an event type.

        Args:
            event_type: Event type.
            handler: Handler function to remove.
        """
        logger.debug("Unregistering handler for event type: %s", event_type.value)
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)

    async def _call_handlers(self, event: AGUIEvent) -> None:
        """
        Call registered handlers for an event.

        Args:
            event: Event to handle.
        """
        handlers = self._handlers.get(event.type, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    "Handler error for %s: %s",
                    event.type.value,
                    e,
                )

    def get_active_workflows(self) -> list[str]:
        """
        Get list of workflows with active streams.

        Returns:
            List of workflow IDs.
        """
        return list(self._streams.keys())

    def get_stream_count(self, workflow_id: str) -> int:
        """
        Get number of active streams for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            Number of active streams.
        """
        return len(self._streams.get(workflow_id, []))

    async def close_all(self) -> None:
        """Close all streams and cleanup."""
        logger.info("Closing all event streams")

        async with self._lock:
            for workflow_id, streams in self._streams.items():
                for stream in streams:
                    stream.close()
                logger.debug("Closed streams for workflow: %s", workflow_id)

            self._streams.clear()

        logger.info("All event streams closed")


# Global event emitter instance
_emitter: EventEmitter | None = None


def get_event_emitter() -> EventEmitter:
    """
    Get the global event emitter instance.

    Returns:
        Global EventEmitter instance.
    """
    global _emitter
    if _emitter is None:
        _emitter = EventEmitter()
    return _emitter


def reset_event_emitter() -> None:
    """Reset the global event emitter (for testing)."""
    global _emitter
    if _emitter is not None:
        # Close streams synchronously by just setting closed flag
        for streams in _emitter._streams.values():
            for stream in streams:
                stream.close()
        _emitter._streams.clear()
    _emitter = None


logger.info("AG-UI stream module initialized")
