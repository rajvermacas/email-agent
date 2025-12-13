"""
Unit tests for Gemini provider.
"""

from unittest.mock import MagicMock, patch

import pytest

from info_agent.llm.gemini_provider import GeminiProvider
from info_agent.utils.exceptions import LLMError, LLMProviderNotFoundError


class TestGeminiProviderInit:
    """Tests for Gemini provider initialization."""

    def test_valid_initialization(self) -> None:
        """Test provider initializes with valid API key."""
        provider = GeminiProvider(
            api_key="test-google-key",
            model="gemini-pro",
        )

        assert provider.model == "gemini-pro"
        assert provider.provider_name == "gemini"

    def test_missing_api_key_raises(self) -> None:
        """Test missing API key raises error."""
        with pytest.raises(LLMProviderNotFoundError) as exc_info:
            GeminiProvider(api_key="", model="gemini-pro")

        assert "Google API key is required" in str(exc_info.value)
        assert exc_info.value.details["provider"] == "gemini"

    def test_repr(self) -> None:
        """Test string representation."""
        provider = GeminiProvider(api_key="test-key", model="gemini-1.5-pro")
        assert "GeminiProvider" in repr(provider)
        assert "gemini-1.5-pro" in repr(provider)


class TestGeminiProviderGetChatModel:
    """Tests for get_chat_model method."""

    def test_get_chat_model_default_args(self) -> None:
        """Test getting chat model with default arguments."""
        provider = GeminiProvider(api_key="test-key", model="gemini-pro")

        with patch(
            "info_agent.llm.gemini_provider.ChatGoogleGenerativeAI"
        ) as mock_chat:
            mock_chat.return_value = MagicMock()

            model = provider.get_chat_model()

            assert model is not None
            mock_chat.assert_called_once()

            call_kwargs = mock_chat.call_args.kwargs
            assert call_kwargs["model"] == "gemini-pro"
            assert call_kwargs["temperature"] == 0.0

    def test_get_chat_model_custom_args(self) -> None:
        """Test getting chat model with custom arguments."""
        provider = GeminiProvider(api_key="test-key", model="gemini-1.5-flash")

        with patch(
            "info_agent.llm.gemini_provider.ChatGoogleGenerativeAI"
        ) as mock_chat:
            mock_chat.return_value = MagicMock()

            provider.get_chat_model(
                temperature=0.5,
                max_tokens=2000,
            )

            call_kwargs = mock_chat.call_args.kwargs
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_output_tokens"] == 2000

    def test_get_chat_model_exception_handling(self) -> None:
        """Test exception handling in get_chat_model."""
        provider = GeminiProvider(api_key="test-key", model="gemini-pro")

        with patch(
            "info_agent.llm.gemini_provider.ChatGoogleGenerativeAI"
        ) as mock_chat:
            mock_chat.side_effect = Exception("Invalid API key")

            with pytest.raises(LLMError) as exc_info:
                provider.get_chat_model()

            assert "Failed to create Gemini chat model" in str(exc_info.value)


class TestGeminiProviderValidation:
    """Tests for validate_connection method."""

    def test_validate_connection_success(self) -> None:
        """Test successful connection validation."""
        provider = GeminiProvider(api_key="test-key", model="gemini-pro")

        with patch.object(provider, "get_chat_model") as mock_get:
            mock_get.return_value = MagicMock()

            result = provider.validate_connection()

            assert result is True

    def test_validate_connection_failure(self) -> None:
        """Test failed connection validation."""
        provider = GeminiProvider(api_key="test-key", model="gemini-pro")

        with patch.object(provider, "get_chat_model") as mock_get:
            mock_get.side_effect = Exception("API error")

            with pytest.raises(LLMError) as exc_info:
                provider.validate_connection()

            assert "validation failed" in str(exc_info.value)
