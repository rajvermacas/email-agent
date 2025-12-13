"""
SMTP server implementation using aiosmtpd.

This module provides an async SMTP server that receives emails, stores them
in the database, and triggers webhook notifications. Uses aiosmtpd for the
SMTP protocol handling.

Usage:
    from info_agent.email.smtp import start_smtp_server

    await start_smtp_server(
        host="localhost",
        port=1025,
        storage=storage,
        webhook_notifier=notifier
    )
"""

import asyncio
import base64
import email
import re
import uuid
from datetime import datetime, timezone
from email.message import Message

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, Envelope, Session

from info_agent.config import get_settings
from info_agent.email.models import EmailAttachment, StoredEmail
from info_agent.email.storage import EmailStorage
from info_agent.email.webhook import WebhookNotifier
from info_agent.utils.exceptions import EmailError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class EmailHandler:
    """
    SMTP handler for receiving and processing emails.

    Implements the aiosmtpd handler interface to receive emails via SMTP,
    parse them, store in database, and trigger webhooks.
    """

    def __init__(
        self, storage: EmailStorage, webhook_notifier: WebhookNotifier | None = None
    ) -> None:
        """
        Initialize email handler.

        Args:
            storage: Email storage instance for persisting emails.
            webhook_notifier: Optional webhook notifier for email events.

        Raises:
            EmailError: If storage is not provided.
        """
        if storage is None:
            raise EmailError(
                message="Storage is required for EmailHandler",
                details={"storage": storage},
            )

        self.storage = storage
        self.webhook_notifier = webhook_notifier
        logger.info(
            "EmailHandler initialized",
            has_webhook=self.webhook_notifier is not None,
        )

    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope) -> str:
        """
        Handle incoming email data from SMTP.

        This method is called by aiosmtpd when an email is received.

        Args:
            server: SMTP server instance.
            session: SMTP session information.
            envelope: Email envelope containing message data.

        Returns:
            SMTP status message.
        """
        logger.info(
            "Received email via SMTP",
            mail_from=envelope.mail_from,
            rcpt_tos=envelope.rcpt_tos,
            peer=session.peer,
        )

        try:
            # Parse email message
            msg = email.message_from_bytes(envelope.content)
            logger.debug("Email message parsed", mail_from=envelope.mail_from)

            # Extract email fields
            from_address = self._extract_email(envelope.mail_from)
            to_address = self._extract_email(
                envelope.rcpt_tos[0] if envelope.rcpt_tos else ""
            )
            subject = self._decode_header(msg.get("Subject", "(No Subject)"))
            body_text = self._extract_body(msg)
            thread_id = self._extract_thread_id(msg)
            attachments = self._extract_attachments(msg)

            logger.debug(
                "Email fields extracted",
                from_address=from_address,
                to_address=to_address,
                subject=subject,
                thread_id=thread_id,
                attachment_count=len(attachments),
            )

            # Generate unique message ID
            message_id = f"msg-{uuid.uuid4().hex[:16]}"
            logger.debug("Generated message ID", message_id=message_id)

            # Create stored email
            stored_email = StoredEmail(
                id=message_id,
                inbox=to_address,
                thread_id=thread_id,
                from_address=from_address,
                to_address=to_address,
                subject=subject,
                body_text=body_text,
                attachments=attachments,
                received_at=datetime.now(timezone.utc),
                read=False,
            )

            # Save to storage
            await self.storage.save_email(stored_email)
            logger.info(
                "Email stored successfully",
                message_id=message_id,
                inbox=to_address,
                from_address=from_address,
            )

            # Send webhook notification
            if self.webhook_notifier:
                try:
                    await self.webhook_notifier.notify(stored_email)
                    logger.info("Webhook notification sent", message_id=message_id)
                except Exception as e:
                    # Log webhook error but don't fail the email receipt
                    logger.error(
                        "Failed to send webhook notification",
                        message_id=message_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
            else:
                logger.debug("No webhook notifier configured", message_id=message_id)

            return "250 Message accepted for delivery"

        except Exception as e:
            logger.error(
                "Failed to handle email",
                mail_from=envelope.mail_from,
                error=str(e),
                error_type=type(e).__name__,
            )
            return f"554 Transaction failed: {str(e)}"

    def _extract_email(self, address: str) -> str:
        """
        Extract email address from various formats.

        Args:
            address: Email address string (may include name).

        Returns:
            Cleaned email address.

        Raises:
            EmailError: If email address is invalid.
        """
        if not address:
            raise EmailError(
                message="Email address is required",
                details={"address": address},
            )

        # Extract email from "Name <email@example.com>" format
        match = re.search(r"<(.+?)>", address)
        if match:
            email_addr = match.group(1)
        else:
            email_addr = address.strip()

        # Basic validation
        if "@" not in email_addr:
            raise EmailError(
                message="Invalid email address format",
                details={"address": address, "extracted": email_addr},
            )

        logger.debug("Email address extracted", original=address, extracted=email_addr)
        return email_addr

    def _decode_header(self, header: str) -> str:
        """
        Decode email header (handles encoding).

        Args:
            header: Header string to decode.

        Returns:
            Decoded header string.
        """
        if not header:
            return ""

        decoded_parts = []
        for part, encoding in email.header.decode_header(header):
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(encoding or "utf-8", errors="replace"))
            else:
                decoded_parts.append(part)

        return "".join(decoded_parts).strip()

    def _extract_body(self, msg: Message) -> str:
        """
        Extract plain text body from email message.

        Args:
            msg: Email message object.

        Returns:
            Plain text body content.
        """
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")

        return body.strip() if body else "(No body)"

    def _extract_thread_id(self, msg: Message) -> str | None:
        """
        Extract thread ID from email headers.

        Looks for In-Reply-To or References headers to determine thread ID.

        Args:
            msg: Email message object.

        Returns:
            Thread ID if found, None otherwise.
        """
        # Check In-Reply-To header
        in_reply_to = msg.get("In-Reply-To")
        if in_reply_to:
            logger.debug("Thread ID from In-Reply-To", thread_id=in_reply_to)
            return in_reply_to.strip()

        # Check References header (first reference is usually thread root)
        references = msg.get("References")
        if references:
            refs = references.strip().split()
            if refs:
                logger.debug("Thread ID from References", thread_id=refs[0])
                return refs[0]

        logger.debug("No thread ID found in headers")
        return None

    def _extract_attachments(self, msg: Message) -> list[EmailAttachment]:
        """
        Extract attachments from email message.

        Args:
            msg: Email message object.

        Returns:
            List of email attachments.
        """
        attachments = []

        if not msg.is_multipart():
            return attachments

        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                filename = part.get_filename()
                if not filename:
                    continue

                content_type = part.get_content_type()
                payload = part.get_payload(decode=True)

                if payload:
                    # Encode content as base64
                    content_b64 = base64.b64encode(payload).decode("ascii")

                    attachment = EmailAttachment(
                        filename=filename,
                        content_type=content_type,
                        size=len(payload),
                        content=content_b64,
                    )
                    attachments.append(attachment)

                    logger.debug(
                        "Attachment extracted",
                        filename=filename,
                        content_type=content_type,
                        size=len(payload),
                    )

        return attachments


async def start_smtp_server(
    host: str,
    port: int,
    storage: EmailStorage,
    webhook_notifier: WebhookNotifier | None = None,
) -> Controller:
    """
    Start the SMTP server.

    Args:
        host: Host address to bind to.
        port: Port number to listen on.
        storage: Email storage instance.
        webhook_notifier: Optional webhook notifier.

    Returns:
        Controller instance managing the SMTP server.

    Raises:
        EmailError: If server startup fails.
    """
    logger.info("Starting SMTP server", host=host, port=port)

    if not host:
        raise EmailError(
            message="Host is required for SMTP server",
            details={"host": host},
        )

    if not port or port < 1 or port > 65535:
        raise EmailError(
            message="Valid port number is required (1-65535)",
            details={"port": port},
        )

    try:
        handler = EmailHandler(storage=storage, webhook_notifier=webhook_notifier)
        controller = Controller(handler, hostname=host, port=port)
        controller.start()

        logger.info("SMTP server started successfully", host=host, port=port)
        return controller

    except Exception as e:
        logger.error(
            "Failed to start SMTP server",
            host=host,
            port=port,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise EmailError(
            message=f"Failed to start SMTP server: {e}",
            details={"host": host, "port": port, "error": str(e)},
        ) from e
