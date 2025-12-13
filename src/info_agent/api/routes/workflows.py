"""
Workflow management endpoints for Info-Agent Gateway.

This module provides REST API endpoints for creating, managing, and
monitoring information retrieval workflows.

Endpoints:
- POST /workflows - Create new workflow with uploaded instructions
- GET /workflows - List all workflows
- GET /workflows/{id} - Get workflow status
- POST /workflows/{id}/approve - Approve execution plan
- POST /workflows/{id}/reject - Reject plan with feedback
- DELETE /workflows/{id} - Cancel workflow
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from info_agent.api.models.requests import ApproveWorkflowRequest, CreateWorkflowRequest
from info_agent.api.models.responses import (
    PlanStep,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowStatus,
    WorkflowStatusResponse,
)
from info_agent.config import get_settings
from info_agent.utils.exceptions import WorkflowError, WorkflowNotFoundError
from info_agent.utils.logging import bind_context, clear_context, get_logger
from info_agent.workflow.checkpointer import (
    delete_workflow_thread,
    get_workflow_state,
    list_workflow_threads,
)
from info_agent.workflow.graph import get_compiled_workflow, resume_workflow, run_workflow
from info_agent.workflow.state import create_initial_state

logger = get_logger(__name__)


def create_workflow_router() -> APIRouter:
    """
    Create the workflow management router.

    Returns:
        APIRouter instance with workflow endpoints.
    """
    logger.info("Creating workflow management router")

    router = APIRouter(
        prefix="/workflows",
        tags=["Workflows"],
        responses={
            status.HTTP_500_INTERNAL_SERVER_ERROR: {
                "description": "Internal server error"
            },
        },
    )

    @router.post(
        "",
        response_model=WorkflowResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create workflow",
        description="Create a new workflow with uploaded instruction file",
    )
    async def create_workflow(
        name: str = Form(..., description="Workflow name"),
        description: str | None = Form(None, description="Workflow description"),
        instructions_file: UploadFile = File(..., description="Instructions PDF/text file"),
    ) -> WorkflowResponse:
        """
        Create a new information retrieval workflow.

        The workflow is initialized with the uploaded instruction file,
        which will be parsed by the Supervisor Agent to extract:
        - Target email address
        - Target name
        - Requested information

        Args:
            name: Human-readable workflow name.
            description: Optional detailed description.
            instructions_file: Uploaded instruction file (PDF, TXT, MD).

        Returns:
            WorkflowResponse with created workflow details.

        Raises:
            HTTPException: If validation fails or workflow creation fails.
        """
        logger.info(
            "Creating new workflow",
            name=name,
            filename=instructions_file.filename,
        )

        # Validate workflow name
        if not name or not name.strip():
            logger.error("Workflow creation failed - empty name")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow name is required and cannot be empty",
            )

        # Validate file upload
        if not instructions_file:
            logger.error("Workflow creation failed - no file uploaded")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Instructions file is required",
            )

        if not instructions_file.filename:
            logger.error("Workflow creation failed - file has no filename")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must have a filename",
            )

        # Validate file type
        allowed_extensions = {".pdf", ".txt", ".md"}
        file_ext = None
        for ext in allowed_extensions:
            if instructions_file.filename.lower().endswith(ext):
                file_ext = ext
                break

        if file_ext is None:
            logger.error(
                "Workflow creation failed - invalid file type",
                filename=instructions_file.filename,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
            )

        # Read file content
        try:
            logger.debug("Reading instruction file content")
            file_content = await instructions_file.read()

            if not file_content:
                logger.error("Workflow creation failed - empty file")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Instructions file is empty",
                )

            # Decode content (for text files)
            if file_ext in {".txt", ".md"}:
                instructions_text = file_content.decode("utf-8")
            else:
                # For PDF, store as base64 or raw bytes
                # In a real implementation, you'd extract text from PDF
                instructions_text = file_content.decode("utf-8", errors="replace")

            logger.debug(
                "File content read successfully",
                size_bytes=len(file_content),
            )

        except UnicodeDecodeError as e:
            logger.error(
                "Failed to decode instruction file",
                filename=instructions_file.filename,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File encoding error. Please upload a UTF-8 encoded text file.",
            ) from e
        except Exception as e:
            logger.error(
                "Failed to read instruction file",
                filename=instructions_file.filename,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read file: {str(e)}",
            ) from e

        # Generate workflow ID
        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"

        bind_context(workflow_id=workflow_id)

        try:
            logger.info(
                "Initializing workflow",
                workflow_id=workflow_id,
                name=name,
            )

            # Create initial workflow state
            initial_state = create_initial_state(
                workflow_id=workflow_id,
                workflow_name=name.strip(),
                instructions=instructions_text,
                instructions_filename=instructions_file.filename,
            )

            logger.debug(
                "Initial state created",
                workflow_id=workflow_id,
                status=initial_state["status"],
            )

            # Start workflow execution in background
            # Note: We return immediately after creating the workflow,
            # the actual execution happens asynchronously
            logger.info(
                "Starting workflow execution",
                workflow_id=workflow_id,
            )

            # Run workflow asynchronously
            # In production, you might use a background task runner
            import asyncio

            asyncio.create_task(_run_workflow_background(workflow_id, initial_state))

            # Return workflow response
            now = datetime.utcnow()

            response = WorkflowResponse(
                id=workflow_id,
                name=name.strip(),
                description=description.strip() if description else None,
                status=WorkflowStatus.CREATED,
                created_at=now,
                updated_at=now,
            )

            logger.info(
                "Workflow created successfully",
                workflow_id=workflow_id,
                name=name,
            )

            return response

        except Exception as e:
            logger.error(
                "Failed to create workflow",
                workflow_id=workflow_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create workflow: {str(e)}",
            ) from e

        finally:
            clear_context()

    @router.get(
        "",
        response_model=WorkflowListResponse,
        status_code=status.HTTP_200_OK,
        summary="List workflows",
        description="List all workflows with their current status",
    )
    async def list_workflows() -> WorkflowListResponse:
        """
        List all workflows.

        Retrieves all workflows from the checkpoint database and returns
        their basic information and current status.

        Returns:
            WorkflowListResponse with list of all workflows.

        Raises:
            HTTPException: If listing fails.
        """
        logger.info("Listing all workflows")

        try:
            settings = get_settings()
            compiled_workflow = get_compiled_workflow()

            # Get all workflow IDs
            workflow_ids = await list_workflow_threads(settings.checkpoint_db_path)

            logger.debug(
                "Retrieved workflow IDs",
                count=len(workflow_ids),
            )

            # Retrieve state for each workflow
            workflows: list[WorkflowResponse] = []

            for workflow_id in workflow_ids:
                logger.debug("Fetching workflow state", workflow_id=workflow_id)

                state = await get_workflow_state(compiled_workflow, workflow_id)

                if state is None:
                    logger.warning(
                        "Workflow has no state, skipping",
                        workflow_id=workflow_id,
                    )
                    continue

                # Build workflow response
                workflow = WorkflowResponse(
                    id=workflow_id,
                    name=state.get("workflow_name", "Unknown"),
                    description=None,  # Description not stored in state
                    status=WorkflowStatus(state.get("status", "created")),
                    created_at=datetime.fromisoformat(
                        state.get("created_at", datetime.utcnow().isoformat())
                    ),
                    updated_at=datetime.fromisoformat(
                        state.get("updated_at", datetime.utcnow().isoformat())
                    ),
                )

                workflows.append(workflow)

            logger.info(
                "Workflows listed successfully",
                total_count=len(workflows),
            )

            return WorkflowListResponse(
                workflows=workflows,
                total=len(workflows),
            )

        except Exception as e:
            logger.error(
                "Failed to list workflows",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list workflows: {str(e)}",
            ) from e

    @router.get(
        "/{workflow_id}",
        response_model=WorkflowStatusResponse,
        status_code=status.HTTP_200_OK,
        summary="Get workflow status",
        description="Get detailed status of a specific workflow",
    )
    async def get_workflow_status(workflow_id: str) -> WorkflowStatusResponse:
        """
        Get detailed workflow status.

        Retrieves complete status information for a workflow, including:
        - Current execution status
        - Execution plan and progress
        - Target information
        - Email thread details
        - Any errors

        Args:
            workflow_id: Workflow identifier.

        Returns:
            WorkflowStatusResponse with detailed status.

        Raises:
            HTTPException: If workflow not found or retrieval fails.
        """
        logger.info("Getting workflow status", workflow_id=workflow_id)

        if not workflow_id:
            logger.error("Get workflow status failed - missing ID")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow ID is required",
            )

        bind_context(workflow_id=workflow_id)

        try:
            compiled_workflow = get_compiled_workflow()

            # Get workflow state
            state = await get_workflow_state(compiled_workflow, workflow_id)

            if state is None:
                logger.warning("Workflow not found", workflow_id=workflow_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow not found: {workflow_id}",
                )

            logger.debug("Workflow state retrieved", workflow_id=workflow_id)

            # Build plan steps from state
            plan_steps = None
            if state.get("plan"):
                plan_steps = [
                    PlanStep(
                        step=step["step"],
                        action=step["action"],
                        description=step["description"],
                        status=step.get("status", "pending"),
                    )
                    for step in state["plan"]
                ]

            # Build response
            response = WorkflowStatusResponse(
                id=workflow_id,
                status=WorkflowStatus(state.get("status", "created")),
                current_step=state.get("current_step"),
                plan=plan_steps,
                target_email=state.get("target_email"),
                target_name=state.get("target_name"),
                requested_info=state.get("requested_info"),
                email_thread_id=state.get("email_thread_id"),
                received_response=state.get("received_response"),
                error=state.get("error"),
                updated_at=datetime.fromisoformat(
                    state.get("updated_at", datetime.utcnow().isoformat())
                ),
            )

            logger.info(
                "Workflow status retrieved successfully",
                workflow_id=workflow_id,
                status=response.status,
            )

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Failed to get workflow status",
                workflow_id=workflow_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get workflow status: {str(e)}",
            ) from e

        finally:
            clear_context()

    @router.post(
        "/{workflow_id}/approve",
        response_model=WorkflowStatusResponse,
        status_code=status.HTTP_200_OK,
        summary="Approve execution plan",
        description="Approve the generated execution plan and continue workflow",
    )
    async def approve_workflow(
        workflow_id: str,
        request: ApproveWorkflowRequest,
    ) -> WorkflowStatusResponse:
        """
        Approve or reject the execution plan.

        When the Supervisor Agent generates an execution plan, it waits for
        user approval before proceeding. This endpoint allows approving or
        rejecting the plan.

        Args:
            workflow_id: Workflow identifier.
            request: Approval request with decision and optional feedback.

        Returns:
            WorkflowStatusResponse with updated status.

        Raises:
            HTTPException: If workflow not found or approval fails.
        """
        logger.info(
            "Processing workflow approval",
            workflow_id=workflow_id,
            approved=request.approved,
        )

        if not workflow_id:
            logger.error("Approve workflow failed - missing ID")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow ID is required",
            )

        bind_context(workflow_id=workflow_id)

        try:
            compiled_workflow = get_compiled_workflow()

            # Verify workflow exists and is awaiting approval
            state = await get_workflow_state(compiled_workflow, workflow_id)

            if state is None:
                logger.warning("Workflow not found", workflow_id=workflow_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow not found: {workflow_id}",
                )

            current_status = state.get("status", "")

            if current_status != WorkflowStatus.AWAITING_APPROVAL.value:
                logger.warning(
                    "Workflow not awaiting approval",
                    workflow_id=workflow_id,
                    current_status=current_status,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Workflow is not awaiting approval. Current status: {current_status}",
                )

            # Prepare state updates
            state_updates = {
                "plan_approved": request.approved,
                "plan_rejected": not request.approved,
                "approval_feedback": request.feedback,
                "updated_at": datetime.utcnow().isoformat(),
            }

            logger.debug(
                "Resuming workflow with approval decision",
                workflow_id=workflow_id,
                approved=request.approved,
            )

            # Resume workflow with approval decision
            try:
                result = await resume_workflow(
                    workflow_id=workflow_id,
                    updates=state_updates,
                )

                logger.info(
                    "Workflow approval processed",
                    workflow_id=workflow_id,
                    approved=request.approved,
                    new_status=result.get("status", "unknown"),
                )

                # Build response
                plan_steps = None
                if result.get("plan"):
                    plan_steps = [
                        PlanStep(
                            step=step["step"],
                            action=step["action"],
                            description=step["description"],
                            status=step.get("status", "pending"),
                        )
                        for step in result["plan"]
                    ]

                return WorkflowStatusResponse(
                    id=workflow_id,
                    status=WorkflowStatus(result.get("status", "executing")),
                    current_step=result.get("current_step"),
                    plan=plan_steps,
                    target_email=result.get("target_email"),
                    target_name=result.get("target_name"),
                    requested_info=result.get("requested_info"),
                    email_thread_id=result.get("email_thread_id"),
                    received_response=result.get("received_response"),
                    error=result.get("error"),
                    updated_at=datetime.fromisoformat(
                        result.get("updated_at", datetime.utcnow().isoformat())
                    ),
                )

            except WorkflowNotFoundError as e:
                logger.error(
                    "Workflow not found during approval",
                    workflow_id=workflow_id,
                    error=str(e),
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow not found: {workflow_id}",
                ) from e

            except WorkflowError as e:
                logger.error(
                    "Workflow approval processing failed",
                    workflow_id=workflow_id,
                    error=str(e),
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Workflow approval failed: {e.message}",
                ) from e

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during workflow approval",
                workflow_id=workflow_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process approval: {str(e)}",
            ) from e

        finally:
            clear_context()

    @router.post(
        "/{workflow_id}/reject",
        response_model=WorkflowStatusResponse,
        status_code=status.HTTP_200_OK,
        summary="Reject execution plan",
        description="Reject the execution plan with feedback for regeneration",
    )
    async def reject_workflow(
        workflow_id: str,
        request: ApproveWorkflowRequest,
    ) -> WorkflowStatusResponse:
        """
        Reject the execution plan.

        Rejecting the plan causes the Supervisor Agent to regenerate the
        execution plan, taking into account the provided feedback.

        Args:
            workflow_id: Workflow identifier.
            request: Rejection request with feedback.

        Returns:
            WorkflowStatusResponse with updated status.

        Raises:
            HTTPException: If workflow not found or rejection fails.
        """
        logger.info(
            "Processing workflow rejection",
            workflow_id=workflow_id,
            has_feedback=bool(request.feedback),
        )

        # Rejection is the same as approval with approved=False
        request.approved = False

        return await approve_workflow(workflow_id, request)

    @router.delete(
        "/{workflow_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Cancel workflow",
        description="Cancel a workflow and delete its state",
    )
    async def cancel_workflow(workflow_id: str) -> None:
        """
        Cancel and delete a workflow.

        This cancels the workflow execution and removes all its state
        and checkpoints from the database. This action is irreversible.

        Args:
            workflow_id: Workflow identifier.

        Raises:
            HTTPException: If workflow not found or deletion fails.
        """
        logger.info("Cancelling workflow", workflow_id=workflow_id)

        if not workflow_id:
            logger.error("Cancel workflow failed - missing ID")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow ID is required",
            )

        bind_context(workflow_id=workflow_id)

        try:
            settings = get_settings()
            compiled_workflow = get_compiled_workflow()

            # Verify workflow exists
            state = await get_workflow_state(compiled_workflow, workflow_id)

            if state is None:
                logger.warning("Workflow not found", workflow_id=workflow_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow not found: {workflow_id}",
                )

            # Delete workflow thread and all checkpoints
            deleted = await delete_workflow_thread(
                settings.checkpoint_db_path,
                workflow_id,
            )

            if not deleted:
                logger.error(
                    "Failed to delete workflow",
                    workflow_id=workflow_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete workflow",
                )

            logger.info(
                "Workflow cancelled successfully",
                workflow_id=workflow_id,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during workflow cancellation",
                workflow_id=workflow_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel workflow: {str(e)}",
            ) from e

        finally:
            clear_context()

    logger.info("Workflow management router created successfully")
    return router


async def _run_workflow_background(
    workflow_id: str,
    initial_state: dict[str, Any],
) -> None:
    """
    Run workflow in background.

    This is called as a background task to execute the workflow
    asynchronously after creation.

    Args:
        workflow_id: Workflow identifier.
        initial_state: Initial workflow state.
    """
    logger.info("Running workflow in background", workflow_id=workflow_id)

    bind_context(workflow_id=workflow_id)

    try:
        result = await run_workflow(
            workflow_id=workflow_id,
            initial_state=initial_state,
        )

        logger.info(
            "Background workflow completed",
            workflow_id=workflow_id,
            final_status=result.get("status", "unknown"),
        )

    except Exception as e:
        logger.error(
            "Background workflow failed",
            workflow_id=workflow_id,
            error=str(e),
            error_type=type(e).__name__,
        )

    finally:
        clear_context()
