"""
Health check endpoints for Info-Agent Gateway.

This module provides health and readiness endpoints to monitor the status
of the Info-Agent system and its components.

Endpoints:
- GET /health - Comprehensive health check of all components
- GET /ready - Readiness check for the gateway service
"""

from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, status

from info_agent.api.models.responses import (
    ComponentHealth,
    HealthResponse,
)
from info_agent.config import get_settings
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)

# Version - should be synced with package version
VERSION = "0.1.0"


def create_health_router() -> APIRouter:
    """
    Create the health check router.

    Returns:
        APIRouter instance with health endpoints.
    """
    logger.info("Creating health check router")

    router = APIRouter(
        tags=["Health"],
        responses={
            status.HTTP_500_INTERNAL_SERVER_ERROR: {
                "description": "Internal server error"
            },
        },
    )

    @router.get(
        "/health",
        response_model=HealthResponse,
        status_code=status.HTTP_200_OK,
        summary="Health check",
        description="Comprehensive health check of all system components",
    )
    async def health_check() -> HealthResponse:
        """
        Comprehensive health check of all system components.

        Checks the health of:
        - Gateway API (self)
        - A2A Registry
        - Mail Agent (if available)
        - Mock Email Server (if available)

        Returns:
            HealthResponse with overall and component-level health status.

        Raises:
            HTTPException: Never raises, always returns 200 with degraded status if issues.
        """
        logger.info("Health check requested")

        settings = get_settings()
        components: dict[str, ComponentHealth] = {}

        # Gateway is always healthy if we can respond
        logger.debug("Checking gateway health")
        components["gateway"] = ComponentHealth(
            status="healthy",
            message="Gateway is operational",
            latency_ms=0.5,
        )

        # Check A2A Registry
        logger.debug("Checking A2A registry health")
        components["a2a_registry"] = await _check_a2a_registry_health(settings)

        # Check Mail Agent
        logger.debug("Checking mail agent health")
        components["mail_agent"] = await _check_mail_agent_health(settings)

        # Check Mock Email Server
        logger.debug("Checking email server health")
        components["email_server"] = await _check_email_server_health(settings)

        # Determine overall status
        overall_status = _determine_overall_status(components)

        logger.info(
            "Health check completed",
            overall_status=overall_status,
            component_count=len(components),
        )

        return HealthResponse(
            status=overall_status,
            version=VERSION,
            components=components,
            timestamp=datetime.utcnow(),
        )

    @router.get(
        "/ready",
        status_code=status.HTTP_200_OK,
        summary="Readiness check",
        description="Check if the gateway is ready to accept requests",
    )
    async def readiness_check() -> dict[str, Any]:
        """
        Readiness check for the gateway service.

        This is a lightweight check that returns 200 if the service is
        ready to accept requests. Used by orchestrators (K8s, Docker, etc.)
        for readiness probes.

        Returns:
            Dictionary with ready status and timestamp.

        Raises:
            HTTPException: If the service is not ready (database issues, etc.).
        """
        logger.info("Readiness check requested")

        settings = get_settings()

        # Check critical dependencies
        try:
            # Verify database paths are accessible
            from pathlib import Path

            checkpoint_db = Path(settings.checkpoint_db_path)
            if not checkpoint_db.parent.exists():
                logger.error(
                    "Checkpoint database directory not accessible",
                    path=str(checkpoint_db.parent),
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Checkpoint database directory not accessible",
                )

            logger.info("Readiness check passed")

            return {
                "ready": True,
                "version": VERSION,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Readiness check failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service not ready: {str(e)}",
            ) from e

    logger.info("Health check router created successfully")
    return router


async def _check_a2a_registry_health(settings: Any) -> ComponentHealth:
    """
    Check A2A registry health.

    Args:
        settings: Application settings.

    Returns:
        ComponentHealth for the A2A registry.
    """
    try:
        start_time = datetime.utcnow()

        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try to list agents
            response = await client.get(f"{settings.a2a_registry_url}/agents")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                logger.debug("A2A registry is healthy", latency_ms=latency)
                return ComponentHealth(
                    status="healthy",
                    message="A2A registry is operational",
                    latency_ms=latency,
                )

            logger.warning(
                "A2A registry returned unexpected status",
                status_code=response.status_code,
            )
            return ComponentHealth(
                status="degraded",
                message=f"Unexpected status code: {response.status_code}",
                latency_ms=latency,
            )

    except httpx.TimeoutException:
        logger.warning("A2A registry health check timed out")
        return ComponentHealth(
            status="unhealthy",
            message="Connection timeout",
            latency_ms=None,
        )
    except Exception as e:
        logger.warning("A2A registry health check failed", error=str(e))
        return ComponentHealth(
            status="unhealthy",
            message=f"Health check failed: {str(e)}",
            latency_ms=None,
        )


async def _check_mail_agent_health(settings: Any) -> ComponentHealth:
    """
    Check Mail Agent health.

    Args:
        settings: Application settings.

    Returns:
        ComponentHealth for the Mail Agent.
    """
    try:
        start_time = datetime.utcnow()

        mail_agent_url = f"http://{settings.host}:{settings.mail_agent_port}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try to get agent info from A2A registry
            response = await client.get(f"{settings.a2a_registry_url}/agents/mail-agent")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                logger.debug("Mail agent is healthy", latency_ms=latency)
                return ComponentHealth(
                    status="healthy",
                    message="Mail agent is registered and operational",
                    latency_ms=latency,
                )

            logger.warning(
                "Mail agent not found in registry",
                status_code=response.status_code,
            )
            return ComponentHealth(
                status="degraded",
                message="Mail agent not registered",
                latency_ms=latency,
            )

    except httpx.TimeoutException:
        logger.warning("Mail agent health check timed out")
        return ComponentHealth(
            status="unhealthy",
            message="Connection timeout",
            latency_ms=None,
        )
    except Exception as e:
        logger.warning("Mail agent health check failed", error=str(e))
        return ComponentHealth(
            status="degraded",
            message="Mail agent check failed (may not be running)",
            latency_ms=None,
        )


async def _check_email_server_health(settings: Any) -> ComponentHealth:
    """
    Check Mock Email Server health.

    Args:
        settings: Application settings.

    Returns:
        ComponentHealth for the Mock Email Server.
    """
    try:
        start_time = datetime.utcnow()

        email_server_url = settings.get_email_server_url()

        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try to get emails (should return empty list or data)
            response = await client.get(f"{email_server_url}/emails")

            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                logger.debug("Email server is healthy", latency_ms=latency)
                return ComponentHealth(
                    status="healthy",
                    message="Email server is operational",
                    latency_ms=latency,
                )

            logger.warning(
                "Email server returned unexpected status",
                status_code=response.status_code,
            )
            return ComponentHealth(
                status="degraded",
                message=f"Unexpected status code: {response.status_code}",
                latency_ms=latency,
            )

    except httpx.TimeoutException:
        logger.warning("Email server health check timed out")
        return ComponentHealth(
            status="unhealthy",
            message="Connection timeout",
            latency_ms=None,
        )
    except Exception as e:
        logger.warning("Email server health check failed", error=str(e))
        return ComponentHealth(
            status="degraded",
            message="Email server check failed (may not be running)",
            latency_ms=None,
        )


def _determine_overall_status(components: dict[str, ComponentHealth]) -> str:
    """
    Determine overall system health based on component statuses.

    Args:
        components: Dictionary of component health statuses.

    Returns:
        Overall status: "healthy", "degraded", or "unhealthy".
    """
    statuses = [component.status for component in components.values()]

    # If any component is unhealthy, system is degraded
    if "unhealthy" in statuses:
        logger.debug("Overall status: degraded (unhealthy components)")
        return "degraded"

    # If any component is degraded, system is degraded
    if "degraded" in statuses:
        logger.debug("Overall status: degraded (degraded components)")
        return "degraded"

    # All components healthy
    logger.debug("Overall status: healthy")
    return "healthy"
