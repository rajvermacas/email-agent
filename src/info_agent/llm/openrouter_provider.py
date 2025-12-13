"""
OpenRouter LLM Provider implementation.

Provides integration with OpenRouter's API which gives access to multiple LLM providers.
Uses the OpenAI-compatible API endpoint.
"""

from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from info_agent.llm.base import BaseLLMProvider
from info_agent.utils.exceptions import LLMError, LLMProviderNotFoundError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(BaseLLMProvider):
    """
    OpenRouter LLM provider.

    OpenRouter provides access to multiple LLM providers through a unified API.
    Model format: provider/model (e.g., 'anthropic/claude-3-opus', 'google/gemini-pro')
    """

    def __init__(self, api_key: str, model: str) -> None:
        """
        Initialize the OpenRouter provider.

        Args:
            api_key: OpenRouter API key.
            model: Model identifier (e.g., 'anthropic/claude-3-opus').

        Raises:
            LLMProviderNotFoundError: If api_key is empty.
        """
        if not api_key:
            logger.error("openrouter_provider_init_failed", reason="missing_api_key")
            raise LLMProviderNotFoundError(
                "OpenRouter API key is required",
                provider="openrouter",
            )

        super().__init__(model)
        self._api_key = api_key

        logger.info(
            "openrouter_provider_created",
            model=model,
            api_key_preview=api_key[:8] + "..." if len(api_key) > 8 else "***",
        )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "openrouter"

    def get_chat_model(
        self,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        streaming: bool = True,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Get an OpenRouter chat model instance.

        Uses the OpenAI-compatible ChatOpenAI client with OpenRouter's base URL.

        Args:
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            streaming: Whether to enable streaming.
            **kwargs: Additional arguments passed to ChatOpenAI.

        Returns:
            ChatOpenAI: LangChain chat model configured for OpenRouter.

        Raises:
            LLMError: If model creation fails.
        """
        logger.debug(
            "creating_openrouter_chat_model",
            model=self.model,
            temperature=temperature,
            streaming=streaming,
        )

        try:
            model_kwargs: dict[str, Any] = {
                "api_key": self._api_key,
                "base_url": OPENROUTER_BASE_URL,
                "model": self.model,
                "temperature": temperature,
                "streaming": streaming,
                **kwargs,
            }

            if max_tokens is not None:
                model_kwargs["max_tokens"] = max_tokens

            # Add OpenRouter-specific headers
            default_headers = kwargs.get("default_headers", {})
            default_headers.update(
                {
                    "HTTP-Referer": "https://info-agent.local",
                    "X-Title": "Info-Agent",
                }
            )
            model_kwargs["default_headers"] = default_headers

            chat_model = ChatOpenAI(**model_kwargs)

            logger.debug("openrouter_chat_model_created", model=self.model)
            return chat_model

        except Exception as e:
            logger.error(
                "openrouter_chat_model_creation_failed",
                model=self.model,
                error=str(e),
            )
            raise LLMError(
                f"Failed to create OpenRouter chat model: {e}",
                provider="openrouter",
                model=self.model,
                cause=e,
            ) from e

    def validate_connection(self) -> bool:
        """
        Validate OpenRouter connection.

        Returns:
            bool: True if connection is valid.

        Raises:
            LLMError: If validation fails.
        """
        logger.debug("validating_openrouter_connection", model=self.model)

        try:
            chat_model = self.get_chat_model(temperature=0, streaming=False)

            if chat_model is not None:
                logger.info("openrouter_connection_valid", model=self.model)
                return True

            return False

        except Exception as e:
            logger.error(
                "openrouter_connection_validation_failed",
                model=self.model,
                error=str(e),
            )
            raise LLMError(
                f"OpenRouter connection validation failed: {e}",
                provider="openrouter",
                model=self.model,
                cause=e,
            ) from e
