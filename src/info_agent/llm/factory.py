"""
Factory functions for LLM instances.

This module provides factory functions for creating and managing LLM instances
using the singleton pattern to ensure efficient resource usage.

Usage:
    from info_agent.llm.factory import get_gemini_llm, reset_llm_instance

    # Get the singleton LLM instance
    llm = get_gemini_llm()
    response = await llm.ainvoke("Hello!")

    # For testing, reset the singleton
    reset_llm_instance()
"""

from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI

from info_agent.config import get_settings
from info_agent.llm.gemini_provider import GeminiProvider
from info_agent.utils.exceptions import LLMError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)

# Global singleton instance
_provider_instance: GeminiProvider | None = None


def get_gemini_llm(**kwargs: Any) -> ChatGoogleGenerativeAI:
    """
    Get the configured Gemini LLM instance (singleton pattern).

    This function maintains a singleton GeminiProvider instance and returns
    the chat model from it. This ensures efficient resource usage by reusing
    the same LLM client across the application.

    Args:
        **kwargs: Optional override parameters for the chat model:
            - temperature: Override default temperature
            - max_tokens: Override default max_tokens
            - model: Override default model name

    Returns:
        ChatGoogleGenerativeAI: Configured LLM instance ready for use.

    Raises:
        LLMError: If LLM initialization or retrieval fails.

    Example:
        # Get default instance
        llm = get_gemini_llm()

        # Get instance with custom temperature
        llm = get_gemini_llm(temperature=0.9)
    """
    global _provider_instance

    logger.debug("get_gemini_llm called", has_overrides=bool(kwargs))

    # Create provider singleton if it doesn't exist
    if _provider_instance is None:
        logger.info("Creating GeminiProvider singleton instance")

        try:
            settings = get_settings()
            _provider_instance = GeminiProvider(settings)

            logger.info(
                "GeminiProvider singleton created",
                model=settings.llm_model,
            )

        except Exception as e:
            logger.error(
                "Failed to create GeminiProvider singleton",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise LLMError(
                message=f"Failed to initialize LLM provider: {str(e)}",
                original_error=e,
            ) from e

    # Get chat model from provider
    try:
        logger.debug("Getting chat model from provider", overrides=kwargs)
        llm = _provider_instance.get_chat_model(**kwargs)

        logger.debug(
            "Chat model retrieved successfully",
            model=_provider_instance.model,
        )

        return llm

    except Exception as e:
        logger.error(
            "Failed to get chat model from provider",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise LLMError(
            message=f"Failed to retrieve LLM instance: {str(e)}",
            model=_provider_instance.model if _provider_instance else None,
            original_error=e,
        ) from e


def reset_llm_instance() -> None:
    """
    Reset the LLM singleton instance.

    This function clears the global singleton instance, forcing a new
    instance to be created on the next call to get_gemini_llm().

    This is primarily useful for:
    - Testing: Reset state between tests
    - Configuration changes: Force reload with new settings
    - Error recovery: Clear potentially corrupted state

    Note:
        This should NOT be called during normal application runtime.
        It's intended for testing and administrative purposes only.

    Example:
        # In test teardown
        reset_llm_instance()
    """
    global _provider_instance

    logger.info("Resetting LLM singleton instance")

    if _provider_instance is not None:
        logger.debug(
            "Clearing existing provider instance",
            model=_provider_instance.model,
        )
        # Reset the provider to clear its cached client
        _provider_instance.reset()
        _provider_instance = None
        logger.info("LLM singleton instance reset complete")
    else:
        logger.debug("No LLM instance to reset (already None)")


def is_llm_initialized() -> bool:
    """
    Check if the LLM singleton instance has been initialized.

    Returns:
        bool: True if the singleton exists, False otherwise.

    Example:
        if not is_llm_initialized():
            logger.info("LLM will be initialized on first use")
    """
    return _provider_instance is not None
