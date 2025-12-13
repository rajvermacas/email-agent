"""
Unit tests for Azure OpenAI provider.
"""

from unittest.mock import MagicMock, patch

import pytest

from info_agent.llm.azure_provider import AzureOpenAIProvider
from info_agent.utils.exceptions import LLMError, LLMProviderNotFoundError


class TestAzureProviderInit:
    """Tests for Azure OpenAI provider initialization."""

    def test_valid_initialization(self) -> None:
        """Test provider initializes with all required parameters."""
        provider = AzureOpenAIProvider(
            api_key="test-azure-key",
            endpoint="https://test.openai.azure.com/",
            deployment_name="gpt-4-deployment",
            model="gpt-4",
        )

        assert provider.model == "gpt-4"
        assert provider.provider_name == "azure_openai"

    def test_missing_api_key_raises(self) -> None:
        """Test missing API key raises error."""
        with pytest.raises(LLMProviderNotFoundError) as exc_info:
            AzureOpenAIProvider(
                api_key="",
                endpoint="https://test.openai.azure.com/",
                deployment_name="gpt-4",
                model="gpt-4",
            )

        assert "api_key" in str(exc_info.value)

    def test_missing_endpoint_raises(self) -> None:
        """Test missing endpoint raises error."""
        with pytest.raises(LLMProviderNotFoundError) as exc_info:
            AzureOpenAIProvider(
                api_key="test-key",
                endpoint="",
                deployment_name="gpt-4",
                model="gpt-4",
            )

        assert "endpoint" in str(exc_info.value)

    def test_missing_deployment_raises(self) -> None:
        """Test missing deployment name raises error."""
        with pytest.raises(LLMProviderNotFoundError) as exc_info:
            AzureOpenAIProvider(
                api_key="test-key",
                endpoint="https://test.openai.azure.com/",
                deployment_name="",
                model="gpt-4",
            )

        assert "deployment_name" in str(exc_info.value)

    def test_multiple_missing_params(self) -> None:
        """Test multiple missing parameters are reported."""
        with pytest.raises(LLMProviderNotFoundError) as exc_info:
            AzureOpenAIProvider(
                api_key="",
                endpoint="",
                deployment_name="",
                model="gpt-4",
            )

        error_msg = str(exc_info.value)
        assert "api_key" in error_msg
        assert "endpoint" in error_msg
        assert "deployment_name" in error_msg


class TestAzureProviderGetChatModel:
    """Tests for get_chat_model method."""

    def test_get_chat_model_default_args(self) -> None:
        """Test getting chat model with default arguments."""
        provider = AzureOpenAIProvider(
            api_key="test-key",
            endpoint="https://test.openai.azure.com/",
            deployment_name="gpt-4-deployment",
            model="gpt-4",
        )

        with patch("info_agent.llm.azure_provider.AzureChatOpenAI") as mock_chat:
            mock_chat.return_value = MagicMock()

            model = provider.get_chat_model()

            assert model is not None
            mock_chat.assert_called_once()

            call_kwargs = mock_chat.call_args.kwargs
            assert call_kwargs["azure_deployment"] == "gpt-4-deployment"
            assert call_kwargs["azure_endpoint"] == "https://test.openai.azure.com/"

    def test_get_chat_model_with_api_version(self) -> None:
        """Test chat model uses specified API version."""
        provider = AzureOpenAIProvider(
            api_key="test-key",
            endpoint="https://test.openai.azure.com/",
            deployment_name="gpt-4",
            model="gpt-4",
            api_version="2024-05-01",
        )

        with patch("info_agent.llm.azure_provider.AzureChatOpenAI") as mock_chat:
            mock_chat.return_value = MagicMock()

            provider.get_chat_model()

            call_kwargs = mock_chat.call_args.kwargs
            assert call_kwargs["api_version"] == "2024-05-01"


class TestAzureProviderValidation:
    """Tests for validate_connection method."""

    def test_validate_connection_success(self) -> None:
        """Test successful connection validation."""
        provider = AzureOpenAIProvider(
            api_key="test-key",
            endpoint="https://test.openai.azure.com/",
            deployment_name="gpt-4",
            model="gpt-4",
        )

        with patch.object(provider, "get_chat_model") as mock_get:
            mock_get.return_value = MagicMock()

            result = provider.validate_connection()

            assert result is True

    def test_validate_connection_failure(self) -> None:
        """Test failed connection validation."""
        provider = AzureOpenAIProvider(
            api_key="test-key",
            endpoint="https://test.openai.azure.com/",
            deployment_name="gpt-4",
            model="gpt-4",
        )

        with patch.object(provider, "get_chat_model") as mock_get:
            mock_get.side_effect = Exception("Authentication failed")

            with pytest.raises(LLMError) as exc_info:
                provider.validate_connection()

            assert "validation failed" in str(exc_info.value)
