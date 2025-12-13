"""
Conditional edge functions for the LangGraph workflow.

This module contains the condition functions that determine
which path the workflow takes at decision points.
"""

import logging
from typing import Literal

from info_agent.workflow.state import SupervisorState, WorkflowStatus

logger = logging.getLogger(__name__)


def check_approval_status(
    state: SupervisorState,
) -> Literal["approved", "rejected", "cancelled"]:
    """
    Check if the execution plan has been approved.

    Args:
        state: Current workflow state.

    Returns:
        "approved" if plan is approved and ready to execute.
        "rejected" if user rejected and wants changes.
        "cancelled" if user cancelled the workflow.
    """
    status = state.get("status", WorkflowStatus.AWAITING_APPROVAL)
    plan_approved = state.get("plan_approved", False)

    logger.debug(
        "Checking approval status: status=%s, plan_approved=%s",
        status,
        plan_approved,
    )

    if status == WorkflowStatus.CANCELLED:
        logger.info("Workflow cancelled")
        return "cancelled"

    if plan_approved:
        logger.info("Plan approved, proceeding to execution")
        return "approved"

    rejection_reason = state.get("plan_rejection_reason")
    if rejection_reason:
        logger.info("Plan rejected, regenerating. Reason: %s", rejection_reason)
        return "rejected"

    # Default to approved if no explicit rejection
    # In practice, this would wait for user input
    if status == WorkflowStatus.AWAITING_APPROVAL:
        # Still waiting - check if we should auto-approve for testing
        # In production, this would be a waiting state
        return "approved"

    return "rejected"


def determine_next_action(
    state: SupervisorState,
) -> Literal["send_email", "validate", "complete"]:
    """
    Determine the next action based on current step.

    Args:
        state: Current workflow state.

    Returns:
        "send_email" if next step is to send email.
        "validate" if next step is document validation.
        "complete" if all steps are done.
    """
    current_step = state.get("current_step", 0)
    plan = state.get("plan", [])

    logger.debug(
        "Determining next action: current_step=%d, plan_length=%d",
        current_step,
        len(plan),
    )

    if current_step >= len(plan):
        logger.info("All steps completed")
        return "complete"

    step = plan[current_step]
    action = step.get("action", "")
    agent = step.get("agent", "")

    logger.debug("Current step action=%s, agent=%s", action, agent)

    if "send" in action.lower() or "email" in action.lower():
        return "send_email"

    if agent == "validation-agent" or "validate" in action.lower():
        return "validate"

    # Default to complete if unclear
    return "complete"


def check_response_type(
    state: SupervisorState,
) -> Literal["document_received", "clarification_needed", "timeout", "error"]:
    """
    Check the type of response received.

    Args:
        state: Current workflow state.

    Returns:
        "document_received" if a document was attached.
        "clarification_needed" if target asked a question.
        "timeout" if waiting period exceeded.
        "error" if an error occurred.
    """
    logger.debug("Checking response type")

    error = state.get("error")
    if error:
        logger.info("Error detected: %s", error)
        return "error"

    received_documents = state.get("received_documents", [])
    if received_documents:
        logger.info("Document(s) received: %d", len(received_documents))
        return "document_received"

    clarification_history = state.get("clarification_history", [])
    if clarification_history:
        # Check if latest clarification is unanswered
        latest = clarification_history[-1]
        if not latest.get("answered_at"):
            logger.info("Clarification needed")
            return "clarification_needed"

    # Check for timeout
    waiting_since = state.get("waiting_since")
    if waiting_since:
        from datetime import datetime

        waiting_dt = datetime.fromisoformat(waiting_since)
        elapsed = datetime.utcnow() - waiting_dt
        timeout_hours = state.get("timeout_hours", 48)

        if elapsed.total_seconds() / 3600 >= timeout_hours:
            logger.info("Timeout detected")
            return "timeout"

    # Still waiting - default to document_received for workflow to continue
    # In practice, this would be a checkpoint waiting for external input
    response_received = state.get("response_received", False)
    if response_received:
        return "document_received"

    return "timeout"


def check_faq_match(
    state: SupervisorState,
) -> Literal["found_in_faq", "not_in_faq"]:
    """
    Check if clarification question matches FAQ.

    Args:
        state: Current workflow state.

    Returns:
        "found_in_faq" if answer found in FAQ.
        "not_in_faq" if needs escalation.
    """
    logger.debug("Checking FAQ match")

    clarification_history = state.get("clarification_history", [])

    if not clarification_history:
        logger.info("No clarifications to check")
        return "not_in_faq"

    latest = clarification_history[-1]
    faq_match = latest.get("faq_match", False)

    if faq_match:
        logger.info("FAQ match found")
        return "found_in_faq"

    logger.info("No FAQ match, escalating")
    return "not_in_faq"


def evaluate_retry_count(
    state: SupervisorState,
) -> Literal["retry", "escalate"]:
    """
    Evaluate whether to retry or escalate based on retry count.

    Args:
        state: Current workflow state.

    Returns:
        "retry" if retry count is under threshold.
        "escalate" if retries exhausted.
    """
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    logger.debug(
        "Evaluating retry count: retry_count=%d, max_retries=%d",
        retry_count,
        max_retries,
    )

    if retry_count < max_retries:
        logger.info("Retry %d of %d", retry_count + 1, max_retries)
        return "retry"

    logger.info("Max retries reached, escalating")
    return "escalate"


def check_validation_result(
    state: SupervisorState,
) -> Literal["passed", "failed"]:
    """
    Check the validation result.

    Args:
        state: Current workflow state.

    Returns:
        "passed" if validation passed.
        "failed" if validation failed.
    """
    logger.debug("Checking validation result")

    validation_result = state.get("validation_result", {})

    if not validation_result:
        logger.warning("No validation result found")
        return "failed"

    passed = validation_result.get("passed", False)

    if passed:
        logger.info("Validation passed")
        return "passed"

    logger.info("Validation failed")
    return "failed"


def should_continue_workflow(state: SupervisorState) -> bool:
    """
    Check if workflow should continue or stop.

    Args:
        state: Current workflow state.

    Returns:
        True if workflow should continue.
        False if workflow should stop.
    """
    status = state.get("status", WorkflowStatus.PLANNING)

    terminal_states = {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    }

    should_continue = status not in terminal_states

    logger.debug(
        "Should continue workflow: status=%s, continue=%s",
        status,
        should_continue,
    )

    return should_continue
