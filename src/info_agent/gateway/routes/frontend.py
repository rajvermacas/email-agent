"""Frontend routes for serving HTML templates.

This module provides routes for serving the Info-Agent dashboard
using Jinja2 templates and static files.
"""

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

# Router for frontend pages
router = APIRouter(tags=["frontend"])

# Template directory path
FRONTEND_DIR = Path(__file__).parent.parent.parent.parent.parent / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"

# Initialize templates - will be None if templates don't exist
_templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    """Get Jinja2 templates instance.

    Returns:
        Jinja2Templates: The templates instance.

    Raises:
        RuntimeError: If templates directory does not exist.
    """
    global _templates

    if _templates is None:
        if not TEMPLATES_DIR.exists():
            logger.error(f"Templates directory not found: {TEMPLATES_DIR}")
            raise RuntimeError(f"Templates directory not found: {TEMPLATES_DIR}")

        logger.info(f"Initializing Jinja2 templates from: {TEMPLATES_DIR}")
        _templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    return _templates


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the main dashboard page.

    Args:
        request: The FastAPI request.

    Returns:
        HTMLResponse: The rendered dashboard HTML.
    """
    logger.info("Rendering dashboard page")
    templates = get_templates()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )


@router.get("/workflows/create", response_class=HTMLResponse)
async def create_workflow_page(request: Request) -> HTMLResponse:
    """Render the workflow creation page.

    Args:
        request: The FastAPI request.

    Returns:
        HTMLResponse: The rendered create workflow HTML.
    """
    logger.info("Rendering create workflow page")
    templates = get_templates()
    return templates.TemplateResponse(
        request=request,
        name="workflow/create.html",
    )


@router.get("/workflows/{workflow_id}", response_class=HTMLResponse)
async def workflow_detail_page(
    request: Request,
    workflow_id: str,
) -> HTMLResponse:
    """Render the workflow detail page.

    Args:
        request: The FastAPI request.
        workflow_id: The workflow identifier.

    Returns:
        HTMLResponse: The rendered workflow detail HTML.
    """
    logger.info(f"Rendering workflow detail page for: {workflow_id}")
    templates = get_templates()
    return templates.TemplateResponse(
        request=request,
        name="workflow/detail.html",
        context={"workflow_id": workflow_id},
    )


def reset_templates() -> None:
    """Reset the templates instance for testing."""
    global _templates
    _templates = None
    logger.debug("Templates instance reset")
