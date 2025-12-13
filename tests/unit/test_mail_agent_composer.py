"""
Unit tests for Email Composer.

Tests the EmailComposer class with mocked LLM to avoid
actual API calls during testing.
"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

from info_agent.agents.mail.composer import EmailComposer
from info_agent.utils.exceptions import LLMError, ValidationError


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    response = Mock()
    response.content = json.dumps({
        "subject": "Meeting Request",
        "body": "Dear Recipient,\n\nI hope this email finds you well.\n\nBest regards"
    })
    return response


@pytest.fixture
def mock_llm():
    """Create a mock LLM instance."""
    llm = AsyncMock()
    return llm


class TestEmailComposerInit:
    """Tests for EmailComposer initialization."""

    def test_init_success(self):
        """Test successful composer initialization."""
        composer = EmailComposer()

        assert composer is not None
        # LLM is lazily initialized, so no instance yet
        assert composer.SYSTEM_PROMPT is not None
        assert "professional email composer" in composer.SYSTEM_PROMPT.lower()

    def test_system_prompt_content(self):
        """Test system prompt contains required guidelines."""
        composer = EmailComposer()

        assert "professional" in composer.SYSTEM_PROMPT
        assert "JSON" in composer.SYSTEM_PROMPT
        assert "subject" in composer.SYSTEM_PROMPT
        assert "body" in composer.SYSTEM_PROMPT


class TestEmailComposerComposeEmail:
    """Tests for EmailComposer.compose_email method."""

    @pytest.mark.asyncio
    async def test_compose_email_success(self, mock_llm, mock_llm_response):
        """Test successful email composition."""
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm):
            result = await composer.compose_email(
                to_address="client@example.com",
                instructions="Request a meeting next week to discuss the project",
            )

            assert result["subject"] == "Meeting Request"
            assert "Dear Recipient" in result["body"]
            assert "Best regards" in result["body"]

            # Verify LLM was called
            mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_compose_email_with_custom_subject(self, mock_llm, mock_llm_response):
        """Test email composition with custom subject override."""
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm):
            result = await composer.compose_email(
                to_address="team@example.com",
                instructions="Inform team about the update",
                subject="Custom Subject - Project Update",
            )

            # Custom subject should override LLM-generated one
            assert result["subject"] == "Custom Subject - Project Update"
            assert "Dear Recipient" in result["body"]

    @pytest.mark.asyncio
    async def test_compose_email_missing_to_address(self):
        """Test composition fails when to_address is missing."""
        composer = EmailComposer()

        with pytest.raises(ValidationError) as exc_info:
            await composer.compose_email(
                to_address="",
                instructions="Send an email",
            )

        assert "Recipient address (to_address) is required" in str(exc_info.value)
        assert exc_info.value.field == "to_address"

    @pytest.mark.asyncio
    async def test_compose_email_missing_instructions(self):
        """Test composition fails when instructions are missing."""
        composer = EmailComposer()

        with pytest.raises(ValidationError) as exc_info:
            await composer.compose_email(
                to_address="client@example.com",
                instructions="",
            )

        assert "Email instructions are required" in str(exc_info.value)
        assert exc_info.value.field == "instructions"

    @pytest.mark.asyncio
    async def test_compose_email_whitespace_instructions(self):
        """Test composition fails when instructions are only whitespace."""
        composer = EmailComposer()

        with pytest.raises(ValidationError) as exc_info:
            await composer.compose_email(
                to_address="client@example.com",
                instructions="   \n\t  ",
            )

        assert "instructions cannot be empty or whitespace" in str(exc_info.value)
        assert exc_info.value.field == "instructions"

    @pytest.mark.asyncio
    async def test_compose_email_llm_initialization_failure(self):
        """Test composition handles LLM initialization failure."""
        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm") as mock_get_llm:
            mock_get_llm.side_effect = Exception("API key not found")

            with pytest.raises(LLMError) as exc_info:
                await composer.compose_email(
                    to_address="client@example.com",
                    instructions="Send email",
                )

            assert "Failed to initialize LLM for email composition" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_compose_email_llm_invocation_failure(self, mock_llm):
        """Test composition handles LLM invocation failure."""
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API timeout"))

        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm):
            with pytest.raises(LLMError) as exc_info:
                await composer.compose_email(
                    to_address="client@example.com",
                    instructions="Send email",
                )

            assert "Failed to generate email content" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_compose_email_invalid_json_response(self, mock_llm):
        """Test composition handles invalid JSON in LLM response."""
        invalid_response = Mock()
        invalid_response.content = "This is not valid JSON"

        mock_llm.ainvoke = AsyncMock(return_value=invalid_response)

        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm):
            with pytest.raises(LLMError) as exc_info:
                await composer.compose_email(
                    to_address="client@example.com",
                    instructions="Send email",
                )

            assert "Failed to parse LLM output" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_compose_email_missing_subject_in_response(self, mock_llm):
        """Test composition handles missing subject in LLM response."""
        response = Mock()
        response.content = json.dumps({"body": "Email body only"})

        mock_llm.ainvoke = AsyncMock(return_value=response)

        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm):
            with pytest.raises(LLMError) as exc_info:
                await composer.compose_email(
                    to_address="client@example.com",
                    instructions="Send email",
                )

            assert "Failed to parse LLM output" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_compose_email_missing_body_in_response(self, mock_llm):
        """Test composition handles missing body in LLM response."""
        response = Mock()
        response.content = json.dumps({"subject": "Subject only"})

        mock_llm.ainvoke = AsyncMock(return_value=response)

        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm):
            with pytest.raises(LLMError) as exc_info:
                await composer.compose_email(
                    to_address="client@example.com",
                    instructions="Send email",
                )

            assert "Failed to parse LLM output" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_compose_email_with_higher_temperature(self, mock_llm, mock_llm_response):
        """Test composition uses specified temperature."""
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm) as mock_get_llm:
            await composer.compose_email(
                to_address="client@example.com",
                instructions="Write a creative email",
            )

            # Verify temperature was passed
            mock_get_llm.assert_called_once_with(temperature=0.7)


class TestEmailComposerBuildUserPrompt:
    """Tests for EmailComposer._build_user_prompt method."""

    def test_build_user_prompt_basic(self):
        """Test building basic user prompt."""
        composer = EmailComposer()

        prompt = composer._build_user_prompt(
            to_address="client@example.com",
            instructions="Request a meeting",
        )

        assert "client@example.com" in prompt
        assert "Request a meeting" in prompt
        assert "Compose an email to:" in prompt

    def test_build_user_prompt_with_custom_subject(self):
        """Test building user prompt with custom subject."""
        composer = EmailComposer()

        prompt = composer._build_user_prompt(
            to_address="team@example.com",
            instructions="Send update",
            custom_subject="Team Update - Q4",
        )

        assert "Team Update - Q4" in prompt
        assert "Use this subject line:" in prompt

    def test_build_user_prompt_without_custom_subject(self):
        """Test building user prompt without custom subject."""
        composer = EmailComposer()

        prompt = composer._build_user_prompt(
            to_address="client@example.com",
            instructions="Send email",
        )

        assert "Use this subject line:" not in prompt


class TestEmailComposerParseResponse:
    """Tests for EmailComposer._parse_llm_response method."""

    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        composer = EmailComposer()

        response_text = json.dumps({
            "subject": "Test Subject",
            "body": "Test body content"
        })

        result = composer._parse_llm_response(response_text)

        assert result["subject"] == "Test Subject"
        assert result["body"] == "Test body content"

    def test_parse_response_json_in_code_block(self):
        """Test parsing JSON wrapped in markdown code block."""
        composer = EmailComposer()

        response_text = """```json
{
  "subject": "Meeting Request",
  "body": "Dear Client,\\n\\nLet's meet.\\n\\nBest regards"
}
```"""

        result = composer._parse_llm_response(response_text)

        assert result["subject"] == "Meeting Request"
        assert "Dear Client" in result["body"]

    def test_parse_response_generic_code_block(self):
        """Test parsing JSON in generic code block."""
        composer = EmailComposer()

        response_text = """```
{
  "subject": "Update",
  "body": "Here is the update"
}
```"""

        result = composer._parse_llm_response(response_text)

        assert result["subject"] == "Update"
        assert result["body"] == "Here is the update"

    def test_parse_response_invalid_json(self):
        """Test parsing handles invalid JSON."""
        composer = EmailComposer()

        response_text = "Not valid JSON at all"

        with pytest.raises(ValueError) as exc_info:
            composer._parse_llm_response(response_text)

        assert "not valid JSON" in str(exc_info.value)

    def test_parse_response_missing_subject_field(self):
        """Test parsing handles missing subject field."""
        composer = EmailComposer()

        response_text = json.dumps({"body": "Only body here"})

        with pytest.raises(KeyError) as exc_info:
            composer._parse_llm_response(response_text)

        assert "subject" in str(exc_info.value)

    def test_parse_response_missing_body_field(self):
        """Test parsing handles missing body field."""
        composer = EmailComposer()

        response_text = json.dumps({"subject": "Only subject here"})

        with pytest.raises(KeyError) as exc_info:
            composer._parse_llm_response(response_text)

        assert "body" in str(exc_info.value)

    def test_parse_response_subject_not_string(self):
        """Test parsing handles non-string subject."""
        composer = EmailComposer()

        response_text = json.dumps({"subject": 123, "body": "Body text"})

        with pytest.raises(ValueError) as exc_info:
            composer._parse_llm_response(response_text)

        assert "Subject must be a string" in str(exc_info.value)

    def test_parse_response_body_not_string(self):
        """Test parsing handles non-string body."""
        composer = EmailComposer()

        response_text = json.dumps({"subject": "Subject", "body": ["list", "of", "items"]})

        with pytest.raises(ValueError) as exc_info:
            composer._parse_llm_response(response_text)

        assert "Body must be a string" in str(exc_info.value)

    def test_parse_response_empty_subject(self):
        """Test parsing handles empty subject."""
        composer = EmailComposer()

        response_text = json.dumps({"subject": "   ", "body": "Body text"})

        with pytest.raises(ValueError) as exc_info:
            composer._parse_llm_response(response_text)

        assert "Subject cannot be empty" in str(exc_info.value)

    def test_parse_response_empty_body(self):
        """Test parsing handles empty body."""
        composer = EmailComposer()

        response_text = json.dumps({"subject": "Subject", "body": "   "})

        with pytest.raises(ValueError) as exc_info:
            composer._parse_llm_response(response_text)

        assert "Body cannot be empty" in str(exc_info.value)

    def test_parse_response_strips_whitespace(self):
        """Test parsing strips leading/trailing whitespace."""
        composer = EmailComposer()

        response_text = json.dumps({
            "subject": "  Subject with spaces  ",
            "body": "  Body with spaces  "
        })

        result = composer._parse_llm_response(response_text)

        assert result["subject"] == "Subject with spaces"
        assert result["body"] == "Body with spaces"


class TestEmailComposerIntegration:
    """Integration-style tests for common usage scenarios."""

    @pytest.mark.asyncio
    async def test_typical_composition_workflow(self, mock_llm):
        """Test typical workflow of composing multiple emails."""
        # Setup mock responses
        response1 = Mock()
        response1.content = json.dumps({
            "subject": "Meeting Request",
            "body": "Dear Client,\n\nI'd like to schedule a meeting.\n\nBest regards"
        })

        response2 = Mock()
        response2.content = json.dumps({
            "subject": "Follow-up",
            "body": "Dear Client,\n\nFollowing up on my previous email.\n\nBest regards"
        })

        mock_llm.ainvoke = AsyncMock(side_effect=[response1, response2])

        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm):
            # Compose initial email
            email1 = await composer.compose_email(
                to_address="client@example.com",
                instructions="Request a meeting to discuss the project",
            )

            assert email1["subject"] == "Meeting Request"

            # Compose follow-up email
            email2 = await composer.compose_email(
                to_address="client@example.com",
                instructions="Follow up on the meeting request",
            )

            assert email2["subject"] == "Follow-up"

            # Both compositions should have called LLM
            assert mock_llm.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_compose_with_various_instructions(self, mock_llm):
        """Test composing emails with different instruction types."""
        responses = [
            Mock(content=json.dumps({"subject": "Information Request", "body": "Please provide..."})),
            Mock(content=json.dumps({"subject": "Status Update", "body": "Here is the update..."})),
            Mock(content=json.dumps({"subject": "Thank You", "body": "Thank you for..."})),
        ]

        mock_llm.ainvoke = AsyncMock(side_effect=responses)

        composer = EmailComposer()

        instructions = [
            "Request information about Q3 reports",
            "Provide status update on the project",
            "Thank the client for their cooperation",
        ]

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm):
            results = []
            for instruction in instructions:
                result = await composer.compose_email(
                    to_address="client@example.com",
                    instructions=instruction,
                )
                results.append(result)

            assert len(results) == 3
            assert results[0]["subject"] == "Information Request"
            assert results[1]["subject"] == "Status Update"
            assert results[2]["subject"] == "Thank You"

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, mock_llm):
        """Test handling errors and retrying with different inputs."""
        # First call fails
        mock_llm.ainvoke = AsyncMock(side_effect=[
            Exception("Temporary API error"),
            Mock(content=json.dumps({"subject": "Retry Success", "body": "Email body"}))
        ])

        composer = EmailComposer()

        with patch("info_agent.agents.mail.composer.get_gemini_llm", return_value=mock_llm):
            # First attempt fails
            with pytest.raises(LLMError):
                await composer.compose_email(
                    to_address="client@example.com",
                    instructions="Send email",
                )

            # Second attempt succeeds
            result = await composer.compose_email(
                to_address="client@example.com",
                instructions="Send email again",
            )

            assert result["subject"] == "Retry Success"
