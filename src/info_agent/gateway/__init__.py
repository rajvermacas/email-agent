"""
FastAPI Gateway for Info-Agent.

The Gateway serves as the main entry point for the system, providing:
- REST API endpoints for workflow management
- SSE streaming for AG-UI events
- Webhook receivers for email notifications
- Embedded Supervisor Agent integration

Components:
- GatewayApp: Main FastAPI application factory
- WorkflowRouter: Workflow management endpoints
- WebhookRouter: Webhook receivers
- HealthRouter: Health check endpoints
"""

from info_agent.gateway.app import create_app, GatewayApp

__all__ = [
    "create_app",
    "GatewayApp",
]
