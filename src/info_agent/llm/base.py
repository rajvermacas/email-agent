"""
Base LLM Provider interface.

This module defines the abstract base class that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel

from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers (OpenAI, Azure, Gemini, OpenRouter) must inherit from this
    class and implement the required methods.
    """

    def __init__(self, model: str) -> None:
        """
        Initialize the provider.

        Args:
            model: Model identifier for this provider.
        """
        self.model = model
        logger.debug(
            "llm_provider_initialized",
            provider=self.__class__.__name__,
            model=model,
        )

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'azure_openai')."""
        pass

    @abstractmethod
    def get_chat_model(
        self,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        streaming: bool = True,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Get a LangChain chat model instance.

        Args:
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens in response (None = model default).
            streaming: Whether to enable streaming responses.
            **kwargs: Additional provider-specific arguments.

        Returns:
            BaseChatModel: A LangChain chat model instance.

        Raises:
            LLMError: If the model cannot be created.
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """
        Validate that the provider is properly configured and reachable.

        Returns:
            bool: True if connection is valid.

        Raises:
            LLMError: If validation fails.
        """
        pass

    def __repr__(self) -> str:
        """Return string representation."""
        return f"{self.__class__.__name__}(model={self.model!r})"
