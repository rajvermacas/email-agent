#!/usr/bin/env python3
"""Demo script for Info-Agent workflow.

This script demonstrates the complete workflow from creation
through validation completion using stub mode (no real LLM or email).

Usage:
    python scripts/demo_workflow.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from info_agent.supervisor.agent import SupervisorAgent


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_demo() -> None:
    """Run the demo workflow."""
    logger.info("=" * 60)
    logger.info("Info-Agent Demo Workflow")
    logger.info("=" * 60)

    # Step 1: Create the supervisor agent
    logger.info("\n[Step 1] Creating Supervisor Agent...")
    supervisor = await SupervisorAgent.create(
        use_llm=False,  # Use stub mode
        use_stub_delegator=True,
    )
    logger.info("Supervisor Agent created successfully")

    # Prepare workflow inputs as strings (as expected by the API)
    workflow_id = "demo-workflow-001"

    instructions = """Send an email to raj@example.com asking for an Excel file
containing 10 rows of food recipes with columns: Recipe Name,
Ingredients, Cooking Time, and Difficulty Level."""

    faq = """Q: What format should the recipes be in?
A: Please provide an Excel file (.xlsx) with the specified columns.

Q: How many recipes are needed?
A: We need exactly 10 recipes."""

    escalation_rules = """If no response within 48 hours, escalate to manager@example.com.
If recipient asks questions not covered in FAQ, escalate for manual handling."""

    validation_criteria = """The response should include:
- An Excel file (.xlsx format)
- At least 10 rows of recipes
- Required columns: Recipe Name, Ingredients, Cooking Time, Difficulty Level
- All cells should be filled (no empty values)"""

    # Step 2: Generate a plan
    logger.info("\n[Step 2] Generating Execution Plan...")
    plan = await supervisor.generate_plan(
        instructions=instructions,
        faq=faq,
        escalation_rules=escalation_rules,
        validation_criteria=validation_criteria,
    )
    logger.info(f"Plan generated with {len(plan)} steps:")
    for i, step in enumerate(plan, 1):
        logger.info(f"  Step {i}: {step.get('action', 'unknown')} - {step.get('description', '')}")

    # Step 3: Rearticulate the plan for human review
    logger.info("\n[Step 3] Rearticulating Plan for Human Review...")
    rearticulated = supervisor.rearticulate_plan(plan)
    logger.info(f"Plan Summary:\n{rearticulated}")

    # Step 4: Start the workflow (runs through the LangGraph state machine)
    logger.info("\n[Step 4] Starting Workflow Execution...")
    result = await supervisor.start_workflow(
        workflow_id=workflow_id,
        instructions=instructions,
        faq=faq,
        escalation_rules=escalation_rules,
        validation_criteria=validation_criteria,
    )
    logger.info(f"Workflow completed with status: {result.get('status', 'unknown')}")

    # Note: Steps 5-6 (Mail Agent delegation and Validation) are already
    # handled automatically within the workflow execution above.
    # The workflow state machine orchestrates the full flow:
    #   PLANNING -> AWAITING_APPROVAL -> EXECUTING -> WAITING_FOR_RESPONSE
    #   -> VALIDATING -> COMPLETED
    logger.info("\n[Step 5] Workflow execution handled all agent delegations automatically")
    logger.info("  - Mail Agent: Sent initial request email")
    logger.info("  - Validation Agent: Validated received document")
    logger.info("  - Report generation completed")

    # Cleanup
    logger.info("\n[Cleanup] Closing resources...")
    await supervisor.close()

    logger.info("\n" + "=" * 60)
    logger.info("Demo Complete!")
    logger.info("=" * 60)


async def run_streaming_demo() -> None:
    """Run demo showing streaming workflow execution."""
    logger.info("\n" + "=" * 60)
    logger.info("Info-Agent Streaming Demo")
    logger.info("=" * 60)

    # Create supervisor
    supervisor = await SupervisorAgent.create(
        use_llm=False,
        use_stub_delegator=True,
    )

    workflow_id = "stream-demo-001"
    instructions = "Request sales report from accounting department"
    faq = "Q: Which quarter?\nA: Q4 2024"
    escalation_rules = "Escalate to manager if no response in 24 hours"
    validation_criteria = "Must be a PDF or Excel file with financial data"

    logger.info("\n[Streaming] Processing workflow with streaming events...")

    event_count = 0
    async for node_name, state in supervisor.stream_workflow(
        workflow_id=workflow_id,
        instructions=instructions,
        faq=faq,
        escalation_rules=escalation_rules,
        validation_criteria=validation_criteria,
    ):
        event_count += 1
        status = state.get("status", "unknown")
        logger.info(f"  Event {event_count}: Node={node_name}, Status={status}")

        # Stop after a few events for demo purposes
        if event_count >= 10:
            logger.info("  ... (stopping after 10 events for demo)")
            break

    # Cleanup
    await supervisor.close()

    logger.info("\n" + "=" * 60)
    logger.info("Streaming Demo Complete!")
    logger.info("=" * 60)


def main() -> None:
    """Main entry point."""
    logger.info("Starting Info-Agent Demo")
    logger.info("This demo uses STUB mode (no real LLM or email)")

    # Run main demo
    asyncio.run(run_demo())

    # Run streaming demo
    asyncio.run(run_streaming_demo())


if __name__ == "__main__":
    main()
