"""
Unit tests for the workflow nodes module.

Tests all workflow node functions including parsing inputs, creating plans,
handling approvals, executing steps, and managing email operations.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from info_agent.workflow.nodes import (
    parse_input_files,
    query_a2a_registry,
    create_execution_plan,
    wait_for_user_approval,
    check_approval_status,
    execute_current_step,
    determine_next_action,
    invoke_mail_agent_send,
    wait_for_email_response,
    check_response_received,
    handle_email_response,
    _parse_json_response,
)
from info_agent.workflow.state import WorkflowStatus, SupervisorState
from info_agent.utils.exceptions import LLMError, A2AError, WorkflowError


@pytest.fixture
def basic_state():
    """Create a basic workflow state for testing."""
    state: SupervisorState = {
        "workflow_id": "wf-test-123",
        "workflow_name": "Test Workflow",
        "instructions": "Please request Q4 reports from finance@example.com",
        "instructions_filename": "request.txt",
        "target_email": "",
        "target_name": "",
        "requested_info": "",
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


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    mock_response = Mock()
    mock_response.content = '{"target_email": "finance@example.com", "target_name": "Finance Team", "requested_info": "Q4 Financial Reports"}'
    return mock_response


@pytest.fixture
def mock_llm():
    """Create a mock LLM instance."""
    mock = AsyncMock()
    return mock


class TestParseJsonResponse:
    """Tests for the _parse_json_response helper function."""

    def test_parse_json_response_plain_json(self):
        """Test parsing plain JSON response."""
        json_str = '{"key": "value", "number": 42}'
        result = _parse_json_response(json_str)

        assert result == {"key": "value", "number": 42}

    def test_parse_json_response_with_markdown_json_block(self):
        """Test parsing JSON wrapped in markdown code block."""
        json_str = '''```json
{"key": "value", "number": 42}
```'''
        result = _parse_json_response(json_str)

        assert result == {"key": "value", "number": 42}

    def test_parse_json_response_with_plain_markdown_block(self):
        """Test parsing JSON wrapped in plain markdown code block."""
        json_str = '''```
{"key": "value", "number": 42}
```'''
        result = _parse_json_response(json_str)

        assert result == {"key": "value", "number": 42}

    def test_parse_json_response_with_whitespace(self):
        """Test parsing JSON with leading/trailing whitespace."""
        json_str = '  \n  {"key": "value"}  \n  '
        result = _parse_json_response(json_str)

        assert result == {"key": "value"}

    def test_parse_json_response_invalid_json(self):
        """Test parsing invalid JSON raises ValueError."""
        json_str = '{"invalid": json syntax}'

        with pytest.raises(ValueError) as exc_info:
            _parse_json_response(json_str)

        assert "Invalid JSON" in str(exc_info.value)

    def test_parse_json_response_empty_string(self):
        """Test parsing empty string raises ValueError."""
        with pytest.raises(ValueError):
            _parse_json_response("")

    def test_parse_json_response_complex_json(self):
        """Test parsing complex nested JSON."""
        json_str = '''```json
{
    "level1": {
        "level2": ["item1", "item2"],
        "number": 123
    },
    "list": [1, 2, 3]
}
```'''
        result = _parse_json_response(json_str)

        assert result["level1"]["level2"] == ["item1", "item2"]
        assert result["list"] == [1, 2, 3]


class TestParseInputFiles:
    """Tests for the parse_input_files node."""

    @pytest.mark.asyncio
    @patch("info_agent.llm.get_gemini_llm")
    @patch("info_agent.workflow.nodes.datetime")
    async def test_parse_input_files_success(
        self, mock_datetime, mock_get_llm, basic_state, mock_llm, mock_llm_response
    ):
        """Test successful parsing of input files."""
        mock_get_llm.return_value = mock_llm
        mock_llm.ainvoke.return_value = mock_llm_response

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await parse_input_files(basic_state)

        # Verify LLM was called
        mock_llm.ainvoke.assert_called_once()
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "Please request Q4 reports from finance@example.com" in call_args

        # Verify returned state updates
        assert result["target_email"] == "finance@example.com"
        assert result["target_name"] == "Finance Team"
        assert result["requested_info"] == "Q4 Financial Reports"
        assert result["status"] == WorkflowStatus.PLANNING.value
        assert result["updated_at"] == "2025-01-15T11:00:00Z"

        # Verify audit log entry was added
        assert len(result["audit_log"]) > 0
        assert result["audit_log"][-1]["action"] == "parse_inputs"

    @pytest.mark.asyncio
    async def test_parse_input_files_missing_instructions(self, basic_state):
        """Test parse_input_files fails when instructions are missing."""
        basic_state["instructions"] = ""

        with pytest.raises(WorkflowError) as exc_info:
            await parse_input_files(basic_state)

        assert "No instructions provided" in str(exc_info.value)
        assert exc_info.value.workflow_id == "wf-test-123"
        assert exc_info.value.step == "parse_inputs"

    @pytest.mark.asyncio
    @patch("info_agent.llm.get_gemini_llm")
    async def test_parse_input_files_invalid_email(
        self, mock_get_llm, basic_state, mock_llm
    ):
        """Test parse_input_files fails with invalid email."""
        mock_get_llm.return_value = mock_llm

        # LLM returns response without @ in email
        mock_response = Mock()
        mock_response.content = '{"target_email": "invalid-email", "target_name": "Test", "requested_info": "Info"}'
        mock_llm.ainvoke.return_value = mock_response

        with pytest.raises(WorkflowError) as exc_info:
            await parse_input_files(basic_state)

        assert "Invalid or missing target email" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.llm.get_gemini_llm")
    async def test_parse_input_files_llm_error(self, mock_get_llm, basic_state, mock_llm):
        """Test parse_input_files handles LLM errors."""
        mock_get_llm.return_value = mock_llm
        mock_llm.ainvoke.side_effect = Exception("API rate limit exceeded")

        with pytest.raises(LLMError) as exc_info:
            await parse_input_files(basic_state)

        assert "Failed to parse instructions" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.llm.get_gemini_llm")
    async def test_parse_input_files_extraction_prompt_format(
        self, mock_get_llm, basic_state, mock_llm, mock_llm_response
    ):
        """Test that extraction prompt is formatted correctly."""
        mock_get_llm.return_value = mock_llm
        mock_llm.ainvoke.return_value = mock_llm_response

        await parse_input_files(basic_state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "Extract the following information" in call_args
        assert "target_email" in call_args
        assert "target_name" in call_args
        assert "requested_info" in call_args


class TestQueryA2ARegistry:
    """Tests for the query_a2a_registry node."""

    @pytest.mark.asyncio
    @patch("info_agent.config.get_settings")
    @patch("info_agent.a2a.client.A2AClient")
    @patch("info_agent.workflow.nodes.datetime")
    async def test_query_a2a_registry_success(
        self, mock_datetime, mock_a2a_client_class, mock_get_settings, basic_state
    ):
        """Test successful A2A registry query."""
        mock_settings = Mock()
        mock_settings.a2a_registry_url = "http://registry:8000"
        mock_get_settings.return_value = mock_settings

        mock_client = AsyncMock()
        mock_a2a_client_class.return_value = mock_client
        mock_client.list_agents.return_value = [
            {"name": "mail-agent", "url": "http://mail-agent:8001"},
            {"name": "other-agent", "url": "http://other:8002"},
        ]

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await query_a2a_registry(basic_state)

        # Verify client was created with correct URL
        mock_a2a_client_class.assert_called_once_with("http://registry:8000")

        # Verify agents were listed
        mock_client.list_agents.assert_called_once()

        # Verify result contains audit entry
        assert result["updated_at"] == "2025-01-15T11:00:00Z"
        audit_entry = result["audit_log"][-1]
        assert audit_entry["action"] == "lookup_agents"
        assert "http://mail-agent:8001" in audit_entry["details"]

    @pytest.mark.asyncio
    @patch("info_agent.config.get_settings")
    @patch("info_agent.a2a.client.A2AClient")
    @patch("info_agent.workflow.nodes.datetime")
    async def test_query_a2a_registry_mail_agent_not_found(
        self, mock_datetime, mock_a2a_client_class, mock_get_settings, basic_state
    ):
        """Test when mail agent is not found in registry."""
        mock_settings = Mock()
        mock_settings.a2a_registry_url = "http://registry:8000"
        mock_get_settings.return_value = mock_settings

        mock_client = AsyncMock()
        mock_a2a_client_class.return_value = mock_client
        mock_client.list_agents.return_value = [
            {"name": "other-agent", "url": "http://other:8002"},
        ]

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await query_a2a_registry(basic_state)

        # Should not fail, just log
        audit_entry = result["audit_log"][-1]
        assert "not found" in audit_entry["details"].lower()

    @pytest.mark.asyncio
    @patch("info_agent.config.get_settings")
    @patch("info_agent.a2a.client.A2AClient")
    @patch("info_agent.workflow.nodes.datetime")
    async def test_query_a2a_registry_exception_handling(
        self, mock_datetime, mock_a2a_client_class, mock_get_settings, basic_state
    ):
        """Test that registry query exceptions don't fail the workflow."""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        mock_client = AsyncMock()
        mock_a2a_client_class.return_value = mock_client
        mock_client.list_agents.side_effect = Exception("Connection timeout")

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        # Should not raise exception
        result = await query_a2a_registry(basic_state)

        # Should log the error
        audit_entry = result["audit_log"][-1]
        assert "failed" in audit_entry["details"].lower()


class TestCreateExecutionPlan:
    """Tests for the create_execution_plan node."""

    @pytest.mark.asyncio
    @patch("info_agent.llm.get_gemini_llm")
    @patch("info_agent.workflow.nodes.datetime")
    async def test_create_execution_plan_success(
        self, mock_datetime, mock_get_llm, basic_state, mock_llm
    ):
        """Test successful execution plan creation."""
        basic_state["target_email"] = "finance@example.com"
        basic_state["target_name"] = "Finance Team"
        basic_state["requested_info"] = "Q4 Reports"

        mock_get_llm.return_value = mock_llm

        mock_response = Mock()
        mock_response.content = '''```json
{
    "plan": [
        {"step": 1, "action": "send_email", "description": "Send request email", "status": "pending"},
        {"step": 2, "action": "wait_response", "description": "Wait for reply", "status": "pending"}
    ],
    "summary": "Send email and wait for response"
}
```'''
        mock_llm.ainvoke.return_value = mock_response

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await create_execution_plan(basic_state)

        # Verify LLM was called
        mock_llm.ainvoke.assert_called_once()
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "Finance Team" in call_args
        assert "finance@example.com" in call_args
        assert "Q4 Reports" in call_args

        # Verify plan was created
        assert len(result["plan"]) == 2
        assert result["plan"][0]["action"] == "send_email"
        assert result["plan"][1]["action"] == "wait_response"
        assert result["status"] == WorkflowStatus.AWAITING_APPROVAL.value
        assert result["current_step"] == 0

    @pytest.mark.asyncio
    @patch("info_agent.llm.get_gemini_llm")
    async def test_create_execution_plan_llm_error(
        self, mock_get_llm, basic_state, mock_llm
    ):
        """Test create_execution_plan handles LLM errors."""
        basic_state["target_email"] = "test@example.com"

        mock_get_llm.return_value = mock_llm
        mock_llm.ainvoke.side_effect = Exception("LLM service unavailable")

        with pytest.raises(LLMError) as exc_info:
            await create_execution_plan(basic_state)

        assert "Failed to generate execution plan" in str(exc_info.value)


class TestWaitForUserApproval:
    """Tests for the wait_for_user_approval node."""

    @pytest.mark.asyncio
    @patch("info_agent.workflow.nodes.datetime")
    async def test_wait_for_user_approval(self, mock_datetime, basic_state):
        """Test wait_for_user_approval updates state correctly."""
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await wait_for_user_approval(basic_state)

        assert result["status"] == WorkflowStatus.AWAITING_APPROVAL.value
        assert result["updated_at"] == "2025-01-15T11:00:00Z"


class TestCheckApprovalStatus:
    """Tests for the check_approval_status routing function."""

    def test_check_approval_status_approved(self, basic_state):
        """Test routing when plan is approved."""
        basic_state["plan_approved"] = True

        result = check_approval_status(basic_state)

        assert result == "approved"

    def test_check_approval_status_rejected(self, basic_state):
        """Test routing when plan is rejected."""
        basic_state["plan_rejected"] = True

        result = check_approval_status(basic_state)

        assert result == "rejected"

    def test_check_approval_status_cancelled(self, basic_state):
        """Test routing when workflow is cancelled."""
        basic_state["plan_cancelled"] = True

        result = check_approval_status(basic_state)

        assert result == "cancelled"

    def test_check_approval_status_default(self, basic_state):
        """Test routing defaults to approved."""
        result = check_approval_status(basic_state)

        assert result == "approved"

    def test_check_approval_status_priority(self, basic_state):
        """Test that approved has priority over rejected."""
        basic_state["plan_approved"] = True
        basic_state["plan_rejected"] = True

        result = check_approval_status(basic_state)

        assert result == "approved"


class TestExecuteCurrentStep:
    """Tests for the execute_current_step node."""

    @pytest.mark.asyncio
    @patch("info_agent.workflow.nodes.datetime")
    async def test_execute_current_step_success(self, mock_datetime, basic_state):
        """Test executing current step."""
        basic_state["plan"] = [
            {"step": 1, "action": "send_email", "description": "Send request", "status": "pending"},
        ]
        basic_state["current_step"] = 0

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await execute_current_step(basic_state)

        assert result["status"] == WorkflowStatus.EXECUTING.value
        assert result["updated_at"] == "2025-01-15T11:00:00Z"

        # Verify audit log
        audit_entry = result["audit_log"][-1]
        assert audit_entry["action"] == "execute_step"
        assert "send_email" in str(audit_entry["metadata"])

    @pytest.mark.asyncio
    async def test_execute_current_step_all_steps_completed(self, basic_state):
        """Test execute_current_step when all steps are done."""
        basic_state["plan"] = [
            {"step": 1, "action": "send_email", "description": "Send", "status": "completed"},
        ]
        basic_state["current_step"] = 1  # Beyond plan length

        result = await execute_current_step(basic_state)

        assert result["status"] == WorkflowStatus.COMPLETED.value


class TestDetermineNextAction:
    """Tests for the determine_next_action routing function."""

    def test_determine_next_action_send_email(self, basic_state):
        """Test routing to send_email action."""
        basic_state["plan"] = [
            {"step": 1, "action": "send_email", "description": "Send", "status": "pending"},
        ]
        basic_state["current_step"] = 0

        result = determine_next_action(basic_state)

        assert result == "send_email"

    def test_determine_next_action_wait_response(self, basic_state):
        """Test routing to wait_response action."""
        basic_state["plan"] = [
            {"step": 1, "action": "wait_response", "description": "Wait", "status": "pending"},
        ]
        basic_state["current_step"] = 0

        result = determine_next_action(basic_state)

        assert result == "wait_response"

    def test_determine_next_action_complete(self, basic_state):
        """Test routing to complete when no more steps."""
        basic_state["plan"] = [
            {"step": 1, "action": "send_email", "description": "Send", "status": "completed"},
        ]
        basic_state["current_step"] = 1  # Beyond plan

        result = determine_next_action(basic_state)

        assert result == "complete"

    def test_determine_next_action_unknown_action(self, basic_state):
        """Test routing with unknown action defaults to complete."""
        basic_state["plan"] = [
            {"step": 1, "action": "unknown_action", "description": "Unknown", "status": "pending"},
        ]
        basic_state["current_step"] = 0

        result = determine_next_action(basic_state)

        assert result == "complete"


class TestInvokeMailAgentSend:
    """Tests for the invoke_mail_agent_send node."""

    @pytest.mark.asyncio
    @patch("info_agent.config.get_settings")
    @patch("info_agent.llm.get_gemini_llm")
    @patch("info_agent.a2a.client.A2AClient")
    @patch("info_agent.workflow.nodes.datetime")
    async def test_invoke_mail_agent_send_success(
        self, mock_datetime, mock_a2a_client_class, mock_get_llm,
        mock_get_settings, basic_state, mock_llm
    ):
        """Test successful email sending via mail agent."""
        basic_state["target_email"] = "finance@example.com"
        basic_state["target_name"] = "Finance Team"
        basic_state["requested_info"] = "Q4 Reports"
        basic_state["current_step"] = 0

        # Mock settings
        mock_settings = Mock()
        mock_settings.host = "localhost"
        mock_settings.mail_agent_port = 8001
        mock_get_settings.return_value = mock_settings

        # Mock LLM for email composition
        mock_get_llm.return_value = mock_llm
        mock_response = Mock()
        mock_response.content = "Dear Finance Team,\n\nPlease provide Q4 reports.\n\nThank you."
        mock_llm.ainvoke.return_value = mock_response

        # Mock A2A client
        mock_client = AsyncMock()
        mock_a2a_client_class.return_value = mock_client
        mock_client.send_task.return_value = {
            "message_id": "msg-123",
            "thread_id": "thread-456",
        }

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await invoke_mail_agent_send(basic_state)

        # Verify LLM was used to compose email
        mock_llm.ainvoke.assert_called_once()
        compose_prompt = mock_llm.ainvoke.call_args[0][0]
        assert "Finance Team" in compose_prompt
        assert "Q4 Reports" in compose_prompt

        # Verify A2A client was called
        mock_client.send_task.assert_called_once()
        task_args = mock_client.send_task.call_args
        assert task_args[1]["skill_id"] == "send-email"
        assert task_args[1]["payload"]["to"] == "finance@example.com"

        # Verify result
        assert result["sent_email_id"] == "msg-123"
        assert result["email_thread_id"] == "thread-456"
        assert result["current_step"] == 1
        assert result["status"] == WorkflowStatus.WAITING_FOR_RESPONSE.value

    @pytest.mark.asyncio
    @patch("info_agent.config.get_settings")
    @patch("info_agent.llm.get_gemini_llm")
    @patch("info_agent.a2a.client.A2AClient")
    async def test_invoke_mail_agent_send_client_error(
        self, mock_a2a_client_class, mock_get_llm, mock_get_settings, basic_state, mock_llm
    ):
        """Test error handling when mail agent fails."""
        basic_state["target_email"] = "test@example.com"
        basic_state["requested_info"] = "Test"

        mock_settings = Mock()
        mock_settings.host = "localhost"
        mock_settings.mail_agent_port = 8001
        mock_get_settings.return_value = mock_settings

        mock_get_llm.return_value = mock_llm
        mock_response = Mock()
        mock_response.content = "Email body"
        mock_llm.ainvoke.return_value = mock_response

        mock_client = AsyncMock()
        mock_a2a_client_class.return_value = mock_client
        mock_client.send_task.side_effect = Exception("Mail service unavailable")

        with pytest.raises(A2AError) as exc_info:
            await invoke_mail_agent_send(basic_state)

        assert "Failed to send email" in str(exc_info.value)
        assert exc_info.value.agent_name == "mail-agent"
        assert exc_info.value.skill_id == "send-email"


class TestWaitForEmailResponse:
    """Tests for the wait_for_email_response node."""

    @pytest.mark.asyncio
    @patch("info_agent.workflow.nodes.datetime")
    async def test_wait_for_email_response(self, mock_datetime, basic_state):
        """Test wait_for_email_response updates state correctly."""
        basic_state["email_thread_id"] = "thread-123"

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T11:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await wait_for_email_response(basic_state)

        assert result["status"] == WorkflowStatus.WAITING_FOR_RESPONSE.value
        assert result["updated_at"] == "2025-01-15T11:00:00Z"


class TestCheckResponseReceived:
    """Tests for the check_response_received routing function."""

    def test_check_response_received_yes(self, basic_state):
        """Test routing when response is received."""
        basic_state["received_response"] = "Here are the Q4 reports..."

        result = check_response_received(basic_state)

        assert result == "received"

    def test_check_response_received_no(self, basic_state):
        """Test routing when response is not received."""
        basic_state["received_response"] = None

        result = check_response_received(basic_state)

        assert result == "waiting"

    def test_check_response_received_empty_string(self, basic_state):
        """Test that empty string is treated as no response."""
        basic_state["received_response"] = ""

        result = check_response_received(basic_state)

        assert result == "waiting"


class TestHandleEmailResponse:
    """Tests for the handle_email_response node."""

    @pytest.mark.asyncio
    @patch("info_agent.workflow.nodes.datetime")
    async def test_handle_email_response_success(self, mock_datetime, basic_state):
        """Test successful handling of email response."""
        basic_state["received_response"] = "Here are the requested reports."
        basic_state["received_response_subject"] = "RE: Q4 Reports"
        basic_state["received_attachments"] = [
            {
                "filename": "q4_report.pdf",
                "size": 1024,
                "mime_type": "application/pdf",
                "content_path": "/tmp/q4_report.pdf",
            }
        ]
        basic_state["current_step"] = 1

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T12:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await handle_email_response(basic_state)

        assert result["current_step"] == 2
        assert result["status"] == WorkflowStatus.COMPLETED.value
        assert result["updated_at"] == "2025-01-15T12:00:00Z"

        # Verify audit log
        audit_entry = result["audit_log"][-1]
        assert audit_entry["action"] == "process_response"
        assert audit_entry["metadata"]["has_attachments"] is True

    @pytest.mark.asyncio
    @patch("info_agent.workflow.nodes.datetime")
    async def test_handle_email_response_no_attachments(self, mock_datetime, basic_state):
        """Test handling response without attachments."""
        basic_state["received_response"] = "No reports available."
        basic_state["received_attachments"] = []

        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T12:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        result = await handle_email_response(basic_state)

        audit_entry = result["audit_log"][-1]
        assert audit_entry["metadata"]["has_attachments"] is False


class TestIntegrationScenarios:
    """Integration-style tests for workflow node interactions."""

    @pytest.mark.asyncio
    @patch("info_agent.llm.get_gemini_llm")
    @patch("info_agent.config.get_settings")
    @patch("info_agent.a2a.client.A2AClient")
    @patch("info_agent.workflow.nodes.datetime")
    async def test_full_workflow_node_sequence(
        self, mock_datetime, mock_a2a_client_class, mock_get_settings,
        mock_get_llm, basic_state, mock_llm
    ):
        """Test a complete sequence of node executions."""
        # Setup mocks
        mock_now = Mock()
        mock_now.isoformat.return_value = "2025-01-15T10:00:00Z"
        mock_datetime.utcnow.return_value = mock_now

        mock_get_llm.return_value = mock_llm

        # Step 1: Parse inputs
        parse_response = Mock()
        parse_response.content = '{"target_email": "test@example.com", "target_name": "Test User", "requested_info": "Test Info"}'
        mock_llm.ainvoke.return_value = parse_response

        state = await parse_input_files(basic_state)
        assert state["target_email"] == "test@example.com"
        assert state["status"] == WorkflowStatus.PLANNING.value

        # Update state
        basic_state.update(state)

        # Step 2: Create plan
        plan_response = Mock()
        plan_response.content = '''{"plan": [{"step": 1, "action": "send_email", "description": "Send", "status": "pending"}], "summary": "Test plan"}'''
        mock_llm.ainvoke.return_value = plan_response

        state = await create_execution_plan(basic_state)
        assert len(state["plan"]) == 1
        assert state["status"] == WorkflowStatus.AWAITING_APPROVAL.value

        # Update state
        basic_state.update(state)

        # Step 3: Approval
        basic_state["plan_approved"] = True
        approval_route = check_approval_status(basic_state)
        assert approval_route == "approved"

        # Step 4: Execute step
        state = await execute_current_step(basic_state)
        assert state["status"] == WorkflowStatus.EXECUTING.value

        basic_state.update(state)

        # Step 5: Determine next action
        next_action = determine_next_action(basic_state)
        assert next_action == "send_email"

    @pytest.mark.asyncio
    @patch("info_agent.llm.get_gemini_llm")
    async def test_error_recovery_flow(self, mock_get_llm, basic_state, mock_llm):
        """Test error handling across multiple nodes."""
        mock_get_llm.return_value = mock_llm

        # First attempt fails
        mock_llm.ainvoke.side_effect = Exception("Temporary error")

        with pytest.raises(LLMError):
            await parse_input_files(basic_state)

        # Retry succeeds
        mock_llm.ainvoke.side_effect = None
        parse_response = Mock()
        parse_response.content = '{"target_email": "test@example.com", "target_name": "Test", "requested_info": "Info"}'
        mock_llm.ainvoke.return_value = parse_response

        state = await parse_input_files(basic_state)
        assert state["target_email"] == "test@example.com"
