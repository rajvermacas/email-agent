"""
FastAPI route modules for the Gateway.

This package contains all API route definitions organized by domain:
- workflows: Workflow management endpoints
- webhooks: Webhook receivers
- health: Health check endpoints
- frontend: HTML template routes
"""

from info_agent.gateway.routes.frontend import router as frontend_router
from info_agent.gateway.routes.health import router as health_router
from info_agent.gateway.routes.webhooks import router as webhooks_router
from info_agent.gateway.routes.workflows import router as workflows_router

__all__ = [
    "frontend_router",
    "health_router",
    "webhooks_router",
    "workflows_router",
]
