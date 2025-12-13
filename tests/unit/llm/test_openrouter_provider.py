"""
Unit tests for OpenRouter provider.
"""

from unittest.mock import MagicMock, patch

import pytest

from info_agent.llm.openrouter_provider import OPENROUTER_BASE_URL, OpenRouterProvider
from info_agent.utils.exceptions import LLMError, LLMProviderNotFoundError


class TestOpenRouterProviderInit:
    """Tests for OpenRouter provider initialization."""

    def test_valid_initialization(self) -> None:
        """Test provider initializes with valid API key."""
        provider = OpenRouterProvider(
            api_key="sk-or-test-key",
            model="anthropic/claude-3-opus",
        )

        assert provider.model == "anthropic/claude-3-opus"
        assert provider.provider_name == "openrouter"

    def test_missing_api_key_raises(self) -> None:
        """Test missing API key raises error."""
        with pytest.raises(LLMProviderNotFoundError) as exc_info:
            OpenRouterProvider(api_key="", model="anthropic/claude-3-opus")

        assert "OpenRouter API key is required" in str(exc_info.value)
        assert exc_info.value.details["provider"] == "openrouter"

    def test_repr(self) -> None:
        """Test string representation."""
        provider = OpenRouterProvider(
            api_key="sk-or-test", model="google/gemini-pro"
        )
        assert "OpenRouterProvider" in repr(provider)
        assert "google/gemini-pro" in repr(provider)


class TestOpenRouterProviderGetChatModel:
    """Tests for get_chat_model method."""

    def test_get_chat_model_uses_openrouter_base_url(self) -> None:
        """Test chat model uses OpenRouter base URL."""
        provider = OpenRouterProvider(
            api_key="sk-or-test", model="anthropic/claude-3-opus"
        )

        with patch("info_agent.llm.openrouter_provider.ChatOpenAI") as mock_chat:
            mock_chat.return_value = MagicMock()

            provider.get_chat_model()

            call_kwargs = mock_chat.call_args.kwargs
            assert call_kwargs["base_url"] == OPENROUTER_BASE_URL

    def test_get_chat_model_includes_headers(self) -> None:
        """Test chat model includes OpenRouter-specific headers."""
        provider = OpenRouterProvider(
            api_key="sk-or-test", model="anthropic/claude-3-opus"
        )

        with patch("info_agent.llm.openrouter_provider.ChatOpenAI") as mock_chat:
            mock_chat.return_value = MagicMock()

            provider.get_chat_model()

            call_kwargs = mock_chat.call_args.kwargs
            headers = call_kwargs.get("default_headers", {})
            assert "HTTP-Referer" in headers
            assert "X-Title" in headers

    def test_get_chat_model_custom_args(self) -> None:
        """Test getting chat model with custom arguments."""
        provider = OpenRouterProvider(
            api_key="sk-or-test", model="openai/gpt-4-turbo"
        )

        with patch("info_agent.llm.openrouter_provider.ChatOpenAI") as mock_chat:
            mock_chat.return_value = MagicMock()

            provider.get_chat_model(
                temperature=0.8,
                max_tokens=4000,
                streaming=False,
            )

            call_kwargs = mock_chat.call_args.kwargs
            assert call_kwargs["temperature"] == 0.8
            assert call_kwargs["max_tokens"] == 4000
            assert call_kwargs["streaming"] is False

    def test_get_chat_model_exception_handling(self) -> None:
        """Test exception handling in get_chat_model."""
        provider = OpenRouterProvider(
            api_key="sk-or-test", model="invalid/model"
        )

        with patch("info_agent.llm.openrouter_provider.ChatOpenAI") as mock_chat:
            mock_chat.side_effect = Exception("Invalid model")

            with pytest.raises(LLMError) as exc_info:
                provider.get_chat_model()

            assert "Failed to create OpenRouter chat model" in str(exc_info.value)


class TestOpenRouterProviderValidation:
    """Tests for validate_connection method."""

    def test_validate_connection_success(self) -> None:
        """Test successful connection validation."""
        provider = OpenRouterProvider(
            api_key="sk-or-test", model="anthropic/claude-3-opus"
        )

        with patch.object(provider, "get_chat_model") as mock_get:
            mock_get.return_value = MagicMock()

            result = provider.validate_connection()

            assert result is True

    def test_validate_connection_failure(self) -> None:
        """Test failed connection validation."""
        provider = OpenRouterProvider(
            api_key="sk-or-test", model="anthropic/claude-3-opus"
        )

        with patch.object(provider, "get_chat_model") as mock_get:
            mock_get.side_effect = Exception("Invalid credentials")

            with pytest.raises(LLMError) as exc_info:
                provider.validate_connection()

            assert "validation failed" in str(exc_info.value)


class TestOpenRouterBaseURL:
    """Tests for OpenRouter base URL constant."""

    def test_base_url_format(self) -> None:
        """Test base URL is correctly formatted."""
        assert OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"
        assert OPENROUTER_BASE_URL.startswith("https://")
