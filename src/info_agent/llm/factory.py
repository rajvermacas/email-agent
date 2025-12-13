"""
LLM Provider Factory.

This module provides a factory function for creating LLM providers based on configuration.
"""

from typing import TYPE_CHECKING

from info_agent.config import LLMProvider, Settings
from info_agent.llm.base import BaseLLMProvider
from info_agent.utils.exceptions import LLMProviderNotFoundError
from info_agent.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def get_available_providers() -> list[str]:
    """
    Get list of available LLM provider names.

    Returns:
        list[str]: List of provider names.
    """
    return [p.value for p in LLMProvider]


def create_llm_provider(settings: Settings) -> BaseLLMProvider:
    """
    Create an LLM provider based on settings.

    Factory function that instantiates the appropriate LLM provider
    based on the LLM_PROVIDER configuration.

    Args:
        settings: Application settings with LLM configuration.

    Returns:
        BaseLLMProvider: Configured LLM provider instance.

    Raises:
        LLMProviderNotFoundError: If the provider is not supported or
            required credentials are missing.

    Example:
        >>> from info_agent.config import get_settings
        >>> settings = get_settings()
        >>> provider = create_llm_provider(settings)
        >>> chat_model = provider.get_chat_model(temperature=0)
    """
    provider_type = settings.llm_provider
    model = settings.llm_model

    logger.info(
        "creating_llm_provider",
        provider=provider_type.value,
        model=model,
    )

    if provider_type == LLMProvider.OPENAI:
        return _create_openai_provider(settings)

    elif provider_type == LLMProvider.AZURE_OPENAI:
        return _create_azure_provider(settings)

    elif provider_type == LLMProvider.GEMINI:
        return _create_gemini_provider(settings)

    elif provider_type == LLMProvider.OPENROUTER:
        return _create_openrouter_provider(settings)

    else:
        logger.error(
            "unknown_llm_provider",
            provider=provider_type.value,
            available=get_available_providers(),
        )
        raise LLMProviderNotFoundError(
            f"Unknown LLM provider: {provider_type.value}. "
            f"Available providers: {get_available_providers()}",
            provider=provider_type.value,
        )


def _create_openai_provider(settings: Settings) -> BaseLLMProvider:
    """Create OpenAI provider."""
    from info_agent.llm.openai_provider import OpenAIProvider

    logger.debug("creating_openai_provider", model=settings.llm_model)

    return OpenAIProvider(
        api_key=settings.openai_api_key or "",
        model=settings.llm_model,
    )


def _create_azure_provider(settings: Settings) -> BaseLLMProvider:
    """Create Azure OpenAI provider."""
    from info_agent.llm.azure_provider import AzureOpenAIProvider

    logger.debug(
        "creating_azure_provider",
        deployment=settings.azure_openai_deployment_name,
    )

    return AzureOpenAIProvider(
        api_key=settings.azure_openai_api_key or "",
        endpoint=settings.azure_openai_endpoint or "",
        deployment_name=settings.azure_openai_deployment_name or "",
        model=settings.llm_model,
        api_version=settings.azure_openai_api_version,
    )


def _create_gemini_provider(settings: Settings) -> BaseLLMProvider:
    """Create Gemini provider."""
    from info_agent.llm.gemini_provider import GeminiProvider

    logger.debug("creating_gemini_provider", model=settings.llm_model)

    return GeminiProvider(
        api_key=settings.google_api_key or "",
        model=settings.llm_model,
    )


def _create_openrouter_provider(settings: Settings) -> BaseLLMProvider:
    """Create OpenRouter provider."""
    from info_agent.llm.openrouter_provider import OpenRouterProvider

    logger.debug("creating_openrouter_provider", model=settings.llm_model)

    return OpenRouterProvider(
        api_key=settings.openrouter_api_key or "",
        model=settings.llm_model,
    )
