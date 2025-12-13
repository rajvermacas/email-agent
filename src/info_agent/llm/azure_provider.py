"""
Azure OpenAI LLM Provider implementation.

Provides integration with Azure OpenAI Service using langchain-openai.
"""

from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import AzureChatOpenAI

from info_agent.llm.base import BaseLLMProvider
from info_agent.utils.exceptions import LLMError, LLMProviderNotFoundError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class AzureOpenAIProvider(BaseLLMProvider):
    """
    Azure OpenAI LLM provider using Azure OpenAI Service.

    Requires an Azure OpenAI resource with a deployed model.
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment_name: str,
        model: str,
        api_version: str = "2024-02-01",
    ) -> None:
        """
        Initialize the Azure OpenAI provider.

        Args:
            api_key: Azure OpenAI API key.
            endpoint: Azure OpenAI endpoint URL.
            deployment_name: Name of the deployed model in Azure.
            model: Model identifier for reference.
            api_version: Azure OpenAI API version.

        Raises:
            LLMProviderNotFoundError: If required parameters are missing.
        """
        missing = []
        if not api_key:
            missing.append("api_key")
        if not endpoint:
            missing.append("endpoint")
        if not deployment_name:
            missing.append("deployment_name")

        if missing:
            logger.error(
                "azure_provider_init_failed",
                reason="missing_parameters",
                missing=missing,
            )
            raise LLMProviderNotFoundError(
                f"Azure OpenAI requires: {', '.join(missing)}",
                provider="azure_openai",
            )

        super().__init__(model)
        self._api_key = api_key
        self._endpoint = endpoint
        self._deployment_name = deployment_name
        self._api_version = api_version

        logger.info(
            "azure_provider_created",
            endpoint=endpoint,
            deployment_name=deployment_name,
            api_version=api_version,
        )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "azure_openai"

    def get_chat_model(
        self,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        streaming: bool = True,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Get an Azure OpenAI chat model instance.

        Args:
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens in response.
            streaming: Whether to enable streaming.
            **kwargs: Additional arguments passed to AzureChatOpenAI.

        Returns:
            AzureChatOpenAI: LangChain Azure OpenAI chat model.

        Raises:
            LLMError: If model creation fails.
        """
        logger.debug(
            "creating_azure_chat_model",
            deployment=self._deployment_name,
            temperature=temperature,
            streaming=streaming,
        )

        try:
            model_kwargs = {
                "api_key": self._api_key,
                "azure_endpoint": self._endpoint,
                "azure_deployment": self._deployment_name,
                "api_version": self._api_version,
                "temperature": temperature,
                "streaming": streaming,
                **kwargs,
            }

            if max_tokens is not None:
                model_kwargs["max_tokens"] = max_tokens

            chat_model = AzureChatOpenAI(**model_kwargs)

            logger.debug(
                "azure_chat_model_created",
                deployment=self._deployment_name,
            )
            return chat_model

        except Exception as e:
            logger.error(
                "azure_chat_model_creation_failed",
                deployment=self._deployment_name,
                error=str(e),
            )
            raise LLMError(
                f"Failed to create Azure OpenAI chat model: {e}",
                provider="azure_openai",
                model=self._deployment_name,
                cause=e,
            ) from e

    def validate_connection(self) -> bool:
        """
        Validate Azure OpenAI connection.

        Returns:
            bool: True if connection is valid.

        Raises:
            LLMError: If validation fails.
        """
        logger.debug(
            "validating_azure_connection",
            deployment=self._deployment_name,
        )

        try:
            chat_model = self.get_chat_model(temperature=0, streaming=False)

            if chat_model is not None:
                logger.info(
                    "azure_connection_valid",
                    deployment=self._deployment_name,
                )
                return True

            return False

        except Exception as e:
            logger.error(
                "azure_connection_validation_failed",
                deployment=self._deployment_name,
                error=str(e),
            )
            raise LLMError(
                f"Azure OpenAI connection validation failed: {e}",
                provider="azure_openai",
                model=self._deployment_name,
                cause=e,
            ) from e
