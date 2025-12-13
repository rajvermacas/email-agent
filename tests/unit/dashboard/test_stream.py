"""
Unit tests for AG-UI event streaming.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from info_agent.dashboard.events import AGUIEvent, AGUIEventType
from info_agent.dashboard.stream import (
    EventStream,
    EventEmitter,
    get_event_emitter,
    reset_event_emitter,
)


class TestEventStream:
    """Tests for EventStream class."""

    def test_init(self) -> None:
        """Test stream initialization."""
        stream = EventStream(workflow_id="wf-123")

        assert stream.workflow_id == "wf-123"
        assert not stream.is_closed
        assert stream.qsize() == 0

    @pytest.mark.asyncio
    async def test_put_event(self) -> None:
        """Test putting an event."""
        stream = EventStream(workflow_id="wf-123")
        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )

        await stream.put(event)

        assert stream.qsize() == 1

    @pytest.mark.asyncio
    async def test_get_event(self) -> None:
        """Test getting an event."""
        stream = EventStream(workflow_id="wf-123")
        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )

        await stream.put(event)
        retrieved = await stream.get()

        assert retrieved is not None
        assert retrieved.type == AGUIEventType.RUN_STARTED

    @pytest.mark.asyncio
    async def test_get_with_timeout(self) -> None:
        """Test getting with timeout."""
        stream = EventStream(workflow_id="wf-123")

        result = await stream.get(timeout=0.1)

        assert result is None

    @pytest.mark.asyncio
    async def test_put_to_closed_stream_fails(self) -> None:
        """Test putting to closed stream raises error."""
        stream = EventStream(workflow_id="wf-123")
        stream.close()

        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )

        with pytest.raises(RuntimeError):
            await stream.put(event)

    @pytest.mark.asyncio
    async def test_get_from_closed_stream_fails(self) -> None:
        """Test getting from closed stream raises error."""
        stream = EventStream(workflow_id="wf-123")
        stream.close()

        with pytest.raises(RuntimeError):
            await stream.get()

    def test_close(self) -> None:
        """Test closing stream."""
        stream = EventStream(workflow_id="wf-123")

        stream.close()

        assert stream.is_closed

    @pytest.mark.asyncio
    async def test_stream_generator(self) -> None:
        """Test stream generator."""
        stream = EventStream(workflow_id="wf-123")

        # Put some events
        for i in range(3):
            event = AGUIEvent(
                type=AGUIEventType.STATE_DELTA,
                workflow_id="wf-123",
                data={"index": i},
            )
            await stream.put(event)

        # Put terminal event
        finish_event = AGUIEvent(
            type=AGUIEventType.RUN_FINISHED,
            workflow_id="wf-123",
        )
        await stream.put(finish_event)

        # Collect events
        events = []
        async for event in stream.stream(timeout=1.0):
            events.append(event)

        assert len(events) == 4
        assert events[-1].type == AGUIEventType.RUN_FINISHED

    @pytest.mark.asyncio
    async def test_stream_stops_on_error_event(self) -> None:
        """Test stream stops on error event."""
        stream = EventStream(workflow_id="wf-123")

        # Put error event
        error_event = AGUIEvent(
            type=AGUIEventType.RUN_ERROR,
            workflow_id="wf-123",
            data={"error": "Test error"},
        )
        await stream.put(error_event)

        events = []
        async for event in stream.stream(timeout=1.0):
            events.append(event)

        assert len(events) == 1
        assert events[0].type == AGUIEventType.RUN_ERROR


class TestEventEmitter:
    """Tests for EventEmitter class."""

    @pytest.fixture
    def emitter(self) -> EventEmitter:
        """Create an emitter."""
        return EventEmitter()

    @pytest.mark.asyncio
    async def test_create_stream(self, emitter: EventEmitter) -> None:
        """Test creating a stream."""
        stream = await emitter.create_stream("wf-123")

        assert stream is not None
        assert stream.workflow_id == "wf-123"
        assert emitter.get_stream_count("wf-123") == 1

    @pytest.mark.asyncio
    async def test_create_multiple_streams(self, emitter: EventEmitter) -> None:
        """Test creating multiple streams for same workflow."""
        stream1 = await emitter.create_stream("wf-123")
        stream2 = await emitter.create_stream("wf-123")

        assert stream1 is not stream2
        assert emitter.get_stream_count("wf-123") == 2

    @pytest.mark.asyncio
    async def test_remove_stream(self, emitter: EventEmitter) -> None:
        """Test removing a stream."""
        stream = await emitter.create_stream("wf-123")

        await emitter.remove_stream(stream)

        assert emitter.get_stream_count("wf-123") == 0
        assert stream.is_closed

    @pytest.mark.asyncio
    async def test_emit_event(self, emitter: EventEmitter) -> None:
        """Test emitting an event."""
        stream = await emitter.create_stream("wf-123")

        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )
        count = await emitter.emit(event)

        assert count == 1
        assert stream.qsize() == 1

    @pytest.mark.asyncio
    async def test_emit_to_multiple_streams(self, emitter: EventEmitter) -> None:
        """Test emitting to multiple streams."""
        stream1 = await emitter.create_stream("wf-123")
        stream2 = await emitter.create_stream("wf-123")

        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )
        count = await emitter.emit(event)

        assert count == 2
        assert stream1.qsize() == 1
        assert stream2.qsize() == 1

    @pytest.mark.asyncio
    async def test_emit_to_different_workflows(self, emitter: EventEmitter) -> None:
        """Test emitting only goes to correct workflow."""
        stream1 = await emitter.create_stream("wf-123")
        stream2 = await emitter.create_stream("wf-456")

        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )
        count = await emitter.emit(event)

        assert count == 1
        assert stream1.qsize() == 1
        assert stream2.qsize() == 0

    @pytest.mark.asyncio
    async def test_emit_run_started(self, emitter: EventEmitter) -> None:
        """Test emit_run_started convenience method."""
        stream = await emitter.create_stream("wf-123")

        count = await emitter.emit_run_started(
            workflow_id="wf-123",
            run_id="run-456",
            status="planning",
        )

        assert count == 1
        event = await stream.get()
        assert event.type == AGUIEventType.RUN_STARTED
        assert event.run_id == "run-456"

    @pytest.mark.asyncio
    async def test_emit_run_finished(self, emitter: EventEmitter) -> None:
        """Test emit_run_finished convenience method."""
        stream = await emitter.create_stream("wf-123")

        count = await emitter.emit_run_finished(
            workflow_id="wf-123",
            result={"success": True},
        )

        assert count == 1
        event = await stream.get()
        assert event.type == AGUIEventType.RUN_FINISHED

    @pytest.mark.asyncio
    async def test_emit_run_error(self, emitter: EventEmitter) -> None:
        """Test emit_run_error convenience method."""
        stream = await emitter.create_stream("wf-123")

        count = await emitter.emit_run_error(
            workflow_id="wf-123",
            error="Test error",
            error_code="TEST_ERROR",
        )

        assert count == 1
        event = await stream.get()
        assert event.type == AGUIEventType.RUN_ERROR
        assert event.data["error"] == "Test error"

    @pytest.mark.asyncio
    async def test_emit_state_delta(self, emitter: EventEmitter) -> None:
        """Test emit_state_delta convenience method."""
        stream = await emitter.create_stream("wf-123")

        count = await emitter.emit_state_delta(
            workflow_id="wf-123",
            delta={"status": "completed"},
        )

        assert count == 1
        event = await stream.get()
        assert event.type == AGUIEventType.STATE_DELTA

    @pytest.mark.asyncio
    async def test_register_handler(self, emitter: EventEmitter) -> None:
        """Test registering an event handler."""
        handled_events = []

        def handler(event: AGUIEvent) -> None:
            handled_events.append(event)

        emitter.register_handler(AGUIEventType.RUN_STARTED, handler)

        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )
        await emitter.emit(event)

        assert len(handled_events) == 1
        assert handled_events[0].type == AGUIEventType.RUN_STARTED

    @pytest.mark.asyncio
    async def test_register_async_handler(self, emitter: EventEmitter) -> None:
        """Test registering an async event handler."""
        handled_events = []

        async def handler(event: AGUIEvent) -> None:
            handled_events.append(event)

        emitter.register_handler(AGUIEventType.RUN_STARTED, handler)

        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )
        await emitter.emit(event)

        assert len(handled_events) == 1

    @pytest.mark.asyncio
    async def test_unregister_handler(self, emitter: EventEmitter) -> None:
        """Test unregistering an event handler."""
        handled_events = []

        def handler(event: AGUIEvent) -> None:
            handled_events.append(event)

        emitter.register_handler(AGUIEventType.RUN_STARTED, handler)
        emitter.unregister_handler(AGUIEventType.RUN_STARTED, handler)

        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )
        await emitter.emit(event)

        assert len(handled_events) == 0

    @pytest.mark.asyncio
    async def test_handler_error_doesnt_stop_emission(
        self, emitter: EventEmitter
    ) -> None:
        """Test handler errors don't stop event emission."""
        stream = await emitter.create_stream("wf-123")

        def bad_handler(event: AGUIEvent) -> None:
            raise ValueError("Handler error")

        emitter.register_handler(AGUIEventType.RUN_STARTED, bad_handler)

        event = AGUIEvent(
            type=AGUIEventType.RUN_STARTED,
            workflow_id="wf-123",
        )
        count = await emitter.emit(event)

        # Event should still be sent to stream despite handler error
        assert count == 1

    def test_get_active_workflows(self) -> None:
        """Test getting active workflows."""
        emitter = EventEmitter()

        assert emitter.get_active_workflows() == []

    @pytest.mark.asyncio
    async def test_get_active_workflows_with_streams(
        self, emitter: EventEmitter
    ) -> None:
        """Test getting active workflows with streams."""
        await emitter.create_stream("wf-123")
        await emitter.create_stream("wf-456")

        workflows = emitter.get_active_workflows()

        assert "wf-123" in workflows
        assert "wf-456" in workflows

    @pytest.mark.asyncio
    async def test_close_all(self, emitter: EventEmitter) -> None:
        """Test closing all streams."""
        stream1 = await emitter.create_stream("wf-123")
        stream2 = await emitter.create_stream("wf-456")

        await emitter.close_all()

        assert stream1.is_closed
        assert stream2.is_closed
        assert emitter.get_active_workflows() == []


class TestGlobalEmitter:
    """Tests for global emitter functions."""

    @pytest.fixture(autouse=True)
    def reset_emitter(self) -> None:
        """Reset global emitter before each test."""
        reset_event_emitter()

    def test_get_event_emitter(self) -> None:
        """Test getting global emitter."""
        emitter = get_event_emitter()

        assert emitter is not None
        assert isinstance(emitter, EventEmitter)

    def test_get_event_emitter_returns_same_instance(self) -> None:
        """Test getting global emitter returns same instance."""
        emitter1 = get_event_emitter()
        emitter2 = get_event_emitter()

        assert emitter1 is emitter2

    def test_reset_event_emitter(self) -> None:
        """Test resetting global emitter."""
        emitter1 = get_event_emitter()
        reset_event_emitter()
        emitter2 = get_event_emitter()

        assert emitter1 is not emitter2


class TestEventStreamConcurrency:
    """Tests for concurrent event stream operations."""

    @pytest.mark.asyncio
    async def test_concurrent_puts(self) -> None:
        """Test concurrent event puts."""
        stream = EventStream(workflow_id="wf-123")

        async def put_event(index: int) -> None:
            event = AGUIEvent(
                type=AGUIEventType.STATE_DELTA,
                workflow_id="wf-123",
                data={"index": index},
            )
            await stream.put(event)

        # Put 10 events concurrently
        await asyncio.gather(*[put_event(i) for i in range(10)])

        assert stream.qsize() == 10

    @pytest.mark.asyncio
    async def test_concurrent_streams(self) -> None:
        """Test concurrent stream creation."""
        emitter = EventEmitter()

        async def create_and_use(index: int) -> None:
            stream = await emitter.create_stream(f"wf-{index}")
            event = AGUIEvent(
                type=AGUIEventType.RUN_STARTED,
                workflow_id=f"wf-{index}",
            )
            await emitter.emit(event)

        await asyncio.gather(*[create_and_use(i) for i in range(10)])

        assert len(emitter.get_active_workflows()) == 10

    @pytest.mark.asyncio
    async def test_producer_consumer(self) -> None:
        """Test producer-consumer pattern."""
        stream = EventStream(workflow_id="wf-123")
        received_events = []

        async def producer() -> None:
            for i in range(5):
                event = AGUIEvent(
                    type=AGUIEventType.STATE_DELTA,
                    workflow_id="wf-123",
                    data={"index": i},
                )
                await stream.put(event)
                await asyncio.sleep(0.01)

            # Send terminal event
            await stream.put(
                AGUIEvent(
                    type=AGUIEventType.RUN_FINISHED,
                    workflow_id="wf-123",
                )
            )

        async def consumer() -> None:
            async for event in stream.stream(timeout=1.0):
                received_events.append(event)

        await asyncio.gather(producer(), consumer())

        assert len(received_events) == 6  # 5 delta + 1 finished
