"""
LLM Provider Abstraction for Info-Agent.

This module provides a unified interface for multiple LLM providers:
- OpenAI
- Azure OpenAI
- Google Gemini
- OpenRouter

Usage:
    from info_agent.llm import create_llm_provider, BaseLLMProvider

    provider = create_llm_provider(settings)
    chat_model = provider.get_chat_model(temperature=0)
    response = await chat_model.ainvoke([HumanMessage(content="Hello")])
"""

from info_agent.llm.base import BaseLLMProvider
from info_agent.llm.factory import create_llm_provider, get_available_providers

__all__ = [
    "BaseLLMProvider",
    "create_llm_provider",
    "get_available_providers",
]
