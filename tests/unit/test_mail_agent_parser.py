"""
Unit tests for Email Parser.

Tests the EmailParser class with mocked LLM to avoid
actual API calls during testing.
"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

from info_agent.agents.mail.parser import EmailParser
from info_agent.utils.exceptions import LLMError, ValidationError


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response with parsed email data."""
    response = Mock()
    response.content = json.dumps({
        "intent": "meeting_request",
        "key_points": ["Meeting next Tuesday", "Project discussion", "2 PM time slot"],
        "action_items": ["Confirm availability", "Prepare project update"],
        "requires_response": True,
        "sentiment": "positive",
        "important_dates": ["Next Tuesday 2 PM"],
        "contact_info": [],
        "summary": "Client requesting meeting next Tuesday at 2 PM to discuss project progress"
    })
    return response


@pytest.fixture
def mock_llm():
    """Create a mock LLM instance."""
    llm = AsyncMock()
    return llm


class TestEmailParserInit:
    """Tests for EmailParser initialization."""

    def test_init_success(self):
        """Test successful parser initialization."""
        parser = EmailParser()

        assert parser is not None
        assert parser.SYSTEM_PROMPT is not None
        assert "email analysis assistant" in parser.SYSTEM_PROMPT.lower()

    def test_system_prompt_content(self):
        """Test system prompt contains required analysis fields."""
        parser = EmailParser()

        required_fields = [
            "intent",
            "key_points",
            "action_items",
            "requires_response",
            "sentiment",
            "important_dates",
            "contact_info",
            "summary",
        ]

        for field in required_fields:
            assert field.lower() in parser.SYSTEM_PROMPT.lower()


class TestEmailParserParseEmail:
    """Tests for EmailParser.parse_email method."""

    @pytest.mark.asyncio
    async def test_parse_email_success(self, mock_llm, mock_llm_response):
        """Test successful email parsing."""
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        parser = EmailParser()

        with patch("info_agent.agents.mail.parser.get_gemini_llm", return_value=mock_llm):
            result = await parser.parse_email(
                from_address="client@example.com",
                subject="Meeting Request",
                body="Hi, I'd like to schedule a meeting next Tuesday at 2 PM to discuss the project.",
            )

            assert result["intent"] == "meeting_request"
            assert result["requires_response"] is True
            assert result["sentiment"] == "positive"
            assert len(result["key_points"]) == 3
            assert len(result["action_items"]) == 2
            assert "Next Tuesday 2 PM" in result["important_dates"]

            # Verify LLM was called
            mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_email_missing_from_address(self):
        """Test parsing fails when from_address is missing."""
        parser = EmailParser()

        with pytest.raises(ValidationError) as exc_info:
            await parser.parse_email(
                from_address="",
                subject="Test",
                body="Body",
            )

        assert "Sender address (from_address) is required" in str(exc_info.value)
        assert exc_info.value.field == "from_address"

    @pytest.mark.asyncio
    async def test_parse_email_missing_subject(self):
        """Test parsing fails when subject is missing."""
        parser = EmailParser()

        with pytest.raises(ValidationError) as exc_info:
            await parser.parse_email(
                from_address="sender@example.com",
                subject="",
                body="Body",
            )

        assert "Email subject is required" in str(exc_info.value)
        assert exc_info.value.field == "subject"

    @pytest.mark.asyncio
    async def test_parse_email_missing_body(self):
        """Test parsing fails when body is missing."""
        parser = EmailParser()

        with pytest.raises(ValidationError) as exc_info:
            await parser.parse_email(
                from_address="sender@example.com",
                subject="Test",
                body="",
            )

        assert "Email body is required" in str(exc_info.value)
        assert exc_info.value.field == "body"

    @pytest.mark.asyncio
    async def test_parse_email_whitespace_body(self):
        """Test parsing fails when body is only whitespace."""
        parser = EmailParser()

        with pytest.raises(ValidationError) as exc_info:
            await parser.parse_email(
                from_address="sender@example.com",
                subject="Test",
                body="   \n\t  ",
            )

        assert "Email body cannot be empty or whitespace" in str(exc_info.value)
        assert exc_info.value.field == "body"

    @pytest.mark.asyncio
    async def test_parse_email_llm_initialization_failure(self):
        """Test parsing handles LLM initialization failure."""
        parser = EmailParser()

        with patch("info_agent.agents.mail.parser.get_gemini_llm") as mock_get_llm:
            mock_get_llm.side_effect = Exception("API key not found")

            with pytest.raises(LLMError) as exc_info:
                await parser.parse_email(
                    from_address="sender@example.com",
                    subject="Test",
                    body="Body",
                )

            assert "Failed to initialize LLM for email parsing" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_email_llm_invocation_failure(self, mock_llm):
        """Test parsing handles LLM invocation failure."""
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API timeout"))

        parser = EmailParser()

        with patch("info_agent.agents.mail.parser.get_gemini_llm", return_value=mock_llm):
            with pytest.raises(LLMError) as exc_info:
                await parser.parse_email(
                    from_address="sender@example.com",
                    subject="Test",
                    body="Body",
                )

            assert "Failed to parse email content" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_email_invalid_json_response(self, mock_llm):
        """Test parsing handles invalid JSON in LLM response."""
        invalid_response = Mock()
        invalid_response.content = "This is not valid JSON"

        mock_llm.ainvoke = AsyncMock(return_value=invalid_response)

        parser = EmailParser()

        with patch("info_agent.agents.mail.parser.get_gemini_llm", return_value=mock_llm):
            with pytest.raises(LLMError) as exc_info:
                await parser.parse_email(
                    from_address="sender@example.com",
                    subject="Test",
                    body="Body",
                )

            assert "Failed to parse LLM output" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_parse_email_with_lower_temperature(self, mock_llm, mock_llm_response):
        """Test parsing uses lower temperature for consistency."""
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        parser = EmailParser()

        with patch("info_agent.agents.mail.parser.get_gemini_llm", return_value=mock_llm) as mock_get_llm:
            await parser.parse_email(
                from_address="sender@example.com",
                subject="Test",
                body="Body",
            )

            # Verify temperature was passed (should be lower for parsing)
            mock_get_llm.assert_called_once_with(temperature=0.3)


class TestEmailParserBuildUserPrompt:
    """Tests for EmailParser._build_user_prompt method."""

    def test_build_user_prompt_complete(self):
        """Test building complete user prompt."""
        parser = EmailParser()

        prompt = parser._build_user_prompt(
            from_address="sender@example.com",
            subject="Meeting Request",
            body="I'd like to schedule a meeting next week.",
        )

        assert "sender@example.com" in prompt
        assert "Meeting Request" in prompt
        assert "I'd like to schedule a meeting next week." in prompt
        assert "Analyze this email" in prompt

    def test_build_user_prompt_structure(self):
        """Test user prompt has correct structure."""
        parser = EmailParser()

        prompt = parser._build_user_prompt(
            from_address="client@example.com",
            subject="Test Subject",
            body="Test body",
        )

        assert "From:" in prompt
        assert "Subject:" in prompt
        assert "Body:" in prompt


class TestEmailParserParseResponse:
    """Tests for EmailParser._parse_llm_response method."""

    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        parser = EmailParser()

        response_text = json.dumps({
            "intent": "information_query",
            "key_points": ["Request for data"],
            "action_items": ["Provide data"],
            "requires_response": True,
            "sentiment": "neutral",
            "important_dates": [],
            "contact_info": [],
            "summary": "User requesting data"
        })

        result = parser._parse_llm_response(response_text)

        assert result["intent"] == "information_query"
        assert result["requires_response"] is True
        assert result["sentiment"] == "neutral"

    def test_parse_response_json_in_code_block(self):
        """Test parsing JSON wrapped in markdown code block."""
        parser = EmailParser()

        response_text = """```json
{
  "intent": "meeting_request",
  "key_points": ["Meeting"],
  "action_items": [],
  "requires_response": true,
  "sentiment": "positive",
  "important_dates": ["Tomorrow"],
  "contact_info": [],
  "summary": "Meeting request"
}
```"""

        result = parser._parse_llm_response(response_text)

        assert result["intent"] == "meeting_request"
        assert "Tomorrow" in result["important_dates"]

    def test_parse_response_generic_code_block(self):
        """Test parsing JSON in generic code block."""
        parser = EmailParser()

        response_text = """```
{
  "intent": "complaint",
  "key_points": ["Issue"],
  "action_items": ["Fix issue"],
  "requires_response": true,
  "sentiment": "negative",
  "important_dates": [],
  "contact_info": [],
  "summary": "Customer complaint"
}
```"""

        result = parser._parse_llm_response(response_text)

        assert result["intent"] == "complaint"
        assert result["sentiment"] == "negative"

    def test_parse_response_invalid_json(self):
        """Test parsing handles invalid JSON."""
        parser = EmailParser()

        response_text = "Not valid JSON at all"

        with pytest.raises(ValueError) as exc_info:
            parser._parse_llm_response(response_text)

        assert "not valid JSON" in str(exc_info.value)


class TestEmailParserValidateParsedData:
    """Tests for EmailParser._validate_parsed_data method."""

    def test_validate_complete_data(self):
        """Test validation passes with complete data."""
        parser = EmailParser()

        data = {
            "intent": "meeting_request",
            "key_points": ["Point 1"],
            "action_items": ["Action 1"],
            "requires_response": True,
            "sentiment": "positive",
            "important_dates": ["Tomorrow"],
            "contact_info": [],
            "summary": "Summary text"
        }

        # Should not raise exception
        parser._validate_parsed_data(data)

    def test_validate_missing_intent(self):
        """Test validation fails when intent is missing."""
        parser = EmailParser()

        data = {
            "key_points": [],
            "action_items": [],
            "requires_response": True,
            "sentiment": "neutral",
            "important_dates": [],
            "contact_info": [],
            "summary": "Summary"
        }

        with pytest.raises(KeyError) as exc_info:
            parser._validate_parsed_data(data)

        assert "intent" in str(exc_info.value)

    def test_validate_missing_key_points(self):
        """Test validation fails when key_points is missing."""
        parser = EmailParser()

        data = {
            "intent": "query",
            "action_items": [],
            "requires_response": True,
            "sentiment": "neutral",
            "important_dates": [],
            "contact_info": [],
            "summary": "Summary"
        }

        with pytest.raises(KeyError) as exc_info:
            parser._validate_parsed_data(data)

        assert "key_points" in str(exc_info.value)

    def test_validate_intent_not_string(self):
        """Test validation fails when intent is not a string."""
        parser = EmailParser()

        data = {
            "intent": 123,
            "key_points": [],
            "action_items": [],
            "requires_response": True,
            "sentiment": "neutral",
            "important_dates": [],
            "contact_info": [],
            "summary": "Summary"
        }

        with pytest.raises(ValueError) as exc_info:
            parser._validate_parsed_data(data)

        assert "Intent must be a string" in str(exc_info.value)

    def test_validate_key_points_not_list(self):
        """Test validation fails when key_points is not a list."""
        parser = EmailParser()

        data = {
            "intent": "query",
            "key_points": "not a list",
            "action_items": [],
            "requires_response": True,
            "sentiment": "neutral",
            "important_dates": [],
            "contact_info": [],
            "summary": "Summary"
        }

        with pytest.raises(ValueError) as exc_info:
            parser._validate_parsed_data(data)

        assert "Key points must be a list" in str(exc_info.value)

    def test_validate_requires_response_not_boolean(self):
        """Test validation fails when requires_response is not boolean."""
        parser = EmailParser()

        data = {
            "intent": "query",
            "key_points": [],
            "action_items": [],
            "requires_response": "yes",
            "sentiment": "neutral",
            "important_dates": [],
            "contact_info": [],
            "summary": "Summary"
        }

        with pytest.raises(ValueError) as exc_info:
            parser._validate_parsed_data(data)

        assert "Requires response must be a boolean" in str(exc_info.value)

    def test_validate_empty_intent(self):
        """Test validation fails when intent is empty."""
        parser = EmailParser()

        data = {
            "intent": "   ",
            "key_points": [],
            "action_items": [],
            "requires_response": True,
            "sentiment": "neutral",
            "important_dates": [],
            "contact_info": [],
            "summary": "Summary"
        }

        with pytest.raises(ValueError) as exc_info:
            parser._validate_parsed_data(data)

        assert "Intent cannot be empty" in str(exc_info.value)

    def test_validate_empty_summary(self):
        """Test validation fails when summary is empty."""
        parser = EmailParser()

        data = {
            "intent": "query",
            "key_points": [],
            "action_items": [],
            "requires_response": True,
            "sentiment": "neutral",
            "important_dates": [],
            "contact_info": [],
            "summary": "   "
        }

        with pytest.raises(ValueError) as exc_info:
            parser._validate_parsed_data(data)

        assert "Summary cannot be empty" in str(exc_info.value)


class TestEmailParserIntegration:
    """Integration-style tests for common usage scenarios."""

    @pytest.mark.asyncio
    async def test_parse_meeting_request_email(self, mock_llm):
        """Test parsing a typical meeting request email."""
        response = Mock()
        response.content = json.dumps({
            "intent": "meeting_request",
            "key_points": ["Meeting next Tuesday", "Discuss Q4 goals", "2 PM preferred time"],
            "action_items": ["Confirm availability", "Send calendar invite"],
            "requires_response": True,
            "sentiment": "positive",
            "important_dates": ["Next Tuesday 2 PM"],
            "contact_info": [],
            "summary": "Client requesting meeting next Tuesday at 2 PM to discuss Q4 goals"
        })

        mock_llm.ainvoke = AsyncMock(return_value=response)

        parser = EmailParser()

        with patch("info_agent.agents.mail.parser.get_gemini_llm", return_value=mock_llm):
            result = await parser.parse_email(
                from_address="client@example.com",
                subject="Meeting Request - Q4 Goals",
                body="Hi, I'd like to schedule a meeting next Tuesday at 2 PM to discuss our Q4 goals. Please let me know if this works for you.",
            )

            assert result["intent"] == "meeting_request"
            assert result["requires_response"] is True
            assert len(result["key_points"]) == 3
            assert len(result["action_items"]) == 2

    @pytest.mark.asyncio
    async def test_parse_complaint_email(self, mock_llm):
        """Test parsing a complaint email."""
        response = Mock()
        response.content = json.dumps({
            "intent": "complaint",
            "key_points": ["Service delay", "Missing features", "Poor support"],
            "action_items": ["Address delays", "Improve support response time"],
            "requires_response": True,
            "sentiment": "negative",
            "important_dates": [],
            "contact_info": ["+1-555-0123"],
            "summary": "Customer complaining about service delays and poor support"
        })

        mock_llm.ainvoke = AsyncMock(return_value=response)

        parser = EmailParser()

        with patch("info_agent.agents.mail.parser.get_gemini_llm", return_value=mock_llm):
            result = await parser.parse_email(
                from_address="unhappy@example.com",
                subject="Service Issues",
                body="I'm very disappointed with the service delays and lack of support. Please call me at +1-555-0123 to discuss.",
            )

            assert result["intent"] == "complaint"
            assert result["sentiment"] == "negative"
            assert result["requires_response"] is True
            assert "+1-555-0123" in result["contact_info"]

    @pytest.mark.asyncio
    async def test_parse_information_query(self, mock_llm):
        """Test parsing an information query email."""
        response = Mock()
        response.content = json.dumps({
            "intent": "information_query",
            "key_points": ["Request for Q3 reports", "Financial data needed"],
            "action_items": ["Provide Q3 financial reports"],
            "requires_response": True,
            "sentiment": "neutral",
            "important_dates": ["By end of week"],
            "contact_info": [],
            "summary": "Request for Q3 financial reports needed by end of week"
        })

        mock_llm.ainvoke = AsyncMock(return_value=response)

        parser = EmailParser()

        with patch("info_agent.agents.mail.parser.get_gemini_llm", return_value=mock_llm):
            result = await parser.parse_email(
                from_address="manager@example.com",
                subject="Q3 Reports Request",
                body="Could you please send me the Q3 financial reports by the end of this week?",
            )

            assert result["intent"] == "information_query"
            assert result["sentiment"] == "neutral"
            assert "Provide Q3 financial reports" in result["action_items"]

    @pytest.mark.asyncio
    async def test_parse_thank_you_email(self, mock_llm):
        """Test parsing a thank you email."""
        response = Mock()
        response.content = json.dumps({
            "intent": "thank_you",
            "key_points": ["Appreciation for help", "Project success"],
            "action_items": [],
            "requires_response": False,
            "sentiment": "positive",
            "important_dates": [],
            "contact_info": [],
            "summary": "Client thanking for help with successful project completion"
        })

        mock_llm.ainvoke = AsyncMock(return_value=response)

        parser = EmailParser()

        with patch("info_agent.agents.mail.parser.get_gemini_llm", return_value=mock_llm):
            result = await parser.parse_email(
                from_address="client@example.com",
                subject="Thank You!",
                body="Thank you so much for your help. The project was a great success!",
            )

            assert result["intent"] == "thank_you"
            assert result["sentiment"] == "positive"
            assert result["requires_response"] is False
            assert len(result["action_items"]) == 0
