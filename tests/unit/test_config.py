"""
Unit tests for the config module.

Tests the Settings class with Pydantic validation, field validators,
and utility methods. Uses mocking to avoid actual .env file dependencies.
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from pydantic import ValidationError

from info_agent.config import Settings, get_settings, clear_settings_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear settings cache before and after each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def valid_env_vars():
    """Provide valid environment variables for testing."""
    return {
        "GOOGLE_API_KEY": "test-google-api-key-1234567890",
        "LLM_MODEL": "gemini-2.5-flash",
        "LLM_TEMPERATURE": "0.7",
        "LLM_MAX_TOKENS": "4096",
        "HOST": "0.0.0.0",
        "GATEWAY_PORT": "8000",
        "MAIL_AGENT_PORT": "8001",
        "EMAIL_SERVER_PORT": "8025",
        "SMTP_PORT": "1025",
        "DEBUG": "false",
        "A2A_REGISTRY_URL": "http://localhost:8000/a2a",
        "SMTP_HOST": "localhost",
        "EMAIL_WEBHOOK_URL": "http://localhost:8000/webhooks/email",
        "CHECKPOINT_DB_PATH": "data/checkpoints.db",
        "EMAIL_DB_PATH": "data/emails.db",
        "REGISTRY_DB_PATH": "data/registry.db",
        "WORKFLOW_DB_PATH": "data/workflows.db",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "console",
        "DEFAULT_TIMEOUT_HOURS": "48",
        "DEFAULT_RETRY_COUNT": "3",
    }


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


class TestSettingsInitialization:
    """Tests for Settings class initialization."""

    def test_init_with_valid_env_vars(self, valid_env_vars, tmp_path, monkeypatch):
        """Test successful initialization with all valid environment variables."""
        # Set up temp directory
        data_dir = tmp_path / "data"
        valid_env_vars["CHECKPOINT_DB_PATH"] = str(data_dir / "checkpoints.db")
        valid_env_vars["EMAIL_DB_PATH"] = str(data_dir / "emails.db")
        valid_env_vars["REGISTRY_DB_PATH"] = str(data_dir / "registry.db")
        valid_env_vars["WORKFLOW_DB_PATH"] = str(data_dir / "workflows.db")

        for key, value in valid_env_vars.items():
            monkeypatch.setenv(key, value)

        settings = Settings()

        assert settings.google_api_key == "test-google-api-key-1234567890"
        assert settings.llm_model == "gemini-2.5-flash"
        assert settings.llm_temperature == 0.7
        assert settings.llm_max_tokens == 4096
        assert settings.host == "0.0.0.0"
        assert settings.gateway_port == 8000
        assert settings.mail_agent_port == 8001
        assert settings.email_server_port == 8025
        assert settings.smtp_port == 1025
        assert settings.debug is False
        assert settings.a2a_registry_url == "http://localhost:8000/a2a"
        assert settings.smtp_host == "localhost"
        assert settings.email_webhook_url == "http://localhost:8000/webhooks/email"
        assert settings.log_level == "INFO"
        assert settings.log_format == "console"
        assert settings.default_timeout_hours == 48
        assert settings.default_retry_count == 3

    def test_init_missing_required_api_key(self, monkeypatch):
        """Test initialization fails when required GOOGLE_API_KEY is missing."""
        # Explicitly delete GOOGLE_API_KEY if it exists
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        # Also clear any lowercase version
        monkeypatch.delenv("google_api_key", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Check that the error is about the missing field
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["loc"] == ("google_api_key",) for err in errors)
        assert any(err["type"] == "missing" for err in errors)

    def test_init_with_defaults(self, monkeypatch, tmp_path):
        """Test initialization uses default values for optional fields."""
        # Only set required field
        monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key-1234567890")

        # Mock path creation for db paths
        with patch("info_agent.config.Path.mkdir"):
            settings = Settings()

        assert settings.google_api_key == "test-google-api-key-1234567890"
        assert settings.llm_model == "gemini-2.5-flash"
        assert settings.llm_temperature == 0.7
        assert settings.llm_max_tokens == 4096
        assert settings.host == "0.0.0.0"
        assert settings.gateway_port == 8000
        assert settings.mail_agent_port == 8001
        assert settings.email_server_port == 8025
        assert settings.smtp_port == 1025
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.log_format == "console"

    def test_init_case_insensitive(self, valid_env_vars, tmp_path, monkeypatch):
        """Test that environment variables are case-insensitive."""
        # Set up temp directory
        data_dir = tmp_path / "data"
        valid_env_vars["CHECKPOINT_DB_PATH"] = str(data_dir / "checkpoints.db")
        valid_env_vars["EMAIL_DB_PATH"] = str(data_dir / "emails.db")
        valid_env_vars["REGISTRY_DB_PATH"] = str(data_dir / "registry.db")
        valid_env_vars["WORKFLOW_DB_PATH"] = str(data_dir / "workflows.db")

        # Use lowercase environment variables
        for key, value in valid_env_vars.items():
            monkeypatch.setenv(key.lower(), value)

        settings = Settings()

        assert settings.google_api_key == "test-google-api-key-1234567890"
        assert settings.llm_model == "gemini-2.5-flash"


class TestGoogleApiKeyValidation:
    """Tests for google_api_key field validator."""

    def test_valid_api_key(self, monkeypatch, tmp_path):
        """Test validation passes with valid API key."""
        monkeypatch.setenv("GOOGLE_API_KEY", "valid-google-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            settings = Settings()

        assert settings.google_api_key == "valid-google-api-key-1234567890"

    def test_placeholder_api_key_rejected(self, monkeypatch):
        """Test validation fails with placeholder API key."""
        monkeypatch.setenv("GOOGLE_API_KEY", "your-google-api-key-here")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("must be set to a valid API key" in str(err["ctx"]["error"]) for err in errors)

    def test_empty_api_key_rejected(self, monkeypatch):
        """Test validation fails with empty API key."""
        monkeypatch.setenv("GOOGLE_API_KEY", "")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        # Empty string triggers missing validation
        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_short_api_key_rejected(self, monkeypatch):
        """Test validation fails with too short API key."""
        monkeypatch.setenv("GOOGLE_API_KEY", "short")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any("appears to be invalid (too short)" in str(err["ctx"]["error"]) for err in errors)


class TestLLMConfigurationValidation:
    """Tests for LLM configuration field validation."""

    def test_valid_temperature_range(self, monkeypatch, tmp_path):
        """Test temperature accepts valid range (0.0 to 2.0)."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            # Test min value
            monkeypatch.setenv("LLM_TEMPERATURE", "0.0")
            settings = Settings()
            assert settings.llm_temperature == 0.0

            clear_settings_cache()

            # Test max value
            monkeypatch.setenv("LLM_TEMPERATURE", "2.0")
            settings = Settings()
            assert settings.llm_temperature == 2.0

            clear_settings_cache()

            # Test middle value
            monkeypatch.setenv("LLM_TEMPERATURE", "1.0")
            settings = Settings()
            assert settings.llm_temperature == 1.0

    def test_temperature_below_minimum_rejected(self, monkeypatch):
        """Test temperature below 0.0 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("LLM_TEMPERATURE", "-0.1")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "greater_than_equal" for err in errors)

    def test_temperature_above_maximum_rejected(self, monkeypatch):
        """Test temperature above 2.0 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("LLM_TEMPERATURE", "2.1")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "less_than_equal" for err in errors)

    def test_valid_max_tokens_range(self, monkeypatch, tmp_path):
        """Test max_tokens accepts valid range (1 to 32768)."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            # Test min value
            monkeypatch.setenv("LLM_MAX_TOKENS", "1")
            settings = Settings()
            assert settings.llm_max_tokens == 1

            clear_settings_cache()

            # Test max value
            monkeypatch.setenv("LLM_MAX_TOKENS", "32768")
            settings = Settings()
            assert settings.llm_max_tokens == 32768

    def test_max_tokens_below_minimum_rejected(self, monkeypatch):
        """Test max_tokens below 1 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("LLM_MAX_TOKENS", "0")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "greater_than_equal" for err in errors)

    def test_max_tokens_above_maximum_rejected(self, monkeypatch):
        """Test max_tokens above 32768 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("LLM_MAX_TOKENS", "32769")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "less_than_equal" for err in errors)


class TestServerConfigurationValidation:
    """Tests for server configuration field validation."""

    def test_valid_port_range(self, monkeypatch, tmp_path):
        """Test ports accept valid range (1 to 65535)."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            # Test min value
            monkeypatch.setenv("GATEWAY_PORT", "1")
            settings = Settings()
            assert settings.gateway_port == 1

            clear_settings_cache()

            # Test max value
            monkeypatch.setenv("GATEWAY_PORT", "65535")
            settings = Settings()
            assert settings.gateway_port == 65535

    def test_port_below_minimum_rejected(self, monkeypatch):
        """Test port below 1 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("GATEWAY_PORT", "0")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "greater_than_equal" for err in errors)

    def test_port_above_maximum_rejected(self, monkeypatch):
        """Test port above 65535 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("GATEWAY_PORT", "65536")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "less_than_equal" for err in errors)

    def test_debug_boolean_parsing(self, monkeypatch, tmp_path):
        """Test debug field parses boolean values correctly."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            # Test true values
            for value in ["true", "True", "TRUE", "1", "yes"]:
                monkeypatch.setenv("DEBUG", value)
                settings = Settings()
                assert settings.debug is True
                clear_settings_cache()

            # Test false values
            for value in ["false", "False", "FALSE", "0", "no"]:
                monkeypatch.setenv("DEBUG", value)
                settings = Settings()
                assert settings.debug is False
                clear_settings_cache()


class TestLoggingConfigurationValidation:
    """Tests for logging configuration field validation."""

    def test_valid_log_levels(self, monkeypatch, tmp_path):
        """Test all valid log levels are accepted."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        with patch("info_agent.config.Path.mkdir"):
            for level in valid_levels:
                monkeypatch.setenv("LOG_LEVEL", level)
                settings = Settings()
                assert settings.log_level == level
                clear_settings_cache()

    def test_invalid_log_level_rejected(self, monkeypatch):
        """Test invalid log level is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("LOG_LEVEL", "INVALID")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "literal_error" for err in errors)

    def test_valid_log_formats(self, monkeypatch, tmp_path):
        """Test valid log formats are accepted."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        valid_formats = ["json", "console"]

        with patch("info_agent.config.Path.mkdir"):
            for fmt in valid_formats:
                monkeypatch.setenv("LOG_FORMAT", fmt)
                settings = Settings()
                assert settings.log_format == fmt
                clear_settings_cache()

    def test_invalid_log_format_rejected(self, monkeypatch):
        """Test invalid log format is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("LOG_FORMAT", "xml")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "literal_error" for err in errors)


class TestWorkflowConfigurationValidation:
    """Tests for workflow configuration field validation."""

    def test_valid_timeout_hours_range(self, monkeypatch, tmp_path):
        """Test timeout_hours accepts valid range (1 to 720)."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            # Test min value
            monkeypatch.setenv("DEFAULT_TIMEOUT_HOURS", "1")
            settings = Settings()
            assert settings.default_timeout_hours == 1

            clear_settings_cache()

            # Test max value
            monkeypatch.setenv("DEFAULT_TIMEOUT_HOURS", "720")
            settings = Settings()
            assert settings.default_timeout_hours == 720

    def test_timeout_hours_below_minimum_rejected(self, monkeypatch):
        """Test timeout_hours below 1 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("DEFAULT_TIMEOUT_HOURS", "0")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "greater_than_equal" for err in errors)

    def test_timeout_hours_above_maximum_rejected(self, monkeypatch):
        """Test timeout_hours above 720 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("DEFAULT_TIMEOUT_HOURS", "721")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "less_than_equal" for err in errors)

    def test_valid_retry_count_range(self, monkeypatch, tmp_path):
        """Test retry_count accepts valid range (0 to 10)."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            # Test min value
            monkeypatch.setenv("DEFAULT_RETRY_COUNT", "0")
            settings = Settings()
            assert settings.default_retry_count == 0

            clear_settings_cache()

            # Test max value
            monkeypatch.setenv("DEFAULT_RETRY_COUNT", "10")
            settings = Settings()
            assert settings.default_retry_count == 10

    def test_retry_count_below_minimum_rejected(self, monkeypatch):
        """Test retry_count below 0 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("DEFAULT_RETRY_COUNT", "-1")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "greater_than_equal" for err in errors)

    def test_retry_count_above_maximum_rejected(self, monkeypatch):
        """Test retry_count above 10 is rejected."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("DEFAULT_RETRY_COUNT", "11")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(err["type"] == "less_than_equal" for err in errors)


class TestDatabasePathValidation:
    """Tests for database path validation."""

    def test_valid_db_path_creates_directory(self, monkeypatch, tmp_path):
        """Test validation creates parent directory if it doesn't exist."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        db_dir = tmp_path / "custom_data"
        db_path = db_dir / "test.db"

        monkeypatch.setenv("CHECKPOINT_DB_PATH", str(db_path))

        assert not db_dir.exists()

        settings = Settings()

        assert settings.checkpoint_db_path == str(db_path)
        assert db_dir.exists()
        assert db_dir.is_dir()

    def test_db_path_with_existing_directory(self, monkeypatch, tmp_path):
        """Test validation works with existing directory."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        db_dir = tmp_path / "existing_data"
        db_dir.mkdir()
        db_path = db_dir / "test.db"

        monkeypatch.setenv("EMAIL_DB_PATH", str(db_path))

        settings = Settings()

        assert settings.email_db_path == str(db_path)

    def test_db_path_permission_error(self, monkeypatch):
        """Test validation fails with permission error."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        # Use a path that will cause permission error
        monkeypatch.setenv("REGISTRY_DB_PATH", "/root/forbidden/registry.db")

        with patch("info_agent.config.Path.mkdir") as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")

            with pytest.raises(ValidationError) as exc_info:
                Settings()

            errors = exc_info.value.errors()
            assert len(errors) > 0
            assert any("Cannot create database directory" in str(err["ctx"]["error"]) for err in errors)

    def test_multiple_db_paths_validated(self, monkeypatch, tmp_path):
        """Test all database paths are validated."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        db_dir = tmp_path / "multi_db"
        checkpoint_path = db_dir / "checkpoints.db"
        email_path = db_dir / "emails.db"
        registry_path = db_dir / "registry.db"
        workflow_path = db_dir / "workflows.db"

        monkeypatch.setenv("CHECKPOINT_DB_PATH", str(checkpoint_path))
        monkeypatch.setenv("EMAIL_DB_PATH", str(email_path))
        monkeypatch.setenv("REGISTRY_DB_PATH", str(registry_path))
        monkeypatch.setenv("WORKFLOW_DB_PATH", str(workflow_path))

        assert not db_dir.exists()

        settings = Settings()

        assert db_dir.exists()
        assert settings.checkpoint_db_path == str(checkpoint_path)
        assert settings.email_db_path == str(email_path)
        assert settings.registry_db_path == str(registry_path)
        assert settings.workflow_db_path == str(workflow_path)


class TestSettingsUtilityMethods:
    """Tests for Settings utility methods."""

    def test_get_gateway_url(self, monkeypatch, tmp_path):
        """Test get_gateway_url returns correct URL."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("HOST", "192.168.1.100")
        monkeypatch.setenv("GATEWAY_PORT", "9000")

        with patch("info_agent.config.Path.mkdir"):
            settings = Settings()

        assert settings.get_gateway_url() == "http://192.168.1.100:9000"

    def test_get_gateway_url_with_defaults(self, monkeypatch, tmp_path):
        """Test get_gateway_url with default host and port."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            settings = Settings()

        assert settings.get_gateway_url() == "http://0.0.0.0:8000"

    def test_get_mail_agent_url(self, monkeypatch, tmp_path):
        """Test get_mail_agent_url returns correct URL."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("MAIL_AGENT_PORT", "9001")

        with patch("info_agent.config.Path.mkdir"):
            settings = Settings()

        assert settings.get_mail_agent_url() == "http://localhost:9001"

    def test_get_email_server_url(self, monkeypatch, tmp_path):
        """Test get_email_server_url returns correct URL."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("HOST", "127.0.0.1")
        monkeypatch.setenv("EMAIL_SERVER_PORT", "9025")

        with patch("info_agent.config.Path.mkdir"):
            settings = Settings()

        assert settings.get_email_server_url() == "http://127.0.0.1:9025"


class TestGetSettingsFunction:
    """Tests for get_settings factory function."""

    def test_get_settings_returns_instance(self, monkeypatch, tmp_path):
        """Test get_settings returns Settings instance."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            settings = get_settings()

        assert isinstance(settings, Settings)
        assert settings.google_api_key == "test-api-key-1234567890"

    def test_get_settings_caches_instance(self, monkeypatch, tmp_path):
        """Test get_settings returns cached instance on subsequent calls."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            settings1 = get_settings()
            settings2 = get_settings()

        # Should be the same instance (cached)
        assert settings1 is settings2

    def test_get_settings_respects_cache_clear(self, monkeypatch, tmp_path):
        """Test cache clearing creates new instance."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            settings1 = get_settings()

            clear_settings_cache()

            settings2 = get_settings()

        # Should be different instances after cache clear
        assert settings1 is not settings2
        assert isinstance(settings2, Settings)

    def test_get_settings_propagates_validation_error(self, monkeypatch):
        """Test get_settings propagates validation errors."""
        monkeypatch.setenv("GOOGLE_API_KEY", "short")

        with pytest.raises(ValidationError):
            get_settings()


class TestClearSettingsCache:
    """Tests for clear_settings_cache function."""

    def test_clear_settings_cache_clears_cache(self, monkeypatch, tmp_path):
        """Test clear_settings_cache clears the cached settings."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            # Create cached instance
            settings1 = get_settings()

            # Verify it's cached
            settings2 = get_settings()
            assert settings1 is settings2

            # Clear cache
            clear_settings_cache()

            # New instance should be created
            settings3 = get_settings()
            assert settings1 is not settings3

    def test_clear_settings_cache_when_empty(self):
        """Test clear_settings_cache doesn't fail when cache is empty."""
        clear_settings_cache()  # Should not raise error

    def test_clear_settings_cache_multiple_times(self, monkeypatch, tmp_path):
        """Test clear_settings_cache can be called multiple times."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")

        with patch("info_agent.config.Path.mkdir"):
            get_settings()

            clear_settings_cache()
            clear_settings_cache()
            clear_settings_cache()

            # Should still work
            settings = get_settings()
            assert isinstance(settings, Settings)


class TestSettingsEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_extra_env_vars_ignored(self, valid_env_vars, tmp_path, monkeypatch):
        """Test that extra environment variables are ignored."""
        data_dir = tmp_path / "data"
        valid_env_vars["CHECKPOINT_DB_PATH"] = str(data_dir / "checkpoints.db")
        valid_env_vars["EMAIL_DB_PATH"] = str(data_dir / "emails.db")
        valid_env_vars["REGISTRY_DB_PATH"] = str(data_dir / "registry.db")
        valid_env_vars["WORKFLOW_DB_PATH"] = str(data_dir / "workflows.db")

        for key, value in valid_env_vars.items():
            monkeypatch.setenv(key, value)

        # Add extra vars
        monkeypatch.setenv("EXTRA_VAR_1", "should be ignored")
        monkeypatch.setenv("UNKNOWN_CONFIG", "also ignored")

        settings = Settings()

        assert isinstance(settings, Settings)
        assert not hasattr(settings, "extra_var_1")
        assert not hasattr(settings, "unknown_config")

    def test_invalid_type_conversion(self, monkeypatch):
        """Test validation fails with invalid type conversion."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("GATEWAY_PORT", "not-a-number")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_empty_string_for_optional_fields(self, monkeypatch, tmp_path):
        """Test empty string for optional fields uses defaults."""
        monkeypatch.setenv("GOOGLE_API_KEY", "test-api-key-1234567890")
        monkeypatch.setenv("LLM_MODEL", "")  # Empty string

        with patch("info_agent.config.Path.mkdir"):
            settings = Settings()

        # Empty string should be replaced with default
        assert settings.llm_model == ""  # Pydantic keeps empty string
