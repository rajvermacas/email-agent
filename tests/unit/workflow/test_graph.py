"""
Unit tests for workflow graph.
"""

import tempfile
from pathlib import Path

import pytest

from langgraph.checkpoint.sqlite import SqliteSaver

from info_agent.workflow.graph import (
    create_workflow_graph,
    create_workflow,
    InfoAgentWorkflow,
)
from info_agent.workflow.checkpointer import create_checkpointer
from info_agent.workflow.state import WorkflowStatus


class TestCreateWorkflowGraph:
    """Tests for create_workflow_graph function."""

    def test_creates_graph(self) -> None:
        """Test graph is created."""
        graph = create_workflow_graph()

        assert graph is not None

    def test_has_entry_point(self) -> None:
        """Test graph has entry point."""
        graph = create_workflow_graph()

        # Entry point should be set - check __start__ is in edges tuple
        start_edges = [edge for edge in graph.edges if edge[0] == "__start__"]
        assert len(start_edges) > 0, "No entry point edge found"
        assert start_edges[0][1] == "parse_inputs", "Entry point should be parse_inputs"

    def test_has_all_nodes(self) -> None:
        """Test graph has all required nodes."""
        graph = create_workflow_graph()

        expected_nodes = [
            "parse_inputs",
            "lookup_agents",
            "generate_plan",
            "await_approval",
            "execute_step",
            "send_email",
            "wait_response",
            "handle_clarification",
            "check_timeout",
            "escalate",
            "validate_document",
            "report_results",
        ]

        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"


class TestInfoAgentWorkflow:
    """Tests for InfoAgentWorkflow class."""

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_checkpoints.db"

    def test_init_without_checkpointer(self) -> None:
        """Test initialization without checkpointer."""
        workflow = InfoAgentWorkflow()

        assert workflow.checkpointer is None
        assert workflow.graph is not None

    @pytest.mark.asyncio
    async def test_init_with_checkpoint_path(self, temp_db: Path) -> None:
        """Test initialization with checkpoint path."""
        workflow = await InfoAgentWorkflow.create(checkpoint_db_path=temp_db)

        assert workflow.checkpointer is not None

    def test_init_with_checkpointer(self, temp_db: Path) -> None:
        """Test initialization with pre-created checkpointer."""
        checkpointer = create_checkpointer(temp_db)
        workflow = InfoAgentWorkflow(checkpointer=checkpointer)

        assert workflow.checkpointer is checkpointer

    @pytest.mark.asyncio
    async def test_run_simple_workflow(self) -> None:
        """Test running a simple workflow."""
        workflow = InfoAgentWorkflow()

        result = await workflow.run(
            workflow_id="wf-test",
            instructions="Send email to test@example.com",
            faq="Q: Format? A: Excel",
            escalation_rules="Escalate to admin@example.com after 48 hours",
            validation_criteria="Must have 10 rows",
        )

        assert result is not None
        assert result["workflow_id"] == "wf-test"

    @pytest.mark.asyncio
    async def test_run_sets_status_to_completed(self) -> None:
        """Test that run completes workflow."""
        workflow = InfoAgentWorkflow()

        result = await workflow.run(
            workflow_id="wf-test",
            instructions="Send email to test@example.com",
            faq="FAQ content",
            escalation_rules="Rules content",
            validation_criteria="Criteria content",
        )

        assert result["status"] == WorkflowStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_stream_workflow(self) -> None:
        """Test streaming workflow execution."""
        workflow = InfoAgentWorkflow()

        events = []
        async for node_name, state in workflow.stream(
            workflow_id="wf-test",
            instructions="Send email to test@example.com",
            faq="FAQ content",
            escalation_rules="Rules content",
            validation_criteria="Criteria content",
        ):
            events.append((node_name, state))

        # Should have multiple events
        assert len(events) > 0

        # First event should be from parse_inputs
        assert events[0][0] == "parse_inputs"

    @pytest.mark.asyncio
    async def test_get_state_without_checkpointer(self) -> None:
        """Test get_state returns None without checkpointer."""
        workflow = InfoAgentWorkflow()

        result = await workflow.get_state("wf-test")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_state_with_checkpointer(self, temp_db: Path) -> None:
        """Test get_state returns state with checkpointer."""
        workflow = await InfoAgentWorkflow.create(checkpoint_db_path=temp_db)

        # Run workflow to create checkpoint
        await workflow.run(
            workflow_id="wf-test",
            instructions="Send email to test@example.com",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        # Get state
        state = await workflow.get_state("wf-test")

        assert state is not None

    @pytest.mark.asyncio
    async def test_resume_without_checkpointer_raises(self) -> None:
        """Test resume raises error without checkpointer."""
        workflow = InfoAgentWorkflow()

        with pytest.raises(ValueError, match="Cannot resume without checkpointer"):
            await workflow.resume("wf-test")

    @pytest.mark.asyncio
    async def test_resume_nonexistent_workflow_raises(self, temp_db: Path) -> None:
        """Test resume raises error for nonexistent workflow."""
        workflow = await InfoAgentWorkflow.create(checkpoint_db_path=temp_db)

        with pytest.raises(ValueError, match="No checkpoint found"):
            await workflow.resume("nonexistent")

    @pytest.mark.asyncio
    async def test_approve_plan(self, temp_db: Path) -> None:
        """Test approving workflow plan."""
        workflow = await InfoAgentWorkflow.create(checkpoint_db_path=temp_db)

        # First run workflow
        await workflow.run(
            workflow_id="wf-test",
            instructions="Send email to test@example.com",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        # Approve should work (even though workflow is complete)
        # This tests the method works with existing checkpoints
        result = await workflow.approve_plan("wf-test")

        assert result is not None

    @pytest.mark.asyncio
    async def test_reject_plan(self, temp_db: Path) -> None:
        """Test rejecting workflow plan calls resume and completes workflow."""
        workflow = await InfoAgentWorkflow.create(checkpoint_db_path=temp_db)

        # First run workflow - it completes normally
        await workflow.run(
            workflow_id="wf-test",
            instructions="Send email to test@example.com",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

        # After a completed run, calling reject_plan will re-run the workflow
        # which will complete again (since stub mode simulates responses).
        # Note: rejection reason is cleared when generate_plan regenerates the plan.
        result = await workflow.reject_plan("wf-test", "Need more details")

        # Result should exist and be completed
        assert result is not None
        # Workflow completes after re-plan since stub mode auto-approves
        assert result.get("status") == WorkflowStatus.COMPLETED


class TestCreateWorkflow:
    """Tests for create_workflow function."""

    def test_create_without_path(self) -> None:
        """Test creating workflow without checkpoint path."""
        workflow = create_workflow()

        assert isinstance(workflow, InfoAgentWorkflow)
        assert workflow.checkpointer is None

    @pytest.mark.asyncio
    async def test_create_async_with_path(self) -> None:
        """Test creating async workflow with checkpoint path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            workflow = await InfoAgentWorkflow.create(checkpoint_db_path=db_path)

            assert isinstance(workflow, InfoAgentWorkflow)
            assert workflow.checkpointer is not None

    @pytest.mark.asyncio
    async def test_create_async_with_string_path(self) -> None:
        """Test creating async workflow with string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/test.db"

            workflow = await InfoAgentWorkflow.create(checkpoint_db_path=db_path)

            assert isinstance(workflow, InfoAgentWorkflow)
            assert workflow.checkpointer is not None
