"""
Mock SMTP server implementation.

Provides an async SMTP server for receiving emails.
"""

import asyncio
import email
from email.header import decode_header
from email.message import Message
from typing import Any

import structlog
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope, Session, SMTP

from info_agent.email_server.models import (
    Attachment,
    Email,
    EmailAddress,
    EmailStatus,
)
from info_agent.email_server.storage import EmailStorage
from info_agent.email_server.webhooks import WebhookManager
from info_agent.utils.exceptions import EmailServerError

logger = structlog.get_logger(__name__)


class SMTPHandler:
    """
    SMTP message handler.

    Processes incoming SMTP messages and stores them in email storage.

    Attributes:
        _storage: Email storage instance.
        _webhook_manager: Webhook manager for notifications.
    """

    def __init__(
        self,
        storage: EmailStorage,
        webhook_manager: WebhookManager | None = None,
    ) -> None:
        """
        Initialize SMTP handler.

        Args:
            storage: Email storage instance.
            webhook_manager: Optional webhook manager.
        """
        self._storage = storage
        self._webhook_manager = webhook_manager

        logger.info("smtp_handler_initialized")

    async def handle_RCPT(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
        address: str,
        rcpt_options: list[str],
    ) -> str:
        """
        Handle RCPT TO command.

        Args:
            server: SMTP server instance.
            session: Current session.
            envelope: Message envelope.
            address: Recipient address.
            rcpt_options: RCPT options.

        Returns:
            SMTP response code.
        """
        # Accept all recipients for mock server
        envelope.rcpt_tos.append(address)
        logger.debug("smtp_rcpt_to", address=address)
        return "250 OK"

    async def handle_DATA(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
    ) -> str:
        """
        Handle DATA command (message content).

        Args:
            server: SMTP server instance.
            session: Current session.
            envelope: Message envelope with content.

        Returns:
            SMTP response code.
        """
        try:
            # Parse the email message
            message = email.message_from_bytes(envelope.content)

            # Extract sender
            from_addr = envelope.mail_from or ""
            from_header = message.get("From", from_addr)
            from_address = EmailAddress.from_string(from_header)

            # Extract recipients
            to_addresses = []
            for addr in envelope.rcpt_tos:
                to_addresses.append(EmailAddress.from_string(addr))

            # Also parse To header for display names
            to_header = message.get("To", "")
            if to_header:
                for part in to_header.split(","):
                    part = part.strip()
                    if part:
                        parsed = EmailAddress.from_string(part)
                        # Update display name if we have a match
                        for i, addr in enumerate(to_addresses):
                            if addr.address.lower() == parsed.address.lower():
                                to_addresses[i] = parsed

            # Extract CC
            cc_addresses = []
            cc_header = message.get("Cc", "")
            if cc_header:
                for part in cc_header.split(","):
                    part = part.strip()
                    if part:
                        cc_addresses.append(EmailAddress.from_string(part))

            # Extract subject
            subject = self._decode_header(message.get("Subject", ""))

            # Extract body and attachments
            body_text, body_html, attachments = self._extract_content(message)

            # Extract threading headers
            message_id = message.get("Message-ID")
            in_reply_to = message.get("In-Reply-To")
            references_header = message.get("References", "")
            references = [r.strip() for r in references_header.split() if r.strip()]

            # Build email object
            email_obj = Email(
                from_address=from_address,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                attachments=attachments,
                message_id=message_id,
                in_reply_to=in_reply_to,
                references=references,
                status=EmailStatus.RECEIVED,
                mailbox="inbox",
                headers=dict(message.items()),
            )

            # Store the email
            stored_email = self._storage.store(email_obj)

            logger.info(
                "smtp_email_received",
                email_id=stored_email.id,
                from_address=from_addr,
                to_addresses=[a.address for a in to_addresses],
                subject=subject[:50] if subject else "",
            )

            # Dispatch webhook
            if self._webhook_manager:
                self._webhook_manager.dispatch_email_event(
                    WebhookManager.EVENT_EMAIL_RECEIVED,
                    stored_email,
                )

            return "250 Message accepted for delivery"

        except Exception as e:
            logger.error("smtp_data_error", error=str(e))
            return f"550 Error processing message: {e}"

    def _decode_header(self, header_value: str | None) -> str:
        """
        Decode an email header value.

        Args:
            header_value: Raw header value.

        Returns:
            Decoded string.
        """
        if not header_value:
            return ""

        decoded_parts = decode_header(header_value)
        result_parts = []

        for content, charset in decoded_parts:
            if isinstance(content, bytes):
                try:
                    result_parts.append(content.decode(charset or "utf-8"))
                except (UnicodeDecodeError, LookupError):
                    result_parts.append(content.decode("utf-8", errors="replace"))
            else:
                result_parts.append(content)

        return "".join(result_parts)

    def _extract_content(
        self, message: Message
    ) -> tuple[str, str | None, list[Attachment]]:
        """
        Extract body and attachments from email message.

        Args:
            message: Email message object.

        Returns:
            Tuple of (text body, html body, list of attachments).
        """
        body_text = ""
        body_html = None
        attachments = []

        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Check if it's an attachment
                if "attachment" in content_disposition:
                    filename = part.get_filename() or "attachment"
                    payload = part.get_payload(decode=True)
                    if payload:
                        import base64

                        attachments.append(
                            Attachment(
                                filename=filename,
                                content_type=content_type,
                                content=base64.b64encode(payload).decode("utf-8"),
                                size=len(payload),
                            )
                        )
                elif content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode("utf-8", errors="replace")
                elif content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_html = payload.decode("utf-8", errors="replace")
        else:
            # Non-multipart message
            content_type = message.get_content_type()
            payload = message.get_payload(decode=True)

            if payload:
                if content_type == "text/html":
                    body_html = payload.decode("utf-8", errors="replace")
                else:
                    body_text = payload.decode("utf-8", errors="replace")

        return body_text, body_html, attachments


class MockSMTPServer:
    """
    Mock SMTP server for development and testing.

    Provides a complete SMTP server that stores emails in memory
    and supports webhooks for real-time notifications.

    Attributes:
        _host: Host to bind to.
        _port: Port to listen on.
        _storage: Email storage instance.
        _webhook_manager: Webhook manager instance.
        _controller: SMTP controller (when running).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 2525,
        storage: EmailStorage | None = None,
        webhook_manager: WebhookManager | None = None,
    ) -> None:
        """
        Initialize mock SMTP server.

        Args:
            host: Host to bind to.
            port: Port to listen on.
            storage: Email storage (created if not provided).
            webhook_manager: Webhook manager (created if not provided).
        """
        self._host = host
        self._port = port
        self._storage = storage or EmailStorage()
        self._webhook_manager = webhook_manager or WebhookManager()
        self._controller: Controller | None = None
        self._running = False

        logger.info(
            "smtp_server_initialized",
            host=host,
            port=port,
        )

    @property
    def storage(self) -> EmailStorage:
        """Get email storage instance."""
        return self._storage

    @property
    def webhook_manager(self) -> WebhookManager:
        """Get webhook manager instance."""
        return self._webhook_manager

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    @property
    def host(self) -> str:
        """Get server host."""
        return self._host

    @property
    def port(self) -> int:
        """Get server port."""
        return self._port

    def start(self) -> None:
        """
        Start the SMTP server.

        Raises:
            EmailServerError: If server fails to start.
        """
        if self._running:
            logger.warning("smtp_server_already_running")
            return

        try:
            handler = SMTPHandler(self._storage, self._webhook_manager)
            self._controller = Controller(
                handler,
                hostname=self._host,
                port=self._port,
            )
            self._controller.start()
            self._running = True

            logger.info(
                "smtp_server_started",
                host=self._host,
                port=self._port,
            )

        except Exception as e:
            logger.error("smtp_server_start_failed", error=str(e))
            raise EmailServerError(
                message=f"Failed to start SMTP server: {e}",
                details={"host": self._host, "port": self._port, "error": str(e)},
            ) from e

    def stop(self) -> None:
        """Stop the SMTP server."""
        if not self._running:
            logger.warning("smtp_server_not_running")
            return

        try:
            if self._controller:
                self._controller.stop()
                self._controller = None

            self._running = False

            logger.info("smtp_server_stopped")

        except Exception as e:
            logger.error("smtp_server_stop_failed", error=str(e))

    def __enter__(self) -> "MockSMTPServer":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop()
