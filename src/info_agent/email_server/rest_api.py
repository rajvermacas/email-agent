"""
REST API for mock email server.

Provides HTTP endpoints for managing emails, webhooks, and server operations.
"""

from typing import Any

import structlog
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from info_agent.email_server.models import (
    Email,
    EmailCreateRequest,
    EmailListResponse,
    EmailStatus,
    WebhookConfig,
)
from info_agent.email_server.storage import EmailStorage
from info_agent.email_server.webhooks import WebhookManager
from info_agent.utils.helpers import get_current_timestamp

logger = structlog.get_logger(__name__)


def create_email_api(
    storage: EmailStorage,
    webhook_manager: WebhookManager,
) -> APIRouter:
    """
    Create FastAPI router for email API.

    Args:
        storage: Email storage instance.
        webhook_manager: Webhook manager instance.

    Returns:
        Configured APIRouter.
    """
    router = APIRouter(prefix="/api/emails", tags=["emails"])

    @router.get("", response_model=EmailListResponse)
    async def list_emails(
        address: str = Query(..., description="Email address to list emails for"),
        mailbox: str = Query("inbox", description="Mailbox to list"),
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Page size"),
        status: EmailStatus | None = Query(None, description="Filter by status"),
    ) -> EmailListResponse:
        """List emails in a mailbox."""
        logger.debug(
            "api_list_emails",
            address=address,
            mailbox=mailbox,
            page=page,
        )

        emails, total = storage.list_by_mailbox(
            address=address,
            mailbox=mailbox,
            page=page,
            page_size=page_size,
            status=status,
        )

        has_more = (page * page_size) < total

        return EmailListResponse(
            emails=emails,
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more,
        )

    @router.get("/search")
    async def search_emails(
        query: str = Query(..., min_length=1, description="Search query"),
        address: str | None = Query(None, description="Filter by address"),
        mailbox: str | None = Query(None, description="Filter by mailbox"),
        limit: int = Query(50, ge=1, le=100, description="Max results"),
    ) -> list[Email]:
        """Search emails by content."""
        logger.debug("api_search_emails", query=query, limit=limit)

        return storage.search(
            query=query,
            address=address,
            mailbox=mailbox,
            limit=limit,
        )

    @router.get("/threads/{thread_id}")
    async def get_thread(thread_id: str) -> list[Email]:
        """Get all emails in a thread."""
        logger.debug("api_get_thread", thread_id=thread_id)

        emails = storage.list_by_thread(thread_id)
        if not emails:
            raise HTTPException(status_code=404, detail="Thread not found")

        return emails

    @router.get("/{email_id}", response_model=Email)
    async def get_email(email_id: str) -> Email:
        """Get a specific email by ID."""
        logger.debug("api_get_email", email_id=email_id)

        email = storage.get(email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        return email

    @router.post("", response_model=Email, status_code=201)
    async def send_email(request: EmailCreateRequest) -> Email:
        """Send/create a new email."""
        logger.info(
            "api_send_email",
            from_address=request.from_address,
            to_addresses=request.to_addresses,
        )

        email = request.to_email()
        email.status = EmailStatus.SENT
        email.mailbox = "sent"

        stored = storage.store(email)

        # Also store a copy in recipient's inbox
        for to_addr in email.to_addresses:
            inbox_copy = email.model_copy()
            inbox_copy.mailbox = "inbox"
            inbox_copy.status = EmailStatus.DELIVERED
            storage.store(inbox_copy)

        # Dispatch webhook
        webhook_manager.dispatch_email_event(
            WebhookManager.EVENT_EMAIL_SENT,
            stored,
        )

        return stored

    @router.post("/{email_id}/read")
    async def mark_as_read(email_id: str) -> Email:
        """Mark an email as read."""
        logger.debug("api_mark_read", email_id=email_id)

        email = storage.get(email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        email.mark_as_read()
        storage.update(email)

        webhook_manager.dispatch_email_event(
            WebhookManager.EVENT_EMAIL_READ,
            email,
        )

        return email

    @router.delete("/{email_id}", status_code=204)
    async def delete_email(email_id: str) -> None:
        """Delete an email."""
        logger.info("api_delete_email", email_id=email_id)

        if not storage.delete(email_id):
            raise HTTPException(status_code=404, detail="Email not found")

    @router.get("/stats/summary")
    async def get_stats() -> dict[str, Any]:
        """Get email storage statistics."""
        return storage.get_stats()

    return router


def create_webhook_api(webhook_manager: WebhookManager) -> APIRouter:
    """
    Create FastAPI router for webhook API.

    Args:
        webhook_manager: Webhook manager instance.

    Returns:
        Configured APIRouter.
    """
    router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

    @router.get("", response_model=list[WebhookConfig])
    async def list_webhooks(
        active_only: bool = Query(False, description="Only return active webhooks"),
    ) -> list[WebhookConfig]:
        """List all registered webhooks."""
        return webhook_manager.list_all(active_only=active_only)

    @router.post("", response_model=WebhookConfig, status_code=201)
    async def register_webhook(
        url: str = Query(..., description="Webhook URL"),
        events: list[str] | None = Query(None, description="Events to subscribe to"),
        secret: str | None = Query(None, description="Webhook secret"),
    ) -> WebhookConfig:
        """Register a new webhook."""
        logger.info("api_register_webhook", url=url, events=events)

        try:
            return webhook_manager.register(
                url=url,
                events=events,
                secret=secret,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @router.get("/{webhook_id}", response_model=WebhookConfig)
    async def get_webhook(webhook_id: str) -> WebhookConfig:
        """Get a specific webhook."""
        webhook = webhook_manager.get(webhook_id)
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return webhook

    @router.patch("/{webhook_id}", response_model=WebhookConfig)
    async def update_webhook(
        webhook_id: str,
        url: str | None = Query(None),
        events: list[str] | None = Query(None),
        active: bool | None = Query(None),
    ) -> WebhookConfig:
        """Update a webhook configuration."""
        webhook = webhook_manager.update(
            webhook_id=webhook_id,
            url=url,
            events=events,
            active=active,
        )
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return webhook

    @router.delete("/{webhook_id}", status_code=204)
    async def unregister_webhook(webhook_id: str) -> None:
        """Unregister a webhook."""
        if not webhook_manager.unregister(webhook_id):
            raise HTTPException(status_code=404, detail="Webhook not found")

    @router.get("/events/types")
    async def get_event_types() -> list[str]:
        """Get available webhook event types."""
        return WebhookManager.ALL_EVENTS

    return router


def create_email_server_app(
    storage: EmailStorage | None = None,
    webhook_manager: WebhookManager | None = None,
) -> FastAPI:
    """
    Create complete FastAPI application for email server.

    Args:
        storage: Email storage instance (created if not provided).
        webhook_manager: Webhook manager (created if not provided).

    Returns:
        Configured FastAPI application.
    """
    storage = storage or EmailStorage()
    webhook_manager = webhook_manager or WebhookManager()

    app = FastAPI(
        title="Mock Email Server",
        description="Development email server with REST API and webhooks",
        version="1.0.0",
    )

    # Include routers
    app.include_router(create_email_api(storage, webhook_manager))
    app.include_router(create_webhook_api(webhook_manager))

    # Store references for access
    app.state.storage = storage
    app.state.webhook_manager = webhook_manager

    @app.get("/", response_class=HTMLResponse)
    async def email_web_ui() -> str:
        """Simple web UI for viewing emails."""
        return get_email_web_ui_html()

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": get_current_timestamp(),
            "email_count": storage.count(),
            "webhook_count": webhook_manager.count(),
        }

    logger.info("email_server_app_created")

    return app


def get_email_web_ui_html() -> str:
    """
    Get HTML for simple email web UI.

    Returns:
        HTML string for email viewer.
    """
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mock Email Server</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <header class="mb-8">
            <h1 class="text-3xl font-bold text-gray-800">Mock Email Server</h1>
            <p class="text-gray-600">Development email viewer</p>
        </header>

        <div class="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">Check Mailbox</h2>
            <form id="mailbox-form" class="flex gap-4">
                <input
                    type="email"
                    id="email-address"
                    placeholder="Enter email address..."
                    class="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                <select
                    id="mailbox-select"
                    class="px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    <option value="inbox">Inbox</option>
                    <option value="sent">Sent</option>
                </select>
                <button
                    type="submit"
                    class="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
                >
                    Load Emails
                </button>
            </form>
        </div>

        <div id="email-list" class="bg-white rounded-lg shadow-md">
            <div class="p-6 text-center text-gray-500">
                Enter an email address to view emails
            </div>
        </div>

        <div id="email-detail" class="hidden mt-6 bg-white rounded-lg shadow-md p-6">
            <button
                onclick="closeEmailDetail()"
                class="mb-4 text-blue-500 hover:underline"
            >
                &larr; Back to list
            </button>
            <div id="email-content"></div>
        </div>
    </div>

    <script>
        const form = document.getElementById('mailbox-form');
        const emailList = document.getElementById('email-list');
        const emailDetail = document.getElementById('email-detail');
        const emailContent = document.getElementById('email-content');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const address = document.getElementById('email-address').value;
            const mailbox = document.getElementById('mailbox-select').value;

            if (!address) return;

            emailList.innerHTML = '<div class="p-6 text-center">Loading...</div>';

            try {
                const response = await fetch(
                    `/api/emails?address=${encodeURIComponent(address)}&mailbox=${mailbox}`
                );
                const data = await response.json();

                if (data.emails.length === 0) {
                    emailList.innerHTML = '<div class="p-6 text-center text-gray-500">No emails found</div>';
                    return;
                }

                let html = '<ul class="divide-y">';
                for (const email of data.emails) {
                    html += `
                        <li class="p-4 hover:bg-gray-50 cursor-pointer" onclick="showEmail('${email.id}')">
                            <div class="flex justify-between">
                                <span class="font-medium">${escapeHtml(email.from_address.address)}</span>
                                <span class="text-sm text-gray-500">${email.created_at}</span>
                            </div>
                            <div class="text-gray-800">${escapeHtml(email.subject || '(no subject)')}</div>
                            <div class="text-sm text-gray-500 truncate">${escapeHtml(email.body_text.substring(0, 100))}</div>
                        </li>
                    `;
                }
                html += '</ul>';
                emailList.innerHTML = html;
            } catch (error) {
                emailList.innerHTML = `<div class="p-6 text-center text-red-500">Error: ${error.message}</div>`;
            }
        });

        async function showEmail(id) {
            try {
                const response = await fetch(`/api/emails/${id}`);
                const email = await response.json();

                emailContent.innerHTML = `
                    <div class="space-y-4">
                        <div>
                            <span class="font-semibold">From:</span> ${escapeHtml(email.from_address.address)}
                        </div>
                        <div>
                            <span class="font-semibold">To:</span> ${email.to_addresses.map(a => escapeHtml(a.address)).join(', ')}
                        </div>
                        <div>
                            <span class="font-semibold">Subject:</span> ${escapeHtml(email.subject)}
                        </div>
                        <div>
                            <span class="font-semibold">Date:</span> ${email.created_at}
                        </div>
                        <hr>
                        <div class="whitespace-pre-wrap">${escapeHtml(email.body_text)}</div>
                    </div>
                `;

                emailList.classList.add('hidden');
                emailDetail.classList.remove('hidden');

                // Mark as read
                await fetch(`/api/emails/${id}/read`, { method: 'POST' });
            } catch (error) {
                alert('Error loading email: ' + error.message);
            }
        }

        function closeEmailDetail() {
            emailDetail.classList.add('hidden');
            emailList.classList.remove('hidden');
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>
"""
