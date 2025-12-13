"""
Unit tests for configuration module.

Tests the Settings class, environment variable handling,
and LLM provider credential validation.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from info_agent.config import (
    LLMProvider,
    LogFormat,
    MissingConfigurationError,
    Settings,
    clear_settings_cache,
    get_settings,
)


class TestLLMProviderEnum:
    """Tests for LLMProvider enum."""

    def test_openai_value(self) -> None:
        """Test OpenAI provider value."""
        assert LLMProvider.OPENAI.value == "openai"

    def test_azure_value(self) -> None:
        """Test Azure OpenAI provider value."""
        assert LLMProvider.AZURE_OPENAI.value == "azure_openai"

    def test_gemini_value(self) -> None:
        """Test Gemini provider value."""
        assert LLMProvider.GEMINI.value == "gemini"

    def test_openrouter_value(self) -> None:
        """Test OpenRouter provider value."""
        assert LLMProvider.OPENROUTER.value == "openrouter"


class TestLogFormatEnum:
    """Tests for LogFormat enum."""

    def test_json_value(self) -> None:
        """Test JSON format value."""
        assert LogFormat.JSON.value == "json"

    def test_console_value(self) -> None:
        """Test console format value."""
        assert LogFormat.CONSOLE.value == "console"


class TestSettingsOpenAI:
    """Tests for Settings with OpenAI provider."""

    def test_valid_openai_settings(self, test_env_vars: dict[str, str]) -> None:
        """Test valid OpenAI configuration."""
        with patch.dict(os.environ, test_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            assert settings.llm_provider == LLMProvider.OPENAI
            assert settings.llm_model == "gpt-4-turbo"
            assert settings.openai_api_key == "test-openai-key"

    def test_missing_openai_api_key(self, test_env_vars: dict[str, str]) -> None:
        """Test OpenAI without API key raises error."""
        env_vars = {k: v for k, v in test_env_vars.items() if k != "OPENAI_API_KEY"}

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            with pytest.raises(MissingConfigurationError) as exc_info:
                Settings()

            assert "OPENAI_API_KEY" in str(exc_info.value)
            assert exc_info.value.field_name == "openai_api_key"


class TestSettingsAzure:
    """Tests for Settings with Azure OpenAI provider."""

    def test_valid_azure_settings(self, azure_env_vars: dict[str, str]) -> None:
        """Test valid Azure OpenAI configuration."""
        with patch.dict(os.environ, azure_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            assert settings.llm_provider == LLMProvider.AZURE_OPENAI
            assert settings.azure_openai_api_key == "test-azure-key"
            assert settings.azure_openai_endpoint == "https://test.openai.azure.com/"
            assert settings.azure_openai_deployment_name == "gpt-4-deployment"

    def test_missing_azure_endpoint(self, azure_env_vars: dict[str, str]) -> None:
        """Test Azure without endpoint raises error."""
        env_vars = {k: v for k, v in azure_env_vars.items() if k != "AZURE_OPENAI_ENDPOINT"}

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            with pytest.raises(MissingConfigurationError) as exc_info:
                Settings()

            assert "AZURE_OPENAI_ENDPOINT" in str(exc_info.value)

    def test_missing_azure_deployment_name(self, azure_env_vars: dict[str, str]) -> None:
        """Test Azure without deployment name raises error."""
        env_vars = {
            k: v for k, v in azure_env_vars.items() if k != "AZURE_OPENAI_DEPLOYMENT_NAME"
        }

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            with pytest.raises(MissingConfigurationError) as exc_info:
                Settings()

            assert "AZURE_OPENAI_DEPLOYMENT_NAME" in str(exc_info.value)


class TestSettingsGemini:
    """Tests for Settings with Gemini provider."""

    def test_valid_gemini_settings(self, gemini_env_vars: dict[str, str]) -> None:
        """Test valid Gemini configuration."""
        with patch.dict(os.environ, gemini_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            assert settings.llm_provider == LLMProvider.GEMINI
            assert settings.google_api_key == "test-google-key"

    def test_missing_google_api_key(self, gemini_env_vars: dict[str, str]) -> None:
        """Test Gemini without API key raises error."""
        env_vars = {k: v for k, v in gemini_env_vars.items() if k != "GOOGLE_API_KEY"}

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            with pytest.raises(MissingConfigurationError) as exc_info:
                Settings()

            assert "GOOGLE_API_KEY" in str(exc_info.value)


class TestSettingsOpenRouter:
    """Tests for Settings with OpenRouter provider."""

    def test_valid_openrouter_settings(self, openrouter_env_vars: dict[str, str]) -> None:
        """Test valid OpenRouter configuration."""
        with patch.dict(os.environ, openrouter_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            assert settings.llm_provider == LLMProvider.OPENROUTER
            assert settings.openrouter_api_key == "test-openrouter-key"

    def test_missing_openrouter_api_key(self, openrouter_env_vars: dict[str, str]) -> None:
        """Test OpenRouter without API key raises error."""
        env_vars = {k: v for k, v in openrouter_env_vars.items() if k != "OPENROUTER_API_KEY"}

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            with pytest.raises(MissingConfigurationError) as exc_info:
                Settings()

            assert "OPENROUTER_API_KEY" in str(exc_info.value)


class TestSettingsValidation:
    """Tests for Settings validation."""

    def test_missing_llm_provider_raises_error(self) -> None:
        """Test missing LLM provider raises ValidationError."""
        env_vars = {"LLM_MODEL": "gpt-4", "OPENAI_API_KEY": "test-key"}

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            with pytest.raises(ValidationError):
                Settings()

    def test_missing_llm_model_raises_error(self, test_env_vars: dict[str, str]) -> None:
        """Test missing LLM model raises ValidationError."""
        env_vars = {k: v for k, v in test_env_vars.items() if k != "LLM_MODEL"}

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            with pytest.raises(ValidationError):
                Settings()

    def test_invalid_log_level_raises_error(self, test_env_vars: dict[str, str]) -> None:
        """Test invalid log level raises error."""
        env_vars = {**test_env_vars, "LOG_LEVEL": "INVALID"}

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            with pytest.raises(MissingConfigurationError) as exc_info:
                Settings()

            assert "log_level" in str(exc_info.value)

    def test_valid_log_levels(self, test_env_vars: dict[str, str]) -> None:
        """Test all valid log levels are accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            env_vars = {**test_env_vars, "LOG_LEVEL": level}

            with patch.dict(os.environ, env_vars, clear=True):
                clear_settings_cache()
                settings = Settings()
                assert settings.log_level == level

    def test_log_level_case_insensitive(self, test_env_vars: dict[str, str]) -> None:
        """Test log level is case insensitive."""
        env_vars = {**test_env_vars, "LOG_LEVEL": "debug"}

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()
            assert settings.log_level == "DEBUG"

    def test_invalid_port_raises_error(self, test_env_vars: dict[str, str]) -> None:
        """Test invalid port raises ValidationError."""
        env_vars = {**test_env_vars, "GATEWAY_PORT": "99999"}

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            with pytest.raises(ValidationError):
                Settings()


class TestSettingsComputedProperties:
    """Tests for Settings computed properties."""

    def test_allowed_origins_list(self, test_env_vars: dict[str, str]) -> None:
        """Test allowed_origins_list property."""
        env_vars = {
            **test_env_vars,
            "ALLOWED_ORIGINS": "http://localhost:8000, http://localhost:3000",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            origins = settings.allowed_origins_list
            assert len(origins) == 2
            assert "http://localhost:8000" in origins
            assert "http://localhost:3000" in origins

    def test_gateway_url(self, test_env_vars: dict[str, str]) -> None:
        """Test gateway_url property."""
        with patch.dict(os.environ, test_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            assert settings.gateway_url == "http://127.0.0.1:8000"

    def test_mail_agent_url(self, test_env_vars: dict[str, str]) -> None:
        """Test mail_agent_url property."""
        with patch.dict(os.environ, test_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            assert "8002" in settings.mail_agent_url

    def test_validation_agent_url(self, test_env_vars: dict[str, str]) -> None:
        """Test validation_agent_url property."""
        with patch.dict(os.environ, test_env_vars, clear=True):
            clear_settings_cache()
            settings = Settings()

            assert "8003" in settings.validation_agent_url


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_caching(self, test_env_vars: dict[str, str]) -> None:
        """Test get_settings returns cached instance."""
        with patch.dict(os.environ, test_env_vars, clear=True):
            clear_settings_cache()

            settings1 = get_settings()
            settings2 = get_settings()

            assert settings1 is settings2

    def test_clear_settings_cache(self, test_env_vars: dict[str, str]) -> None:
        """Test clear_settings_cache clears the cache."""
        with patch.dict(os.environ, test_env_vars, clear=True):
            clear_settings_cache()

            settings1 = get_settings()
            clear_settings_cache()
            settings2 = get_settings()

            # Different instances after cache clear
            assert settings1 is not settings2


class TestMissingConfigurationError:
    """Tests for MissingConfigurationError."""

    def test_error_message(self) -> None:
        """Test error message format."""
        error = MissingConfigurationError("api_key", "API key is required")

        assert error.field_name == "api_key"
        assert error.message == "API key is required"
        assert "api_key" in str(error)
        assert "API key is required" in str(error)

    def test_error_inheritance(self) -> None:
        """Test MissingConfigurationError is an Exception."""
        error = MissingConfigurationError("field", "message")
        assert isinstance(error, Exception)
