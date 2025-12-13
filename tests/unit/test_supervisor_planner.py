"""
Unit tests for Supervisor Execution Planner.

Tests the ExecutionPlanner class with mocked LLM to avoid
actual API calls during testing.
"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

from info_agent.agents.supervisor.planner import ExecutionPlanner, generate_email_content
from info_agent.utils.exceptions import LLMError, ValidationError


@pytest.fixture
def mock_llm():
    """Create a mock LLM instance."""
    llm = AsyncMock()
    return llm


@pytest.fixture
def mock_plan_response():
    """Create a mock LLM response with execution plan."""
    response = Mock()
    response.content = json.dumps({
        "plan": [
            {"step": 1, "action": "send_email", "description": "Send email requesting information", "status": "pending"},
            {"step": 2, "action": "wait_response", "description": "Wait for email reply", "status": "pending"},
            {"step": 3, "action": "process_response", "description": "Process received information", "status": "pending"}
        ],
        "summary": "Send email to request information, wait for reply, and process response",
        "email_subject": "Information Request - Q3 Reports",
        "email_body": "Dear John,\n\nI hope this email finds you well.\n\nI am writing to request the Q3 2024 financial reports.\n\nBest regards"
    })
    return response


class TestExecutionPlannerInit:
    """Tests for ExecutionPlanner initialization."""

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_init_success(self, mock_get_llm):
        """Test successful planner initialization."""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        planner = ExecutionPlanner()

        assert planner.llm is not None
        assert planner.AVAILABLE_ACTIONS is not None
        assert "send_email" in planner.AVAILABLE_ACTIONS
        assert "wait_response" in planner.AVAILABLE_ACTIONS

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_init_llm_failure(self, mock_get_llm):
        """Test initialization handles LLM failure."""
        mock_get_llm.side_effect = Exception("API key not found")

        with pytest.raises(LLMError) as exc_info:
            ExecutionPlanner()

        assert "Failed to initialize ExecutionPlanner" in str(exc_info.value)


class TestExecutionPlannerGeneratePlan:
    """Tests for ExecutionPlanner.generate_plan method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_plan_success(self, mock_get_llm, mock_plan_response):
        """Test successful plan generation."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_plan_response)
        mock_get_llm.return_value = mock_llm

        planner = ExecutionPlanner()

        result = await planner.generate_plan(
            target_email="john@example.com",
            target_name="John Doe",
            requested_info="Q3 2024 financial reports",
        )

        assert "plan" in result
        assert "summary" in result
        assert "email_subject" in result
        assert "email_body" in result

        assert len(result["plan"]) == 3
        assert result["plan"][0]["action"] == "send_email"
        assert result["email_subject"] == "Information Request - Q3 Reports"
        assert "Dear John" in result["email_body"]

        # Verify LLM was called
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_plan_with_instructions(self, mock_get_llm, mock_plan_response):
        """Test plan generation with optional instructions."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_plan_response)
        mock_get_llm.return_value = mock_llm

        planner = ExecutionPlanner()

        result = await planner.generate_plan(
            target_email="john@example.com",
            target_name="John Doe",
            requested_info="Q3 reports",
            instructions="Original instruction: Please be polite and professional",
        )

        assert result is not None
        # Instructions should be included in prompt
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "Original instruction" in call_args or "polite" in call_args.lower()

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_plan_with_feedback(self, mock_get_llm, mock_plan_response):
        """Test plan generation with feedback from rejection."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_plan_response)
        mock_get_llm.return_value = mock_llm

        planner = ExecutionPlanner()

        result = await planner.generate_plan(
            target_email="john@example.com",
            target_name="John Doe",
            requested_info="Q3 reports",
            feedback="Please be more specific about which reports are needed",
        )

        assert result is not None
        # Feedback should be included in prompt
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "feedback" in call_args.lower() or "specific" in call_args.lower()

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_plan_missing_target_email(self, mock_get_llm):
        """Test plan generation fails with missing target_email."""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        planner = ExecutionPlanner()

        with pytest.raises(ValidationError) as exc_info:
            await planner.generate_plan(
                target_email="",
                target_name="John Doe",
                requested_info="Q3 reports",
            )

        assert "target_email is required" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_plan_invalid_email(self, mock_get_llm):
        """Test plan generation fails with invalid email format."""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        planner = ExecutionPlanner()

        with pytest.raises(ValidationError) as exc_info:
            await planner.generate_plan(
                target_email="invalid-email",
                target_name="John Doe",
                requested_info="Q3 reports",
            )

        assert "Invalid email address format" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_plan_missing_target_name(self, mock_get_llm):
        """Test plan generation fails with missing target_name."""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        planner = ExecutionPlanner()

        with pytest.raises(ValidationError) as exc_info:
            await planner.generate_plan(
                target_email="john@example.com",
                target_name="",
                requested_info="Q3 reports",
            )

        assert "target_name is required" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_plan_missing_requested_info(self, mock_get_llm):
        """Test plan generation fails with missing requested_info."""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        planner = ExecutionPlanner()

        with pytest.raises(ValidationError) as exc_info:
            await planner.generate_plan(
                target_email="john@example.com",
                target_name="John Doe",
                requested_info="",
            )

        assert "requested_info is required" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_plan_llm_invocation_failure(self, mock_get_llm):
        """Test plan generation handles LLM invocation failure."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API timeout"))
        mock_get_llm.return_value = mock_llm

        planner = ExecutionPlanner()

        with pytest.raises(LLMError) as exc_info:
            await planner.generate_plan(
                target_email="john@example.com",
                target_name="John Doe",
                requested_info="Q3 reports",
            )

        assert "Failed to generate execution plan" in str(exc_info.value)


class TestExecutionPlannerParseResponse:
    """Tests for ExecutionPlanner._parse_plan_response method."""

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_parse_response_valid_json(self, mock_get_llm):
        """Test parsing valid JSON response."""
        mock_get_llm.return_value = Mock()
        planner = ExecutionPlanner()

        response_text = json.dumps({
            "plan": [{"step": 1, "action": "send_email", "description": "Send", "status": "pending"}],
            "summary": "Test plan",
            "email_subject": "Test",
            "email_body": "Body"
        })

        result = planner._parse_plan_response(response_text)

        assert "plan" in result
        assert len(result["plan"]) == 1

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_parse_response_with_markdown(self, mock_get_llm):
        """Test parsing JSON in markdown code block."""
        mock_get_llm.return_value = Mock()
        planner = ExecutionPlanner()

        response_text = """```json
{
  "plan": [{"step": 1, "action": "send_email", "description": "Send", "status": "pending"}],
  "summary": "Test",
  "email_subject": "Subject",
  "email_body": "Body"
}
```"""

        result = planner._parse_plan_response(response_text)

        assert "plan" in result

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_parse_response_invalid_json(self, mock_get_llm):
        """Test parsing handles invalid JSON."""
        mock_get_llm.return_value = Mock()
        planner = ExecutionPlanner()

        response_text = "Not valid JSON"

        with pytest.raises(LLMError) as exc_info:
            planner._parse_plan_response(response_text)

        assert "invalid JSON" in str(exc_info.value)


class TestExecutionPlannerValidatePlan:
    """Tests for ExecutionPlanner._validate_plan method."""

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_validate_plan_complete(self, mock_get_llm):
        """Test validation passes with complete plan."""
        mock_get_llm.return_value = Mock()
        planner = ExecutionPlanner()

        plan_data = {
            "plan": [
                {"step": 1, "action": "send_email", "description": "Send email", "status": "pending"}
            ],
            "summary": "Plan summary",
            "email_subject": "Subject",
            "email_body": "Body text"
        }

        # Should not raise exception
        planner._validate_plan(plan_data)

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_validate_plan_missing_field(self, mock_get_llm):
        """Test validation fails with missing required field."""
        mock_get_llm.return_value = Mock()
        planner = ExecutionPlanner()

        plan_data = {
            "plan": [],
            "summary": "Summary",
            # missing email_subject and email_body
        }

        with pytest.raises(ValidationError) as exc_info:
            planner._validate_plan(plan_data)

        assert "missing required fields" in str(exc_info.value).lower()

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_validate_plan_empty_plan(self, mock_get_llm):
        """Test validation fails with empty plan."""
        mock_get_llm.return_value = Mock()
        planner = ExecutionPlanner()

        plan_data = {
            "plan": [],
            "summary": "Summary",
            "email_subject": "Subject",
            "email_body": "Body"
        }

        with pytest.raises(ValidationError) as exc_info:
            planner._validate_plan(plan_data)

        assert "at least one step" in str(exc_info.value)

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_validate_plan_invalid_action(self, mock_get_llm):
        """Test validation fails with invalid action."""
        mock_get_llm.return_value = Mock()
        planner = ExecutionPlanner()

        plan_data = {
            "plan": [
                {"step": 1, "action": "invalid_action", "description": "Invalid", "status": "pending"}
            ],
            "summary": "Summary",
            "email_subject": "Subject",
            "email_body": "Body"
        }

        with pytest.raises(ValidationError) as exc_info:
            planner._validate_plan(plan_data)

        assert "invalid action" in str(exc_info.value).lower()

    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    def test_validate_plan_empty_subject(self, mock_get_llm):
        """Test validation fails with empty subject."""
        mock_get_llm.return_value = Mock()
        planner = ExecutionPlanner()

        plan_data = {
            "plan": [
                {"step": 1, "action": "send_email", "description": "Send", "status": "pending"}
            ],
            "summary": "Summary",
            "email_subject": "   ",
            "email_body": "Body"
        }

        with pytest.raises(ValidationError) as exc_info:
            planner._validate_plan(plan_data)

        assert "subject cannot be empty" in str(exc_info.value).lower()


class TestGenerateEmailContent:
    """Tests for generate_email_content standalone function."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_email_content_success(self, mock_get_llm):
        """Test successful email content generation."""
        response = Mock()
        response.content = json.dumps({
            "subject": "Information Request",
            "body": "Dear John,\n\nPlease send the reports.\n\nBest regards"
        })

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=response)
        mock_get_llm.return_value = mock_llm

        result = await generate_email_content(
            target_name="John Doe",
            requested_info="Q3 reports",
        )

        assert result["subject"] == "Information Request"
        assert "Dear John" in result["body"]

    @pytest.mark.asyncio
    @patch("info_agent.agents.supervisor.planner.get_gemini_llm")
    async def test_generate_email_content_with_instructions(self, mock_get_llm):
        """Test email generation with custom instructions."""
        response = Mock()
        response.content = json.dumps({
            "subject": "Urgent Request",
            "body": "Body text"
        })

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=response)
        mock_get_llm.return_value = mock_llm

        result = await generate_email_content(
            target_name="John Doe",
            requested_info="Reports",
            custom_instructions="Make it urgent",
        )

        assert result is not None
        # Custom instructions should be in prompt
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert "urgent" in call_args.lower()

    @pytest.mark.asyncio
    async def test_generate_email_content_missing_target_name(self):
        """Test email generation fails with missing target_name."""
        with pytest.raises(ValidationError) as exc_info:
            await generate_email_content(
                target_name="",
                requested_info="Reports",
            )

        assert "target_name is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_email_content_missing_requested_info(self):
        """Test email generation fails with missing requested_info."""
        with pytest.raises(ValidationError) as exc_info:
            await generate_email_content(
                target_name="John Doe",
                requested_info="",
            )

        assert "requested_info is required" in str(exc_info.value)
