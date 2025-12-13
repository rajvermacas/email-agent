"""
Configuration management for Info-Agent.

This module provides centralized configuration using Pydantic Settings.
All required settings MUST be explicitly provided - no fallback values.

Usage:
    from info_agent.config import get_settings
    settings = get_settings()
"""

import logging
from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class LogFormat(str, Enum):
    """Supported log formats."""

    JSON = "json"
    CONSOLE = "console"


class MissingConfigurationError(Exception):
    """Raised when required configuration is missing."""

    def __init__(self, field_name: str, message: str) -> None:
        """Initialize with field name and message."""
        self.field_name = field_name
        self.message = message
        super().__init__(f"Missing configuration for '{field_name}': {message}")


class Settings(BaseSettings):
    """
    Application settings with strict validation.

    All required fields MUST be provided via environment variables or .env file.
    No fallback/default values for critical configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # LLM PROVIDER CONFIGURATION
    # =========================================================================

    llm_provider: LLMProvider = Field(
        ...,
        description="LLM provider to use (openai, azure_openai, gemini, openrouter)",
    )

    llm_model: str = Field(
        ...,
        description="Model name/identifier for the selected provider",
    )

    # OpenAI
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (required if llm_provider=openai)",
    )

    # Azure OpenAI
    azure_openai_api_key: Optional[str] = Field(
        default=None,
        description="Azure OpenAI API key (required if llm_provider=azure_openai)",
    )
    azure_openai_endpoint: Optional[str] = Field(
        default=None,
        description="Azure OpenAI endpoint URL",
    )
    azure_openai_deployment_name: Optional[str] = Field(
        default=None,
        description="Azure OpenAI deployment name",
    )
    azure_openai_api_version: str = Field(
        default="2024-02-01",
        description="Azure OpenAI API version",
    )

    # Google Gemini
    google_api_key: Optional[str] = Field(
        default=None,
        description="Google API key (required if llm_provider=gemini)",
    )

    # OpenRouter
    openrouter_api_key: Optional[str] = Field(
        default=None,
        description="OpenRouter API key (required if llm_provider=openrouter)",
    )

    # =========================================================================
    # SERVER CONFIGURATION
    # =========================================================================

    gateway_host: str = Field(
        default="0.0.0.0",
        description="FastAPI gateway host",
    )
    gateway_port: int = Field(
        default=8000,
        description="FastAPI gateway port",
        ge=1,
        le=65535,
    )

    mail_agent_host: str = Field(
        default="0.0.0.0",
        description="Mail agent host",
    )
    mail_agent_port: int = Field(
        default=8002,
        description="Mail agent port",
        ge=1,
        le=65535,
    )

    validation_agent_host: str = Field(
        default="0.0.0.0",
        description="Validation agent host",
    )
    validation_agent_port: int = Field(
        default=8003,
        description="Validation agent port",
        ge=1,
        le=65535,
    )

    email_server_host: str = Field(
        default="0.0.0.0",
        description="Mock email server host",
    )
    email_server_port: int = Field(
        default=8080,
        description="Mock email server HTTP port",
        ge=1,
        le=65535,
    )
    smtp_port: int = Field(
        default=1025,
        description="Mock email server SMTP port",
        ge=1,
        le=65535,
    )

    a2a_registry_url: str = Field(
        default="http://localhost:8000/api/registry",
        description="A2A Registry URL",
    )

    # =========================================================================
    # EMAIL CONFIGURATION
    # =========================================================================

    smtp_host: str = Field(
        default="localhost",
        description="SMTP server host",
    )
    email_webhook_url: str = Field(
        default="http://localhost:8000/webhooks/email",
        description="Webhook URL for email notifications",
    )

    # =========================================================================
    # DATABASE PATHS
    # =========================================================================

    checkpoint_db_path: str = Field(
        default="data/checkpoints.db",
        description="Path to SQLite checkpoint database",
    )
    email_db_path: str = Field(
        default="data/emails.db",
        description="Path to SQLite email database",
    )
    registry_db_path: str = Field(
        default="data/registry.db",
        description="Path to SQLite registry database",
    )

    # =========================================================================
    # TIMEOUT CONFIGURATION
    # =========================================================================

    default_timeout_hours: float = Field(
        default=48.0,
        description="Default timeout for email response (hours)",
        gt=0,
    )
    default_retry_count: int = Field(
        default=3,
        description="Number of retries before escalation",
        ge=1,
    )
    validation_timeout_seconds: int = Field(
        default=30,
        description="Python execution timeout for validation (seconds)",
        ge=1,
        le=300,
    )

    # =========================================================================
    # LOGGING CONFIGURATION
    # =========================================================================

    log_level: str = Field(
        default="INFO",
        description="Log level",
    )
    log_format: LogFormat = Field(
        default=LogFormat.JSON,
        description="Log format (json or console)",
    )

    # =========================================================================
    # SECURITY CONFIGURATION
    # =========================================================================

    allowed_origins: str = Field(
        default="http://localhost:8000,http://localhost:3000,http://localhost:8080",
        description="CORS allowed origins (comma-separated)",
    )
    debug: bool = Field(
        default=False,
        description="Debug mode",
    )

    # =========================================================================
    # VALIDATORS
    # =========================================================================

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise MissingConfigurationError(
                "log_level",
                f"Invalid log level '{v}'. Must be one of: {valid_levels}",
            )
        return upper_v

    @model_validator(mode="after")
    def validate_llm_provider_credentials(self) -> "Settings":
        """Validate that required credentials are provided for selected LLM provider."""
        provider = self.llm_provider

        logger.debug(f"Validating LLM provider credentials for: {provider}")

        if provider == LLMProvider.OPENAI:
            if not self.openai_api_key:
                raise MissingConfigurationError(
                    "openai_api_key",
                    "OPENAI_API_KEY is required when LLM_PROVIDER=openai",
                )

        elif provider == LLMProvider.AZURE_OPENAI:
            missing_fields = []
            if not self.azure_openai_api_key:
                missing_fields.append("AZURE_OPENAI_API_KEY")
            if not self.azure_openai_endpoint:
                missing_fields.append("AZURE_OPENAI_ENDPOINT")
            if not self.azure_openai_deployment_name:
                missing_fields.append("AZURE_OPENAI_DEPLOYMENT_NAME")

            if missing_fields:
                raise MissingConfigurationError(
                    "azure_openai",
                    f"The following fields are required when LLM_PROVIDER=azure_openai: "
                    f"{', '.join(missing_fields)}",
                )

        elif provider == LLMProvider.GEMINI:
            if not self.google_api_key:
                raise MissingConfigurationError(
                    "google_api_key",
                    "GOOGLE_API_KEY is required when LLM_PROVIDER=gemini",
                )

        elif provider == LLMProvider.OPENROUTER:
            if not self.openrouter_api_key:
                raise MissingConfigurationError(
                    "openrouter_api_key",
                    "OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter",
                )

        logger.debug(f"LLM provider credentials validated successfully for: {provider}")
        return self

    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================

    @property
    def allowed_origins_list(self) -> list[str]:
        """Get allowed origins as a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def gateway_url(self) -> str:
        """Get the gateway URL."""
        return f"http://{self.gateway_host}:{self.gateway_port}"

    @property
    def mail_agent_url(self) -> str:
        """Get the mail agent URL."""
        return f"http://{self.mail_agent_host}:{self.mail_agent_port}"

    @property
    def validation_agent_url(self) -> str:
        """Get the validation agent URL."""
        return f"http://{self.validation_agent_host}:{self.validation_agent_port}"

    @property
    def email_server_url(self) -> str:
        """Get the email server URL."""
        return f"http://{self.email_server_host}:{self.email_server_port}"


@lru_cache
def get_settings() -> Settings:
    """
    Get application settings (cached).

    Returns:
        Settings: Application settings instance.

    Raises:
        MissingConfigurationError: If required configuration is missing.
        ValidationError: If configuration values are invalid.
    """
    logger.info("Loading application settings...")
    settings = Settings()
    logger.info(f"Settings loaded successfully. LLM Provider: {settings.llm_provider}")
    return settings


def clear_settings_cache() -> None:
    """Clear the settings cache (useful for testing)."""
    get_settings.cache_clear()
    logger.debug("Settings cache cleared")
