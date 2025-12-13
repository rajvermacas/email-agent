"""
LangGraph workflow graph definition.

This module defines the Supervisor Agent's workflow graph using LangGraph.
The workflow orchestrates the information retrieval process from parsing
instructions to collecting email responses.
"""

from typing import Any

from langgraph.graph import END, StateGraph

from info_agent.utils.logging import get_logger
from info_agent.workflow.checkpointer import compile_workflow_with_checkpointer
from info_agent.workflow.nodes import (
    check_approval_status,
    check_response_received,
    create_execution_plan,
    determine_next_action,
    execute_current_step,
    handle_email_response,
    invoke_mail_agent_send,
    parse_input_files,
    query_a2a_registry,
    wait_for_email_response,
    wait_for_user_approval,
)
from info_agent.workflow.state import SupervisorState

logger = get_logger(__name__)


def create_workflow_graph() -> StateGraph:
    """
    Create the LangGraph workflow graph for the Supervisor Agent.

    The workflow follows this general flow:
    1. Parse input instruction files
    2. Query A2A registry for available agents
    3. Generate execution plan
    4. Wait for user approval
    5. Execute plan (send email, wait for response)
    6. Process received response

    Returns:
        StateGraph: Configured workflow graph (not yet compiled).
    """
    logger.info("Creating workflow graph")

    # Create the workflow graph with state schema
    workflow = StateGraph(SupervisorState)

    # Add nodes
    logger.debug("Adding workflow nodes")

    workflow.add_node("parse_inputs", parse_input_files)
    workflow.add_node("lookup_agents", query_a2a_registry)
    workflow.add_node("generate_plan", create_execution_plan)
    workflow.add_node("await_approval", wait_for_user_approval)
    workflow.add_node("execute_step", execute_current_step)
    workflow.add_node("send_email", invoke_mail_agent_send)
    workflow.add_node("wait_response", wait_for_email_response)
    workflow.add_node("process_response", handle_email_response)

    logger.debug("Workflow nodes added: 8 nodes")

    # Set entry point
    workflow.set_entry_point("parse_inputs")
    logger.debug("Entry point set to 'parse_inputs'")

    # Define edges
    logger.debug("Adding workflow edges")

    # Linear flow from start to plan generation
    workflow.add_edge("parse_inputs", "lookup_agents")
    workflow.add_edge("lookup_agents", "generate_plan")
    workflow.add_edge("generate_plan", "await_approval")

    # Conditional routing after approval
    workflow.add_conditional_edges(
        "await_approval",
        check_approval_status,
        {
            "approved": "execute_step",
            "rejected": "generate_plan",  # Re-generate plan
            "cancelled": END,
        },
    )

    # Conditional routing based on step action
    workflow.add_conditional_edges(
        "execute_step",
        determine_next_action,
        {
            "send_email": "send_email",
            "wait_response": "wait_response",
            "complete": END,
        },
    )

    # After sending email, wait for response
    workflow.add_edge("send_email", "wait_response")

    # Conditional routing when waiting for response
    workflow.add_conditional_edges(
        "wait_response",
        check_response_received,
        {
            "received": "process_response",
            "waiting": "wait_response",  # Keep waiting
        },
    )

    # Final processing leads to completion
    workflow.add_edge("process_response", END)

    logger.info("Workflow graph created successfully")

    return workflow


def compile_workflow(db_path: str | None = None) -> Any:
    """
    Compile the workflow with SQLite checkpointing.

    Args:
        db_path: Optional path to checkpoint database.
                 If not provided, uses config setting.

    Returns:
        Compiled LangGraph workflow with checkpointing.
    """
    logger.info("Compiling workflow")

    # Get db_path from settings if not provided
    if db_path is None:
        from info_agent.config import get_settings
        settings = get_settings()
        db_path = settings.checkpoint_db_path

    # Create and compile the workflow
    workflow = create_workflow_graph()
    compiled = compile_workflow_with_checkpointer(workflow, db_path)

    logger.info("Workflow compiled successfully", db_path=db_path)

    return compiled


# Module-level compiled workflow singleton
_compiled_workflow: Any = None


def get_compiled_workflow() -> Any:
    """
    Get the compiled workflow singleton.

    Returns:
        Compiled workflow instance.
    """
    global _compiled_workflow

    if _compiled_workflow is None:
        logger.info("Initializing compiled workflow singleton")
        _compiled_workflow = compile_workflow()

    return _compiled_workflow


def reset_compiled_workflow() -> None:
    """Reset the compiled workflow singleton. Useful for testing."""
    global _compiled_workflow
    logger.debug("Resetting compiled workflow singleton")
    _compiled_workflow = None


async def run_workflow(
    workflow_id: str,
    initial_state: SupervisorState,
    compiled_workflow: Any | None = None,
) -> SupervisorState:
    """
    Run the workflow with given initial state.

    Args:
        workflow_id: Unique identifier for this workflow run.
        initial_state: Initial state to start the workflow.
        compiled_workflow: Optional compiled workflow to use.
                          If not provided, uses the singleton.

    Returns:
        Final state after workflow execution.
    """
    logger.info(f"Running workflow {workflow_id}")

    if compiled_workflow is None:
        compiled_workflow = get_compiled_workflow()

    config = {"configurable": {"thread_id": workflow_id}}

    logger.debug(f"Invoking workflow {workflow_id}")
    result = await compiled_workflow.ainvoke(initial_state, config)

    logger.info(
        f"Workflow {workflow_id} reached state: {result.get('status', 'unknown')}"
    )

    return result


async def resume_workflow(
    workflow_id: str,
    updates: dict[str, Any] | None = None,
    compiled_workflow: Any | None = None,
) -> SupervisorState:
    """
    Resume a paused workflow with optional state updates.

    This is used to continue a workflow after external events
    (e.g., user approval, email received).

    Args:
        workflow_id: Workflow to resume.
        updates: Optional state updates to apply.
        compiled_workflow: Optional compiled workflow to use.

    Returns:
        Final state after resumption.
    """
    logger.info(f"Resuming workflow {workflow_id}")

    if compiled_workflow is None:
        compiled_workflow = get_compiled_workflow()

    config = {"configurable": {"thread_id": workflow_id}}

    # Get current state
    current_state = compiled_workflow.get_state(config)
    if not current_state or not current_state.values:
        logger.error(f"No state found for workflow {workflow_id}")
        raise ValueError(f"Workflow {workflow_id} not found")

    state = dict(current_state.values)

    # Apply updates if provided
    if updates:
        logger.debug(f"Applying updates to workflow {workflow_id}: {list(updates.keys())}")
        state.update(updates)

    # Resume workflow
    logger.debug(f"Resuming workflow {workflow_id} from current state")
    result = await compiled_workflow.ainvoke(state, config)

    logger.info(
        f"Workflow {workflow_id} resumed, now at state: {result.get('status', 'unknown')}"
    )

    return result
