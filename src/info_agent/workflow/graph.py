"""
LangGraph workflow graph definition for Info-Agent.

This module defines the main workflow graph that orchestrates
the multi-agent information retrieval and validation system.
"""

import logging
from pathlib import Path
from typing import Any, AsyncIterator

from langgraph.graph import END, StateGraph

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from info_agent.workflow.checkpointer import create_checkpointer, create_async_checkpointer
from info_agent.workflow.conditions import (
    check_approval_status,
    check_faq_match,
    check_response_type,
    check_validation_result,
    determine_next_action,
    evaluate_retry_count,
)
from info_agent.workflow.nodes import (
    await_approval_node,
    check_timeout_node,
    escalate_node,
    execute_step_node,
    generate_plan_node,
    handle_clarification_node,
    lookup_agents_node,
    parse_inputs_node,
    report_results_node,
    send_email_node,
    validate_document_node,
    wait_response_node,
)
from info_agent.workflow.state import SupervisorState, create_initial_state

logger = logging.getLogger(__name__)


def create_workflow_graph() -> StateGraph:
    """
    Create the LangGraph workflow graph.

    Returns:
        Configured StateGraph with all nodes and edges.
    """
    logger.info("Creating workflow graph")

    # Create the workflow graph with SupervisorState
    workflow = StateGraph(SupervisorState)

    # Add nodes
    workflow.add_node("parse_inputs", parse_inputs_node)
    workflow.add_node("lookup_agents", lookup_agents_node)
    workflow.add_node("generate_plan", generate_plan_node)
    workflow.add_node("await_approval", await_approval_node)
    workflow.add_node("execute_step", execute_step_node)
    workflow.add_node("send_email", send_email_node)
    workflow.add_node("wait_response", wait_response_node)
    workflow.add_node("handle_clarification", handle_clarification_node)
    workflow.add_node("check_timeout", check_timeout_node)
    workflow.add_node("escalate", escalate_node)
    workflow.add_node("validate_document", validate_document_node)
    workflow.add_node("report_results", report_results_node)

    # Set entry point
    workflow.set_entry_point("parse_inputs")

    # Define linear edges
    workflow.add_edge("parse_inputs", "lookup_agents")
    workflow.add_edge("lookup_agents", "generate_plan")
    workflow.add_edge("generate_plan", "await_approval")

    # Conditional edge: approval check
    workflow.add_conditional_edges(
        "await_approval",
        check_approval_status,
        {
            "approved": "execute_step",
            "rejected": "generate_plan",
            "cancelled": END,
        },
    )

    # Conditional edge: determine next action
    workflow.add_conditional_edges(
        "execute_step",
        determine_next_action,
        {
            "send_email": "send_email",
            "validate": "validate_document",
            "complete": "report_results",
        },
    )

    # After sending email, wait for response
    workflow.add_edge("send_email", "wait_response")

    # Conditional edge: check response type
    workflow.add_conditional_edges(
        "wait_response",
        check_response_type,
        {
            "document_received": "validate_document",
            "clarification_needed": "handle_clarification",
            "timeout": "check_timeout",
            "error": "escalate",
        },
    )

    # Conditional edge: FAQ match check
    workflow.add_conditional_edges(
        "handle_clarification",
        check_faq_match,
        {
            "found_in_faq": "send_email",
            "not_in_faq": "escalate",
        },
    )

    # Conditional edge: retry count check
    workflow.add_conditional_edges(
        "check_timeout",
        evaluate_retry_count,
        {
            "retry": "send_email",
            "escalate": "escalate",
        },
    )

    # After escalation, wait for response
    workflow.add_edge("escalate", "wait_response")

    # Conditional edge: validation result
    workflow.add_conditional_edges(
        "validate_document",
        check_validation_result,
        {
            "passed": "report_results",
            "failed": "report_results",
        },
    )

    # Report results is the final node
    workflow.add_edge("report_results", END)

    logger.info("Workflow graph created successfully")

    return workflow


class InfoAgentWorkflow:
    """
    High-level workflow manager for Info-Agent.

    This class provides a clean interface for running and managing
    Info-Agent workflows with optional checkpointing.

    For workflows with checkpointing from a path, use the async factory method:
        workflow = await InfoAgentWorkflow.create(checkpoint_db_path=path)

    For workflows without checkpointing or with a pre-created checkpointer:
        workflow = InfoAgentWorkflow()  # no checkpointing
        workflow = InfoAgentWorkflow(checkpointer=my_checkpointer)
    """

    def __init__(
        self,
        checkpointer: SqliteSaver | AsyncSqliteSaver | None = None,
    ) -> None:
        """
        Initialize the workflow manager.

        Args:
            checkpointer: Optional pre-configured checkpointer.
                Use InfoAgentWorkflow.create() factory method for path-based initialization.
        """
        logger.info("Initializing InfoAgentWorkflow")

        self._graph = create_workflow_graph()
        self._checkpointer = checkpointer
        self._checkpointer_ctx = None  # Context manager for async checkpointer

        # Compile the workflow
        if self._checkpointer:
            self._app = self._graph.compile(checkpointer=self._checkpointer)
            logger.info("Workflow compiled with checkpointing enabled")
        else:
            self._app = self._graph.compile()
            logger.info("Workflow compiled without checkpointing")

    @classmethod
    async def create(
        cls,
        checkpoint_db_path: str | Path | None = None,
        checkpointer: SqliteSaver | AsyncSqliteSaver | None = None,
    ) -> "InfoAgentWorkflow":
        """
        Async factory method for creating InfoAgentWorkflow with checkpointing.

        Args:
            checkpoint_db_path: Optional path for checkpoint database.
            checkpointer: Optional pre-configured checkpointer.

        Returns:
            Configured InfoAgentWorkflow instance.
        """
        if checkpointer is not None:
            return cls(checkpointer=checkpointer)

        if checkpoint_db_path is not None:
            async_checkpointer, ctx_manager = await create_async_checkpointer(checkpoint_db_path)
            instance = cls(checkpointer=async_checkpointer)
            instance._checkpointer_ctx = ctx_manager
            return instance

        return cls()

    async def close(self) -> None:
        """Close the workflow and release resources."""
        if self._checkpointer_ctx is not None:
            await self._checkpointer_ctx.__aexit__(None, None, None)
            self._checkpointer_ctx = None
            logger.info("Workflow checkpointer closed")

    @property
    def graph(self) -> StateGraph:
        """Get the underlying StateGraph."""
        return self._graph

    @property
    def checkpointer(self) -> SqliteSaver | AsyncSqliteSaver | None:
        """Get the checkpointer if configured."""
        return self._checkpointer

    async def run(
        self,
        workflow_id: str,
        instructions: str,
        faq: str,
        escalation_rules: str,
        validation_criteria: str,
    ) -> SupervisorState:
        """
        Run a workflow to completion.

        Args:
            workflow_id: Unique workflow identifier.
            instructions: Raw instructions content.
            faq: Raw FAQ content.
            escalation_rules: Raw escalation rules content.
            validation_criteria: Raw validation criteria content.

        Returns:
            Final workflow state.
        """
        logger.info("Running workflow_id=%s", workflow_id)

        initial_state = create_initial_state(
            workflow_id=workflow_id,
            instructions=instructions,
            faq=faq,
            escalation_rules=escalation_rules,
            validation_criteria=validation_criteria,
        )

        config = {"configurable": {"thread_id": workflow_id}}

        result = await self._app.ainvoke(initial_state, config)

        logger.info("Workflow completed: workflow_id=%s", workflow_id)

        return result

    async def stream(
        self,
        workflow_id: str,
        instructions: str,
        faq: str,
        escalation_rules: str,
        validation_criteria: str,
    ) -> AsyncIterator[tuple[str, SupervisorState]]:
        """
        Stream workflow execution events.

        Args:
            workflow_id: Unique workflow identifier.
            instructions: Raw instructions content.
            faq: Raw FAQ content.
            escalation_rules: Raw escalation rules content.
            validation_criteria: Raw validation criteria content.

        Yields:
            Tuples of (node_name, state) for each step.
        """
        logger.info("Streaming workflow_id=%s", workflow_id)

        initial_state = create_initial_state(
            workflow_id=workflow_id,
            instructions=instructions,
            faq=faq,
            escalation_rules=escalation_rules,
            validation_criteria=validation_criteria,
        )

        config = {"configurable": {"thread_id": workflow_id}}

        async for event in self._app.astream(initial_state, config):
            for node_name, state in event.items():
                logger.debug("Workflow event: node=%s", node_name)
                yield node_name, state

        logger.info("Workflow streaming completed: workflow_id=%s", workflow_id)

    async def resume(
        self,
        workflow_id: str,
        updates: dict[str, Any] | None = None,
    ) -> SupervisorState:
        """
        Resume a checkpointed workflow.

        Args:
            workflow_id: Workflow identifier to resume.
            updates: Optional state updates to apply.

        Returns:
            Final workflow state after resumption.

        Raises:
            ValueError: If no checkpoint found for workflow_id.
        """
        if self._checkpointer is None:
            raise ValueError("Cannot resume without checkpointer")

        logger.info("Resuming workflow_id=%s", workflow_id)

        config = {"configurable": {"thread_id": workflow_id}}

        # Get latest checkpoint - use async method for AsyncSqliteSaver
        if isinstance(self._checkpointer, AsyncSqliteSaver):
            checkpoint_tuple = await self._checkpointer.aget_tuple(config)
        else:
            checkpoint_tuple = self._checkpointer.get_tuple(config)

        if checkpoint_tuple is None:
            raise ValueError(f"No checkpoint found for workflow_id={workflow_id}")

        # Apply updates if provided
        if updates:
            state = checkpoint_tuple.checkpoint.get("channel_values", {})
            state.update(updates)
            result = await self._app.ainvoke(state, config)
        else:
            # Resume from checkpoint
            state = checkpoint_tuple.checkpoint.get("channel_values", {})
            result = await self._app.ainvoke(state, config)

        logger.info("Workflow resumed and completed: workflow_id=%s", workflow_id)

        return result

    async def get_state(self, workflow_id: str) -> SupervisorState | None:
        """
        Get current state for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            Current state or None if not found.
        """
        if self._checkpointer is None:
            logger.warning("Cannot get state without checkpointer")
            return None

        config = {"configurable": {"thread_id": workflow_id}}

        # Use async method for AsyncSqliteSaver
        if isinstance(self._checkpointer, AsyncSqliteSaver):
            checkpoint_tuple = await self._checkpointer.aget_tuple(config)
        else:
            checkpoint_tuple = self._checkpointer.get_tuple(config)

        if checkpoint_tuple is None:
            return None

        return checkpoint_tuple.checkpoint.get("channel_values", {})

    async def approve_plan(self, workflow_id: str) -> SupervisorState:
        """
        Approve the execution plan for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            Updated state after approval.

        Raises:
            ValueError: If workflow not found or not in awaiting approval state.
        """
        logger.info("Approving plan for workflow_id=%s", workflow_id)

        state = await self.get_state(workflow_id)

        if state is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        return await self.resume(
            workflow_id,
            updates={"plan_approved": True},
        )

    async def reject_plan(
        self,
        workflow_id: str,
        reason: str,
    ) -> SupervisorState:
        """
        Reject the execution plan for a workflow.

        Args:
            workflow_id: Workflow identifier.
            reason: Reason for rejection.

        Returns:
            Updated state after rejection.

        Raises:
            ValueError: If workflow not found.
        """
        logger.info("Rejecting plan for workflow_id=%s, reason=%s", workflow_id, reason)

        state = await self.get_state(workflow_id)

        if state is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        return await self.resume(
            workflow_id,
            updates={
                "plan_approved": False,
                "plan_rejection_reason": reason,
            },
        )


def create_workflow() -> InfoAgentWorkflow:
    """
    Create a new InfoAgentWorkflow instance without checkpointing.

    For workflows with checkpointing, use the async factory method:
        workflow = await InfoAgentWorkflow.create(checkpoint_db_path=path)

    Returns:
        Configured InfoAgentWorkflow instance without checkpointing.
    """
    logger.info("Creating workflow without checkpointing")

    return InfoAgentWorkflow()


async def create_workflow_async(
    checkpoint_db_path: str | Path | None = None,
) -> InfoAgentWorkflow:
    """
    Create a new InfoAgentWorkflow instance with optional async checkpointing.

    Args:
        checkpoint_db_path: Optional path for checkpoint database.

    Returns:
        Configured InfoAgentWorkflow instance.
    """
    logger.info("Creating async workflow with checkpoint_db_path=%s", checkpoint_db_path)

    return await InfoAgentWorkflow.create(checkpoint_db_path=checkpoint_db_path)
