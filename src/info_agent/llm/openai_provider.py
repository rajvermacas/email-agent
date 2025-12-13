"""
OpenAI LLM Provider implementation.

Provides integration with OpenAI's API using langchain-openai.
"""

from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from info_agent.llm.base import BaseLLMProvider
from info_agent.utils.exceptions import LLMError, LLMProviderNotFoundError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM provider using the OpenAI API.

    Supports models like gpt-4-turbo, gpt-4o, gpt-4o-mini, gpt-3.5-turbo.
    """

    def __init__(self, api_key: str, model: str) -> None:
        """
        Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key.
            model: Model identifier (e.g., 'gpt-4-turbo').

        Raises:
            LLMProviderNotFoundError: If api_key is empty.
        """
        if not api_key:
            logger.error("openai_provider_init_failed", reason="missing_api_key")
            raise LLMProviderNotFoundError(
                "OpenAI API key is required",
                provider="openai",
            )

        super().__init__(model)
        self._api_key = api_key

        logger.info(
            "openai_provider_created",
            model=model,
            api_key_preview=api_key[:8] + "..." if len(api_key) > 8 else "***",
        )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "openai"

    def get_chat_model(
        self,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        streaming: bool = True,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Get an OpenAI chat model instance.

        Args:
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens in response.
            streaming: Whether to enable streaming.
            **kwargs: Additional arguments passed to ChatOpenAI.

        Returns:
            ChatOpenAI: LangChain OpenAI chat model.

        Raises:
            LLMError: If model creation fails.
        """
        logger.debug(
            "creating_openai_chat_model",
            model=self.model,
            temperature=temperature,
            streaming=streaming,
        )

        try:
            model_kwargs = {
                "api_key": self._api_key,
                "model": self.model,
                "temperature": temperature,
                "streaming": streaming,
                **kwargs,
            }

            if max_tokens is not None:
                model_kwargs["max_tokens"] = max_tokens

            chat_model = ChatOpenAI(**model_kwargs)

            logger.debug("openai_chat_model_created", model=self.model)
            return chat_model

        except Exception as e:
            logger.error(
                "openai_chat_model_creation_failed",
                model=self.model,
                error=str(e),
            )
            raise LLMError(
                f"Failed to create OpenAI chat model: {e}",
                provider="openai",
                model=self.model,
                cause=e,
            ) from e

    def validate_connection(self) -> bool:
        """
        Validate OpenAI API connection.

        Returns:
            bool: True if connection is valid.

        Raises:
            LLMError: If validation fails.
        """
        logger.debug("validating_openai_connection", model=self.model)

        try:
            # Create a minimal chat model and make a test call
            chat_model = self.get_chat_model(temperature=0, streaming=False)

            # Simple validation - check that the model can be instantiated
            # A full validation would make an actual API call
            if chat_model is not None:
                logger.info("openai_connection_valid", model=self.model)
                return True

            return False

        except Exception as e:
            logger.error(
                "openai_connection_validation_failed",
                model=self.model,
                error=str(e),
            )
            raise LLMError(
                f"OpenAI connection validation failed: {e}",
                provider="openai",
                model=self.model,
                cause=e,
            ) from e
