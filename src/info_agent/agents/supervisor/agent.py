"""
Supervisor Agent for Info-Agent system.

This module implements the main Supervisor Agent that orchestrates the entire
information retrieval workflow using LangGraph for state management and
checkpointing.

The Supervisor Agent:
- Creates and manages workflow instances
- Generates execution plans using the ExecutionPlanner
- Delegates email tasks to Mail Agent via A2A protocol
- Tracks workflow state via SQLite checkpointing
- Handles user approval for plans
- Processes email responses and completes workflows

Usage:
    from info_agent.agents.supervisor.agent import SupervisorAgent

    # Initialize the agent
    agent = SupervisorAgent()

    # Create a new workflow
    workflow_id = await agent.create_workflow(
        workflow_name="Collect Q3 Reports",
        instructions="Please collect Q3 2024 financial reports from john@example.com",
        instructions_filename="request.txt"
    )

    # Approve the plan
    await agent.approve_plan(workflow_id)

    # Get workflow status
    state = await agent.get_workflow_state(workflow_id)
"""

import uuid
from datetime import datetime
from typing import Any

from info_agent.a2a.sdk_client_wrapper import get_sdk_client, SDKClientWrapper
from info_agent.agents.supervisor.planner import ExecutionPlanner
from info_agent.agents.supervisor.state import (
    SupervisorState,
    WorkflowStatus,
    add_audit_entry,
    create_initial_state,
)
from info_agent.config import get_settings
from info_agent.utils.exceptions import (
    A2AError,
    AgentCommunicationError,
    ValidationError,
    WorkflowError,
    WorkflowNotFoundError,
)
from info_agent.utils.logging import get_logger
from info_agent.workflow.graph import (
    compile_workflow,
    get_compiled_workflow,
    resume_workflow,
    run_workflow,
)

logger = get_logger(__name__)


class SupervisorAgent:
    """
    Main orchestrator agent for information retrieval workflows.

    The Supervisor Agent coordinates the entire workflow lifecycle:
    1. Workflow creation and initialization
    2. Execution plan generation via ExecutionPlanner
    3. User approval management
    4. Task delegation to Mail Agent via A2A
    5. Response processing and workflow completion

    All workflow state is persisted via LangGraph's SQLite checkpointing,
    enabling workflows to pause, resume, and recover from failures.

    Attributes:
        settings: Application settings instance.
        planner: ExecutionPlanner for generating execution plans.
        compiled_workflow: Compiled LangGraph workflow with checkpointing.
        a2a_client: SDK client wrapper for A2A protocol communication.
    """

    def __init__(
        self,
        settings: Any | None = None,
        compiled_workflow: Any | None = None,
    ) -> None:
        """
        Initialize the Supervisor Agent.

        Args:
            settings: Optional settings override. If not provided, uses get_settings().
            compiled_workflow: Optional pre-compiled workflow. If not provided,
                             uses the singleton workflow.

        Raises:
            ConfigurationError: If settings cannot be loaded.
            LLMError: If ExecutionPlanner initialization fails.
        """
        logger.info("Initializing SupervisorAgent")

        # Load settings
        if settings is None:
            self.settings = get_settings()
            logger.debug("Loaded settings from environment")
        else:
            self.settings = settings
            logger.debug("Using provided settings")

        # Initialize execution planner
        logger.debug("Initializing ExecutionPlanner")
        self.planner = ExecutionPlanner()
        logger.debug("ExecutionPlanner initialized")

        # Get or use compiled workflow
        if compiled_workflow is None:
            logger.debug("Using singleton compiled workflow")
            self.compiled_workflow = get_compiled_workflow()
        else:
            logger.debug("Using provided compiled workflow")
            self.compiled_workflow = compiled_workflow

        # Initialize SDK A2A client wrapper
        logger.debug("Initializing SDK A2A client", registry_url=self.settings.a2a_registry_url)
        self.a2a_client = get_sdk_client(registry_url=self.settings.a2a_registry_url)

        logger.info("SupervisorAgent initialized successfully")

    async def create_workflow(
        self,
        workflow_name: str,
        instructions: str,
        instructions_filename: str,
    ) -> str:
        """
        Create a new information retrieval workflow.

        This method initializes a new workflow with the provided instructions.
        The workflow will parse the instructions, generate an execution plan,
        and wait for user approval.

        Args:
            workflow_name: Human-readable name for the workflow (required).
            instructions: Raw instruction text content (required).
            instructions_filename: Original filename (required).

        Returns:
            Workflow ID (UUID string).

        Raises:
            ValidationError: If required parameters are missing.
            WorkflowError: If workflow creation fails.

        Example:
            agent = SupervisorAgent()
            workflow_id = await agent.create_workflow(
                workflow_name="Get Q3 Reports",
                instructions="Please send an email to john@example.com...",
                instructions_filename="request.txt"
            )
        """
        logger.info("Creating new workflow", workflow_name=workflow_name)

        # Validate required parameters
        if not workflow_name:
            logger.error("workflow_name is required")
            raise ValidationError(
                message="workflow_name is required",
                field="workflow_name",
            )

        if not instructions:
            logger.error("instructions are required")
            raise ValidationError(
                message="instructions are required",
                field="instructions",
            )

        if not instructions_filename:
            logger.error("instructions_filename is required")
            raise ValidationError(
                message="instructions_filename is required",
                field="instructions_filename",
            )

        # Generate workflow ID
        workflow_id = f"wf-{uuid.uuid4()}"
        logger.info("Generated workflow ID", workflow_id=workflow_id)

        # Create initial state
        initial_state = create_initial_state(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            instructions=instructions,
            instructions_filename=instructions_filename,
        )

        logger.debug(
            "Created initial state",
            workflow_id=workflow_id,
            status=initial_state["status"],
        )

        # Run the workflow (will pause at approval checkpoint)
        try:
            logger.info("Starting workflow execution", workflow_id=workflow_id)

            final_state = await run_workflow(
                workflow_id=workflow_id,
                initial_state=initial_state,
                compiled_workflow=self.compiled_workflow,
            )

            logger.info(
                "Workflow created and reached checkpoint",
                workflow_id=workflow_id,
                status=final_state.get("status"),
            )

            return workflow_id

        except Exception as e:
            logger.error(
                "Failed to create workflow",
                workflow_id=workflow_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise WorkflowError(
                message=f"Failed to create workflow: {str(e)}",
                workflow_id=workflow_id,
                step="create_workflow",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    async def get_workflow_state(self, workflow_id: str) -> SupervisorState:
        """
        Retrieve current state of a workflow.

        Args:
            workflow_id: Workflow to retrieve (required).

        Returns:
            Current SupervisorState of the workflow.

        Raises:
            ValidationError: If workflow_id is missing.
            WorkflowNotFoundError: If workflow doesn't exist.

        Example:
            state = await agent.get_workflow_state("wf-123")
            print(f"Status: {state['status']}")
            print(f"Plan: {state['plan']}")
        """
        logger.info("Retrieving workflow state", workflow_id=workflow_id)

        if not workflow_id:
            logger.error("workflow_id is required")
            raise ValidationError(
                message="workflow_id is required",
                field="workflow_id",
            )

        try:
            config = {"configurable": {"thread_id": workflow_id}}
            current_state = self.compiled_workflow.get_state(config)

            if not current_state or not current_state.values:
                logger.error("Workflow not found", workflow_id=workflow_id)
                raise WorkflowNotFoundError(
                    workflow_id=workflow_id,
                    details={"operation": "get_state"},
                )

            state = dict(current_state.values)
            logger.debug(
                "Retrieved workflow state",
                workflow_id=workflow_id,
                status=state.get("status"),
            )

            return state

        except WorkflowNotFoundError:
            raise

        except Exception as e:
            logger.error(
                "Failed to retrieve workflow state",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise WorkflowError(
                message=f"Failed to retrieve workflow state: {str(e)}",
                workflow_id=workflow_id,
                step="get_state",
                details={"error": str(e)},
            ) from e

    async def approve_plan(
        self,
        workflow_id: str,
        feedback: str | None = None,
    ) -> SupervisorState:
        """
        Approve the execution plan for a workflow.

        This method approves the generated plan and allows the workflow to
        proceed with execution (sending emails, waiting for responses, etc.).

        Args:
            workflow_id: Workflow to approve (required).
            feedback: Optional feedback/notes about the approval.

        Returns:
            Updated SupervisorState after approval.

        Raises:
            ValidationError: If workflow_id is missing.
            WorkflowNotFoundError: If workflow doesn't exist.
            WorkflowError: If workflow is not in awaiting_approval state.

        Example:
            await agent.approve_plan("wf-123")
        """
        logger.info("Approving workflow plan", workflow_id=workflow_id)

        if not workflow_id:
            logger.error("workflow_id is required")
            raise ValidationError(
                message="workflow_id is required",
                field="workflow_id",
            )

        # Get current state to validate
        current_state = await self.get_workflow_state(workflow_id)

        # Validate workflow is in correct state
        if current_state.get("status") != WorkflowStatus.AWAITING_APPROVAL.value:
            logger.error(
                "Workflow not awaiting approval",
                workflow_id=workflow_id,
                current_status=current_state.get("status"),
            )
            raise WorkflowError(
                message=(
                    f"Workflow is not awaiting approval. "
                    f"Current status: {current_state.get('status')}"
                ),
                workflow_id=workflow_id,
                step="approve_plan",
                details={"current_status": current_state.get("status")},
            )

        # Update state with approval
        updates = {
            "plan_approved": True,
            "plan_rejected": False,
            "plan_cancelled": False,
            "approval_feedback": feedback,
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": add_audit_entry(
                current_state,
                action="plan_approved",
                details="User approved execution plan",
                metadata={"feedback": feedback} if feedback else None,
            ),
        }

        logger.debug("Resuming workflow with approval", workflow_id=workflow_id)

        try:
            final_state = await resume_workflow(
                workflow_id=workflow_id,
                updates=updates,
                compiled_workflow=self.compiled_workflow,
            )

            logger.info(
                "Workflow plan approved and resumed",
                workflow_id=workflow_id,
                new_status=final_state.get("status"),
            )

            return final_state

        except Exception as e:
            logger.error(
                "Failed to approve plan",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise WorkflowError(
                message=f"Failed to approve plan: {str(e)}",
                workflow_id=workflow_id,
                step="approve_plan",
                details={"error": str(e)},
            ) from e

    async def reject_plan(
        self,
        workflow_id: str,
        feedback: str,
    ) -> SupervisorState:
        """
        Reject the execution plan and request regeneration.

        This method rejects the current plan and triggers regeneration
        with the provided feedback incorporated.

        Args:
            workflow_id: Workflow to reject plan for (required).
            feedback: Feedback explaining why the plan was rejected (required).

        Returns:
            Updated SupervisorState with new plan.

        Raises:
            ValidationError: If parameters are missing.
            WorkflowNotFoundError: If workflow doesn't exist.
            WorkflowError: If workflow is not in awaiting_approval state.

        Example:
            await agent.reject_plan(
                "wf-123",
                feedback="Please be more specific in the email"
            )
        """
        logger.info("Rejecting workflow plan", workflow_id=workflow_id)

        if not workflow_id:
            logger.error("workflow_id is required")
            raise ValidationError(
                message="workflow_id is required",
                field="workflow_id",
            )

        if not feedback:
            logger.error("feedback is required for plan rejection")
            raise ValidationError(
                message="feedback is required when rejecting a plan",
                field="feedback",
            )

        # Get current state to validate
        current_state = await self.get_workflow_state(workflow_id)

        # Validate workflow is in correct state
        if current_state.get("status") != WorkflowStatus.AWAITING_APPROVAL.value:
            logger.error(
                "Workflow not awaiting approval",
                workflow_id=workflow_id,
                current_status=current_state.get("status"),
            )
            raise WorkflowError(
                message=(
                    f"Workflow is not awaiting approval. "
                    f"Current status: {current_state.get('status')}"
                ),
                workflow_id=workflow_id,
                step="reject_plan",
                details={"current_status": current_state.get("status")},
            )

        # Update state with rejection
        updates = {
            "plan_approved": False,
            "plan_rejected": True,
            "plan_cancelled": False,
            "approval_feedback": feedback,
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": add_audit_entry(
                current_state,
                action="plan_rejected",
                details="User rejected execution plan",
                metadata={"feedback": feedback},
            ),
        }

        logger.debug("Resuming workflow with rejection", workflow_id=workflow_id)

        try:
            final_state = await resume_workflow(
                workflow_id=workflow_id,
                updates=updates,
                compiled_workflow=self.compiled_workflow,
            )

            logger.info(
                "Workflow plan rejected, new plan generated",
                workflow_id=workflow_id,
                new_status=final_state.get("status"),
            )

            return final_state

        except Exception as e:
            logger.error(
                "Failed to reject plan",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise WorkflowError(
                message=f"Failed to reject plan: {str(e)}",
                workflow_id=workflow_id,
                step="reject_plan",
                details={"error": str(e)},
            ) from e

    async def cancel_workflow(self, workflow_id: str) -> SupervisorState:
        """
        Cancel a workflow.

        This method cancels the workflow and prevents further execution.

        Args:
            workflow_id: Workflow to cancel (required).

        Returns:
            Final SupervisorState after cancellation.

        Raises:
            ValidationError: If workflow_id is missing.
            WorkflowNotFoundError: If workflow doesn't exist.

        Example:
            await agent.cancel_workflow("wf-123")
        """
        logger.info("Cancelling workflow", workflow_id=workflow_id)

        if not workflow_id:
            logger.error("workflow_id is required")
            raise ValidationError(
                message="workflow_id is required",
                field="workflow_id",
            )

        # Get current state
        current_state = await self.get_workflow_state(workflow_id)

        # Update state with cancellation
        updates = {
            "plan_approved": False,
            "plan_rejected": False,
            "plan_cancelled": True,
            "status": WorkflowStatus.CANCELLED.value,
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": add_audit_entry(
                current_state,
                action="workflow_cancelled",
                details="User cancelled workflow",
            ),
        }

        logger.debug("Resuming workflow with cancellation", workflow_id=workflow_id)

        try:
            final_state = await resume_workflow(
                workflow_id=workflow_id,
                updates=updates,
                compiled_workflow=self.compiled_workflow,
            )

            logger.info("Workflow cancelled successfully", workflow_id=workflow_id)

            return final_state

        except Exception as e:
            logger.error(
                "Failed to cancel workflow",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise WorkflowError(
                message=f"Failed to cancel workflow: {str(e)}",
                workflow_id=workflow_id,
                step="cancel_workflow",
                details={"error": str(e)},
            ) from e

    async def handle_email_received(
        self,
        workflow_id: str,
        email_id: str,
        subject: str,
        body: str,
        sender: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> SupervisorState:
        """
        Handle an incoming email response for a workflow.

        This method is called when an email response is received that
        matches a workflow's thread. It updates the workflow state and
        triggers response processing.

        Args:
            workflow_id: Workflow that received the response (required).
            email_id: ID of the received email (required).
            subject: Email subject (required).
            body: Email body text (required).
            sender: Sender email address (required).
            attachments: Optional list of attachment metadata.

        Returns:
            Updated SupervisorState after processing response.

        Raises:
            ValidationError: If required parameters are missing.
            WorkflowNotFoundError: If workflow doesn't exist.

        Example:
            await agent.handle_email_received(
                workflow_id="wf-123",
                email_id="msg-456",
                subject="Re: Information Request",
                body="Here is the information...",
                sender="john@example.com",
                attachments=[{"filename": "report.pdf", ...}]
            )
        """
        logger.info(
            "Handling received email",
            workflow_id=workflow_id,
            email_id=email_id,
            sender=sender,
        )

        # Validate required parameters
        if not workflow_id:
            raise ValidationError(
                message="workflow_id is required",
                field="workflow_id",
            )

        if not email_id:
            raise ValidationError(
                message="email_id is required",
                field="email_id",
            )

        if not subject:
            raise ValidationError(
                message="subject is required",
                field="subject",
            )

        if not body:
            raise ValidationError(
                message="body is required",
                field="body",
            )

        if not sender:
            raise ValidationError(
                message="sender is required",
                field="sender",
            )

        # Get current state
        current_state = await self.get_workflow_state(workflow_id)

        # Update state with received email
        updates = {
            "received_response": body,
            "received_response_subject": subject,
            "received_attachments": attachments or [],
            "status": WorkflowStatus.COMPLETED.value,
            "updated_at": datetime.utcnow().isoformat(),
            "audit_log": add_audit_entry(
                current_state,
                action="email_received",
                details=f"Received email response from {sender}",
                metadata={
                    "email_id": email_id,
                    "sender": sender,
                    "subject": subject,
                    "attachment_count": len(attachments or []),
                },
            ),
        }

        logger.debug(
            "Resuming workflow with email response",
            workflow_id=workflow_id,
        )

        try:
            final_state = await resume_workflow(
                workflow_id=workflow_id,
                updates=updates,
                compiled_workflow=self.compiled_workflow,
            )

            logger.info(
                "Email response processed successfully",
                workflow_id=workflow_id,
                new_status=final_state.get("status"),
            )

            return final_state

        except Exception as e:
            logger.error(
                "Failed to handle received email",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise WorkflowError(
                message=f"Failed to handle received email: {str(e)}",
                workflow_id=workflow_id,
                step="handle_email_received",
                details={"error": str(e)},
            ) from e

    async def send_email_via_mail_agent(
        self,
        workflow_id: str,
        to_email: str,
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        """
        Send an email via the Mail Agent using A2A protocol.

        This method delegates the email sending task to the Mail Agent
        via the A2A protocol.

        Args:
            workflow_id: Associated workflow ID (required).
            to_email: Recipient email address (required).
            subject: Email subject (required).
            body: Email body text (required).

        Returns:
            Task result from Mail Agent containing email details.

        Raises:
            ValidationError: If required parameters are missing.
            A2AError: If A2A communication fails.
            AgentCommunicationError: If Mail Agent is unreachable.

        Example:
            result = await agent.send_email_via_mail_agent(
                workflow_id="wf-123",
                to_email="john@example.com",
                subject="Information Request",
                body="Dear John, ..."
            )
            email_id = result["email_id"]
        """
        logger.info(
            "Sending email via Mail Agent",
            workflow_id=workflow_id,
            to_email=to_email,
        )

        # Validate required parameters
        if not workflow_id:
            raise ValidationError(
                message="workflow_id is required",
                field="workflow_id",
            )

        if not to_email:
            raise ValidationError(
                message="to_email is required",
                field="to_email",
            )

        if not subject:
            raise ValidationError(
                message="subject is required",
                field="subject",
            )

        if not body:
            raise ValidationError(
                message="body is required",
                field="body",
            )

        # Prepare task payload
        payload = {
            "to": to_email,
            "subject": subject,
            "body": body,
            "workflow_id": workflow_id,
        }

        logger.debug(
            "Sending A2A task to Mail Agent",
            agent_name="mail-agent",
            skill_id="send_email",
        )

        try:
            result = await self.a2a_client.send_task(
                agent_name="mail-agent",
                skill_id="send_email",
                payload=payload,
            )

            logger.info(
                "Email sent successfully via Mail Agent",
                workflow_id=workflow_id,
                email_id=result.get("email_id"),
            )

            return result

        except (A2AError, AgentCommunicationError) as e:
            logger.error(
                "Failed to send email via Mail Agent",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error sending email",
                workflow_id=workflow_id,
                error=str(e),
            )
            raise AgentCommunicationError(
                message=f"Unexpected error sending email: {str(e)}",
                agent_name="mail-agent",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e
