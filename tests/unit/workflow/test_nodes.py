"""
Unit tests for workflow nodes.
"""

import pytest
from datetime import datetime

from info_agent.workflow.state import (
    SupervisorState,
    WorkflowStatus,
    create_initial_state,
)
from info_agent.workflow.nodes import (
    parse_inputs_node,
    lookup_agents_node,
    generate_plan_node,
    await_approval_node,
    execute_step_node,
    send_email_node,
    wait_response_node,
    handle_clarification_node,
    check_timeout_node,
    escalate_node,
    validate_document_node,
    report_results_node,
)


class TestParseInputsNode:
    """Tests for parse_inputs_node."""

    @pytest.fixture
    def basic_state(self) -> SupervisorState:
        """Create basic initial state."""
        return create_initial_state(
            workflow_id="wf-123",
            instructions="Send email to raj@gmail.com asking for Excel with 10 recipes",
            faq="Q: Format? A: Excel",
            escalation_rules="If no reply in 48 hours, contact vishal@gmail.com. For clarifications, email mrinal@gmail.com",
            validation_criteria="Must have 10 rows",
        )

    @pytest.mark.asyncio
    async def test_extracts_target_email(self, basic_state: SupervisorState) -> None:
        """Test extraction of target email."""
        result = await parse_inputs_node(basic_state)

        assert result["target_email"] == "raj@gmail.com"

    @pytest.mark.asyncio
    async def test_extracts_escalation_contact(self, basic_state: SupervisorState) -> None:
        """Test extraction of escalation contact."""
        result = await parse_inputs_node(basic_state)

        assert result["escalation_contact"] == "vishal@gmail.com"

    @pytest.mark.asyncio
    async def test_extracts_clarification_contact(self, basic_state: SupervisorState) -> None:
        """Test extraction of clarification contact."""
        result = await parse_inputs_node(basic_state)

        assert result["clarification_contact"] == "mrinal@gmail.com"

    @pytest.mark.asyncio
    async def test_extracts_timeout_hours(self, basic_state: SupervisorState) -> None:
        """Test extraction of timeout hours."""
        result = await parse_inputs_node(basic_state)

        assert result["timeout_hours"] == 48

    @pytest.mark.asyncio
    async def test_creates_audit_entry(self, basic_state: SupervisorState) -> None:
        """Test audit entry is created."""
        result = await parse_inputs_node(basic_state)

        audit_log = result["audit_log"]
        inputs_parsed_entries = [e for e in audit_log if e["event_type"] == "inputs_parsed"]

        assert len(inputs_parsed_entries) == 1

    @pytest.mark.asyncio
    async def test_handles_missing_email(self) -> None:
        """Test handling when no email in instructions."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Send a request for recipes",
            faq="FAQ",
            escalation_rules="Contact support",
            validation_criteria="Criteria",
        )

        result = await parse_inputs_node(state)

        assert result["target_email"] == ""


class TestLookupAgentsNode:
    """Tests for lookup_agents_node."""

    @pytest.fixture
    def basic_state(self) -> SupervisorState:
        """Create basic initial state."""
        return create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )

    @pytest.mark.asyncio
    async def test_returns_available_agents(self, basic_state: SupervisorState) -> None:
        """Test that available agents are returned."""
        result = await lookup_agents_node(basic_state)

        assert len(result["available_agents"]) > 0

    @pytest.mark.asyncio
    async def test_includes_mail_agent(self, basic_state: SupervisorState) -> None:
        """Test mail agent is included."""
        result = await lookup_agents_node(basic_state)

        agent_names = [a["name"] for a in result["available_agents"]]
        assert "mail-agent" in agent_names

    @pytest.mark.asyncio
    async def test_includes_validation_agent(self, basic_state: SupervisorState) -> None:
        """Test validation agent is included."""
        result = await lookup_agents_node(basic_state)

        agent_names = [a["name"] for a in result["available_agents"]]
        assert "validation-agent" in agent_names

    @pytest.mark.asyncio
    async def test_creates_audit_entry(self, basic_state: SupervisorState) -> None:
        """Test audit entry is created."""
        result = await lookup_agents_node(basic_state)

        audit_log = result["audit_log"]
        discovered_entries = [e for e in audit_log if e["event_type"] == "agents_discovered"]

        assert len(discovered_entries) == 1


class TestGeneratePlanNode:
    """Tests for generate_plan_node."""

    @pytest.fixture
    def state_with_parsed_inputs(self) -> SupervisorState:
        """Create state with parsed inputs."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Must have 10 rows",
        )
        state["target_email"] = "target@example.com"
        state["requested_info"] = "Please send Excel with recipes"
        state["timeout_hours"] = 48
        return state

    @pytest.mark.asyncio
    async def test_generates_plan(self, state_with_parsed_inputs: SupervisorState) -> None:
        """Test plan is generated."""
        result = await generate_plan_node(state_with_parsed_inputs)

        assert len(result["plan"]) > 0

    @pytest.mark.asyncio
    async def test_plan_includes_send_email_step(self, state_with_parsed_inputs: SupervisorState) -> None:
        """Test plan includes send email step."""
        result = await generate_plan_node(state_with_parsed_inputs)

        actions = [step["action"] for step in result["plan"]]
        assert any("send" in action for action in actions)

    @pytest.mark.asyncio
    async def test_plan_includes_validation_step(self, state_with_parsed_inputs: SupervisorState) -> None:
        """Test plan includes validation step."""
        result = await generate_plan_node(state_with_parsed_inputs)

        agents = [step["agent"] for step in result["plan"]]
        assert "validation-agent" in agents

    @pytest.mark.asyncio
    async def test_sets_awaiting_approval_status(self, state_with_parsed_inputs: SupervisorState) -> None:
        """Test status is set to awaiting approval."""
        result = await generate_plan_node(state_with_parsed_inputs)

        assert result["status"] == WorkflowStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_resets_current_step(self, state_with_parsed_inputs: SupervisorState) -> None:
        """Test current step is reset to 0."""
        result = await generate_plan_node(state_with_parsed_inputs)

        assert result["current_step"] == 0


class TestAwaitApprovalNode:
    """Tests for await_approval_node."""

    @pytest.fixture
    def state_awaiting_approval(self) -> SupervisorState:
        """Create state awaiting approval."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["status"] = WorkflowStatus.AWAITING_APPROVAL
        state["plan"] = [{"step_number": 1, "action": "test"}]
        return state

    @pytest.mark.asyncio
    async def test_passthrough_state(self, state_awaiting_approval: SupervisorState) -> None:
        """Test node is passthrough."""
        result = await await_approval_node(state_awaiting_approval)

        # Status should remain unchanged
        assert result["status"] == WorkflowStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_creates_audit_entry(self, state_awaiting_approval: SupervisorState) -> None:
        """Test audit entry is created."""
        result = await await_approval_node(state_awaiting_approval)

        audit_log = result["audit_log"]
        awaiting_entries = [e for e in audit_log if e["event_type"] == "awaiting_approval"]

        assert len(awaiting_entries) == 1


class TestExecuteStepNode:
    """Tests for execute_step_node."""

    @pytest.fixture
    def state_with_plan(self) -> SupervisorState:
        """Create state with plan."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["plan"] = [
            {"step_number": 1, "action": "send_email", "status": "pending"},
            {"step_number": 2, "action": "validate", "status": "pending"},
        ]
        state["current_step"] = 0
        return state

    @pytest.mark.asyncio
    async def test_marks_step_in_progress(self, state_with_plan: SupervisorState) -> None:
        """Test current step is marked in progress."""
        result = await execute_step_node(state_with_plan)

        assert result["plan"][0]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_sets_started_at(self, state_with_plan: SupervisorState) -> None:
        """Test started_at is set."""
        result = await execute_step_node(state_with_plan)

        assert result["plan"][0]["started_at"] is not None

    @pytest.mark.asyncio
    async def test_updates_status_to_executing(self, state_with_plan: SupervisorState) -> None:
        """Test status is updated to executing."""
        result = await execute_step_node(state_with_plan)

        assert result["status"] == WorkflowStatus.EXECUTING

    @pytest.mark.asyncio
    async def test_completes_when_no_more_steps(self) -> None:
        """Test workflow completes when all steps done."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["plan"] = [
            {"step_number": 1, "action": "test", "status": "completed"},
        ]
        state["current_step"] = 1  # Past last step

        result = await execute_step_node(state)

        assert result["status"] == WorkflowStatus.COMPLETED


class TestSendEmailNode:
    """Tests for send_email_node."""

    @pytest.fixture
    def state_ready_to_send(self) -> SupervisorState:
        """Create state ready to send email."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["target_email"] = "target@example.com"
        state["requested_info"] = "Please send recipes"
        state["plan"] = [
            {"step_number": 1, "action": "send_email", "status": "in_progress"},
        ]
        state["current_step"] = 0
        return state

    @pytest.mark.asyncio
    async def test_creates_email_thread(self, state_ready_to_send: SupervisorState) -> None:
        """Test email thread is created."""
        result = await send_email_node(state_ready_to_send)

        assert len(result["email_threads"]) == 1
        assert result["email_threads"][0]["target_email"] == "target@example.com"

    @pytest.mark.asyncio
    async def test_marks_step_completed(self, state_ready_to_send: SupervisorState) -> None:
        """Test step is marked completed."""
        result = await send_email_node(state_ready_to_send)

        assert result["plan"][0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_increments_current_step(self, state_ready_to_send: SupervisorState) -> None:
        """Test current step is incremented."""
        result = await send_email_node(state_ready_to_send)

        assert result["current_step"] == 1

    @pytest.mark.asyncio
    async def test_sets_waiting_since(self, state_ready_to_send: SupervisorState) -> None:
        """Test waiting_since is set."""
        result = await send_email_node(state_ready_to_send)

        assert result["waiting_since"] is not None

    @pytest.mark.asyncio
    async def test_updates_status_to_waiting(self, state_ready_to_send: SupervisorState) -> None:
        """Test status is updated to waiting for response."""
        result = await send_email_node(state_ready_to_send)

        assert result["status"] == WorkflowStatus.WAITING_FOR_RESPONSE


class TestWaitResponseNode:
    """Tests for wait_response_node."""

    @pytest.mark.asyncio
    async def test_passthrough(self) -> None:
        """Test node is passthrough."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["waiting_since"] = datetime.utcnow().isoformat()

        result = await wait_response_node(state)

        # Should return same state
        assert result["workflow_id"] == "wf-123"


class TestHandleClarificationNode:
    """Tests for handle_clarification_node."""

    @pytest.fixture
    def state_with_clarification(self) -> SupervisorState:
        """Create state with pending clarification."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="Q: What format? A: Use Excel format with columns",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["clarification_history"] = [
            {
                "id": "clar-1",
                "question": "What format should I use?",
                "source_email": "user@example.com",
                "faq_match": False,
                "answer": None,
            }
        ]
        return state

    @pytest.mark.asyncio
    async def test_matches_faq(self, state_with_clarification: SupervisorState) -> None:
        """Test FAQ matching."""
        result = await handle_clarification_node(state_with_clarification)

        latest = result["clarification_history"][-1]
        assert latest["faq_match"] is True

    @pytest.mark.asyncio
    async def test_no_match_escalates(self) -> None:
        """Test non-matching question is escalated."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="Q: Format? A: Excel",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["clarification_history"] = [
            {
                "id": "clar-1",
                "question": "Can you give me more time?",
                "source_email": "user@example.com",
                "faq_match": False,
                "answer": None,
            }
        ]

        result = await handle_clarification_node(state)

        latest = result["clarification_history"][-1]
        assert latest["escalated"] is True


class TestCheckTimeoutNode:
    """Tests for check_timeout_node."""

    @pytest.mark.asyncio
    async def test_no_timeout_when_within_limit(self) -> None:
        """Test no timeout when within limit."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["waiting_since"] = datetime.utcnow().isoformat()
        state["timeout_hours"] = 48

        result = await check_timeout_node(state)

        # Retry count should not be incremented
        assert result.get("retry_count", 0) == 0

    @pytest.mark.asyncio
    async def test_timeout_increments_retry(self) -> None:
        """Test timeout increments retry count."""
        from datetime import timedelta

        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        # Set waiting since to more than timeout hours ago
        old_time = datetime.utcnow() - timedelta(hours=50)
        state["waiting_since"] = old_time.isoformat()
        state["timeout_hours"] = 48

        result = await check_timeout_node(state)

        assert result["retry_count"] == 1


class TestEscalateNode:
    """Tests for escalate_node."""

    @pytest.mark.asyncio
    async def test_updates_status_to_escalated(self) -> None:
        """Test status is updated to escalated."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["escalation_contact"] = "admin@example.com"

        result = await escalate_node(state)

        assert result["status"] == WorkflowStatus.ESCALATED

    @pytest.mark.asyncio
    async def test_creates_audit_entry(self) -> None:
        """Test audit entry is created."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["escalation_contact"] = "admin@example.com"

        result = await escalate_node(state)

        audit_log = result["audit_log"]
        escalated_entries = [e for e in audit_log if e["event_type"] == "escalated"]

        assert len(escalated_entries) == 1


class TestValidateDocumentNode:
    """Tests for validate_document_node."""

    @pytest.fixture
    def state_with_document(self) -> SupervisorState:
        """Create state with received document."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Must have 10 rows",
        )
        state["received_documents"] = [
            {
                "id": "doc-1",
                "filename": "recipes.xlsx",
                "content_type": "application/xlsx",
                "size_bytes": 15000,
            }
        ]
        return state

    @pytest.mark.asyncio
    async def test_creates_validation_result(self, state_with_document: SupervisorState) -> None:
        """Test validation result is created."""
        result = await validate_document_node(state_with_document)

        assert result["validation_result"] is not None
        assert result["validation_result"]["document_name"] == "recipes.xlsx"

    @pytest.mark.asyncio
    async def test_updates_status_to_validating(self, state_with_document: SupervisorState) -> None:
        """Test status is updated to validating."""
        result = await validate_document_node(state_with_document)

        assert result["status"] == WorkflowStatus.VALIDATING

    @pytest.mark.asyncio
    async def test_skips_when_no_documents(self) -> None:
        """Test skips validation when no documents."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["received_documents"] = []

        result = await validate_document_node(state)

        audit_log = result["audit_log"]
        skipped_entries = [e for e in audit_log if e["event_type"] == "validation_skipped"]

        assert len(skipped_entries) == 1


class TestReportResultsNode:
    """Tests for report_results_node."""

    @pytest.fixture
    def state_with_results(self) -> SupervisorState:
        """Create state with validation results."""
        state = create_initial_state(
            workflow_id="wf-123",
            instructions="Test",
            faq="FAQ",
            escalation_rules="Rules",
            validation_criteria="Criteria",
        )
        state["target_email"] = "target@example.com"
        state["validation_result"] = {
            "passed": True,
            "score": 1.0,
        }
        state["received_documents"] = [{"id": "doc-1"}]
        state["email_threads"] = [{"id": "thread-1"}]
        return state

    @pytest.mark.asyncio
    async def test_creates_final_report(self, state_with_results: SupervisorState) -> None:
        """Test final report is created."""
        result = await report_results_node(state_with_results)

        assert result["final_report"] is not None
        assert result["final_report"]["workflow_id"] == "wf-123"

    @pytest.mark.asyncio
    async def test_report_includes_validation_status(self, state_with_results: SupervisorState) -> None:
        """Test report includes validation status."""
        result = await report_results_node(state_with_results)

        assert result["final_report"]["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_updates_status_to_completed(self, state_with_results: SupervisorState) -> None:
        """Test status is updated to completed."""
        result = await report_results_node(state_with_results)

        assert result["status"] == WorkflowStatus.COMPLETED
