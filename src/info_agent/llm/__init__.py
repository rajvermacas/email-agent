"""
LLM Integration Module for Info-Agent.

This module provides LLM (Large Language Model) integration using Google's Gemini
via LangChain. It implements a provider pattern with lazy initialization and
singleton factory functions for efficient resource usage.

Key Components:
    - GeminiProvider: Wrapper for Gemini LLM with lazy initialization
    - Factory functions: Singleton pattern for LLM instance management

Usage:
    from info_agent.llm import get_gemini_llm

    # Get the configured LLM instance
    llm = get_gemini_llm()

    # Use with LangChain
    response = await llm.ainvoke("Generate a plan to collect information")

    # For testing, reset the singleton
    from info_agent.llm import reset_llm_instance
    reset_llm_instance()
"""

from info_agent.llm.factory import (
    get_gemini_llm,
    is_llm_initialized,
    reset_llm_instance,
)
from info_agent.llm.gemini_provider import GeminiProvider

__all__ = [
    # Provider class
    "GeminiProvider",
    # Factory functions
    "get_gemini_llm",
    "reset_llm_instance",
    "is_llm_initialized",
]
