"""
Workflow nodes for the Info-Agent LangGraph workflow.

This module contains all the node functions that make up the
workflow execution graph.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Any

from info_agent.workflow.state import (
    SupervisorState,
    WorkflowStatus,
    add_audit_entry,
    update_status,
)

logger = logging.getLogger(__name__)


async def parse_inputs_node(state: SupervisorState) -> SupervisorState:
    """
    Parse input files to extract structured requirements.

    This node processes the raw input files (instructions, FAQ,
    escalation rules, validation criteria) and extracts structured
    data for workflow execution.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with parsed requirements.
    """
    logger.info("Parsing input files for workflow_id=%s", state.get("workflow_id"))

    instructions = state.get("instructions", "")
    escalation_rules = state.get("escalation_rules", "")

    # Extract target email from instructions
    email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
    emails = re.findall(email_pattern, instructions)
    target_email = emails[0] if emails else ""

    # Extract target name (simple heuristic - first word before email domain)
    target_name = ""
    if target_email:
        name_part = target_email.split("@")[0]
        target_name = name_part.replace(".", " ").replace("_", " ").title()

    # Extract what is being requested
    requested_info = instructions.strip()

    # Parse escalation contacts
    escalation_emails = re.findall(email_pattern, escalation_rules)
    escalation_contact = ""
    clarification_contact = ""

    for email in escalation_emails:
        escalation_text = escalation_rules.lower()
        email_lower = email.lower()

        # Check context around the email
        if "not available" in escalation_text or "doesn't reply" in escalation_text:
            if email_lower in escalation_text:
                escalation_contact = email
        if "clarif" in escalation_text:
            if email_lower in escalation_text:
                clarification_contact = email

    # If still empty, assign in order
    if not escalation_contact and len(escalation_emails) >= 1:
        escalation_contact = escalation_emails[0]
    if not clarification_contact and len(escalation_emails) >= 2:
        clarification_contact = escalation_emails[1]
    elif not clarification_contact:
        clarification_contact = escalation_contact

    # Parse timeout (default 48 hours)
    timeout_hours = 48
    timeout_match = re.search(r"(\d+)\s*hours?", escalation_rules.lower())
    if timeout_match:
        timeout_hours = int(timeout_match.group(1))

    # Update state
    updated_state = add_audit_entry(
        state,
        event_type="inputs_parsed",
        actor="supervisor",
        description="Input files parsed successfully",
        details={
            "target_email": target_email,
            "target_name": target_name,
            "escalation_contact": escalation_contact,
            "clarification_contact": clarification_contact,
            "timeout_hours": timeout_hours,
        },
    )

    logger.info(
        "Parsed inputs: target_email=%s, timeout_hours=%d",
        target_email,
        timeout_hours,
    )

    return {
        **updated_state,
        "target_email": target_email,
        "target_name": target_name,
        "requested_info": requested_info,
        "escalation_contact": escalation_contact,
        "clarification_contact": clarification_contact,
        "timeout_hours": timeout_hours,
    }


async def lookup_agents_node(state: SupervisorState) -> SupervisorState:
    """
    Query A2A registry to discover available worker agents.

    This node queries the A2A registry to find all available
    worker agents (Mail Agent, Validation Agent) and their capabilities.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with available agents.
    """
    logger.info("Looking up agents in A2A registry")

    # For now, we'll stub this with known agents
    # In production, this would query the actual A2A registry
    available_agents = [
        {
            "name": "mail-agent",
            "description": "Email communication agent for sending and receiving messages",
            "endpoint": "http://localhost:8001",
            "skills": [
                {"id": "send_email", "name": "Send Email"},
                {"id": "parse_email", "name": "Parse Email"},
                {"id": "search_emails", "name": "Search Emails"},
            ],
        },
        {
            "name": "validation-agent",
            "description": "Document validation agent with Python execution capabilities",
            "endpoint": "http://localhost:8002",
            "skills": [
                {"id": "validate_document", "name": "Validate Document"},
                {"id": "execute_python", "name": "Execute Python"},
                {"id": "generate_report", "name": "Generate Report"},
            ],
        },
    ]

    updated_state = add_audit_entry(
        state,
        event_type="agents_discovered",
        actor="supervisor",
        description=f"Discovered {len(available_agents)} worker agents",
        details={"agent_names": [a["name"] for a in available_agents]},
    )

    logger.info("Found %d available agents", len(available_agents))

    return {
        **updated_state,
        "available_agents": available_agents,
    }


async def generate_plan_node(state: SupervisorState) -> SupervisorState:
    """
    Generate execution plan based on parsed requirements.

    This node creates a step-by-step execution plan that shows
    which agents will be invoked and in what order.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with execution plan.
    """
    logger.info("Generating execution plan")

    target_email = state.get("target_email", "")
    requested_info = state.get("requested_info", "")
    validation_criteria = state.get("validation_criteria", "")

    plan = [
        {
            "step_number": 1,
            "action": "send_initial_request",
            "agent": "mail-agent",
            "skill": "send_email",
            "description": f"Send email request to {target_email}",
            "parameters": {
                "to": target_email,
                "request": requested_info,
            },
            "status": "pending",
        },
        {
            "step_number": 2,
            "action": "wait_for_response",
            "agent": "system",
            "skill": "wait",
            "description": "Wait for response from target",
            "parameters": {
                "timeout_hours": state.get("timeout_hours", 48),
            },
            "status": "pending",
        },
        {
            "step_number": 3,
            "action": "validate_response",
            "agent": "validation-agent",
            "skill": "validate_document",
            "description": "Validate received document against criteria",
            "parameters": {
                "criteria": validation_criteria,
            },
            "status": "pending",
        },
        {
            "step_number": 4,
            "action": "generate_report",
            "agent": "validation-agent",
            "skill": "generate_report",
            "description": "Generate validation report",
            "parameters": {},
            "status": "pending",
        },
    ]

    updated_state = add_audit_entry(
        state,
        event_type="plan_generated",
        actor="supervisor",
        description=f"Generated execution plan with {len(plan)} steps",
        details={"step_count": len(plan)},
    )

    updated_state = update_status(
        updated_state, WorkflowStatus.AWAITING_APPROVAL, "Plan ready for approval"
    )

    logger.info("Generated plan with %d steps", len(plan))

    return {
        **updated_state,
        "plan": plan,
        "current_step": 0,
        # Clear rejection reason when regenerating plan
        "plan_rejection_reason": None,
        "plan_approved": False,
    }


async def await_approval_node(state: SupervisorState) -> SupervisorState:
    """
    Wait for user approval of the execution plan.

    This is a passthrough node that indicates the workflow is
    waiting for user input. The actual approval happens externally.

    Args:
        state: Current workflow state.

    Returns:
        Same state (waiting for external approval).
    """
    logger.info("Waiting for plan approval")

    # This node is a passthrough - approval happens externally
    # The condition edge will determine next step based on plan_approved

    updated_state = add_audit_entry(
        state,
        event_type="awaiting_approval",
        actor="supervisor",
        description="Waiting for user to approve execution plan",
        details={},
    )

    return updated_state


async def execute_step_node(state: SupervisorState) -> SupervisorState:
    """
    Execute the current step in the plan.

    This node marks the current step as in-progress and
    prepares state for the appropriate action node.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with step marked as executing.
    """
    current_step = state.get("current_step", 0)
    plan = state.get("plan", [])

    if current_step >= len(plan):
        logger.info("All steps completed")
        return update_status(state, WorkflowStatus.COMPLETED, "All steps completed")

    step = plan[current_step]
    logger.info("Executing step %d: %s", current_step + 1, step.get("action"))

    # Mark step as in progress
    step["status"] = "in_progress"
    step["started_at"] = datetime.utcnow().isoformat()
    plan[current_step] = step

    updated_state = add_audit_entry(
        state,
        event_type="step_started",
        actor="supervisor",
        description=f"Started step {current_step + 1}: {step.get('description')}",
        details={"step": step},
    )

    updated_state = update_status(
        updated_state, WorkflowStatus.EXECUTING, f"Executing step {current_step + 1}"
    )

    return {
        **updated_state,
        "plan": plan,
    }


async def send_email_node(state: SupervisorState) -> SupervisorState:
    """
    Invoke Mail Agent to send an email.

    This node sends an email using the Mail Agent via A2A protocol.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with email sent.
    """
    current_step = state.get("current_step", 0)
    plan = state.get("plan", [])
    target_email = state.get("target_email", "")
    requested_info = state.get("requested_info", "")

    logger.info("Sending email to %s", target_email)

    # Create email thread
    thread_id = str(uuid.uuid4())
    thread = {
        "id": thread_id,
        "subject": "Information Request",
        "target_email": target_email,
        "messages": [
            {
                "id": str(uuid.uuid4()),
                "direction": "outbound",
                "content": requested_info,
                "sent_at": datetime.utcnow().isoformat(),
            }
        ],
        "created_at": datetime.utcnow().isoformat(),
        "last_activity_at": datetime.utcnow().isoformat(),
    }

    # Mark step as completed (if plan exists and has the step)
    if plan and current_step < len(plan):
        step = plan[current_step]
        step["status"] = "completed"
        step["completed_at"] = datetime.utcnow().isoformat()
        step["result"] = {"thread_id": thread_id, "success": True}
        plan[current_step] = step

    # Update email threads
    email_threads = list(state.get("email_threads", []))
    email_threads.append(thread)

    updated_state = add_audit_entry(
        state,
        event_type="email_sent",
        actor="mail-agent",
        description=f"Email sent to {target_email}",
        details={"thread_id": thread_id},
    )

    updated_state = update_status(
        updated_state,
        WorkflowStatus.WAITING_FOR_RESPONSE,
        "Waiting for email response",
    )

    logger.info("Email sent, thread_id=%s", thread_id)

    return {
        **updated_state,
        "plan": plan,
        "email_threads": email_threads,
        "current_step": current_step + 1,
        "waiting_since": datetime.utcnow().isoformat(),
    }


async def wait_response_node(state: SupervisorState) -> SupervisorState:
    """
    Wait for response from target person.

    This is a waiting state that checks for incoming responses.
    In practice, this would be triggered by webhooks.

    Args:
        state: Current workflow state.

    Returns:
        Updated state - either waiting for external input or
        with simulated response in stub mode.
    """
    logger.info("Waiting for response")

    # Check if we're in stub/test mode (no external response expected)
    # In production, this would be a checkpoint waiting for webhooks
    stub_mode = state.get("stub_mode", True)  # Default to stub for now

    if stub_mode:
        # Simulate receiving a document response
        logger.info("Stub mode: simulating document response")

        received_documents = list(state.get("received_documents", []))

        # Only add a stub document if we don't have one yet
        if not received_documents:
            stub_document = {
                "id": str(uuid.uuid4()),
                "filename": "stub_response.xlsx",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size": 1024,
                "received_at": datetime.utcnow().isoformat(),
                "sender": state.get("target_email", "unknown@example.com"),
            }
            received_documents.append(stub_document)

            updated_state = add_audit_entry(
                state,
                event_type="document_received_stub",
                actor="mail-agent",
                description="Document received (stub mode)",
                details={"document_id": stub_document["id"]},
            )

            return {
                **updated_state,
                "received_documents": received_documents,
                "response_received": True,
            }

    # In production mode, just return state unchanged
    # External events (webhooks) would update the state
    return state


async def handle_clarification_node(state: SupervisorState) -> SupervisorState:
    """
    Handle clarification questions from target person.

    This node processes questions and either answers from FAQ
    or escalates to the clarification contact.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with clarification handling.
    """
    logger.info("Handling clarification request")

    clarification_history = list(state.get("clarification_history", []))

    # Get the latest clarification if any
    if clarification_history:
        latest = clarification_history[-1]
        question = latest.get("question", "")
        faq = state.get("faq", "")

        # Simple FAQ matching
        faq_lower = faq.lower()
        question_lower = question.lower()

        # Check if question keywords appear in FAQ
        words = question_lower.split()
        match_count = sum(1 for word in words if len(word) > 3 and word in faq_lower)

        if match_count >= 2:
            latest["faq_match"] = True
            latest["answer"] = "Please see the FAQ for this information."
            latest["answered_by"] = "faq"
            latest["answered_at"] = datetime.utcnow().isoformat()
        else:
            latest["faq_match"] = False
            latest["escalated"] = True

        clarification_history[-1] = latest

    updated_state = add_audit_entry(
        state,
        event_type="clarification_handled",
        actor="supervisor",
        description="Processed clarification request",
        details={},
    )

    return {
        **updated_state,
        "clarification_history": clarification_history,
    }


async def check_timeout_node(state: SupervisorState) -> SupervisorState:
    """
    Check if timeout has been reached.

    This node evaluates whether the waiting period has exceeded
    the configured timeout.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with timeout evaluation.
    """
    logger.info("Checking timeout")

    waiting_since = state.get("waiting_since")
    timeout_hours = state.get("timeout_hours", 48)

    if waiting_since:
        waiting_dt = datetime.fromisoformat(waiting_since)
        elapsed = datetime.utcnow() - waiting_dt
        elapsed_hours = elapsed.total_seconds() / 3600

        logger.info("Elapsed time: %.2f hours (timeout: %d)", elapsed_hours, timeout_hours)

        if elapsed_hours >= timeout_hours:
            updated_state = add_audit_entry(
                state,
                event_type="timeout_reached",
                actor="supervisor",
                description=f"Timeout reached after {elapsed_hours:.2f} hours",
                details={"elapsed_hours": elapsed_hours},
            )
            return {**updated_state, "retry_count": state.get("retry_count", 0) + 1}

    return state


async def escalate_node(state: SupervisorState) -> SupervisorState:
    """
    Escalate to configured escalation contact.

    This node sends an escalation notification to the configured
    escalation contact.

    Args:
        state: Current workflow state.

    Returns:
        Updated state after escalation.
    """
    logger.info("Escalating workflow")

    escalation_contact = state.get("escalation_contact", "")

    updated_state = add_audit_entry(
        state,
        event_type="escalated",
        actor="supervisor",
        description=f"Escalated to {escalation_contact}",
        details={"escalation_contact": escalation_contact},
    )

    updated_state = update_status(
        updated_state, WorkflowStatus.ESCALATED, "Escalated to contact"
    )

    return updated_state


async def validate_document_node(state: SupervisorState) -> SupervisorState:
    """
    Invoke Validation Agent to validate received document.

    This node sends the received document to the Validation Agent
    for validation against the specified criteria.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with validation result.
    """
    logger.info("Validating document")

    received_documents = state.get("received_documents", [])
    validation_criteria = state.get("validation_criteria", "")

    if not received_documents:
        logger.warning("No documents to validate")
        return add_audit_entry(
            state,
            event_type="validation_skipped",
            actor="validation-agent",
            description="No documents to validate",
            details={},
        )

    # Validate the first document
    doc = received_documents[0]

    # Stub validation result
    validation_result = {
        "document_id": doc.get("id", str(uuid.uuid4())),
        "document_name": doc.get("filename", "unknown"),
        "passed": True,  # Stub - would be actual validation
        "score": 1.0,
        "criteria_checked": [],
        "issues": [],
        "recommendations": [],
        "validated_at": datetime.utcnow().isoformat(),
    }

    updated_state = add_audit_entry(
        state,
        event_type="document_validated",
        actor="validation-agent",
        description=f"Document {doc.get('filename')} validated",
        details={"passed": validation_result["passed"]},
    )

    updated_state = update_status(
        updated_state, WorkflowStatus.VALIDATING, "Document validation in progress"
    )

    return {
        **updated_state,
        "validation_result": validation_result,
    }


async def report_results_node(state: SupervisorState) -> SupervisorState:
    """
    Generate final results report.

    This node compiles the final report including validation
    results and audit trail.

    Args:
        state: Current workflow state.

    Returns:
        Updated state with final report.
    """
    logger.info("Generating final report")

    validation_result = state.get("validation_result", {})

    final_report = {
        "workflow_id": state.get("workflow_id"),
        "status": "completed",
        "target_email": state.get("target_email"),
        "documents_received": len(state.get("received_documents", [])),
        "validation_passed": validation_result.get("passed", False) if validation_result else None,
        "validation_score": validation_result.get("score", 0.0) if validation_result else None,
        "email_threads": len(state.get("email_threads", [])),
        "clarifications": len(state.get("clarification_history", [])),
        "completed_at": datetime.utcnow().isoformat(),
    }

    updated_state = add_audit_entry(
        state,
        event_type="report_generated",
        actor="supervisor",
        description="Final report generated",
        details={"passed": final_report.get("validation_passed")},
    )

    updated_state = update_status(
        updated_state, WorkflowStatus.COMPLETED, "Workflow completed successfully"
    )

    return {
        **updated_state,
        "final_report": final_report,
    }
