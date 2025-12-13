#!/usr/bin/env python3
"""Demo script for Info-Agent workflow.

This script demonstrates the complete workflow from creation
through validation completion using the mock email backend.

Usage:
    python scripts/demo_workflow.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from info_agent.a2a.registry import get_registry, reset_registry
from info_agent.mail_agent.agent import MailAgent, get_mail_agent, reset_mail_agent
from info_agent.supervisor.agent import SupervisorAgent
from info_agent.validation_agent.agent import (
    ValidationAgent,
    get_validation_agent,
    reset_validation_agent,
)


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

    # Reset any previous state
    reset_registry()
    reset_mail_agent()
    reset_validation_agent()

    # Step 1: Create the supervisor agent
    logger.info("\n[Step 1] Creating Supervisor Agent...")
    supervisor = SupervisorAgent(
        use_llm=False,  # Use stub mode
        use_stub_delegator=True,
    )
    logger.info("Supervisor Agent created")

    # Step 2: Create a new workflow
    logger.info("\n[Step 2] Creating New Workflow...")
    workflow_result = await supervisor.create_workflow(
        instructions="Send an email to raj@example.com asking for an Excel file "
        "containing 10 rows of food recipes with columns: Recipe Name, "
        "Ingredients, Cooking Time, and Difficulty Level.",
        target_email="raj@example.com",
        faq=[
            {
                "question": "What format should the recipes be in?",
                "answer": "Please provide an Excel file (.xlsx) with the specified columns.",
            },
            {
                "question": "How many recipes are needed?",
                "answer": "We need exactly 10 recipes.",
            },
        ],
        escalation_rules={
            "no_response_hours": 48,
            "escalation_email": "manager@example.com",
        },
        validation_criteria={
            "required_format": "xlsx",
            "required_columns": [
                "Recipe Name",
                "Ingredients",
                "Cooking Time",
                "Difficulty Level",
            ],
            "min_rows": 10,
        },
    )

    workflow_id = workflow_result["workflow_id"]
    logger.info(f"Workflow created: {workflow_id}")
    logger.info(f"Initial status: {workflow_result['status']}")

    # Step 3: Get workflow status
    logger.info("\n[Step 3] Getting Workflow Status...")
    status = await supervisor.get_workflow_status(workflow_id)
    logger.info(f"Status: {status}")

    # Step 4: Approve the plan
    logger.info("\n[Step 4] Approving Execution Plan...")
    await supervisor.approve_plan(workflow_id, approved=True)
    logger.info("Plan approved")

    # Step 5: Check status after approval
    logger.info("\n[Step 5] Checking Status After Approval...")
    status = await supervisor.get_workflow_status(workflow_id)
    logger.info(f"Status after approval: {status.get('status')}")

    # Step 6: Simulate receiving an email response
    logger.info("\n[Step 6] Simulating Email Response...")
    await supervisor.notify_email_received(
        workflow_id=workflow_id,
        email={
            "from_address": "raj@example.com",
            "to_address": "agent@example.com",
            "subject": "Re: Recipe Request",
            "body": "Hi,\n\nPlease find attached the recipes as requested.\n\nBest,\nRaj",
            "timestamp": datetime.utcnow().isoformat(),
            "attachments": [
                {
                    "filename": "recipes.xlsx",
                    "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "size": 15360,
                }
            ],
        },
    )
    logger.info("Email response received and processed")

    # Step 7: Check final status
    logger.info("\n[Step 7] Checking Final Status...")
    final_status = await supervisor.get_workflow_status(workflow_id)
    logger.info(f"Final status: {final_status}")

    # Step 8: List all workflows
    logger.info("\n[Step 8] Listing All Workflows...")
    workflows = await supervisor.list_workflows()
    logger.info(f"Total workflows: {len(workflows)}")
    for wf in workflows:
        logger.info(f"  - {wf['workflow_id']}: {wf['status']}")

    # Cleanup
    logger.info("\n[Cleanup] Closing resources...")
    await supervisor.close()

    logger.info("\n" + "=" * 60)
    logger.info("Demo Complete!")
    logger.info("=" * 60)


async def run_clarification_demo() -> None:
    """Run demo showing clarification handling."""
    logger.info("\n" + "=" * 60)
    logger.info("Info-Agent Clarification Demo")
    logger.info("=" * 60)

    # Reset state
    reset_registry()
    reset_mail_agent()
    reset_validation_agent()

    # Create supervisor
    supervisor = SupervisorAgent(
        use_llm=False,
        use_stub_delegator=True,
    )

    # Create workflow
    logger.info("\n[Step 1] Creating Workflow...")
    result = await supervisor.create_workflow(
        instructions="Request sales report from accounting",
        target_email="accounting@example.com",
        faq=[
            {
                "question": "Which quarter?",
                "answer": "Q4 2024",
            },
        ],
    )
    workflow_id = result["workflow_id"]
    logger.info(f"Workflow created: {workflow_id}")

    # Approve plan
    logger.info("\n[Step 2] Approving Plan...")
    await supervisor.approve_plan(workflow_id, approved=True)

    # Simulate clarification question
    logger.info("\n[Step 3] Simulating Clarification Request...")
    await supervisor.notify_email_received(
        workflow_id=workflow_id,
        email={
            "from_address": "accounting@example.com",
            "subject": "Question about report",
            "body": "Which quarter do you need the report for?",
        },
    )
    logger.info("Clarification question received")

    # Check status
    status = await supervisor.get_workflow_status(workflow_id)
    logger.info(f"Status: {status}")

    # Cleanup
    await supervisor.close()

    logger.info("\n" + "=" * 60)
    logger.info("Clarification Demo Complete!")
    logger.info("=" * 60)


def main() -> None:
    """Main entry point."""
    logger.info("Starting Info-Agent Demo")

    # Run main demo
    asyncio.run(run_demo())

    # Run clarification demo
    asyncio.run(run_clarification_demo())


if __name__ == "__main__":
    main()
