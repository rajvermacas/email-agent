"""
Unit tests for API response models.

Tests the response models defined in src/info_agent/api/models/responses.py
with comprehensive validation, serialization, and edge cases.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from info_agent.api.models.responses import (
    WorkflowStatus,
    WorkflowResponse,
    PlanStep,
    WorkflowStatusResponse,
    WorkflowListResponse,
    UploadedFile,
    FileUploadResponse,
    FileListResponse,
    ComponentHealth,
    HealthResponse,
    ErrorDetail,
    ErrorResponse,
)


class TestWorkflowStatus:
    """Tests for WorkflowStatus enum."""

    def test_workflow_status_values(self):
        """Test all workflow status enum values."""
        assert WorkflowStatus.CREATED.value == "created"
        assert WorkflowStatus.PLANNING.value == "planning"
        assert WorkflowStatus.AWAITING_APPROVAL.value == "awaiting_approval"
        assert WorkflowStatus.EXECUTING.value == "executing"
        assert WorkflowStatus.WAITING_FOR_RESPONSE.value == "waiting_for_response"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"

    def test_workflow_status_from_string(self):
        """Test creating workflow status from string."""
        status = WorkflowStatus("created")
        assert status == WorkflowStatus.CREATED

    def test_workflow_status_invalid_value(self):
        """Test error for invalid workflow status."""
        with pytest.raises(ValueError):
            WorkflowStatus("invalid_status")


class TestWorkflowResponse:
    """Tests for WorkflowResponse model."""

    def test_valid_workflow_response_with_all_fields(self):
        """Test workflow response with all fields."""
        now = datetime.utcnow()

        response = WorkflowResponse(
            id="wf-123",
            name="Test Workflow",
            description="Test description",
            status=WorkflowStatus.CREATED,
            created_at=now,
            updated_at=now
        )

        assert response.id == "wf-123"
        assert response.name == "Test Workflow"
        assert response.description == "Test description"
        assert response.status == WorkflowStatus.CREATED
        assert response.created_at == now
        assert response.updated_at == now

    def test_workflow_response_without_description(self):
        """Test workflow response without optional description."""
        now = datetime.utcnow()

        response = WorkflowResponse(
            id="wf-123",
            name="Test Workflow",
            status=WorkflowStatus.CREATED,
            created_at=now,
            updated_at=now
        )

        assert response.description is None

    def test_workflow_response_different_statuses(self):
        """Test workflow response with different status values."""
        now = datetime.utcnow()

        for status in WorkflowStatus:
            response = WorkflowResponse(
                id="wf-123",
                name="Test",
                status=status,
                created_at=now,
                updated_at=now
            )
            assert response.status == status

    def test_workflow_response_missing_required_fields(self):
        """Test validation error for missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowResponse()

        errors = exc_info.value.errors()
        required_fields = {"id", "name", "status", "created_at", "updated_at"}
        error_fields = {error["loc"][0] for error in errors}
        assert required_fields.issubset(error_fields)

    def test_workflow_response_json_serialization(self):
        """Test JSON serialization of workflow response."""
        now = datetime.utcnow()

        response = WorkflowResponse(
            id="wf-123",
            name="Test",
            status=WorkflowStatus.EXECUTING,
            created_at=now,
            updated_at=now
        )

        json_data = response.model_dump()
        assert json_data["id"] == "wf-123"
        assert json_data["status"] == "executing"


class TestPlanStep:
    """Tests for PlanStep model."""

    def test_valid_plan_step(self):
        """Test valid plan step."""
        step = PlanStep(
            step=1,
            action="send_email",
            description="Send initial email to recipient"
        )

        assert step.step == 1
        assert step.action == "send_email"
        assert step.description == "Send initial email to recipient"
        assert step.status == "pending"

    def test_plan_step_with_custom_status(self):
        """Test plan step with custom status."""
        step = PlanStep(
            step=2,
            action="wait_response",
            description="Wait for response",
            status="completed"
        )

        assert step.status == "completed"

    def test_plan_step_minimum_valid(self):
        """Test plan step with minimum step number."""
        step = PlanStep(
            step=1,
            action="test",
            description="test"
        )

        assert step.step == 1

    def test_plan_step_zero_invalid(self):
        """Test validation error for step number zero."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStep(
                step=0,
                action="test",
                description="test"
            )

        errors = exc_info.value.errors()
        assert any(
            error["type"] == "greater_than_equal"
            for error in errors
        )

    def test_plan_step_negative_invalid(self):
        """Test validation error for negative step number."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStep(
                step=-1,
                action="test",
                description="test"
            )

        errors = exc_info.value.errors()
        assert any(
            error["type"] == "greater_than_equal"
            for error in errors
        )

    def test_plan_step_missing_required_fields(self):
        """Test validation error for missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStep()

        errors = exc_info.value.errors()
        required_fields = {"step", "action", "description"}
        error_fields = {error["loc"][0] for error in errors}
        assert required_fields.issubset(error_fields)


class TestWorkflowStatusResponse:
    """Tests for WorkflowStatusResponse model."""

    def test_valid_workflow_status_response_minimal(self):
        """Test workflow status response with minimal fields."""
        now = datetime.utcnow()

        response = WorkflowStatusResponse(
            id="wf-123",
            status=WorkflowStatus.CREATED,
            updated_at=now
        )

        assert response.id == "wf-123"
        assert response.status == WorkflowStatus.CREATED
        assert response.current_step is None
        assert response.plan is None
        assert response.target_email is None
        assert response.updated_at == now

    def test_workflow_status_response_with_plan(self):
        """Test workflow status response with execution plan."""
        now = datetime.utcnow()
        plan = [
            PlanStep(step=1, action="send_email", description="Send email"),
            PlanStep(step=2, action="wait", description="Wait for response")
        ]

        response = WorkflowStatusResponse(
            id="wf-123",
            status=WorkflowStatus.EXECUTING,
            current_step=1,
            plan=plan,
            updated_at=now
        )

        assert response.current_step == 1
        assert len(response.plan) == 2
        assert response.plan[0].action == "send_email"

    def test_workflow_status_response_with_all_fields(self):
        """Test workflow status response with all fields populated."""
        now = datetime.utcnow()
        plan = [PlanStep(step=1, action="test", description="test")]

        response = WorkflowStatusResponse(
            id="wf-123",
            status=WorkflowStatus.COMPLETED,
            current_step=1,
            plan=plan,
            target_email="test@example.com",
            target_name="Test User",
            requested_info="Financial report",
            email_thread_id="thread-456",
            received_response="Here is the report",
            error=None,
            updated_at=now
        )

        assert response.target_email == "test@example.com"
        assert response.target_name == "Test User"
        assert response.requested_info == "Financial report"
        assert response.email_thread_id == "thread-456"
        assert response.received_response == "Here is the report"
        assert response.error is None

    def test_workflow_status_response_with_error(self):
        """Test workflow status response with error."""
        now = datetime.utcnow()

        response = WorkflowStatusResponse(
            id="wf-123",
            status=WorkflowStatus.FAILED,
            error="Email delivery failed",
            updated_at=now
        )

        assert response.status == WorkflowStatus.FAILED
        assert response.error == "Email delivery failed"


class TestWorkflowListResponse:
    """Tests for WorkflowListResponse model."""

    def test_empty_workflow_list(self):
        """Test workflow list with no workflows."""
        response = WorkflowListResponse(
            workflows=[],
            total=0
        )

        assert len(response.workflows) == 0
        assert response.total == 0

    def test_workflow_list_with_multiple_workflows(self):
        """Test workflow list with multiple workflows."""
        now = datetime.utcnow()
        workflows = [
            WorkflowResponse(
                id=f"wf-{i}",
                name=f"Workflow {i}",
                status=WorkflowStatus.CREATED,
                created_at=now,
                updated_at=now
            )
            for i in range(3)
        ]

        response = WorkflowListResponse(
            workflows=workflows,
            total=3
        )

        assert len(response.workflows) == 3
        assert response.total == 3
        assert response.workflows[0].id == "wf-0"

    def test_workflow_list_total_validation(self):
        """Test that total must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            WorkflowListResponse(
                workflows=[],
                total=-1
            )

        errors = exc_info.value.errors()
        assert any(
            error["type"] == "greater_than_equal"
            for error in errors
        )


class TestUploadedFile:
    """Tests for UploadedFile model."""

    def test_valid_uploaded_file(self):
        """Test valid uploaded file."""
        now = datetime.utcnow()

        file = UploadedFile(
            filename="instructions.pdf",
            file_type="instructions",
            size=1024,
            uploaded_at=now
        )

        assert file.filename == "instructions.pdf"
        assert file.file_type == "instructions"
        assert file.size == 1024
        assert file.uploaded_at == now

    def test_uploaded_file_zero_size(self):
        """Test uploaded file with zero size."""
        now = datetime.utcnow()

        file = UploadedFile(
            filename="empty.txt",
            file_type="instructions",
            size=0,
            uploaded_at=now
        )

        assert file.size == 0

    def test_uploaded_file_negative_size_invalid(self):
        """Test validation error for negative size."""
        now = datetime.utcnow()

        with pytest.raises(ValidationError) as exc_info:
            UploadedFile(
                filename="test.txt",
                file_type="instructions",
                size=-1,
                uploaded_at=now
            )

        errors = exc_info.value.errors()
        assert any(
            error["type"] == "greater_than_equal"
            for error in errors
        )


class TestFileUploadResponse:
    """Tests for FileUploadResponse model."""

    def test_valid_file_upload_response(self):
        """Test valid file upload response."""
        now = datetime.utcnow()
        file = UploadedFile(
            filename="test.pdf",
            file_type="instructions",
            size=2048,
            uploaded_at=now
        )

        response = FileUploadResponse(
            message="File uploaded successfully",
            file=file
        )

        assert response.message == "File uploaded successfully"
        assert response.file.filename == "test.pdf"
        assert response.file.size == 2048


class TestFileListResponse:
    """Tests for FileListResponse model."""

    def test_file_list_response_empty(self):
        """Test file list response with no files."""
        response = FileListResponse(
            workflow_id="wf-123",
            files=[]
        )

        assert response.workflow_id == "wf-123"
        assert len(response.files) == 0

    def test_file_list_response_with_files(self):
        """Test file list response with multiple files."""
        now = datetime.utcnow()
        files = [
            UploadedFile(
                filename=f"file{i}.pdf",
                file_type="instructions",
                size=1024 * i,
                uploaded_at=now
            )
            for i in range(1, 4)
        ]

        response = FileListResponse(
            workflow_id="wf-123",
            files=files
        )

        assert len(response.files) == 3
        assert response.files[0].filename == "file1.pdf"


class TestComponentHealth:
    """Tests for ComponentHealth model."""

    def test_component_health_healthy(self):
        """Test healthy component status."""
        health = ComponentHealth(
            status="healthy",
            message="Component is operational",
            latency_ms=1.5
        )

        assert health.status == "healthy"
        assert health.message == "Component is operational"
        assert health.latency_ms == 1.5

    def test_component_health_degraded(self):
        """Test degraded component status."""
        health = ComponentHealth(
            status="degraded",
            message="Slow response",
            latency_ms=500.0
        )

        assert health.status == "degraded"

    def test_component_health_unhealthy(self):
        """Test unhealthy component status."""
        health = ComponentHealth(
            status="unhealthy",
            message="Connection timeout"
        )

        assert health.status == "unhealthy"
        assert health.latency_ms is None

    def test_component_health_minimal(self):
        """Test component health with minimal fields."""
        health = ComponentHealth(status="healthy")

        assert health.status == "healthy"
        assert health.message is None
        assert health.latency_ms is None

    def test_component_health_negative_latency_invalid(self):
        """Test validation error for negative latency."""
        with pytest.raises(ValidationError) as exc_info:
            ComponentHealth(
                status="healthy",
                latency_ms=-1.0
            )

        errors = exc_info.value.errors()
        assert any(
            error["type"] == "greater_than_equal"
            for error in errors
        )


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_health_response_all_healthy(self):
        """Test health response with all components healthy."""
        now = datetime.utcnow()
        components = {
            "gateway": ComponentHealth(status="healthy", latency_ms=1.0),
            "database": ComponentHealth(status="healthy", latency_ms=2.0),
            "mail_agent": ComponentHealth(status="healthy", latency_ms=3.0)
        }

        response = HealthResponse(
            status="healthy",
            version="0.1.0",
            components=components,
            timestamp=now
        )

        assert response.status == "healthy"
        assert response.version == "0.1.0"
        assert len(response.components) == 3
        assert response.components["gateway"].status == "healthy"
        assert response.timestamp == now

    def test_health_response_degraded_system(self):
        """Test health response with degraded components."""
        now = datetime.utcnow()
        components = {
            "gateway": ComponentHealth(status="healthy", latency_ms=1.0),
            "database": ComponentHealth(status="degraded", latency_ms=100.0)
        }

        response = HealthResponse(
            status="degraded",
            version="0.1.0",
            components=components,
            timestamp=now
        )

        assert response.status == "degraded"

    def test_health_response_unhealthy_system(self):
        """Test health response with unhealthy components."""
        now = datetime.utcnow()
        components = {
            "gateway": ComponentHealth(status="healthy", latency_ms=1.0),
            "database": ComponentHealth(status="unhealthy", message="Connection failed")
        }

        response = HealthResponse(
            status="unhealthy",
            version="0.1.0",
            components=components,
            timestamp=now
        )

        assert response.status == "unhealthy"
        assert response.components["database"].status == "unhealthy"


class TestErrorDetail:
    """Tests for ErrorDetail model."""

    def test_error_detail_minimal(self):
        """Test error detail with minimal fields."""
        error = ErrorDetail(
            code="TEST_ERROR",
            message="Test error message"
        )

        assert error.code == "TEST_ERROR"
        assert error.message == "Test error message"
        assert error.details is None

    def test_error_detail_with_details(self):
        """Test error detail with additional details."""
        error = ErrorDetail(
            code="WORKFLOW_NOT_FOUND",
            message="Workflow not found",
            details={
                "workflow_id": "wf-123",
                "searched_in": "active_workflows"
            }
        )

        assert error.code == "WORKFLOW_NOT_FOUND"
        assert error.details["workflow_id"] == "wf-123"

    def test_error_detail_empty_details(self):
        """Test error detail with empty details dict."""
        error = ErrorDetail(
            code="TEST_ERROR",
            message="Test",
            details={}
        )

        assert error.details == {}


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response_minimal(self):
        """Test error response with minimal error detail."""
        error_detail = ErrorDetail(
            code="VALIDATION_ERROR",
            message="Validation failed"
        )

        response = ErrorResponse(error=error_detail)

        assert response.error.code == "VALIDATION_ERROR"
        assert response.error.message == "Validation failed"

    def test_error_response_with_details(self):
        """Test error response with detailed error information."""
        error_detail = ErrorDetail(
            code="WORKFLOW_ERROR",
            message="Workflow execution failed",
            details={
                "workflow_id": "wf-123",
                "step": "send_email",
                "reason": "SMTP connection timeout"
            }
        )

        response = ErrorResponse(error=error_detail)

        assert response.error.code == "WORKFLOW_ERROR"
        assert response.error.details["step"] == "send_email"

    def test_error_response_json_serialization(self):
        """Test error response JSON serialization."""
        error_detail = ErrorDetail(
            code="TEST_ERROR",
            message="Test message",
            details={"key": "value"}
        )

        response = ErrorResponse(error=error_detail)
        json_data = response.model_dump()

        assert json_data["error"]["code"] == "TEST_ERROR"
        assert json_data["error"]["message"] == "Test message"
        assert json_data["error"]["details"]["key"] == "value"


class TestResponseModelIntegration:
    """Integration tests for response models working together."""

    def test_complete_workflow_lifecycle_responses(self):
        """Test response models through complete workflow lifecycle."""
        now = datetime.utcnow()

        # 1. Create workflow
        create_response = WorkflowResponse(
            id="wf-123",
            name="Test Workflow",
            status=WorkflowStatus.CREATED,
            created_at=now,
            updated_at=now
        )
        assert create_response.status == WorkflowStatus.CREATED

        # 2. Planning status
        planning_response = WorkflowStatusResponse(
            id="wf-123",
            status=WorkflowStatus.PLANNING,
            updated_at=now
        )
        assert planning_response.status == WorkflowStatus.PLANNING

        # 3. Awaiting approval with plan
        plan = [
            PlanStep(step=1, action="send_email", description="Send email"),
            PlanStep(step=2, action="wait", description="Wait for response")
        ]
        approval_response = WorkflowStatusResponse(
            id="wf-123",
            status=WorkflowStatus.AWAITING_APPROVAL,
            plan=plan,
            target_email="test@example.com",
            requested_info="Report",
            updated_at=now
        )
        assert approval_response.status == WorkflowStatus.AWAITING_APPROVAL
        assert len(approval_response.plan) == 2

        # 4. Executing
        executing_response = WorkflowStatusResponse(
            id="wf-123",
            status=WorkflowStatus.EXECUTING,
            current_step=1,
            plan=plan,
            email_thread_id="thread-456",
            updated_at=now
        )
        assert executing_response.current_step == 1

        # 5. Completed
        completed_response = WorkflowStatusResponse(
            id="wf-123",
            status=WorkflowStatus.COMPLETED,
            current_step=2,
            plan=plan,
            received_response="Here is the report",
            updated_at=now
        )
        assert completed_response.status == WorkflowStatus.COMPLETED
        assert completed_response.received_response is not None

    def test_workflow_list_different_statuses(self):
        """Test workflow list with workflows in different states."""
        now = datetime.utcnow()
        workflows = [
            WorkflowResponse(
                id="wf-1",
                name="Workflow 1",
                status=WorkflowStatus.CREATED,
                created_at=now,
                updated_at=now
            ),
            WorkflowResponse(
                id="wf-2",
                name="Workflow 2",
                status=WorkflowStatus.EXECUTING,
                created_at=now,
                updated_at=now
            ),
            WorkflowResponse(
                id="wf-3",
                name="Workflow 3",
                status=WorkflowStatus.COMPLETED,
                created_at=now,
                updated_at=now
            )
        ]

        list_response = WorkflowListResponse(
            workflows=workflows,
            total=3
        )

        assert len(list_response.workflows) == 3
        assert list_response.workflows[1].status == WorkflowStatus.EXECUTING
