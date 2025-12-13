"""
Unit tests for the workflow graph module.

Tests the LangGraph workflow creation, compilation, and execution
including graph structure, routing, and state management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

from info_agent.workflow.graph import (
    create_workflow_graph,
    compile_workflow,
    get_compiled_workflow,
    reset_compiled_workflow,
    run_workflow,
    resume_workflow,
)
from info_agent.workflow.state import SupervisorState, WorkflowStatus


@pytest.fixture(autouse=True)
def reset_workflow_singleton():
    """Reset workflow singleton before and after each test."""
    reset_compiled_workflow()
    yield
    reset_compiled_workflow()


@pytest.fixture
def mock_state_graph():
    """Create a mock StateGraph."""
    return MagicMock()


@pytest.fixture
def mock_compiled_workflow():
    """Create a mock compiled workflow."""
    mock = MagicMock()
    mock.ainvoke = AsyncMock()
    mock.get_state = MagicMock()
    return mock


@pytest.fixture
def basic_workflow_state():
    """Create a basic workflow state for testing."""
    state: SupervisorState = {
        "workflow_id": "wf-test-123",
        "workflow_name": "Test Workflow",
        "instructions": "Test instructions",
        "instructions_filename": "test.txt",
        "target_email": "test@example.com",
        "target_name": "Test User",
        "requested_info": "Test info",
        "status": WorkflowStatus.CREATED.value,
        "plan": [],
        "current_step": 0,
        "plan_approved": False,
        "plan_rejected": False,
        "plan_cancelled": False,
        "approval_feedback": None,
        "email_thread_id": None,
        "sent_email_id": None,
        "sent_email_subject": None,
        "sent_email_body": None,
        "received_response": None,
        "received_response_subject": None,
        "received_attachments": [],
        "audit_log": [],
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
        "error": None,
        "error_step": None,
        "retry_count": 0,
    }
    return state


class TestCreateWorkflowGraph:
    """Tests for the create_workflow_graph function."""

    @patch("info_agent.workflow.graph.StateGraph")
    def test_create_workflow_graph_creates_graph(self, mock_state_graph_class):
        """Test that workflow graph is created with correct state schema."""
        mock_graph = MagicMock()
        mock_state_graph_class.return_value = mock_graph

        result = create_workflow_graph()

        # Verify StateGraph was instantiated with SupervisorState
        mock_state_graph_class.assert_called_once_with(SupervisorState)

        assert result == mock_graph

    @patch("info_agent.workflow.graph.StateGraph")
    def test_create_workflow_graph_adds_all_nodes(self, mock_state_graph_class):
        """Test that all required nodes are added to the graph."""
        mock_graph = MagicMock()
        mock_state_graph_class.return_value = mock_graph

        create_workflow_graph()

        # Verify all nodes were added
        expected_nodes = [
            "parse_inputs",
            "lookup_agents",
            "generate_plan",
            "await_approval",
            "execute_step",
            "send_email",
            "wait_response",
            "process_response",
        ]

        # Check that add_node was called for each expected node
        add_node_calls = [call[0][0] for call in mock_graph.add_node.call_args_list]
        for node_name in expected_nodes:
            assert node_name in add_node_calls

        # Verify total number of nodes
        assert mock_graph.add_node.call_count == 8

    @patch("info_agent.workflow.graph.StateGraph")
    def test_create_workflow_graph_sets_entry_point(self, mock_state_graph_class):
        """Test that entry point is set correctly."""
        mock_graph = MagicMock()
        mock_state_graph_class.return_value = mock_graph

        create_workflow_graph()

        mock_graph.set_entry_point.assert_called_once_with("parse_inputs")

    @patch("info_agent.workflow.graph.StateGraph")
    def test_create_workflow_graph_adds_linear_edges(self, mock_state_graph_class):
        """Test that linear edges are added correctly."""
        mock_graph = MagicMock()
        mock_state_graph_class.return_value = mock_graph

        create_workflow_graph()

        # Verify linear flow edges
        edge_calls = mock_graph.add_edge.call_args_list
        edge_pairs = [(call[0][0], call[0][1]) for call in edge_calls]

        assert ("parse_inputs", "lookup_agents") in edge_pairs
        assert ("lookup_agents", "generate_plan") in edge_pairs
        assert ("generate_plan", "await_approval") in edge_pairs
        assert ("send_email", "wait_response") in edge_pairs

    @patch("info_agent.workflow.graph.StateGraph")
    def test_create_workflow_graph_adds_conditional_edges(self, mock_state_graph_class):
        """Test that conditional edges are added correctly."""
        mock_graph = MagicMock()
        mock_state_graph_class.return_value = mock_graph

        create_workflow_graph()

        # Verify conditional edges were added
        assert mock_graph.add_conditional_edges.call_count == 3

        # Check each conditional edge
        conditional_calls = mock_graph.add_conditional_edges.call_args_list

        # Verify await_approval conditional
        approval_call = next(
            call for call in conditional_calls
            if call[0][0] == "await_approval"
        )
        assert approval_call is not None
        routes = approval_call[0][2]
        assert "approved" in routes
        assert "rejected" in routes
        assert "cancelled" in routes

        # Verify execute_step conditional
        execute_call = next(
            call for call in conditional_calls
            if call[0][0] == "execute_step"
        )
        assert execute_call is not None
        routes = execute_call[0][2]
        assert "send_email" in routes
        assert "wait_response" in routes
        assert "complete" in routes

        # Verify wait_response conditional
        wait_call = next(
            call for call in conditional_calls
            if call[0][0] == "wait_response"
        )
        assert wait_call is not None
        routes = wait_call[0][2]
        assert "received" in routes
        assert "waiting" in routes

    @patch("info_agent.workflow.graph.StateGraph")
    @patch("info_agent.workflow.graph.END")
    def test_create_workflow_graph_includes_end_nodes(
        self, mock_end, mock_state_graph_class
    ):
        """Test that END node is used in routing."""
        mock_graph = MagicMock()
        mock_state_graph_class.return_value = mock_graph

        create_workflow_graph()

        # Check that END is used in edges
        edge_calls = mock_graph.add_edge.call_args_list
        conditional_calls = mock_graph.add_conditional_edges.call_args_list

        # process_response should lead to END
        end_edges = [call for call in edge_calls if call[0][1] == mock_end]
        assert len(end_edges) > 0


class TestCompileWorkflow:
    """Tests for the compile_workflow function."""

    @patch("info_agent.config.get_settings")
    @patch("info_agent.workflow.graph.create_workflow_graph")
    @patch("info_agent.workflow.graph.compile_workflow_with_checkpointer")
    def test_compile_workflow_with_default_db_path(
        self, mock_compile_with_cp, mock_create_graph, mock_get_settings
    ):
        """Test compiling workflow with default db_path from settings."""
        mock_settings = Mock()
        mock_settings.checkpoint_db_path = "/default/path/checkpoints.db"
        mock_get_settings.return_value = mock_settings

        mock_graph = MagicMock()
        mock_create_graph.return_value = mock_graph

        mock_compiled = MagicMock()
        mock_compile_with_cp.return_value = mock_compiled

        result = compile_workflow()

        # Verify settings were retrieved
        mock_get_settings.assert_called_once()

        # Verify graph was created
        mock_create_graph.assert_called_once()

        # Verify compilation with checkpointer
        mock_compile_with_cp.assert_called_once_with(
            mock_graph,
            "/default/path/checkpoints.db"
        )

        assert result == mock_compiled

    @patch("info_agent.workflow.graph.create_workflow_graph")
    @patch("info_agent.workflow.graph.compile_workflow_with_checkpointer")
    def test_compile_workflow_with_custom_db_path(
        self, mock_compile_with_cp, mock_create_graph
    ):
        """Test compiling workflow with custom db_path."""
        mock_graph = MagicMock()
        mock_create_graph.return_value = mock_graph

        mock_compiled = MagicMock()
        mock_compile_with_cp.return_value = mock_compiled

        custom_path = "/custom/path/checkpoints.db"
        result = compile_workflow(db_path=custom_path)

        # Verify custom path was used
        mock_compile_with_cp.assert_called_once_with(mock_graph, custom_path)

        assert result == mock_compiled


class TestGetCompiledWorkflow:
    """Tests for the get_compiled_workflow function."""

    @patch("info_agent.workflow.graph.compile_workflow")
    def test_get_compiled_workflow_creates_singleton(self, mock_compile):
        """Test that get_compiled_workflow creates singleton on first call."""
        mock_compiled = MagicMock()
        mock_compile.return_value = mock_compiled

        # First call creates the singleton
        result1 = get_compiled_workflow()

        assert result1 == mock_compiled
        mock_compile.assert_called_once()

        # Second call returns same instance
        result2 = get_compiled_workflow()

        assert result2 == result1
        # compile_workflow should still only be called once
        mock_compile.assert_called_once()

    @patch("info_agent.workflow.graph.compile_workflow")
    def test_get_compiled_workflow_after_reset(self, mock_compile):
        """Test that get_compiled_workflow creates new instance after reset."""
        mock_compiled1 = MagicMock()
        mock_compiled2 = MagicMock()
        mock_compile.side_effect = [mock_compiled1, mock_compiled2]

        # First call
        result1 = get_compiled_workflow()
        assert result1 == mock_compiled1

        # Reset
        reset_compiled_workflow()

        # Next call creates new instance
        result2 = get_compiled_workflow()
        assert result2 == mock_compiled2
        assert result2 != result1

        # compile_workflow should be called twice
        assert mock_compile.call_count == 2


class TestResetCompiledWorkflow:
    """Tests for the reset_compiled_workflow function."""

    @patch("info_agent.workflow.graph.compile_workflow")
    def test_reset_compiled_workflow(self, mock_compile):
        """Test that reset clears the singleton."""
        mock_compiled = MagicMock()
        mock_compile.return_value = mock_compiled

        # Create singleton
        get_compiled_workflow()
        assert mock_compile.call_count == 1

        # Reset
        reset_compiled_workflow()

        # Next call creates new instance
        get_compiled_workflow()
        assert mock_compile.call_count == 2

    def test_reset_compiled_workflow_when_not_initialized(self):
        """Test that reset doesn't error when singleton not initialized."""
        # Should not raise error
        reset_compiled_workflow()


class TestRunWorkflow:
    """Tests for the run_workflow function."""

    @pytest.mark.asyncio
    async def test_run_workflow_success(self, basic_workflow_state, mock_compiled_workflow):
        """Test successful workflow execution."""
        final_state = basic_workflow_state.copy()
        final_state["status"] = WorkflowStatus.COMPLETED.value

        mock_compiled_workflow.ainvoke.return_value = final_state

        result = await run_workflow(
            "wf-test-123",
            basic_workflow_state,
            compiled_workflow=mock_compiled_workflow
        )

        # Verify workflow was invoked with correct config
        mock_compiled_workflow.ainvoke.assert_called_once()
        call_args = mock_compiled_workflow.ainvoke.call_args
        assert call_args[0][0] == basic_workflow_state
        assert call_args[0][1]["configurable"]["thread_id"] == "wf-test-123"

        assert result["status"] == WorkflowStatus.COMPLETED.value

    @pytest.mark.asyncio
    @patch("info_agent.workflow.graph.get_compiled_workflow")
    async def test_run_workflow_uses_singleton(
        self, mock_get_compiled, basic_workflow_state, mock_compiled_workflow
    ):
        """Test that run_workflow uses singleton when no workflow provided."""
        mock_get_compiled.return_value = mock_compiled_workflow

        final_state = basic_workflow_state.copy()
        mock_compiled_workflow.ainvoke.return_value = final_state

        await run_workflow("wf-test-123", basic_workflow_state)

        # Verify singleton was retrieved
        mock_get_compiled.assert_called_once()

        # Verify workflow was invoked
        mock_compiled_workflow.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_workflow_thread_id_format(
        self, basic_workflow_state, mock_compiled_workflow
    ):
        """Test that thread_id is passed in correct config format."""
        mock_compiled_workflow.ainvoke.return_value = basic_workflow_state

        await run_workflow(
            "custom-thread-id",
            basic_workflow_state,
            compiled_workflow=mock_compiled_workflow
        )

        config = mock_compiled_workflow.ainvoke.call_args[0][1]
        assert "configurable" in config
        assert config["configurable"]["thread_id"] == "custom-thread-id"


class TestResumeWorkflow:
    """Tests for the resume_workflow function."""

    @pytest.mark.asyncio
    async def test_resume_workflow_without_updates(
        self, basic_workflow_state, mock_compiled_workflow
    ):
        """Test resuming workflow without state updates."""
        # Mock get_state
        mock_state = Mock()
        mock_state.values = basic_workflow_state
        mock_compiled_workflow.get_state.return_value = mock_state

        # Mock ainvoke
        final_state = basic_workflow_state.copy()
        final_state["status"] = WorkflowStatus.EXECUTING.value
        mock_compiled_workflow.ainvoke.return_value = final_state

        result = await resume_workflow(
            "wf-test-123",
            updates=None,
            compiled_workflow=mock_compiled_workflow
        )

        # Verify state was retrieved
        mock_compiled_workflow.get_state.assert_called_once()
        config = mock_compiled_workflow.get_state.call_args[0][0]
        assert config["configurable"]["thread_id"] == "wf-test-123"

        # Verify workflow was invoked with current state
        mock_compiled_workflow.ainvoke.assert_called_once()

        assert result["status"] == WorkflowStatus.EXECUTING.value

    @pytest.mark.asyncio
    async def test_resume_workflow_with_updates(
        self, basic_workflow_state, mock_compiled_workflow
    ):
        """Test resuming workflow with state updates."""
        # Mock get_state
        mock_state = Mock()
        mock_state.values = basic_workflow_state
        mock_compiled_workflow.get_state.return_value = mock_state

        # Mock ainvoke
        final_state = basic_workflow_state.copy()
        final_state["plan_approved"] = True
        mock_compiled_workflow.ainvoke.return_value = final_state

        updates = {"plan_approved": True, "approval_feedback": "Looks good"}

        result = await resume_workflow(
            "wf-test-123",
            updates=updates,
            compiled_workflow=mock_compiled_workflow
        )

        # Verify workflow was invoked with updated state
        invoked_state = mock_compiled_workflow.ainvoke.call_args[0][0]
        assert invoked_state["plan_approved"] is True
        assert invoked_state["approval_feedback"] == "Looks good"

        assert result["plan_approved"] is True

    @pytest.mark.asyncio
    async def test_resume_workflow_not_found(self, mock_compiled_workflow):
        """Test resume_workflow raises error when workflow not found."""
        # Mock get_state to return None
        mock_compiled_workflow.get_state.return_value = None

        with pytest.raises(ValueError) as exc_info:
            await resume_workflow(
                "nonexistent-wf",
                compiled_workflow=mock_compiled_workflow
            )

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_resume_workflow_empty_state(self, mock_compiled_workflow):
        """Test resume_workflow raises error when state has no values."""
        # Mock get_state to return state with no values
        mock_state = Mock()
        mock_state.values = None
        mock_compiled_workflow.get_state.return_value = mock_state

        with pytest.raises(ValueError) as exc_info:
            await resume_workflow(
                "wf-test-123",
                compiled_workflow=mock_compiled_workflow
            )

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    @patch("info_agent.workflow.graph.get_compiled_workflow")
    async def test_resume_workflow_uses_singleton(
        self, mock_get_compiled, basic_workflow_state, mock_compiled_workflow
    ):
        """Test that resume_workflow uses singleton when no workflow provided."""
        mock_get_compiled.return_value = mock_compiled_workflow

        # Mock get_state
        mock_state = Mock()
        mock_state.values = basic_workflow_state
        mock_compiled_workflow.get_state.return_value = mock_state

        # Mock ainvoke
        mock_compiled_workflow.ainvoke.return_value = basic_workflow_state

        await resume_workflow("wf-test-123")

        # Verify singleton was retrieved
        mock_get_compiled.assert_called_once()


class TestIntegrationScenarios:
    """Integration-style tests for workflow graph operations."""

    @pytest.mark.asyncio
    @patch("info_agent.workflow.graph.compile_workflow")
    async def test_workflow_creation_and_execution(
        self, mock_compile, basic_workflow_state, mock_compiled_workflow
    ):
        """Test creating, compiling, and running a workflow."""
        mock_compile.return_value = mock_compiled_workflow

        # Get compiled workflow
        workflow = get_compiled_workflow()
        assert workflow == mock_compiled_workflow

        # Run workflow
        final_state = basic_workflow_state.copy()
        final_state["status"] = WorkflowStatus.COMPLETED.value
        mock_compiled_workflow.ainvoke.return_value = final_state

        result = await run_workflow(
            "wf-integration-test",
            basic_workflow_state,
            compiled_workflow=workflow
        )

        assert result["status"] == WorkflowStatus.COMPLETED.value

    @pytest.mark.asyncio
    @patch("info_agent.workflow.graph.compile_workflow")
    async def test_workflow_pause_and_resume(
        self, mock_compile, basic_workflow_state, mock_compiled_workflow
    ):
        """Test pausing and resuming a workflow."""
        mock_compile.return_value = mock_compiled_workflow

        # Initial run pauses at approval
        paused_state = basic_workflow_state.copy()
        paused_state["status"] = WorkflowStatus.AWAITING_APPROVAL.value
        mock_compiled_workflow.ainvoke.return_value = paused_state

        result1 = await run_workflow(
            "wf-pause-test",
            basic_workflow_state,
            compiled_workflow=mock_compiled_workflow
        )

        assert result1["status"] == WorkflowStatus.AWAITING_APPROVAL.value

        # Resume with approval
        mock_state = Mock()
        mock_state.values = paused_state
        mock_compiled_workflow.get_state.return_value = mock_state

        resumed_state = paused_state.copy()
        resumed_state["status"] = WorkflowStatus.EXECUTING.value
        resumed_state["plan_approved"] = True
        mock_compiled_workflow.ainvoke.return_value = resumed_state

        result2 = await resume_workflow(
            "wf-pause-test",
            updates={"plan_approved": True},
            compiled_workflow=mock_compiled_workflow
        )

        assert result2["status"] == WorkflowStatus.EXECUTING.value
        assert result2["plan_approved"] is True

    @pytest.mark.asyncio
    @patch("info_agent.workflow.graph.compile_workflow")
    async def test_multiple_workflow_instances(
        self, mock_compile, basic_workflow_state, mock_compiled_workflow
    ):
        """Test running multiple workflow instances concurrently."""
        mock_compile.return_value = mock_compiled_workflow

        # Create states for multiple workflows
        state1 = basic_workflow_state.copy()
        state1["workflow_id"] = "wf-1"

        state2 = basic_workflow_state.copy()
        state2["workflow_id"] = "wf-2"

        # Mock different final states
        final1 = state1.copy()
        final1["status"] = WorkflowStatus.COMPLETED.value

        final2 = state2.copy()
        final2["status"] = WorkflowStatus.WAITING_FOR_RESPONSE.value

        mock_compiled_workflow.ainvoke.side_effect = [final1, final2]

        # Run both workflows
        result1 = await run_workflow(
            "wf-1",
            state1,
            compiled_workflow=mock_compiled_workflow
        )

        result2 = await run_workflow(
            "wf-2",
            state2,
            compiled_workflow=mock_compiled_workflow
        )

        # Verify both workflows ran with different states
        assert result1["workflow_id"] == "wf-1"
        assert result1["status"] == WorkflowStatus.COMPLETED.value

        assert result2["workflow_id"] == "wf-2"
        assert result2["status"] == WorkflowStatus.WAITING_FOR_RESPONSE.value

        # Verify ainvoke was called twice
        assert mock_compiled_workflow.ainvoke.call_count == 2


class TestGraphStructure:
    """Tests for workflow graph structure and routing."""

    @patch("info_agent.workflow.graph.StateGraph")
    def test_graph_has_all_required_nodes(self, mock_state_graph_class):
        """Test that graph contains all required nodes for the workflow."""
        mock_graph = MagicMock()
        mock_state_graph_class.return_value = mock_graph

        create_workflow_graph()

        # Get all node names
        node_names = [call[0][0] for call in mock_graph.add_node.call_args_list]

        # Verify required nodes
        required_nodes = {
            "parse_inputs",
            "lookup_agents",
            "generate_plan",
            "await_approval",
            "execute_step",
            "send_email",
            "wait_response",
            "process_response",
        }

        assert set(node_names) == required_nodes

    @patch("info_agent.workflow.graph.StateGraph")
    def test_graph_routing_covers_all_cases(self, mock_state_graph_class):
        """Test that graph routing covers all possible workflow states."""
        mock_graph = MagicMock()
        mock_state_graph_class.return_value = mock_graph

        create_workflow_graph()

        # Get conditional edges
        conditional_calls = mock_graph.add_conditional_edges.call_args_list

        # Verify approval routing
        approval_routes = next(
            call[0][2] for call in conditional_calls
            if call[0][0] == "await_approval"
        )
        assert "approved" in approval_routes
        assert "rejected" in approval_routes
        assert "cancelled" in approval_routes

        # Verify execution routing
        execution_routes = next(
            call[0][2] for call in conditional_calls
            if call[0][0] == "execute_step"
        )
        assert "send_email" in execution_routes
        assert "wait_response" in execution_routes
        assert "complete" in execution_routes

        # Verify response routing
        response_routes = next(
            call[0][2] for call in conditional_calls
            if call[0][0] == "wait_response"
        )
        assert "received" in response_routes
        assert "waiting" in response_routes
