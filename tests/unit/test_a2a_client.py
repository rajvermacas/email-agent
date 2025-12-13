"""
Unit tests for A2A client module.

Tests the A2AClient class from src/info_agent/a2a/client.py including:
- Client initialization
- send_task method with various scenarios
- get_agent_card method with various scenarios
- Error handling (timeout, network errors, HTTP errors)

All tests use mocked httpx to avoid actual network requests.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
import httpx

from info_agent.a2a.client import A2AClient
from info_agent.a2a.models import AgentCard, AgentSkill
from info_agent.utils.exceptions import A2AError, AgentCommunicationError


class TestA2AClientInit:
    """Tests for A2AClient initialization."""

    def test_init_with_http_url(self):
        """Test initialization with HTTP URL."""
        client = A2AClient(base_url="http://localhost:8001/a2a")

        assert client.base_url == "http://localhost:8001/a2a"
        assert client.timeout == 30.0

    def test_init_with_https_url(self):
        """Test initialization with HTTPS URL."""
        client = A2AClient(base_url="https://api.example.com/a2a")

        assert client.base_url == "https://api.example.com/a2a"
        assert client.timeout == 30.0

    def test_init_with_trailing_slash(self):
        """Test initialization strips trailing slash from URL."""
        client = A2AClient(base_url="http://localhost:8001/a2a/")

        assert client.base_url == "http://localhost:8001/a2a"

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        client = A2AClient(base_url="http://localhost:8001/a2a", timeout=60.0)

        assert client.timeout == 60.0

    def test_init_with_explicit_none_timeout(self):
        """Test initialization with explicit None timeout uses default."""
        client = A2AClient(base_url="http://localhost:8001/a2a", timeout=None)

        assert client.timeout == 30.0

    def test_init_fails_with_empty_url(self):
        """Test initialization fails with empty URL."""
        with pytest.raises(A2AError) as exc_info:
            A2AClient(base_url="")

        assert "base_url is required" in exc_info.value.message
        assert exc_info.value.code == "A2A_ERROR"

    def test_init_fails_with_invalid_url_scheme(self):
        """Test initialization fails with invalid URL scheme."""
        with pytest.raises(A2AError) as exc_info:
            A2AClient(base_url="ftp://example.com/a2a")

        assert "must start with http:// or https://" in exc_info.value.message
        assert exc_info.value.code == "A2A_ERROR"

    def test_init_fails_with_no_scheme(self):
        """Test initialization fails with URL without scheme."""
        with pytest.raises(A2AError) as exc_info:
            A2AClient(base_url="localhost:8001/a2a")

        assert "must start with http:// or https://" in exc_info.value.message

    def test_default_timeout_constant(self):
        """Test DEFAULT_TIMEOUT constant value."""
        assert A2AClient.DEFAULT_TIMEOUT == 30.0

    def test_agent_card_path_constant(self):
        """Test AGENT_CARD_PATH constant value."""
        assert A2AClient.AGENT_CARD_PATH == "/.well-known/agent.json"


class TestA2AClientSendTask:
    """Tests for send_task method."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_send_task_success(self, mock_client_class):
        """Test sending a task successfully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "task-123",
            "status": "completed",
            "result": {"converted_amount": 92.0, "rate": 0.92},
        }

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")
        result = await client.send_task(
            agent_name="currency-agent",
            skill_id="convert_currency",
            payload={"amount": 100, "from": "USD", "to": "EUR"},
        )

        assert result["task_id"] == "task-123"
        assert result["status"] == "completed"
        assert result["result"]["converted_amount"] == 92.0

        # Verify HTTP request
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8001/a2a/tasks"
        assert call_args[1]["json"]["skill"] == "convert_currency"
        assert call_args[1]["json"]["input"] == {"amount": 100, "from": "USD", "to": "EUR"}
        assert call_args[1]["json"]["blocking"] is True

    @pytest.mark.asyncio
    async def test_send_task_fails_with_empty_agent_name(self):
        """Test that send_task raises A2AError with empty agent_name."""
        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(A2AError) as exc_info:
            await client.send_task(
                agent_name="",
                skill_id="convert_currency",
                payload={"amount": 100},
            )

        assert "agent_name is required" in exc_info.value.message
        assert exc_info.value.code == "A2A_ERROR"

    @pytest.mark.asyncio
    async def test_send_task_fails_with_empty_skill_id(self):
        """Test that send_task raises A2AError with empty skill_id."""
        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(A2AError) as exc_info:
            await client.send_task(
                agent_name="currency-agent",
                skill_id="",
                payload={"amount": 100},
            )

        assert "skill_id is required" in exc_info.value.message
        assert exc_info.value.code == "A2A_ERROR"

    @pytest.mark.asyncio
    async def test_send_task_fails_with_empty_payload(self):
        """Test that send_task raises A2AError with empty payload."""
        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(A2AError) as exc_info:
            await client.send_task(
                agent_name="currency-agent",
                skill_id="convert_currency",
                payload={},
            )

        assert "payload is required and cannot be empty" in exc_info.value.message
        assert exc_info.value.code == "A2A_ERROR"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_send_task_http_400_error(self, mock_client_class):
        """Test handling of HTTP 400 error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request: invalid payload"

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.send_task(
                agent_name="currency-agent",
                skill_id="convert_currency",
                payload={"amount": 100},
            )

        assert "HTTP 400" in exc_info.value.message
        assert exc_info.value.agent_name == "currency-agent"
        assert exc_info.value.code == "AGENT_COMMUNICATION_ERROR"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_send_task_http_500_error(self, mock_client_class):
        """Test handling of HTTP 500 error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.send_task(
                agent_name="currency-agent",
                skill_id="convert_currency",
                payload={"amount": 100},
            )

        assert "HTTP 500" in exc_info.value.message
        assert exc_info.value.agent_name == "currency-agent"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_send_task_timeout_error(self, mock_client_class):
        """Test handling of timeout error."""
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a", timeout=5.0)

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.send_task(
                agent_name="currency-agent",
                skill_id="convert_currency",
                payload={"amount": 100},
            )

        assert "timed out" in exc_info.value.message
        assert exc_info.value.agent_name == "currency-agent"
        assert "timeout" in exc_info.value.details

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_send_task_network_error(self, mock_client_class):
        """Test handling of network error."""
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(
            side_effect=httpx.NetworkError("Connection refused")
        )
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.send_task(
                agent_name="currency-agent",
                skill_id="convert_currency",
                payload={"amount": 100},
            )

        assert "Network error" in exc_info.value.message
        assert exc_info.value.agent_name == "currency-agent"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_send_task_generic_http_error(self, mock_client_class):
        """Test handling of generic HTTP error."""
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(
            side_effect=httpx.HTTPError("Generic HTTP error")
        )
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.send_task(
                agent_name="currency-agent",
                skill_id="convert_currency",
                payload={"amount": 100},
            )

        assert "HTTP error" in exc_info.value.message
        assert exc_info.value.agent_name == "currency-agent"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_send_task_unexpected_error(self, mock_client_class):
        """Test handling of unexpected error."""
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=ValueError("Unexpected error"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.send_task(
                agent_name="currency-agent",
                skill_id="convert_currency",
                payload={"amount": 100},
            )

        assert "Unexpected error" in exc_info.value.message
        assert exc_info.value.agent_name == "currency-agent"
        assert "error_type" in exc_info.value.details

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_send_task_uses_custom_timeout(self, mock_client_class):
        """Test that send_task uses the custom timeout."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"task_id": "task-123", "status": "completed", "result": {}}

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a", timeout=60.0)
        await client.send_task(
            agent_name="currency-agent",
            skill_id="convert_currency",
            payload={"amount": 100},
        )

        # Verify AsyncClient was created with correct timeout
        mock_client_class.assert_called_once_with(timeout=60.0)


class TestA2AClientGetAgentCard:
    """Tests for get_agent_card method."""

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_success(self, mock_client_class):
        """Test getting agent card successfully."""
        card_data = {
            "name": "currency-agent",
            "description": "Currency conversion agent",
            "version": "1.0.0",
            "url": "http://localhost:8001/a2a",
            "capabilities": {"async": True},
            "skills": [
                {
                    "id": "convert",
                    "name": "Convert",
                    "description": "Convert currency",
                    "input_schema": {"type": "object"},
                }
            ],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = card_data

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")
        agent_card = await client.get_agent_card()

        assert isinstance(agent_card, AgentCard)
        assert agent_card.name == "currency-agent"
        assert agent_card.version == "1.0.0"
        assert len(agent_card.skills) == 1

        # Verify HTTP request
        mock_http_client.get.assert_called_once_with(
            "http://localhost:8001/a2a/.well-known/agent.json"
        )

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_with_custom_url(self, mock_client_class):
        """Test getting agent card from custom URL."""
        card_data = {
            "name": "custom-agent",
            "description": "Custom agent",
            "version": "1.0.0",
            "url": "http://custom:8002/a2a",
            "capabilities": {},
            "skills": [
                {
                    "id": "skill1",
                    "name": "Skill 1",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                }
            ],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = card_data

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")
        agent_card = await client.get_agent_card(agent_url="http://custom:8002/a2a")

        assert agent_card.name == "custom-agent"

        # Verify correct URL was used
        mock_http_client.get.assert_called_once_with(
            "http://custom:8002/a2a/.well-known/agent.json"
        )

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_http_404_error(self, mock_client_class):
        """Test handling of HTTP 404 error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not found"

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.get_agent_card()

        assert "Failed to retrieve agent card" in exc_info.value.message
        assert exc_info.value.code == "AGENT_COMMUNICATION_ERROR"

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_missing_required_fields(self, mock_client_class):
        """Test handling of agent card with missing required fields."""
        incomplete_card_data = {
            "name": "incomplete-agent",
            "description": "Missing fields",
            # Missing version, url, capabilities, skills, etc.
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = incomplete_card_data

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(A2AError) as exc_info:
            await client.get_agent_card()

        assert "missing fields" in exc_info.value.message
        assert "missing_fields" in exc_info.value.details

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_invalid_format(self, mock_client_class):
        """Test handling of agent card with invalid format."""
        invalid_card_data = {
            "name": "invalid-agent",
            "description": "Invalid agent",
            "version": "1.0.0",
            "url": "http://localhost:8001/a2a",
            "capabilities": {},
            "skills": [
                {
                    "id": "skill1",
                    "name": "Skill 1",
                    "description": "Test",
                    # Missing input_schema - will fail validation
                }
            ],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = invalid_card_data

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(A2AError) as exc_info:
            await client.get_agent_card()

        assert "Invalid agent card format" in exc_info.value.message

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_timeout_error(self, mock_client_class):
        """Test handling of timeout error."""
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a", timeout=5.0)

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.get_agent_card()

        assert "timed out" in exc_info.value.message
        assert "timeout" in exc_info.value.details

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_network_error(self, mock_client_class):
        """Test handling of network error."""
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(
            side_effect=httpx.NetworkError("Connection refused")
        )
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.get_agent_card()

        assert "Network error" in exc_info.value.message

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_generic_http_error(self, mock_client_class):
        """Test handling of generic HTTP error."""
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(side_effect=httpx.HTTPError("Generic HTTP error"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.get_agent_card()

        assert "HTTP error" in exc_info.value.message

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_unexpected_error(self, mock_client_class):
        """Test handling of unexpected error."""
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(side_effect=ValueError("Unexpected error"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")

        with pytest.raises(AgentCommunicationError) as exc_info:
            await client.get_agent_card()

        assert "Unexpected error" in exc_info.value.message
        assert "error_type" in exc_info.value.details

    @pytest.mark.asyncio
    @patch("info_agent.a2a.client.httpx.AsyncClient")
    async def test_get_agent_card_strips_trailing_slash(self, mock_client_class):
        """Test that get_agent_card handles URLs with trailing slashes."""
        card_data = {
            "name": "test-agent",
            "description": "Test agent",
            "version": "1.0.0",
            "url": "http://localhost:8001/a2a",
            "capabilities": {},
            "skills": [
                {
                    "id": "skill1",
                    "name": "Skill 1",
                    "description": "Test",
                    "input_schema": {"type": "object"},
                }
            ],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = card_data

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_http_client

        client = A2AClient(base_url="http://localhost:8001/a2a")
        await client.get_agent_card(agent_url="http://custom:8002/a2a/")

        # Verify trailing slash was stripped
        mock_http_client.get.assert_called_once_with(
            "http://custom:8002/a2a/.well-known/agent.json"
        )
