"""
Health check routes for the Gateway.

This module provides endpoints for monitoring the health of the
gateway and its dependencies.
"""

import logging
import time
from datetime import datetime

from fastapi import APIRouter, Request

from info_agent.gateway.models import ComponentHealth, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """
    Check the health of the gateway and its components.

    Returns:
        HealthResponse with overall status and component health.
    """
    logger.info("Health check requested")

    components: dict[str, ComponentHealth] = {}
    overall_status = "healthy"

    # Check supervisor
    supervisor_health = await _check_supervisor(request)
    components["supervisor"] = supervisor_health
    if supervisor_health.status != "ok":
        overall_status = "degraded"

    # Check database (if using checkpointer)
    db_health = await _check_database(request)
    components["database"] = db_health
    if db_health.status == "down":
        overall_status = "degraded"

    response = HealthResponse(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.utcnow(),
        components=components,
    )

    logger.info("Health check completed: status=%s", overall_status)
    return response


@router.get("/health/live")
async def liveness_probe() -> dict[str, str]:
    """
    Kubernetes liveness probe endpoint.

    Returns 200 if the service is running.

    Returns:
        Simple status response.
    """
    logger.debug("Liveness probe requested")
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_probe(request: Request) -> dict[str, str]:
    """
    Kubernetes readiness probe endpoint.

    Returns 200 if the service is ready to accept requests.

    Returns:
        Simple status response.

    Raises:
        HTTPException: If service is not ready.
    """
    logger.debug("Readiness probe requested")

    # Check if supervisor is available
    supervisor = getattr(request.app.state, "supervisor", None)
    if supervisor is None:
        logger.warning("Readiness check failed: supervisor not available")
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="Service not ready: supervisor not initialized",
        )

    return {"status": "ok"}


async def _check_supervisor(request: Request) -> ComponentHealth:
    """
    Check supervisor agent health.

    Args:
        request: FastAPI request with app state.

    Returns:
        ComponentHealth for supervisor.
    """
    logger.debug("Checking supervisor health")
    start_time = time.time()

    try:
        supervisor = getattr(request.app.state, "supervisor", None)
        if supervisor is None:
            logger.warning("Supervisor not found in app state")
            return ComponentHealth(
                status="down",
                error="Supervisor not initialized",
            )

        # Basic check that supervisor exists and has workflow
        if supervisor.workflow is None:
            logger.warning("Supervisor workflow not initialized")
            return ComponentHealth(
                status="degraded",
                error="Workflow not initialized",
            )

        latency_ms = (time.time() - start_time) * 1000
        logger.debug("Supervisor health check completed in %.2fms", latency_ms)

        return ComponentHealth(
            status="ok",
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error("Supervisor health check failed: %s", e)
        return ComponentHealth(
            status="down",
            error=str(e),
        )


async def _check_database(request: Request) -> ComponentHealth:
    """
    Check database health.

    Args:
        request: FastAPI request with app state.

    Returns:
        ComponentHealth for database.
    """
    logger.debug("Checking database health")
    start_time = time.time()

    try:
        supervisor = getattr(request.app.state, "supervisor", None)
        if supervisor is None:
            return ComponentHealth(
                status="unknown",
                error="Supervisor not available",
            )

        # Check if checkpointer is configured
        if supervisor.workflow.checkpointer is None:
            # No persistence configured, but that's OK
            return ComponentHealth(
                status="ok",
                latency_ms=0,
                error="No persistence configured (in-memory mode)",
            )

        latency_ms = (time.time() - start_time) * 1000
        logger.debug("Database health check completed in %.2fms", latency_ms)

        return ComponentHealth(
            status="ok",
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return ComponentHealth(
            status="down",
            error=str(e),
        )


logger.info("Health routes module initialized")
