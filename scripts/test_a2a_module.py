#!/usr/bin/env python
"""
Quick test script for A2A module implementation.

This script tests basic functionality of the A2A module components.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def test_models():
    """Test A2A model creation and validation."""
    from info_agent.a2a import AgentSkill, AgentCard, A2ATaskRequest, A2ATaskResponse

    print("\n=== Testing Models ===")

    # Test AgentSkill
    skill = AgentSkill(
        id="convert_currency",
        name="Convert Currency",
        description="Converts between currencies",
        input_schema={
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "from": {"type": "string"},
                "to": {"type": "string"},
            },
            "required": ["amount", "from", "to"],
        },
        example_prompts=["Convert 100 USD to EUR"],
    )
    print(f"✓ AgentSkill created: {skill.name}")

    # Test AgentCard
    card = AgentCard(
        name="currency-agent",
        description="Currency conversion agent",
        version="1.0.0",
        url="http://localhost:8001/a2a",
        capabilities={"async": True, "streaming": False},
        skills=[skill],
        defaultInputModes=["text", "data"],
        defaultOutputModes=["text", "data"],
    )
    print(f"✓ AgentCard created: {card.name} v{card.version}")

    # Test A2ATaskRequest
    task_request = A2ATaskRequest(
        task_id="task-123",
        skill_id="convert_currency",
        payload={"amount": 100, "from": "USD", "to": "EUR"},
    )
    print(f"✓ A2ATaskRequest created: {task_request.task_id}")

    # Test A2ATaskResponse
    task_response = A2ATaskResponse(
        task_id="task-123",
        status="completed",
        result={"converted_amount": 92.0, "rate": 0.92},
    )
    print(f"✓ A2ATaskResponse created: {task_response.status}")

    return card


async def test_storage(agent_card):
    """Test A2A storage operations."""
    from info_agent.a2a import A2AStorage

    print("\n=== Testing Storage ===")

    # Use temporary database
    storage = A2AStorage(db_path="/tmp/test_a2a_registry.db")
    await storage.init_db()
    print("✓ Storage initialized")

    # Save agent
    await storage.save_agent(agent_card)
    print(f"✓ Agent saved: {agent_card.name}")

    # Get agent
    retrieved = await storage.get_agent(agent_card.name)
    print(f"✓ Agent retrieved: {retrieved.name}")

    # List agents
    agents = await storage.list_agents()
    print(f"✓ Agents listed: {len(agents)} agent(s)")

    # Delete agent
    await storage.delete_agent(agent_card.name)
    print(f"✓ Agent deleted: {agent_card.name}")

    # Clean up
    Path("/tmp/test_a2a_registry.db").unlink(missing_ok=True)


async def test_client():
    """Test A2A client creation."""
    from info_agent.a2a import A2AClient

    print("\n=== Testing Client ===")

    client = A2AClient("http://localhost:8001/a2a")
    print(f"✓ A2AClient created: {client.base_url}")
    print(f"✓ Timeout configured: {client.timeout}s")


async def main():
    """Run all tests."""
    print("Testing A2A Module Implementation")
    print("=" * 50)

    try:
        # Test models
        agent_card = await test_models()

        # Test storage
        await test_storage(agent_card)

        # Test client
        await test_client()

        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
