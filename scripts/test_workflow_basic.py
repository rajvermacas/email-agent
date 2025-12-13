#!/usr/bin/env python
"""
Basic workflow test script.

This script tests the basic workflow components to verify
the system is working correctly.

Usage:
    python scripts/test_workflow_basic.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


async def test_config() -> bool:
    """Test configuration loading."""
    print("\n=== Testing Configuration ===")
    try:
        from info_agent.config import get_settings

        settings = get_settings()
        print(f"  Host: {settings.host}")
        print(f"  Port: {settings.port}")
        print(f"  Debug: {settings.debug}")
        print(f"  Log Level: {settings.log_level}")
        print("  ✓ Configuration OK")
        return True
    except Exception as e:
        print(f"  ✗ Configuration Error: {e}")
        return False


async def test_logging() -> bool:
    """Test logging setup."""
    print("\n=== Testing Logging ===")
    try:
        from info_agent.utils.logging import get_logger, setup_logging

        setup_logging(level="INFO", log_format="console", service_name="test")
        logger = get_logger(__name__)
        logger.info("Test log message")
        print("  ✓ Logging OK")
        return True
    except Exception as e:
        print(f"  ✗ Logging Error: {e}")
        return False


async def test_workflow_state() -> bool:
    """Test workflow state creation."""
    print("\n=== Testing Workflow State ===")
    try:
        from info_agent.workflow.state import create_initial_state, WorkflowStatus

        state = create_initial_state(
            workflow_id="test-001",
            workflow_name="Test Workflow",
            instructions="Test instructions",
            instructions_filename="test.txt",
        )

        assert state["workflow_id"] == "test-001"
        assert state["status"] == WorkflowStatus.CREATED.value
        assert len(state["audit_log"]) == 1
        print(f"  Workflow ID: {state['workflow_id']}")
        print(f"  Status: {state['status']}")
        print(f"  Audit Log Entries: {len(state['audit_log'])}")
        print("  ✓ Workflow State OK")
        return True
    except Exception as e:
        print(f"  ✗ Workflow State Error: {e}")
        return False


async def test_workflow_graph() -> bool:
    """Test workflow graph creation."""
    print("\n=== Testing Workflow Graph ===")
    try:
        from info_agent.workflow.graph import create_workflow_graph

        graph = create_workflow_graph()
        print(f"  Graph Type: {type(graph).__name__}")
        print("  ✓ Workflow Graph OK")
        return True
    except Exception as e:
        print(f"  ✗ Workflow Graph Error: {e}")
        return False


async def test_a2a_models() -> bool:
    """Test A2A models creation."""
    print("\n=== Testing A2A Models ===")
    try:
        from info_agent.a2a import AgentSkill, AgentCard

        skill = AgentSkill(
            id="test-skill",
            name="Test Skill",
            description="A test skill",
            input_schema={"type": "object", "properties": {}},
        )

        card = AgentCard(
            name="test-agent",
            description="Test agent",
            version="1.0.0",
            url="http://localhost:8001/a2a",
            capabilities={},
            skills=[skill],
            defaultInputModes=["text"],
            defaultOutputModes=["text"],
        )

        print(f"  Agent Name: {card.name}")
        print(f"  Skills: {len(card.skills)}")
        print("  ✓ A2A Models OK")
        return True
    except Exception as e:
        print(f"  ✗ A2A Models Error: {e}")
        return False


async def test_email_models() -> bool:
    """Test email models creation."""
    print("\n=== Testing Email Models ===")
    try:
        from datetime import datetime, timezone

        from info_agent.email import StoredEmail

        email = StoredEmail(
            id="msg-test-001",
            inbox="test@example.com",
            from_address="sender@example.com",
            to_address="test@example.com",
            subject="Test Email",
            body_text="This is a test email body.",
            received_at=datetime.now(timezone.utc),
        )

        print(f"  Message ID: {email.id}")
        print(f"  Subject: {email.subject}")
        print("  ✓ Email Models OK")
        return True
    except Exception as e:
        print(f"  ✗ Email Models Error: {e}")
        return False


async def test_api_models() -> bool:
    """Test API models creation."""
    print("\n=== Testing API Models ===")
    try:
        from info_agent.api.models.requests import CreateWorkflowRequest
        from info_agent.api.models.responses import WorkflowResponse, WorkflowStatus

        request = CreateWorkflowRequest(
            workflow_name="Test Workflow",
            instructions="Test instructions for workflow",
        )

        print(f"  Request Name: {request.workflow_name}")
        print(f"  Status Enum Values: {[s.value for s in WorkflowStatus]}")
        print("  ✓ API Models OK")
        return True
    except Exception as e:
        print(f"  ✗ API Models Error: {e}")
        return False


async def main() -> None:
    """Run all tests."""
    print("=" * 60)
    print("Info-Agent Basic Component Tests")
    print("=" * 60)

    results = []

    # Run tests
    results.append(await test_config())
    results.append(await test_logging())
    results.append(await test_workflow_state())
    results.append(await test_workflow_graph())
    results.append(await test_a2a_models())
    results.append(await test_email_models())
    results.append(await test_api_models())

    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
