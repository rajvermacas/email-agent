"""
Gemini LLM provider implementation using LangChain.

This module provides the GeminiProvider class that wraps Google's Gemini LLM
using the langchain_google_genai integration. It supports lazy initialization
and extensive logging.

Usage:
    from info_agent.llm.gemini_provider import GeminiProvider
    from info_agent.config import get_settings

    settings = get_settings()
    provider = GeminiProvider(settings)
    llm = provider.get_chat_model()
    response = await llm.ainvoke("Hello, world!")
"""

import logging
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from info_agent.config import Settings
from info_agent.utils.exceptions import LLMError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class GeminiProvider:
    """
    Gemini LLM provider using LangChain's Google Generative AI integration.

    This provider:
    - Uses lazy initialization (only creates client when first requested)
    - Provides comprehensive logging for all operations
    - Raises LLMError for any failures
    - No fallback/default values - all required settings must be provided

    Attributes:
        api_key: Google API key for Gemini.
        model: Gemini model name (e.g., "gemini-2.5-flash").
        temperature: Temperature for response generation (0.0-2.0).
        max_tokens: Maximum tokens in the response.
    """

    def __init__(self, settings: Settings) -> None:
        """
        Initialize the Gemini provider with settings.

        Args:
            settings: Application settings containing LLM configuration.

        Raises:
            LLMError: If required settings are missing or invalid.
        """
        logger.info(
            "Initializing GeminiProvider",
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        # Validate required settings
        if not settings.google_api_key:
            logger.error("GOOGLE_API_KEY is missing from settings")
            raise LLMError(
                message="GOOGLE_API_KEY is required but not provided",
                model=settings.llm_model,
                details={"config_key": "google_api_key"},
            )

        if not settings.llm_model:
            logger.error("LLM_MODEL is missing from settings")
            raise LLMError(
                message="LLM_MODEL is required but not provided",
                model=None,
                details={"config_key": "llm_model"},
            )

        # Store configuration
        self.api_key = settings.google_api_key
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens

        # Client will be created lazily
        self._client: ChatGoogleGenerativeAI | None = None

        logger.info(
            "GeminiProvider initialized successfully",
            model=self.model,
            lazy_initialization=True,
        )

    def get_chat_model(self, **kwargs: Any) -> ChatGoogleGenerativeAI:
        """
        Get or create the chat model instance.

        This method implements lazy initialization - the actual LLM client
        is only created when this method is first called. Subsequent calls
        return the cached instance unless override parameters are provided.

        Args:
            **kwargs: Optional override parameters:
                - temperature: Override default temperature
                - max_tokens: Override default max_tokens
                - model: Override default model name

        Returns:
            ChatGoogleGenerativeAI: Configured LLM instance.

        Raises:
            LLMError: If client creation fails.
        """
        # If overrides are provided, create a new instance
        if kwargs:
            logger.info(
                "Creating new LLM instance with overrides",
                overrides=kwargs,
            )
            return self._create_client(**kwargs)

        # Otherwise use cached instance
        if self._client is None:
            logger.info(
                "Creating LLM client (lazy initialization)",
                model=self.model,
            )
            self._client = self._create_client()
            logger.info(
                "LLM client created successfully",
                model=self.model,
            )

        return self._client

    def _create_client(self, **kwargs: Any) -> ChatGoogleGenerativeAI:
        """
        Create a new ChatGoogleGenerativeAI instance.

        Args:
            **kwargs: Optional override parameters.

        Returns:
            ChatGoogleGenerativeAI: Configured LLM instance.

        Raises:
            LLMError: If client creation fails.
        """
        model_name = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        logger.debug(
            "Creating ChatGoogleGenerativeAI client",
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        try:
            client = ChatGoogleGenerativeAI(
                google_api_key=self.api_key,
                model=model_name,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            logger.debug(
                "ChatGoogleGenerativeAI client created",
                model=model_name,
            )

            return client

        except Exception as e:
            logger.error(
                "Failed to create ChatGoogleGenerativeAI client",
                model=model_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise LLMError(
                message=f"Failed to create Gemini client: {str(e)}",
                model=model_name,
                original_error=e,
            ) from e

    def reset(self) -> None:
        """
        Reset the provider by clearing the cached client.

        This is useful for testing or when you need to force
        recreation of the client with new settings.
        """
        logger.info("Resetting GeminiProvider (clearing cached client)")
        self._client = None
        logger.debug("GeminiProvider reset complete")
