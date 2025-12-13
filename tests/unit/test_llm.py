"""
Unit tests for the LLM module.

Tests the GeminiProvider class and factory functions with mocking
to avoid actual API calls during testing.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

from info_agent.config import Settings
from info_agent.llm import (
    GeminiProvider,
    get_gemini_llm,
    is_llm_initialized,
    reset_llm_instance,
)
from info_agent.utils.exceptions import LLMError


@pytest.fixture(autouse=True)
def reset_llm_singleton():
    """Reset LLM singleton before and after each test."""
    reset_llm_instance()
    yield
    reset_llm_instance()


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=Settings)
    settings.google_api_key = "test-api-key-123456789"
    settings.llm_model = "gemini-2.5-flash"
    settings.llm_temperature = 0.7
    settings.llm_max_tokens = 4096
    return settings


@pytest.fixture
def mock_chat_model():
    """Create a mock ChatGoogleGenerativeAI instance."""
    mock = MagicMock()
    mock.ainvoke = MagicMock(return_value="test response")
    return mock


class TestGeminiProvider:
    """Tests for the GeminiProvider class."""

    def test_init_success(self, mock_settings):
        """Test successful provider initialization."""
        provider = GeminiProvider(mock_settings)

        assert provider.api_key == "test-api-key-123456789"
        assert provider.model == "gemini-2.5-flash"
        assert provider.temperature == 0.7
        assert provider.max_tokens == 4096
        assert provider._client is None  # Lazy initialization

    def test_init_missing_api_key(self, mock_settings):
        """Test initialization fails with missing API key."""
        mock_settings.google_api_key = ""

        with pytest.raises(LLMError) as exc_info:
            GeminiProvider(mock_settings)

        assert "GOOGLE_API_KEY is required" in str(exc_info.value)
        assert exc_info.value.code == "LLM_ERROR"

    def test_init_missing_model(self, mock_settings):
        """Test initialization fails with missing model."""
        mock_settings.llm_model = ""

        with pytest.raises(LLMError) as exc_info:
            GeminiProvider(mock_settings)

        assert "LLM_MODEL is required" in str(exc_info.value)
        assert exc_info.value.code == "LLM_ERROR"

    @patch("info_agent.llm.gemini_provider.ChatGoogleGenerativeAI")
    def test_get_chat_model_lazy_initialization(
        self, mock_chat_class, mock_settings, mock_chat_model
    ):
        """Test lazy initialization of chat model."""
        mock_chat_class.return_value = mock_chat_model

        provider = GeminiProvider(mock_settings)
        assert provider._client is None

        # First call creates the client
        result = provider.get_chat_model()

        assert result == mock_chat_model
        assert provider._client is not None
        mock_chat_class.assert_called_once_with(
            google_api_key="test-api-key-123456789",
            model="gemini-2.5-flash",
            temperature=0.7,
            max_output_tokens=4096,
        )

        # Second call reuses the cached client
        mock_chat_class.reset_mock()
        result2 = provider.get_chat_model()

        assert result2 == mock_chat_model
        mock_chat_class.assert_not_called()  # Should use cached instance

    @patch("info_agent.llm.gemini_provider.ChatGoogleGenerativeAI")
    def test_get_chat_model_with_overrides(
        self, mock_chat_class, mock_settings, mock_chat_model
    ):
        """Test getting chat model with override parameters."""
        mock_chat_class.return_value = mock_chat_model

        provider = GeminiProvider(mock_settings)

        # Get model with custom temperature
        provider.get_chat_model(temperature=0.9, max_tokens=2048)

        mock_chat_class.assert_called_once_with(
            google_api_key="test-api-key-123456789",
            model="gemini-2.5-flash",
            temperature=0.9,
            max_output_tokens=2048,
        )

    @patch("info_agent.llm.gemini_provider.ChatGoogleGenerativeAI")
    def test_get_chat_model_creation_failure(self, mock_chat_class, mock_settings):
        """Test error handling when client creation fails."""
        mock_chat_class.side_effect = Exception("API connection failed")

        provider = GeminiProvider(mock_settings)

        with pytest.raises(LLMError) as exc_info:
            provider.get_chat_model()

        assert "Failed to create Gemini client" in str(exc_info.value)
        assert exc_info.value.code == "LLM_ERROR"
        assert exc_info.value.model == "gemini-2.5-flash"
        assert exc_info.value.original_error is not None

    @patch("info_agent.llm.gemini_provider.ChatGoogleGenerativeAI")
    def test_reset(self, mock_chat_class, mock_settings, mock_chat_model):
        """Test resetting the provider clears cached client."""
        mock_chat_class.return_value = mock_chat_model

        provider = GeminiProvider(mock_settings)

        # Create client
        provider.get_chat_model()
        assert provider._client is not None

        # Reset
        provider.reset()
        assert provider._client is None


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_is_llm_initialized_initially_false(self):
        """Test that LLM is not initialized initially."""
        assert is_llm_initialized() is False

    @patch("info_agent.llm.factory.get_settings")
    @patch("info_agent.llm.gemini_provider.ChatGoogleGenerativeAI")
    def test_get_gemini_llm_creates_singleton(
        self, mock_chat_class, mock_get_settings, mock_settings, mock_chat_model
    ):
        """Test that get_gemini_llm creates and returns singleton."""
        mock_get_settings.return_value = mock_settings
        mock_chat_class.return_value = mock_chat_model

        # First call creates instance
        assert is_llm_initialized() is False
        llm1 = get_gemini_llm()

        assert llm1 == mock_chat_model
        assert is_llm_initialized() is True

        # Second call reuses singleton
        llm2 = get_gemini_llm()
        assert llm2 == mock_chat_model

        # Settings should only be called once
        mock_get_settings.assert_called_once()

    @patch("info_agent.llm.factory.get_settings")
    @patch("info_agent.llm.gemini_provider.ChatGoogleGenerativeAI")
    def test_get_gemini_llm_with_overrides(
        self, mock_chat_class, mock_get_settings, mock_settings, mock_chat_model
    ):
        """Test get_gemini_llm with override parameters."""
        mock_get_settings.return_value = mock_settings
        mock_chat_class.return_value = mock_chat_model

        llm = get_gemini_llm(temperature=0.9)

        assert llm == mock_chat_model
        # Verify that override was passed through
        # (checked in provider tests)

    @patch("info_agent.llm.factory.get_settings")
    def test_get_gemini_llm_initialization_failure(self, mock_get_settings):
        """Test error handling when provider initialization fails."""
        mock_get_settings.side_effect = Exception("Settings load failed")

        with pytest.raises(LLMError) as exc_info:
            get_gemini_llm()

        assert "Failed to initialize LLM provider" in str(exc_info.value)
        assert exc_info.value.code == "LLM_ERROR"

    @patch("info_agent.llm.factory.get_settings")
    @patch("info_agent.llm.gemini_provider.ChatGoogleGenerativeAI")
    def test_reset_llm_instance(
        self, mock_chat_class, mock_get_settings, mock_settings, mock_chat_model
    ):
        """Test reset_llm_instance clears singleton."""
        mock_get_settings.return_value = mock_settings
        mock_chat_class.return_value = mock_chat_model

        # Create singleton
        get_gemini_llm()
        assert is_llm_initialized() is True

        # Reset
        reset_llm_instance()
        assert is_llm_initialized() is False

        # Next call creates new instance
        get_gemini_llm()
        assert is_llm_initialized() is True

    def test_reset_llm_instance_when_not_initialized(self):
        """Test reset_llm_instance when no instance exists."""
        assert is_llm_initialized() is False

        # Should not raise error
        reset_llm_instance()

        assert is_llm_initialized() is False


class TestIntegrationScenarios:
    """Integration-style tests for common usage scenarios."""

    @patch("info_agent.llm.factory.get_settings")
    @patch("info_agent.llm.gemini_provider.ChatGoogleGenerativeAI")
    def test_typical_usage_flow(
        self, mock_chat_class, mock_get_settings, mock_settings, mock_chat_model
    ):
        """Test typical usage flow of getting and using LLM."""
        mock_get_settings.return_value = mock_settings
        mock_chat_class.return_value = mock_chat_model

        # Application startup - nothing initialized
        assert is_llm_initialized() is False

        # First request uses LLM
        llm = get_gemini_llm()
        assert llm == mock_chat_model
        assert is_llm_initialized() is True

        # Subsequent requests reuse instance
        llm2 = get_gemini_llm()
        assert llm2 == llm

        # Test shutdown
        reset_llm_instance()
        assert is_llm_initialized() is False

    @patch("info_agent.llm.factory.get_settings")
    @patch("info_agent.llm.gemini_provider.ChatGoogleGenerativeAI")
    def test_different_temperature_per_request(
        self, mock_chat_class, mock_get_settings, mock_settings, mock_chat_model
    ):
        """Test using different temperatures for different requests."""
        mock_get_settings.return_value = mock_settings
        mock_chat_class.return_value = mock_chat_model

        # Creative task with high temperature
        llm_creative = get_gemini_llm(temperature=0.9)
        assert llm_creative == mock_chat_model

        # Analytical task with low temperature
        llm_analytical = get_gemini_llm(temperature=0.1)
        assert llm_analytical == mock_chat_model

        # Default temperature
        llm_default = get_gemini_llm()
        assert llm_default == mock_chat_model
