"""
Google Gemini LLM Provider implementation.

Provides integration with Google's Gemini API using langchain-google-genai.
"""

from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from info_agent.llm.base import BaseLLMProvider
from info_agent.utils.exceptions import LLMError, LLMProviderNotFoundError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini LLM provider.

    Supports models like gemini-pro, gemini-1.5-pro, gemini-1.5-flash.
    """

    def __init__(self, api_key: str, model: str) -> None:
        """
        Initialize the Gemini provider.

        Args:
            api_key: Google API key with Gemini access.
            model: Model identifier (e.g., 'gemini-pro').

        Raises:
            LLMProviderNotFoundError: If api_key is empty.
        """
        if not api_key:
            logger.error("gemini_provider_init_failed", reason="missing_api_key")
            raise LLMProviderNotFoundError(
                "Google API key is required for Gemini",
                provider="gemini",
            )

        super().__init__(model)
        self._api_key = api_key

        logger.info(
            "gemini_provider_created",
            model=model,
            api_key_preview=api_key[:8] + "..." if len(api_key) > 8 else "***",
        )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "gemini"

    def get_chat_model(
        self,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        streaming: bool = True,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Get a Gemini chat model instance.

        Args:
            temperature: Sampling temperature (0.0-1.0 for Gemini).
            max_tokens: Maximum tokens in response.
            streaming: Whether to enable streaming.
            **kwargs: Additional arguments passed to ChatGoogleGenerativeAI.

        Returns:
            ChatGoogleGenerativeAI: LangChain Gemini chat model.

        Raises:
            LLMError: If model creation fails.
        """
        logger.debug(
            "creating_gemini_chat_model",
            model=self.model,
            temperature=temperature,
            streaming=streaming,
        )

        try:
            model_kwargs: dict[str, Any] = {
                "google_api_key": self._api_key,
                "model": self.model,
                "temperature": temperature,
                **kwargs,
            }

            if max_tokens is not None:
                model_kwargs["max_output_tokens"] = max_tokens

            chat_model = ChatGoogleGenerativeAI(**model_kwargs)

            logger.debug("gemini_chat_model_created", model=self.model)
            return chat_model

        except Exception as e:
            logger.error(
                "gemini_chat_model_creation_failed",
                model=self.model,
                error=str(e),
            )
            raise LLMError(
                f"Failed to create Gemini chat model: {e}",
                provider="gemini",
                model=self.model,
                cause=e,
            ) from e

    def validate_connection(self) -> bool:
        """
        Validate Gemini API connection.

        Returns:
            bool: True if connection is valid.

        Raises:
            LLMError: If validation fails.
        """
        logger.debug("validating_gemini_connection", model=self.model)

        try:
            chat_model = self.get_chat_model(temperature=0, streaming=False)

            if chat_model is not None:
                logger.info("gemini_connection_valid", model=self.model)
                return True

            return False

        except Exception as e:
            logger.error(
                "gemini_connection_validation_failed",
                model=self.model,
                error=str(e),
            )
            raise LLMError(
                f"Gemini connection validation failed: {e}",
                provider="gemini",
                model=self.model,
                cause=e,
            ) from e
