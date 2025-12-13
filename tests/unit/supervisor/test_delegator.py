"""
Unit tests for the TaskDelegator.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from info_agent.supervisor.delegator import TaskDelegator, StubTaskDelegator
from info_agent.a2a.models import Task, TaskState


class TestTaskDelegatorInit:
    """Tests for TaskDelegator initialization."""

    def test_init_default(self) -> None:
        """Test default initialization creates A2A client."""
        delegator = TaskDelegator()

        assert delegator._client is not None

    def test_init_with_client(self) -> None:
        """Test initialization with provided client."""
        mock_client = MagicMock()

        delegator = TaskDelegator(a2a_client=mock_client)

        assert delegator._client is mock_client


class TestTaskDelegatorDelegateTask:
    """Tests for delegate_task method."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock A2A client."""
        client = MagicMock()
        client.send_task = AsyncMock(
            return_value=Task(
                id="task-123",
                state=TaskState.COMPLETED,
                skill_id="test_skill",
                result={"success": True},
            )
        )
        return client

    @pytest.fixture
    def delegator(self, mock_client: MagicMock) -> TaskDelegator:
        """Create a delegator with mock client."""
        return TaskDelegator(a2a_client=mock_client)

    @pytest.mark.asyncio
    async def test_delegate_task_calls_client(
        self,
        delegator: TaskDelegator,
        mock_client: MagicMock,
    ) -> None:
        """Test delegate_task calls the A2A client."""
        await delegator.delegate_task(
            agent_endpoint="http://localhost:8001",
            skill_id="send_email",
            parameters={"to": "test@example.com"},
        )

        mock_client.send_task.assert_called_once_with(
            endpoint="http://localhost:8001",
            skill_id="send_email",
            parameters={"to": "test@example.com"},
            context=None,
        )

    @pytest.mark.asyncio
    async def test_delegate_task_returns_task(
        self,
        delegator: TaskDelegator,
    ) -> None:
        """Test delegate_task returns the task."""
        task = await delegator.delegate_task(
            agent_endpoint="http://localhost:8001",
            skill_id="send_email",
            parameters={},
        )

        assert task.id == "task-123"
        assert task.state == TaskState.COMPLETED

    @pytest.mark.asyncio
    async def test_delegate_task_with_context(
        self,
        delegator: TaskDelegator,
        mock_client: MagicMock,
    ) -> None:
        """Test delegate_task with context."""
        await delegator.delegate_task(
            agent_endpoint="http://localhost:8001",
            skill_id="send_email",
            parameters={},
            context={"workflow_id": "wf-123"},
        )

        mock_client.send_task.assert_called_once()
        call_kwargs = mock_client.send_task.call_args.kwargs
        assert call_kwargs["context"] == {"workflow_id": "wf-123"}


class TestTaskDelegatorGetStatus:
    """Tests for get_task_status method."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock A2A client."""
        client = MagicMock()
        client.get_task = AsyncMock(
            return_value=Task(
                id="task-123",
                state=TaskState.WORKING,
                skill_id="test_skill",
            )
        )
        return client

    @pytest.fixture
    def delegator(self, mock_client: MagicMock) -> TaskDelegator:
        """Create a delegator with mock client."""
        return TaskDelegator(a2a_client=mock_client)

    @pytest.mark.asyncio
    async def test_get_status_calls_client(
        self,
        delegator: TaskDelegator,
        mock_client: MagicMock,
    ) -> None:
        """Test get_task_status calls the A2A client."""
        await delegator.get_task_status(
            agent_endpoint="http://localhost:8001",
            task_id="task-123",
        )

        mock_client.get_task.assert_called_once_with(
            endpoint="http://localhost:8001",
            task_id="task-123",
        )

    @pytest.mark.asyncio
    async def test_get_status_returns_task(
        self,
        delegator: TaskDelegator,
    ) -> None:
        """Test get_task_status returns the task."""
        task = await delegator.get_task_status(
            agent_endpoint="http://localhost:8001",
            task_id="task-123",
        )

        assert task.id == "task-123"
        assert task.state == TaskState.WORKING


class TestTaskDelegatorCancelTask:
    """Tests for cancel_task method."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock A2A client."""
        client = MagicMock()
        client.cancel_task = AsyncMock(
            return_value=Task(
                id="task-123",
                state=TaskState.CANCELLED,
                skill_id="test_skill",
            )
        )
        return client

    @pytest.fixture
    def delegator(self, mock_client: MagicMock) -> TaskDelegator:
        """Create a delegator with mock client."""
        return TaskDelegator(a2a_client=mock_client)

    @pytest.mark.asyncio
    async def test_cancel_task_calls_client(
        self,
        delegator: TaskDelegator,
        mock_client: MagicMock,
    ) -> None:
        """Test cancel_task calls the A2A client."""
        await delegator.cancel_task(
            agent_endpoint="http://localhost:8001",
            task_id="task-123",
        )

        mock_client.cancel_task.assert_called_once_with(
            endpoint="http://localhost:8001",
            task_id="task-123",
        )

    @pytest.mark.asyncio
    async def test_cancel_task_returns_task(
        self,
        delegator: TaskDelegator,
    ) -> None:
        """Test cancel_task returns the task."""
        task = await delegator.cancel_task(
            agent_endpoint="http://localhost:8001",
            task_id="task-123",
        )

        assert task.id == "task-123"
        assert task.state == TaskState.CANCELLED


class TestTaskDelegatorWaitForCompletion:
    """Tests for wait_for_completion method."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock A2A client that completes after 2 checks."""
        client = MagicMock()
        call_count = 0

        async def get_task_mock(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return Task(
                    id="task-123",
                    state=TaskState.WORKING,
                    skill_id="test_skill",
                )
            return Task(
                id="task-123",
                state=TaskState.COMPLETED,
                skill_id="test_skill",
                result={"success": True},
            )

        client.get_task = AsyncMock(side_effect=get_task_mock)
        return client

    @pytest.fixture
    def delegator(self, mock_client: MagicMock) -> TaskDelegator:
        """Create a delegator with mock client."""
        return TaskDelegator(a2a_client=mock_client)

    @pytest.mark.asyncio
    async def test_wait_completes_when_done(
        self,
        delegator: TaskDelegator,
    ) -> None:
        """Test wait_for_completion returns when task completes."""
        task = await delegator.wait_for_completion(
            agent_endpoint="http://localhost:8001",
            task_id="task-123",
            timeout_seconds=10.0,
            poll_interval=0.01,
        )

        assert task.state == TaskState.COMPLETED

    @pytest.mark.asyncio
    async def test_wait_timeout(self) -> None:
        """Test wait_for_completion raises on timeout."""
        client = MagicMock()
        client.get_task = AsyncMock(
            return_value=Task(
                id="task-123",
                state=TaskState.WORKING,
                skill_id="test_skill",
            )
        )
        delegator = TaskDelegator(a2a_client=client)

        with pytest.raises(TimeoutError):
            await delegator.wait_for_completion(
                agent_endpoint="http://localhost:8001",
                task_id="task-123",
                timeout_seconds=0.05,
                poll_interval=0.01,
            )


class TestStubTaskDelegator:
    """Tests for StubTaskDelegator."""

    @pytest.fixture
    def stub_delegator(self) -> StubTaskDelegator:
        """Create a stub delegator."""
        return StubTaskDelegator()

    @pytest.mark.asyncio
    async def test_delegate_returns_completed_task(
        self,
        stub_delegator: StubTaskDelegator,
    ) -> None:
        """Test stub delegate returns completed task."""
        task = await stub_delegator.delegate_task(
            agent_endpoint="http://localhost:8001",
            skill_id="send_email",
            parameters={"to": "test@example.com"},
        )

        assert task.state == TaskState.COMPLETED
        assert task.id is not None

    @pytest.mark.asyncio
    async def test_delegate_send_email_result(
        self,
        stub_delegator: StubTaskDelegator,
    ) -> None:
        """Test stub delegate returns send_email result."""
        task = await stub_delegator.delegate_task(
            agent_endpoint="http://localhost:8001",
            skill_id="send_email",
            parameters={},
        )

        assert len(task.artifacts) > 0
        result = task.artifacts[0].data
        assert result["success"] is True
        assert "message_id" in result
        assert "thread_id" in result

    @pytest.mark.asyncio
    async def test_delegate_validate_document_result(
        self,
        stub_delegator: StubTaskDelegator,
    ) -> None:
        """Test stub delegate returns validate_document result."""
        task = await stub_delegator.delegate_task(
            agent_endpoint="http://localhost:8002",
            skill_id="validate_document",
            parameters={},
        )

        assert len(task.artifacts) > 0
        result = task.artifacts[0].data
        assert result["passed"] is True
        assert result["score"] == 1.0

    @pytest.mark.asyncio
    async def test_delegate_execute_python_result(
        self,
        stub_delegator: StubTaskDelegator,
    ) -> None:
        """Test stub delegate returns execute_python result."""
        task = await stub_delegator.delegate_task(
            agent_endpoint="http://localhost:8002",
            skill_id="execute_python",
            parameters={},
        )

        assert len(task.artifacts) > 0
        result = task.artifacts[0].data
        assert result["success"] is True
        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_delegate_unknown_skill_result(
        self,
        stub_delegator: StubTaskDelegator,
    ) -> None:
        """Test stub delegate returns generic result for unknown skill."""
        task = await stub_delegator.delegate_task(
            agent_endpoint="http://localhost:8001",
            skill_id="unknown_skill",
            parameters={},
        )

        assert len(task.artifacts) > 0
        result = task.artifacts[0].data
        assert result["success"] is True
