"""
Unit tests for OpenAI provider.
"""

from unittest.mock import MagicMock, patch

import pytest

from info_agent.llm.openai_provider import OpenAIProvider
from info_agent.utils.exceptions import LLMError, LLMProviderNotFoundError


class TestOpenAIProviderInit:
    """Tests for OpenAI provider initialization."""

    def test_valid_initialization(self) -> None:
        """Test provider initializes with valid API key."""
        provider = OpenAIProvider(
            api_key="sk-test-key-12345",
            model="gpt-4-turbo",
        )

        assert provider.model == "gpt-4-turbo"
        assert provider.provider_name == "openai"

    def test_missing_api_key_raises(self) -> None:
        """Test missing API key raises error."""
        with pytest.raises(LLMProviderNotFoundError) as exc_info:
            OpenAIProvider(api_key="", model="gpt-4")

        assert "OpenAI API key is required" in str(exc_info.value)
        assert exc_info.value.details["provider"] == "openai"

    def test_repr(self) -> None:
        """Test string representation."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4")
        assert "OpenAIProvider" in repr(provider)
        assert "gpt-4" in repr(provider)


class TestOpenAIProviderGetChatModel:
    """Tests for get_chat_model method."""

    def test_get_chat_model_default_args(self) -> None:
        """Test getting chat model with default arguments."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4-turbo")

        with patch("info_agent.llm.openai_provider.ChatOpenAI") as mock_chat:
            mock_chat.return_value = MagicMock()

            model = provider.get_chat_model()

            assert model is not None
            mock_chat.assert_called_once()

            call_kwargs = mock_chat.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4-turbo"
            assert call_kwargs["temperature"] == 0.0
            assert call_kwargs["streaming"] is True

    def test_get_chat_model_custom_args(self) -> None:
        """Test getting chat model with custom arguments."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4")

        with patch("info_agent.llm.openai_provider.ChatOpenAI") as mock_chat:
            mock_chat.return_value = MagicMock()

            provider.get_chat_model(
                temperature=0.7,
                max_tokens=1000,
                streaming=False,
            )

            call_kwargs = mock_chat.call_args.kwargs
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 1000
            assert call_kwargs["streaming"] is False

    def test_get_chat_model_exception_handling(self) -> None:
        """Test exception handling in get_chat_model."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4")

        with patch("info_agent.llm.openai_provider.ChatOpenAI") as mock_chat:
            mock_chat.side_effect = Exception("Connection error")

            with pytest.raises(LLMError) as exc_info:
                provider.get_chat_model()

            assert "Failed to create OpenAI chat model" in str(exc_info.value)
            assert exc_info.value.details["provider"] == "openai"


class TestOpenAIProviderValidation:
    """Tests for validate_connection method."""

    def test_validate_connection_success(self) -> None:
        """Test successful connection validation."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4")

        with patch.object(provider, "get_chat_model") as mock_get:
            mock_get.return_value = MagicMock()

            result = provider.validate_connection()

            assert result is True

    def test_validate_connection_failure(self) -> None:
        """Test failed connection validation."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4")

        with patch.object(provider, "get_chat_model") as mock_get:
            mock_get.side_effect = Exception("API error")

            with pytest.raises(LLMError) as exc_info:
                provider.validate_connection()

            assert "validation failed" in str(exc_info.value)
