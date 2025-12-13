"""
Configuration management for Info-Agent.

This module provides centralized configuration using Pydantic Settings.
All configuration values are loaded from environment variables with NO fallback
defaults for required values - missing values will raise exceptions.

Usage:
    from info_agent.config import get_settings

    settings = get_settings()
    print(settings.gateway_port)
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings with validation.

    All required settings must be provided via environment variables.
    No fallback defaults are used for required values.

    Raises:
        ValidationError: If required settings are missing or invalid.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===================
    # LLM Configuration
    # ===================
    google_api_key: str = Field(
        ...,  # Required, no default
        description="Google API key for Gemini LLM",
    )
    llm_model: str = Field(
        default="gemini-2.5-flash",
        description="LLM model to use",
    )
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature for response generation",
    )
    llm_max_tokens: int = Field(
        default=4096,
        ge=1,
        le=32768,
        description="Maximum tokens for LLM response",
    )

    # ===================
    # Server Configuration
    # ===================
    host: str = Field(
        default="0.0.0.0",
        description="Host to bind servers to",
    )
    gateway_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port for FastAPI Gateway",
    )
    mail_agent_port: int = Field(
        default=8001,
        ge=1,
        le=65535,
        description="Port for Mail Agent A2A server",
    )
    email_server_port: int = Field(
        default=8025,
        ge=1,
        le=65535,
        description="Port for Mock Email Server REST API",
    )
    smtp_port: int = Field(
        default=1025,
        ge=1,
        le=65535,
        description="Port for Mock Email Server SMTP interface",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    # ===================
    # A2A Registry Configuration
    # ===================
    a2a_registry_url: str = Field(
        default="http://localhost:8000/a2a",
        description="URL of the A2A Registry",
    )

    # ===================
    # Mock Email Server Configuration
    # ===================
    smtp_host: str = Field(
        default="localhost",
        description="SMTP host for Mail Agent to connect to",
    )
    email_webhook_url: str = Field(
        default="http://localhost:8000/webhooks/email",
        description="Webhook URL for email notifications",
    )

    # ===================
    # Database Paths
    # ===================
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
    workflow_db_path: str = Field(
        default="data/workflows.db",
        description="Path to SQLite workflow database",
    )

    # ===================
    # Logging Configuration
    # ===================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: Literal["json", "console"] = Field(
        default="console",
        description="Log output format",
    )

    # ===================
    # Workflow Configuration
    # ===================
    default_timeout_hours: int = Field(
        default=48,
        ge=1,
        le=720,  # Max 30 days
        description="Default timeout for email responses in hours",
    )
    default_retry_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Default number of retry attempts",
    )

    @field_validator("google_api_key")
    @classmethod
    def validate_google_api_key(cls, v: str) -> str:
        """Validate that Google API key is not a placeholder."""
        logger.debug("Validating Google API key")
        if not v or v == "your-google-api-key-here":
            raise ValueError(
                "GOOGLE_API_KEY must be set to a valid API key. "
                "Get one from https://aistudio.google.com/apikey"
            )
        if len(v) < 10:
            raise ValueError("GOOGLE_API_KEY appears to be invalid (too short)")
        logger.debug("Google API key validation passed")
        return v

    @field_validator("checkpoint_db_path", "email_db_path", "registry_db_path", "workflow_db_path")
    @classmethod
    def validate_db_path(cls, v: str) -> str:
        """Ensure database directory can be created."""
        logger.debug(f"Validating database path: {v}")
        path = Path(v)
        parent = path.parent

        # Try to create parent directory if it doesn't exist
        try:
            parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Database directory ensured: {parent}")
        except PermissionError as e:
            raise ValueError(
                f"Cannot create database directory {parent}: {e}"
            ) from e

        return v

    def get_gateway_url(self) -> str:
        """Get the full URL for the gateway."""
        return f"http://{self.host}:{self.gateway_port}"

    def get_mail_agent_url(self) -> str:
        """Get the full URL for the mail agent."""
        return f"http://{self.host}:{self.mail_agent_port}"

    def get_email_server_url(self) -> str:
        """Get the full URL for the mock email server REST API."""
        return f"http://{self.host}:{self.email_server_port}"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings: Application settings instance.

    Raises:
        ValidationError: If required settings are missing or invalid.
    """
    logger.info("Loading application settings")
    settings = Settings()
    logger.info(
        f"Settings loaded - Gateway: {settings.gateway_port}, "
        f"Mail Agent: {settings.mail_agent_port}, "
        f"Email Server: {settings.email_server_port}, "
        f"SMTP: {settings.smtp_port}"
    )
    return settings


def clear_settings_cache() -> None:
    """Clear the settings cache. Useful for testing."""
    logger.debug("Clearing settings cache")
    get_settings.cache_clear()
