"""
Unit tests for LLM provider factory.
"""

import os
from unittest.mock import patch

import pytest

from info_agent.config import LLMProvider, Settings, clear_settings_cache
from info_agent.llm import create_llm_provider, get_available_providers
from info_agent.llm.azure_provider import AzureOpenAIProvider
from info_agent.llm.gemini_provider import GeminiProvider
from info_agent.llm.openai_provider import OpenAIProvider
from info_agent.llm.openrouter_provider import OpenRouterProvider
from info_agent.utils.exceptions import LLMProviderNotFoundError


class TestGetAvailableProviders:
    """Tests for get_available_providers function."""

    def test_returns_all_providers(self) -> None:
        """Test all providers are returned."""
        providers = get_available_providers()

        assert "openai" in providers
        assert "azure_openai" in providers
        assert "gemini" in providers
        assert "openrouter" in providers

    def test_returns_list(self) -> None:
        """Test return type is list."""
        providers = get_available_providers()
        assert isinstance(providers, list)

    def test_correct_count(self) -> None:
        """Test correct number of providers."""
        providers = get_available_providers()
        assert len(providers) == 4


class TestCreateLLMProviderOpenAI:
    """Tests for creating OpenAI provider."""

    def test_create_openai_provider(self, test_env_vars: dict[str, str]) -> None:
        """Test creating OpenAI provider from settings."""
        with patch.dict(os.environ, test_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            provider = create_llm_provider(settings)

            assert isinstance(provider, OpenAIProvider)
            assert provider.provider_name == "openai"
            assert provider.model == "gpt-4-turbo"

    def test_openai_provider_missing_key_raises(self) -> None:
        """Test OpenAI provider raises error without API key."""
        env_vars = {
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "gpt-4",
            "OPENAI_API_KEY": "",  # Empty key
        }

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            # Settings validation should catch this
            with pytest.raises(Exception):
                Settings()


class TestCreateLLMProviderAzure:
    """Tests for creating Azure OpenAI provider."""

    def test_create_azure_provider(self, azure_env_vars: dict[str, str]) -> None:
        """Test creating Azure OpenAI provider from settings."""
        with patch.dict(os.environ, azure_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            provider = create_llm_provider(settings)

            assert isinstance(provider, AzureOpenAIProvider)
            assert provider.provider_name == "azure_openai"


class TestCreateLLMProviderGemini:
    """Tests for creating Gemini provider."""

    def test_create_gemini_provider(self, gemini_env_vars: dict[str, str]) -> None:
        """Test creating Gemini provider from settings."""
        with patch.dict(os.environ, gemini_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            provider = create_llm_provider(settings)

            assert isinstance(provider, GeminiProvider)
            assert provider.provider_name == "gemini"
            assert provider.model == "gemini-pro"


class TestCreateLLMProviderOpenRouter:
    """Tests for creating OpenRouter provider."""

    def test_create_openrouter_provider(
        self, openrouter_env_vars: dict[str, str]
    ) -> None:
        """Test creating OpenRouter provider from settings."""
        with patch.dict(os.environ, openrouter_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            provider = create_llm_provider(settings)

            assert isinstance(provider, OpenRouterProvider)
            assert provider.provider_name == "openrouter"
            assert provider.model == "anthropic/claude-3-opus"
