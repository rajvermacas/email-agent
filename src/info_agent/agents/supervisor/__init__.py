"""
Supervisor Agent module for Info-Agent.

This module implements the Supervisor Agent, the main orchestrator for
information retrieval workflows. It coordinates the entire workflow lifecycle
from plan generation to email communication and response processing.

Components:
    - SupervisorAgent: Main agent class for workflow orchestration
    - ExecutionPlanner: LLM-based plan generator
    - State types and helpers: Workflow state management utilities

The Supervisor Agent uses LangGraph for state management and workflow
orchestration, with SQLite-based checkpointing for persistence and
fault tolerance.

Usage:
    from info_agent.agents.supervisor import SupervisorAgent

    # Initialize the agent
    agent = SupervisorAgent()

    # Create a new workflow
    workflow_id = await agent.create_workflow(
        workflow_name="Collect Q3 Reports",
        instructions="Request Q3 2024 financial reports from john@example.com",
        instructions_filename="request.txt"
    )

    # Get current state
    state = await agent.get_workflow_state(workflow_id)

    # Approve the plan
    await agent.approve_plan(workflow_id)

    # Handle incoming email response
    await agent.handle_email_received(
        workflow_id=workflow_id,
        email_id="msg-123",
        subject="Re: Information Request",
        body="Here are the reports...",
        sender="john@example.com"
    )

Example - Plan Generation:
    from info_agent.agents.supervisor import ExecutionPlanner

    planner = ExecutionPlanner()
    plan_data = await planner.generate_plan(
        target_email="john@example.com",
        target_name="John Doe",
        requested_info="Q3 2024 financial reports"
    )

Example - State Management:
    from info_agent.agents.supervisor import (
        SupervisorState,
        WorkflowStatus,
        create_initial_state,
        add_audit_entry
    )

    # Create initial state
    state = create_initial_state(
        workflow_id="wf-123",
        workflow_name="Test Workflow",
        instructions="Test instructions",
        instructions_filename="test.txt"
    )

    # Add audit entry
    new_audit_log = add_audit_entry(
        state,
        action="test_action",
        details="Test action performed",
        metadata={"key": "value"}
    )
"""

from info_agent.agents.supervisor.agent import SupervisorAgent
from info_agent.agents.supervisor.planner import (
    ExecutionPlanner,
    generate_email_content,
)
from info_agent.agents.supervisor.state import (
    AuditLogEntry,
    EmailAttachment,
    PlanStep,
    SupervisorState,
    WorkflowStatus,
    add_audit_entry,
    create_initial_state,
)

__all__ = [
    # Main agent
    "SupervisorAgent",
    # Planning
    "ExecutionPlanner",
    "generate_email_content",
    # State management
    "SupervisorState",
    "WorkflowStatus",
    "PlanStep",
    "EmailAttachment",
    "AuditLogEntry",
    "create_initial_state",
    "add_audit_entry",
]
