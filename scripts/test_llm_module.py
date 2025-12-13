#!/usr/bin/env python3
"""
Test script for the LLM module.

This script demonstrates the usage of the LLM module and can be used
to verify that the Gemini API key is configured correctly.

Usage:
    python scripts/test_llm_module.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from info_agent.config import get_settings
from info_agent.llm import get_gemini_llm, is_llm_initialized, reset_llm_instance
from info_agent.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def test_llm_basic():
    """Test basic LLM functionality."""
    logger.info("Testing basic LLM functionality")

    try:
        # Get LLM instance
        logger.info("Getting LLM instance")
        llm = get_gemini_llm()
        logger.info("LLM instance obtained successfully", initialized=is_llm_initialized())

        # Test a simple prompt
        logger.info("Sending test prompt to LLM")
        prompt = "Say 'Hello from Info-Agent LLM module!' and nothing else."
        response = await llm.ainvoke(prompt)

        logger.info("Received response from LLM", response_length=len(response.content))
        print(f"\n{'=' * 60}")
        print("LLM Response:")
        print(f"{'=' * 60}")
        print(response.content)
        print(f"{'=' * 60}\n")

        return True

    except Exception as e:
        logger.error("LLM test failed", error=str(e), error_type=type(e).__name__)
        print(f"\nError: {e}\n")
        return False


async def test_llm_with_overrides():
    """Test LLM with custom parameters."""
    logger.info("Testing LLM with custom parameters")

    try:
        # Get LLM with high temperature for creative output
        logger.info("Getting LLM with temperature=0.9")
        llm = get_gemini_llm(temperature=0.9)

        prompt = "Generate a creative metaphor about AI agents working together."
        logger.info("Sending creative prompt to LLM")
        response = await llm.ainvoke(prompt)

        logger.info("Received creative response", response_length=len(response.content))
        print(f"\n{'=' * 60}")
        print("Creative Response (temperature=0.9):")
        print(f"{'=' * 60}")
        print(response.content)
        print(f"{'=' * 60}\n")

        return True

    except Exception as e:
        logger.error("LLM test with overrides failed", error=str(e))
        return False


async def main():
    """Main test function."""
    # Setup logging
    setup_logging(level="INFO", log_format="console")

    logger.info("Starting LLM module tests")
    logger.info("=" * 60)

    # Load and display settings
    try:
        settings = get_settings()
        logger.info(
            "Settings loaded",
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
    except Exception as e:
        logger.error("Failed to load settings", error=str(e))
        print(f"\nError: {e}")
        print("\nMake sure you have a valid .env file with GOOGLE_API_KEY set.")
        print("See .env.example for reference.\n")
        return 1

    # Run tests
    results = []

    print("\n" + "=" * 60)
    print("Test 1: Basic LLM Functionality")
    print("=" * 60)
    results.append(await test_llm_basic())

    print("\n" + "=" * 60)
    print("Test 2: LLM with Custom Parameters")
    print("=" * 60)
    results.append(await test_llm_with_overrides())

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"LLM Initialized: {is_llm_initialized()}")
    print("=" * 60 + "\n")

    # Cleanup
    logger.info("Cleaning up - resetting LLM instance")
    reset_llm_instance()
    logger.info("LLM instance reset", initialized=is_llm_initialized())

    return 0 if all(results) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
