"""
Unit tests for Mail Agent.

Tests the MailAgent class with mocked dependencies (SMTP, LLM, A2A).
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from info_agent.agents.mail.agent import MailAgent
from info_agent.config import Settings
from info_agent.utils.exceptions import A2AError, EmailError, ValidationError


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=Settings)
    settings.smtp_host = "smtp.test.com"
    settings.smtp_port = 25
    settings.a2a_registry_url = "http://registry:8000"
    settings.mail_agent_host = "localhost"
    settings.mail_agent_port = 8001
    settings.get_mail_agent_url = Mock(return_value="http://localhost:8001")
    return settings


class TestMailAgentInit:
    """Tests for MailAgent initialization."""

    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    def test_init_success(self, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test successful agent initialization."""
        agent = MailAgent(mock_settings)

        assert agent.settings == mock_settings
        assert agent.smtp_client is not None
        assert agent.composer is not None
        assert agent.parser is not None
        assert agent.app is not None
        assert agent.agent_card is not None

        # Verify SMTP client created with correct params
        mock_smtp_class.assert_called_once_with(
            host="smtp.test.com",
            port=25,
        )

    @patch("info_agent.agents.mail.agent.SMTPClient")
    def test_init_missing_settings(self, mock_smtp_class):
        """Test initialization fails with missing settings."""
        with pytest.raises(ValidationError) as exc_info:
            MailAgent(None)  # type: ignore

        assert "Settings are required" in str(exc_info.value)

    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    def test_agent_card_creation(self, mock_parser, mock_composer, mock_smtp, mock_settings):
        """Test agent card is created correctly."""
        agent = MailAgent(mock_settings)

        assert agent.agent_card.name == "mail-agent"
        assert agent.agent_card.version == "1.0.0"
        assert len(agent.agent_card.skills) == 2

        skill_ids = [skill.id for skill in agent.agent_card.skills]
        assert "send-email" in skill_ids
        assert "receive-email-webhook" in skill_ids


class TestMailAgentHandleSendEmail:
    """Tests for MailAgent._handle_send_email method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    async def test_handle_send_email_success(self, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test successful send-email handling."""
        # Setup mocks
        mock_composer = Mock()
        mock_composer.compose_email = AsyncMock(return_value={
            "subject": "Meeting Request",
            "body": "Dear Client,\n\nLet's meet.\n\nBest regards"
        })
        mock_composer_class.return_value = mock_composer

        mock_smtp = Mock()
        mock_smtp.send_email = AsyncMock(return_value="<msg-123@smtp.test.com>")
        mock_smtp_class.return_value = mock_smtp

        agent = MailAgent(mock_settings)

        payload = {
            "to_address": "client@example.com",
            "instructions": "Request a meeting",
        }

        result = await agent._handle_send_email(payload)

        assert result["message_id"] == "<msg-123@smtp.test.com>"
        assert result["to_address"] == "client@example.com"
        assert result["subject"] == "Meeting Request"
        assert "Dear Client" in result["body_preview"]
        assert "sent_at" in result

        # Verify composer was called
        mock_composer.compose_email.assert_called_once()

        # Verify SMTP was called
        mock_smtp.send_email.assert_called_once()

    @pytest.mark.asyncio
    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    async def test_handle_send_email_missing_to_address(self, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test send-email fails with missing to_address."""
        agent = MailAgent(mock_settings)

        payload = {
            "instructions": "Send email",
        }

        with pytest.raises(ValidationError) as exc_info:
            await agent._handle_send_email(payload)

        assert "to_address" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    async def test_handle_send_email_missing_instructions(self, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test send-email fails with missing instructions."""
        agent = MailAgent(mock_settings)

        payload = {
            "to_address": "client@example.com",
        }

        with pytest.raises(ValidationError) as exc_info:
            await agent._handle_send_email(payload)

        assert "instructions" in str(exc_info.value)


class TestMailAgentHandleReceiveWebhook:
    """Tests for MailAgent._handle_receive_email_webhook method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    async def test_handle_webhook_success(self, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test successful webhook handling."""
        # Setup mock parser
        mock_parser = Mock()
        mock_parser.parse_email = AsyncMock(return_value={
            "intent": "meeting_request",
            "key_points": ["Meeting", "Next week"],
            "action_items": ["Confirm"],
            "requires_response": True,
            "sentiment": "positive",
            "important_dates": ["Next week"],
            "contact_info": [],
            "summary": "Meeting request"
        })
        mock_parser_class.return_value = mock_parser

        agent = MailAgent(mock_settings)

        payload = {
            "event": "email.received",
            "message_id": "msg-webhook-123",
            "from_address": "client@example.com",
            "to_address": "agent@example.com",
            "subject": "Meeting Request",
            "body": "Let's meet next week",
            "received_at": "2025-12-13T10:00:00Z",
        }

        result = await agent._handle_receive_email_webhook(payload)

        assert result["message_id"] == "msg-webhook-123"
        assert result["from_address"] == "client@example.com"
        assert result["subject"] == "Meeting Request"
        assert result["parsed_data"]["intent"] == "meeting_request"
        assert "processed_at" in result

        # Verify parser was called
        mock_parser.parse_email.assert_called_once()

    @pytest.mark.asyncio
    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    async def test_handle_webhook_missing_required_field(self, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test webhook fails with missing required field."""
        agent = MailAgent(mock_settings)

        payload = {
            "event": "email.received",
            # missing message_id
            "from_address": "client@example.com",
            "to_address": "agent@example.com",
            "subject": "Test",
            "body": "Body",
            "received_at": "2025-12-13T10:00:00Z",
        }

        with pytest.raises(ValidationError) as exc_info:
            await agent._handle_receive_email_webhook(payload)

        assert "message_id" in str(exc_info.value)


class TestMailAgentHandleTask:
    """Tests for MailAgent.handle_task method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    async def test_handle_task_send_email_skill(self, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test handle_task routes send-email correctly."""
        from info_agent.a2a.models import A2ATaskRequest

        # Setup mocks
        mock_composer = Mock()
        mock_composer.compose_email = AsyncMock(return_value={
            "subject": "Test",
            "body": "Body"
        })
        mock_composer_class.return_value = mock_composer

        mock_smtp = Mock()
        mock_smtp.send_email = AsyncMock(return_value="<msg-123@test.com>")
        mock_smtp_class.return_value = mock_smtp

        agent = MailAgent(mock_settings)

        request = A2ATaskRequest(
            task_id="task-123",
            skill_id="send-email",
            payload={
                "to_address": "client@example.com",
                "instructions": "Send email",
            }
        )

        response = await agent.handle_task(request)

        assert response.task_id == "task-123"
        assert response.status == "completed"
        assert response.result is not None
        assert response.error is None

    @pytest.mark.asyncio
    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    async def test_handle_task_unsupported_skill(self, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test handle_task handles unsupported skill."""
        from info_agent.a2a.models import A2ATaskRequest

        agent = MailAgent(mock_settings)

        request = A2ATaskRequest(
            task_id="task-456",
            skill_id="unsupported-skill",
            payload={"data": "test"}  # Payload cannot be empty
        )

        response = await agent.handle_task(request)

        assert response.task_id == "task-456"
        assert response.status == "failed"
        assert response.error is not None
        assert "Unsupported skill" in response.error


class TestMailAgentStart:
    """Tests for MailAgent.start method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    @patch("info_agent.agents.mail.agent.httpx.AsyncClient")
    async def test_start_success(self, mock_httpx, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test successful agent start and registration."""
        # Setup SMTP mock
        mock_smtp = Mock()
        mock_smtp.test_connection = AsyncMock(return_value=True)
        mock_smtp_class.return_value = mock_smtp

        # Setup HTTP mock for registration
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"status": "registered", "agent_name": "mail-agent"})

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_httpx.return_value = mock_client

        agent = MailAgent(mock_settings)

        await agent.start()

        # Verify SMTP test was attempted
        mock_smtp.test_connection.assert_called_once()

        # Verify registration was called
        mock_client.post.assert_called_once()


class TestMailAgentShutdown:
    """Tests for MailAgent.shutdown method."""

    @pytest.mark.asyncio
    @patch("info_agent.agents.mail.agent.SMTPClient")
    @patch("info_agent.agents.mail.agent.EmailComposer")
    @patch("info_agent.agents.mail.agent.EmailParser")
    async def test_shutdown_with_active_tasks(self, mock_parser_class, mock_composer_class, mock_smtp_class, mock_settings):
        """Test shutdown cancels active tasks."""
        agent = MailAgent(mock_settings)

        # Add some active tasks
        agent._active_tasks["task-1"] = {
            "task_id": "task-1",
            "skill_id": "send-email",
            "status": "working",
            "email_task": {},
            "result": None,
            "error": None,
            "payload": None,
        }

        agent._active_tasks["task-2"] = {
            "task_id": "task-2",
            "skill_id": "send-email",
            "status": "submitted",
            "email_task": {},
            "result": None,
            "error": None,
            "payload": None,
        }

        await agent.shutdown()

        # Verify tasks were cancelled
        assert agent._active_tasks["task-1"]["status"] == "cancelled"
        assert agent._active_tasks["task-2"]["status"] == "cancelled"
