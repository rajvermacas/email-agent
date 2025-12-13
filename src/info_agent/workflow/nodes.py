"""
LangGraph workflow node implementations.

This module provides the node functions for the Supervisor Agent's
LangGraph workflow. Each node performs a specific step in the
information retrieval workflow.
"""

import json
import re
from datetime import datetime
from typing import Any

from info_agent.utils.exceptions import LLMError, A2AError, WorkflowError
from info_agent.utils.logging import get_logger
from info_agent.workflow.state import (
    SupervisorState,
    WorkflowStatus,
    add_audit_entry,
)

logger = get_logger(__name__)


async def parse_input_files(state: SupervisorState) -> dict[str, Any]:
    """
    Parse instruction files and extract requirements using LLM.

    This node reads the uploaded instruction file and uses the LLM
    to extract structured information: target email, name, and
    the information being requested.

    Args:
        state: Current workflow state.

    Returns:
        State updates with parsed requirements.

    Raises:
        LLMError: If LLM invocation fails.
        WorkflowError: If parsing fails.
    """
    workflow_id = state["workflow_id"]
    logger.info(f"Parsing input files for workflow {workflow_id}")

    instructions = state.get("instructions", "")
    if not instructions:
        logger.error(f"No instructions provided for workflow {workflow_id}")
        raise WorkflowError(
            message="No instructions provided",
            workflow_id=workflow_id,
            step="parse_inputs",
        )

    # Import here to avoid circular dependency
    from info_agent.llm import get_gemini_llm

    try:
        llm = get_gemini_llm()
        logger.debug(f"LLM obtained for workflow {workflow_id}")

        extraction_prompt = f"""
Extract the following information from these instructions:

Instructions:
{instructions}

Extract and return a JSON object with exactly these fields:
1. target_email: The email address to send the request to
2. target_name: The name of the person (if mentioned, otherwise use "Unknown")
3. requested_info: A brief description of what information/documents are being requested

Respond with ONLY a valid JSON object, no other text:
{{
    "target_email": "...",
    "target_name": "...",
    "requested_info": "..."
}}
"""

        logger.debug(f"Invoking LLM for extraction in workflow {workflow_id}")
        response = await llm.ainvoke(extraction_prompt)
        response_text = response.content.strip()
        logger.debug(f"LLM response received for workflow {workflow_id}")

        # Parse JSON response
        extracted = _parse_json_response(response_text)
        logger.info(
            f"Extracted requirements for workflow {workflow_id}",
            target_email=extracted.get("target_email"),
            target_name=extracted.get("target_name"),
        )

        # Validate required fields
        target_email = extracted.get("target_email", "")
        if not target_email or "@" not in target_email:
            raise WorkflowError(
                message=f"Invalid or missing target email: {target_email}",
                workflow_id=workflow_id,
                step="parse_inputs",
            )

        return {
            "target_email": target_email,
            "target_name": extracted.get("target_name", "Unknown"),
            "requested_info": extracted.get("requested_info", ""),
            "status": WorkflowStatus.PLANNING.value,
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": add_audit_entry(
                state,
                action="parse_inputs",
                details="Extracted requirements from instructions",
                metadata={
                    "target_email": target_email,
                    "target_name": extracted.get("target_name"),
                },
            ),
        }

    except LLMError:
        raise
    except WorkflowError:
        raise
    except Exception as e:
        logger.error(f"Failed to parse inputs for workflow {workflow_id}: {e}")
        raise LLMError(
            message=f"Failed to parse instructions: {e}",
            original_error=e,
        ) from e


async def query_a2a_registry(state: SupervisorState) -> dict[str, Any]:
    """
    Query A2A Registry to discover available agents.

    This node queries the registry to find the Mail Agent
    and verify it's available for task delegation.

    Args:
        state: Current workflow state.

    Returns:
        State updates with registry query results.

    Raises:
        A2AError: If registry query fails.
    """
    workflow_id = state["workflow_id"]
    logger.info(f"Querying A2A Registry for workflow {workflow_id}")

    # Import here to avoid circular dependency
    from info_agent.a2a.client import A2AClient
    from info_agent.config import get_settings

    try:
        settings = get_settings()
        client = A2AClient(settings.a2a_registry_url)

        logger.debug(f"Fetching agents from registry for workflow {workflow_id}")
        agents = await client.list_agents()

        mail_agent = next(
            (a for a in agents if a.get("name") == "mail-agent"),
            None
        )

        if not mail_agent:
            logger.warning(
                f"Mail Agent not found in registry for workflow {workflow_id}"
            )
            # Don't fail - the agent might register later
            return {
                "updated_at": datetime.utcnow().isoformat(),
                "audit_log": add_audit_entry(
                    state,
                    action="lookup_agents",
                    details="Mail Agent not found in registry (will retry)",
                ),
            }

        logger.info(
            f"Found Mail Agent at {mail_agent.get('url')} for workflow {workflow_id}"
        )

        return {
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": add_audit_entry(
                state,
                action="lookup_agents",
                details=f"Found Mail Agent at {mail_agent.get('url')}",
                metadata={"agent_url": mail_agent.get("url")},
            ),
        }

    except Exception as e:
        logger.error(f"Failed to query registry for workflow {workflow_id}: {e}")
        # Don't fail the workflow, just log the error
        return {
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": add_audit_entry(
                state,
                action="lookup_agents",
                details=f"Registry query failed: {e}",
            ),
        }


async def create_execution_plan(state: SupervisorState) -> dict[str, Any]:
    """
    Generate execution plan using LLM.

    This node uses the LLM to create a step-by-step plan
    for collecting the requested information.

    Args:
        state: Current workflow state.

    Returns:
        State updates with generated plan.

    Raises:
        LLMError: If LLM invocation fails.
    """
    workflow_id = state["workflow_id"]
    logger.info(f"Generating execution plan for workflow {workflow_id}")

    from info_agent.llm import get_gemini_llm

    try:
        llm = get_gemini_llm()

        plan_prompt = f"""
Create an execution plan to collect the following information:

Target: {state.get('target_name', 'Unknown')} ({state.get('target_email', '')})
Requested Information: {state.get('requested_info', '')}

Available Actions:
1. send_email - Send an email to the target requesting information
2. wait_response - Wait for email reply from target

Create a step-by-step plan. Respond with ONLY a valid JSON object:
{{
    "plan": [
        {{"step": 1, "action": "send_email", "description": "...", "status": "pending"}},
        {{"step": 2, "action": "wait_response", "description": "...", "status": "pending"}}
    ],
    "summary": "Brief summary of the plan"
}}
"""

        logger.debug(f"Invoking LLM for plan generation in workflow {workflow_id}")
        response = await llm.ainvoke(plan_prompt)
        response_text = response.content.strip()

        plan_data = _parse_json_response(response_text)
        plan = plan_data.get("plan", [])
        summary = plan_data.get("summary", "")

        logger.info(f"Generated plan with {len(plan)} steps for workflow {workflow_id}")

        return {
            "plan": plan,
            "status": WorkflowStatus.AWAITING_APPROVAL.value,
            "current_step": 0,
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": add_audit_entry(
                state,
                action="generate_plan",
                details=summary or f"Generated plan with {len(plan)} steps",
                metadata={"step_count": len(plan)},
            ),
        }

    except Exception as e:
        logger.error(f"Failed to generate plan for workflow {workflow_id}: {e}")
        raise LLMError(
            message=f"Failed to generate execution plan: {e}",
            original_error=e,
        ) from e


async def wait_for_user_approval(state: SupervisorState) -> dict[str, Any]:
    """
    Wait for user to approve the execution plan.

    This node is a checkpoint - the workflow pauses here until
    the user approves or rejects the plan via the API.

    Args:
        state: Current workflow state.

    Returns:
        State updates (minimal, just for tracking).
    """
    workflow_id = state["workflow_id"]
    logger.info(f"Waiting for approval of workflow {workflow_id}")

    return {
        "status": WorkflowStatus.AWAITING_APPROVAL.value,
        "updated_at": datetime.utcnow().isoformat(),
    }


def check_approval_status(state: SupervisorState) -> str:
    """
    Determine routing based on approval status.

    Args:
        state: Current workflow state.

    Returns:
        Next node to route to: "approved", "rejected", or "cancelled".
    """
    workflow_id = state["workflow_id"]

    if state.get("plan_approved"):
        logger.info(f"Plan approved for workflow {workflow_id}")
        return "approved"
    elif state.get("plan_rejected"):
        logger.info(f"Plan rejected for workflow {workflow_id}")
        return "rejected"
    elif state.get("plan_cancelled"):
        logger.info(f"Workflow cancelled: {workflow_id}")
        return "cancelled"

    # Default to approved for basic flow
    logger.debug(f"Defaulting to approved for workflow {workflow_id}")
    return "approved"


async def execute_current_step(state: SupervisorState) -> dict[str, Any]:
    """
    Execute the current step in the plan.

    Args:
        state: Current workflow state.

    Returns:
        State updates based on current step execution.
    """
    workflow_id = state["workflow_id"]
    current_step = state.get("current_step", 0)
    plan = state.get("plan", [])

    if current_step >= len(plan):
        logger.info(f"All steps completed for workflow {workflow_id}")
        return {"status": WorkflowStatus.COMPLETED.value}

    step = plan[current_step]
    logger.info(
        f"Executing step {current_step + 1} for workflow {workflow_id}: {step.get('action')}"
    )

    return {
        "status": WorkflowStatus.EXECUTING.value,
        "updated_at": datetime.utcnow().isoformat(),
        "audit_log": add_audit_entry(
            state,
            action="execute_step",
            details=f"Executing step {current_step + 1}: {step.get('description', '')}",
            metadata={"step": current_step + 1, "action": step.get("action")},
        ),
    }


def determine_next_action(state: SupervisorState) -> str:
    """
    Determine the next action based on current plan step.

    Args:
        state: Current workflow state.

    Returns:
        Next node to route to based on step action.
    """
    current_step = state.get("current_step", 0)
    plan = state.get("plan", [])

    if current_step >= len(plan):
        return "complete"

    step = plan[current_step]
    action = step.get("action", "")

    logger.debug(f"Next action for workflow {state['workflow_id']}: {action}")
    return action if action in ["send_email", "wait_response"] else "complete"


async def invoke_mail_agent_send(state: SupervisorState) -> dict[str, Any]:
    """
    Invoke Mail Agent to send email.

    Args:
        state: Current workflow state.

    Returns:
        State updates with sent email details.

    Raises:
        A2AError: If mail agent invocation fails.
    """
    workflow_id = state["workflow_id"]
    target_email = state.get("target_email", "")
    logger.info(f"Invoking Mail Agent to send email to {target_email}")

    from info_agent.a2a.client import A2AClient
    from info_agent.config import get_settings
    from info_agent.llm import get_gemini_llm

    try:
        # Compose email content using LLM
        llm = get_gemini_llm()

        compose_prompt = f"""
Compose a professional email requesting the following information:

To: {state.get('target_name', 'Sir/Madam')} ({target_email})
Request: {state.get('requested_info', '')}

The email should be:
- Polite and professional
- Clear about what information is needed
- Include a call to action

Respond with just the email body (no subject line, no greeting/signature boilerplate).
"""

        response = await llm.ainvoke(compose_prompt)
        email_body = response.content.strip()

        # Send via Mail Agent
        settings = get_settings()
        client = A2AClient(f"http://{settings.host}:{settings.mail_agent_port}")

        subject = f"Information Request: {state.get('requested_info', '')[:50]}..."

        task_result = await client.send_task(
            skill_id="send-email",
            payload={
                "to": target_email,
                "subject": subject,
                "body": email_body,
            },
        )

        message_id = task_result.get("message_id", "")
        thread_id = task_result.get("thread_id", "")

        logger.info(f"Email sent for workflow {workflow_id}, message_id: {message_id}")

        return {
            "sent_email_id": message_id,
            "email_thread_id": thread_id,
            "sent_email_subject": subject,
            "sent_email_body": email_body,
            "current_step": state.get("current_step", 0) + 1,
            "status": WorkflowStatus.WAITING_FOR_RESPONSE.value,
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": add_audit_entry(
                state,
                action="send_email",
                details=f"Sent email to {target_email}, thread_id: {thread_id}",
                metadata={"message_id": message_id, "thread_id": thread_id},
            ),
        }

    except Exception as e:
        logger.error(f"Failed to send email for workflow {workflow_id}: {e}")
        raise A2AError(
            message=f"Failed to send email: {e}",
            agent_name="mail-agent",
            skill_id="send-email",
        ) from e


async def wait_for_email_response(state: SupervisorState) -> dict[str, Any]:
    """
    Wait for email response from target.

    This node is a checkpoint - the workflow pauses here until
    an email response is received via webhook.

    Args:
        state: Current workflow state.

    Returns:
        State updates (minimal, waiting state).
    """
    workflow_id = state["workflow_id"]
    thread_id = state.get("email_thread_id", "")
    logger.info(f"Waiting for response to thread {thread_id} for workflow {workflow_id}")

    return {
        "status": WorkflowStatus.WAITING_FOR_RESPONSE.value,
        "updated_at": datetime.utcnow().isoformat(),
    }


def check_response_received(state: SupervisorState) -> str:
    """
    Check if email response has been received.

    Args:
        state: Current workflow state.

    Returns:
        "received" if response exists, "waiting" otherwise.
    """
    if state.get("received_response"):
        logger.info(f"Response received for workflow {state['workflow_id']}")
        return "received"

    logger.debug(f"Still waiting for response in workflow {state['workflow_id']}")
    return "waiting"


async def handle_email_response(state: SupervisorState) -> dict[str, Any]:
    """
    Process received email response.

    Args:
        state: Current workflow state.

    Returns:
        State updates marking workflow as completed.
    """
    workflow_id = state["workflow_id"]
    logger.info(f"Processing response for workflow {workflow_id}")

    return {
        "current_step": state.get("current_step", 0) + 1,
        "status": WorkflowStatus.COMPLETED.value,
        "updated_at": datetime.utcnow().isoformat(),
        "audit_log": add_audit_entry(
            state,
            action="process_response",
            details="Email response received and processed",
            metadata={
                "response_subject": state.get("received_response_subject"),
                "has_attachments": len(state.get("received_attachments", [])) > 0,
            },
        ),
    }


def _parse_json_response(response_text: str) -> dict[str, Any]:
    """
    Parse JSON from LLM response, handling markdown code blocks.

    Args:
        response_text: Raw response text from LLM.

    Returns:
        Parsed JSON dictionary.

    Raises:
        ValueError: If JSON parsing fails.
    """
    # Remove markdown code block markers if present
    text = response_text.strip()
    if text.startswith("```"):
        # Remove opening marker (```json or just ```)
        text = re.sub(r"^```(?:json)?\n?", "", text)
        # Remove closing marker
        text = re.sub(r"\n?```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}, text: {text[:100]}...")
        raise ValueError(f"Invalid JSON in LLM response: {e}") from e
