"""
Workflow routes for the Gateway.

This module provides endpoints for managing workflows including
creation, execution, streaming, and status queries.
"""

import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from info_agent.gateway.models import (
    ErrorDetail,
    ErrorResponse,
    PlanStep,
    SSEEvent,
    SSEEventType,
    WorkflowApproveRequest,
    WorkflowAuditEntry,
    WorkflowAuditResponse,
    WorkflowCancelRequest,
    WorkflowCreateRequest,
    WorkflowEmailsResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory workflow storage for demo purposes
# In production, this would be in a database
_workflows: dict[str, dict] = {}


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    payload: WorkflowCreateRequest,
    request: Request,
) -> WorkflowResponse:
    """
    Create a new workflow.

    This endpoint creates a new workflow with the provided inputs
    and initiates the planning phase.

    Args:
        payload: Workflow creation request.
        request: FastAPI request with app state.

    Returns:
        WorkflowResponse with the created workflow.

    Raises:
        HTTPException: If workflow creation fails.
    """
    logger.info("Creating new workflow")

    try:
        supervisor = getattr(request.app.state, "supervisor", None)
        if supervisor is None:
            logger.error("Supervisor not available")
            raise HTTPException(
                status_code=503,
                detail="Supervisor not available",
            )

        # Generate workflow ID
        workflow_id = payload.workflow_id or f"wf-{uuid.uuid4().hex[:8]}"
        logger.info("Generated workflow ID: %s", workflow_id)

        now = datetime.utcnow()

        # Store workflow metadata
        _workflows[workflow_id] = {
            "workflow_id": workflow_id,
            "instructions": payload.instructions,
            "faq": payload.faq,
            "escalation_rules": payload.escalation_rules,
            "validation_criteria": payload.validation_criteria,
            "status": WorkflowStatus.PLANNING,
            "created_at": now,
            "updated_at": now,
            "plan": None,
            "current_step": None,
            "result": None,
            "error": None,
            "audit_log": [],
        }

        # Add audit entry
        _add_audit_entry(
            workflow_id,
            "workflow.created",
            "Workflow created",
        )

        # Start the workflow
        logger.info("Starting workflow: %s", workflow_id)
        result = await supervisor.start_workflow(
            workflow_id=workflow_id,
            instructions=payload.instructions,
            faq=payload.faq,
            escalation_rules=payload.escalation_rules,
            validation_criteria=payload.validation_criteria,
        )

        # Update workflow with result
        if result:
            _workflows[workflow_id]["status"] = WorkflowStatus(
                result.get("status", WorkflowStatus.AWAITING_APPROVAL)
            )
            if "plan" in result:
                _workflows[workflow_id]["plan"] = result["plan"]

        _workflows[workflow_id]["updated_at"] = datetime.utcnow()

        # Add audit entry
        _add_audit_entry(
            workflow_id,
            "workflow.planned",
            "Execution plan generated",
        )

        logger.info(
            "Workflow created successfully: %s, status=%s",
            workflow_id,
            _workflows[workflow_id]["status"],
        )

        return _build_workflow_response(workflow_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create workflow: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create workflow: {e}",
        ) from e


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    offset: int = 0,
    limit: int = 10,
) -> WorkflowListResponse:
    """
    List all workflows.

    Args:
        offset: Pagination offset.
        limit: Maximum number of workflows to return.

    Returns:
        WorkflowListResponse with paginated workflows.
    """
    logger.info("Listing workflows: offset=%d, limit=%d", offset, limit)

    workflows = list(_workflows.values())
    total = len(workflows)

    # Apply pagination
    paginated = workflows[offset : offset + limit]

    response_workflows = [
        _build_workflow_response(w["workflow_id"])
        for w in paginated
    ]

    return WorkflowListResponse(
        workflows=response_workflows,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str) -> WorkflowResponse:
    """
    Get workflow details.

    Args:
        workflow_id: Workflow identifier.

    Returns:
        WorkflowResponse with workflow details.

    Raises:
        HTTPException: If workflow not found.
    """
    logger.info("Getting workflow: %s", workflow_id)

    if workflow_id not in _workflows:
        logger.warning("Workflow not found: %s", workflow_id)
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    return _build_workflow_response(workflow_id)


@router.post("/{workflow_id}/approve", response_model=WorkflowResponse)
async def approve_workflow(
    workflow_id: str,
    payload: WorkflowApproveRequest,
    request: Request,
) -> WorkflowResponse:
    """
    Approve or reject a workflow plan.

    Args:
        workflow_id: Workflow identifier.
        payload: Approval request.
        request: FastAPI request with app state.

    Returns:
        WorkflowResponse with updated workflow.

    Raises:
        HTTPException: If workflow not found or approval fails.
    """
    logger.info(
        "Approving workflow: %s, approved=%s",
        workflow_id,
        payload.approved,
    )

    if workflow_id not in _workflows:
        logger.warning("Workflow not found: %s", workflow_id)
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    try:
        supervisor = getattr(request.app.state, "supervisor", None)
        if supervisor is None:
            raise HTTPException(
                status_code=503,
                detail="Supervisor not available",
            )

        if payload.approved:
            # Approve the plan
            await supervisor.approve_plan(workflow_id)
            _workflows[workflow_id]["status"] = WorkflowStatus.EXECUTING

            _add_audit_entry(
                workflow_id,
                "plan.approved",
                "Execution plan approved",
            )

            logger.info("Workflow plan approved: %s", workflow_id)
        else:
            # Reject the plan
            await supervisor.reject_plan(workflow_id, payload.feedback or "")
            _workflows[workflow_id]["status"] = WorkflowStatus.PLANNING

            _add_audit_entry(
                workflow_id,
                "plan.rejected",
                f"Execution plan rejected: {payload.feedback}",
            )

            logger.info(
                "Workflow plan rejected: %s, feedback=%s",
                workflow_id,
                payload.feedback,
            )

        _workflows[workflow_id]["updated_at"] = datetime.utcnow()

        return _build_workflow_response(workflow_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to approve workflow: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve workflow: {e}",
        ) from e


@router.post("/{workflow_id}/cancel", response_model=WorkflowResponse)
async def cancel_workflow(
    workflow_id: str,
    payload: WorkflowCancelRequest,
) -> WorkflowResponse:
    """
    Cancel a workflow.

    Args:
        workflow_id: Workflow identifier.
        payload: Cancellation request.

    Returns:
        WorkflowResponse with updated workflow.

    Raises:
        HTTPException: If workflow not found.
    """
    logger.info(
        "Cancelling workflow: %s, reason=%s",
        workflow_id,
        payload.reason,
    )

    if workflow_id not in _workflows:
        logger.warning("Workflow not found: %s", workflow_id)
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    _workflows[workflow_id]["status"] = WorkflowStatus.CANCELLED
    _workflows[workflow_id]["updated_at"] = datetime.utcnow()

    _add_audit_entry(
        workflow_id,
        "workflow.cancelled",
        f"Workflow cancelled: {payload.reason or 'No reason provided'}",
    )

    logger.info("Workflow cancelled: %s", workflow_id)

    return _build_workflow_response(workflow_id)


@router.get("/{workflow_id}/status", response_model=WorkflowResponse)
async def get_workflow_status(workflow_id: str) -> WorkflowResponse:
    """
    Get current workflow status.

    This is an alias for get_workflow focused on status.

    Args:
        workflow_id: Workflow identifier.

    Returns:
        WorkflowResponse with workflow status.

    Raises:
        HTTPException: If workflow not found.
    """
    logger.debug("Getting workflow status: %s", workflow_id)
    return await get_workflow(workflow_id)


@router.get("/{workflow_id}/audit", response_model=WorkflowAuditResponse)
async def get_workflow_audit(workflow_id: str) -> WorkflowAuditResponse:
    """
    Get workflow audit log.

    Args:
        workflow_id: Workflow identifier.

    Returns:
        WorkflowAuditResponse with audit entries.

    Raises:
        HTTPException: If workflow not found.
    """
    logger.info("Getting workflow audit log: %s", workflow_id)

    if workflow_id not in _workflows:
        logger.warning("Workflow not found: %s", workflow_id)
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    audit_log = _workflows[workflow_id].get("audit_log", [])

    entries = [
        WorkflowAuditEntry(
            timestamp=entry["timestamp"],
            event_type=entry["event_type"],
            description=entry["description"],
            metadata=entry.get("metadata", {}),
        )
        for entry in audit_log
    ]

    return WorkflowAuditResponse(
        workflow_id=workflow_id,
        entries=entries,
        total=len(entries),
    )


@router.get("/{workflow_id}/emails", response_model=WorkflowEmailsResponse)
async def get_workflow_emails(workflow_id: str) -> WorkflowEmailsResponse:
    """
    Get workflow email history.

    Args:
        workflow_id: Workflow identifier.

    Returns:
        WorkflowEmailsResponse with email threads and messages.

    Raises:
        HTTPException: If workflow not found.
    """
    logger.info("Getting workflow emails: %s", workflow_id)

    if workflow_id not in _workflows:
        logger.warning("Workflow not found: %s", workflow_id)
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    # In a full implementation, this would query the email server
    return WorkflowEmailsResponse(
        workflow_id=workflow_id,
        threads=[],
        messages=[],
    )


@router.get("/{workflow_id}/stream")
async def stream_workflow(
    workflow_id: str,
    request: Request,
) -> StreamingResponse:
    """
    Stream AG-UI events for a workflow.

    This endpoint returns a Server-Sent Events stream with
    real-time updates about workflow execution.

    Args:
        workflow_id: Workflow identifier.
        request: FastAPI request with app state.

    Returns:
        StreamingResponse with SSE events.

    Raises:
        HTTPException: If workflow not found.
    """
    logger.info("Starting SSE stream for workflow: %s", workflow_id)

    if workflow_id not in _workflows:
        logger.warning("Workflow not found: %s", workflow_id)
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_id}",
        )

    return StreamingResponse(
        _generate_sse_events(workflow_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def _generate_sse_events(
    workflow_id: str,
    request: Request,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for a workflow.

    This generator yields SSE-formatted events as the workflow
    progresses through its execution.

    Args:
        workflow_id: Workflow identifier.
        request: FastAPI request with app state.

    Yields:
        SSE-formatted event strings.
    """
    logger.info("Generating SSE events for workflow: %s", workflow_id)

    try:
        supervisor = getattr(request.app.state, "supervisor", None)
        if supervisor is None:
            error_event = SSEEvent(
                event_type=SSEEventType.RUN_ERROR,
                workflow_id=workflow_id,
                data={"error": "Supervisor not available"},
            )
            yield error_event.to_sse_format()
            return

        workflow = _workflows.get(workflow_id)
        if workflow is None:
            error_event = SSEEvent(
                event_type=SSEEventType.RUN_ERROR,
                workflow_id=workflow_id,
                data={"error": "Workflow not found"},
            )
            yield error_event.to_sse_format()
            return

        # Send run started event
        start_event = SSEEvent(
            event_type=SSEEventType.RUN_STARTED,
            workflow_id=workflow_id,
            data={
                "status": workflow["status"].value,
            },
        )
        yield start_event.to_sse_format()

        # Stream workflow execution
        async for node_name, state in supervisor.stream_workflow(
            workflow_id=workflow_id,
            instructions=workflow["instructions"],
            faq=workflow["faq"],
            escalation_rules=workflow["escalation_rules"],
            validation_criteria=workflow["validation_criteria"],
        ):
            logger.debug(
                "Streaming node: workflow=%s, node=%s",
                workflow_id,
                node_name,
            )

            # Determine event type based on node
            event_type = _node_to_event_type(node_name)

            event = SSEEvent(
                event_type=event_type,
                workflow_id=workflow_id,
                data={
                    "node": node_name,
                    "status": state.get("status", "unknown") if isinstance(state, dict) else "unknown",
                },
            )
            yield event.to_sse_format()

            # Update workflow status
            if isinstance(state, dict) and "status" in state:
                try:
                    _workflows[workflow_id]["status"] = WorkflowStatus(state["status"])
                except ValueError:
                    pass

        # Send run finished event
        finish_event = SSEEvent(
            event_type=SSEEventType.RUN_FINISHED,
            workflow_id=workflow_id,
            data={
                "status": _workflows[workflow_id]["status"].value,
            },
        )
        yield finish_event.to_sse_format()

        logger.info("SSE stream completed for workflow: %s", workflow_id)

    except Exception as e:
        logger.error("Error in SSE stream: %s", e)
        error_event = SSEEvent(
            event_type=SSEEventType.RUN_ERROR,
            workflow_id=workflow_id,
            data={"error": str(e)},
        )
        yield error_event.to_sse_format()


def _node_to_event_type(node_name: str) -> SSEEventType:
    """
    Map workflow node names to SSE event types.

    Args:
        node_name: Name of the workflow node.

    Returns:
        Corresponding SSE event type.
    """
    node_event_map = {
        "parse_inputs": SSEEventType.STATE_DELTA,
        "lookup_agents": SSEEventType.STATE_DELTA,
        "generate_plan": SSEEventType.PLAN_GENERATED,
        "await_approval": SSEEventType.STATE_DELTA,
        "execute_step": SSEEventType.STEP_STARTED,
        "send_email": SSEEventType.EMAIL_SENT,
        "wait_response": SSEEventType.STATE_DELTA,
        "handle_clarification": SSEEventType.CLARIFICATION_NEEDED,
        "check_timeout": SSEEventType.STATE_DELTA,
        "escalate": SSEEventType.STATE_DELTA,
        "validate_document": SSEEventType.VALIDATION_STARTED,
        "report_results": SSEEventType.VALIDATION_COMPLETE,
    }

    return node_event_map.get(node_name, SSEEventType.STATE_DELTA)


def _build_workflow_response(workflow_id: str) -> WorkflowResponse:
    """
    Build a WorkflowResponse from stored workflow data.

    Args:
        workflow_id: Workflow identifier.

    Returns:
        WorkflowResponse object.
    """
    workflow = _workflows[workflow_id]

    plan_steps = None
    if workflow.get("plan"):
        plan_steps = [
            PlanStep(
                step_number=step.get("step_number", i + 1),
                action=step.get("action", ""),
                agent=step.get("agent", ""),
                skill=step.get("skill", ""),
                description=step.get("description", ""),
                parameters=step.get("parameters", {}),
                status=step.get("status", "pending"),
            )
            for i, step in enumerate(workflow["plan"])
        ]

    return WorkflowResponse(
        workflow_id=workflow_id,
        status=workflow["status"],
        created_at=workflow["created_at"],
        updated_at=workflow["updated_at"],
        plan=plan_steps,
        current_step=workflow.get("current_step"),
        result=workflow.get("result"),
        error=workflow.get("error"),
    )


def _add_audit_entry(
    workflow_id: str,
    event_type: str,
    description: str,
    metadata: dict | None = None,
) -> None:
    """
    Add an entry to the workflow audit log.

    Args:
        workflow_id: Workflow identifier.
        event_type: Type of event.
        description: Event description.
        metadata: Optional additional metadata.
    """
    if workflow_id not in _workflows:
        return

    entry = {
        "timestamp": datetime.utcnow(),
        "event_type": event_type,
        "description": description,
        "metadata": metadata or {},
    }

    _workflows[workflow_id]["audit_log"].append(entry)
    logger.debug(
        "Added audit entry: workflow=%s, event=%s",
        workflow_id,
        event_type,
    )


# Utility function to clear workflows (for testing)
def clear_workflows() -> None:
    """Clear all stored workflows (for testing)."""
    _workflows.clear()
    logger.info("Cleared all workflows")


logger.info("Workflow routes module initialized")
