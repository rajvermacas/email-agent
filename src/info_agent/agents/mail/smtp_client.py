"""
SMTP client wrapper for sending emails using aiosmtplib.

This module provides an async SMTP client for sending emails via
a configured SMTP server. It handles connection management, email
formatting, and proper error handling.

All operations are async using aiosmtplib.
No fallback/default values - missing configuration raises exceptions.

Usage:
    from info_agent.agents.mail.smtp_client import SMTPClient
    from info_agent.config import get_settings

    settings = get_settings()
    client = SMTPClient(
        host=settings.smtp_host,
        port=settings.smtp_port
    )

    await client.send_email(
        from_address="sender@example.com",
        to_address="recipient@example.com",
        subject="Test Email",
        body_text="This is a test email."
    )
"""

import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib

from info_agent.utils.exceptions import EmailError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class SMTPClient:
    """
    Async SMTP client for sending emails.

    This client handles email formatting, SMTP connection management,
    and error handling for email sending operations.

    Attributes:
        host: SMTP server host.
        port: SMTP server port.
        timeout: Connection timeout in seconds.
    """

    DEFAULT_TIMEOUT = 30.0
    DEFAULT_FROM_ADDRESS = "info-agent@localhost"

    def __init__(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
    ) -> None:
        """
        Initialize SMTP client.

        Args:
            host: SMTP server host (required).
            port: SMTP server port (required).
            timeout: Optional connection timeout in seconds.
                    Defaults to 30 seconds if not provided.

        Raises:
            EmailError: If required parameters are missing or invalid.
        """
        logger.info("Initializing SMTP client", host=host, port=port)

        if not host:
            logger.error("SMTP host is required but not provided")
            raise EmailError(
                message="SMTP host is required",
                details={"parameter": "host"},
            )

        if port is None or port <= 0:
            logger.error("Invalid SMTP port", port=port)
            raise EmailError(
                message="SMTP port must be a positive integer",
                details={"parameter": "port", "value": port},
            )

        if port > 65535:
            logger.error("SMTP port out of range", port=port)
            raise EmailError(
                message="SMTP port must be <= 65535",
                details={"parameter": "port", "value": port},
            )

        self.host = host
        self.port = port
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

        logger.info(
            "SMTP client initialized",
            host=self.host,
            port=self.port,
            timeout=self.timeout,
        )

    async def send_email(
        self,
        to_address: str,
        subject: str,
        body_text: str,
        from_address: str | None = None,
        thread_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Send an email via SMTP.

        Args:
            to_address: Recipient email address (required).
            subject: Email subject line (required).
            body_text: Plain text email body (required).
            from_address: Sender email address (optional, uses default if not provided).
            thread_id: Optional thread ID for email threading.
            attachments: Optional list of attachments (not implemented in MVP).

        Returns:
            Message ID of the sent email.

        Raises:
            EmailError: If required parameters are missing or sending fails.
        """
        logger.info(
            "Preparing to send email",
            to_address=to_address,
            subject=subject,
            has_thread_id=thread_id is not None,
        )

        # Validate required parameters
        if not to_address:
            logger.error("Recipient address is required but not provided")
            raise EmailError(
                message="Recipient address (to_address) is required",
                details={"parameter": "to_address"},
            )

        if not subject:
            logger.error("Email subject is required but not provided")
            raise EmailError(
                message="Email subject is required",
                details={"parameter": "subject"},
            )

        if not body_text:
            logger.error("Email body is required but not provided")
            raise EmailError(
                message="Email body (body_text) is required",
                details={"parameter": "body_text"},
            )

        # Use default from_address if not provided
        sender = from_address or self.DEFAULT_FROM_ADDRESS
        logger.debug("Using sender address", from_address=sender)

        # Generate unique message ID
        message_id = f"<{uuid.uuid4()}@{self.host}>"
        logger.debug("Generated message ID", message_id=message_id)

        # Create MIME message
        try:
            msg = self._create_mime_message(
                from_address=sender,
                to_address=to_address,
                subject=subject,
                body_text=body_text,
                message_id=message_id,
                thread_id=thread_id,
            )
            logger.debug("MIME message created successfully")

        except Exception as e:
            logger.error(
                "Failed to create MIME message",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"Failed to create email message: {str(e)}",
                recipient=to_address,
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e

        # Send email via SMTP
        try:
            logger.info(
                "Connecting to SMTP server",
                host=self.host,
                port=self.port,
            )

            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                timeout=self.timeout,
            )

            logger.info(
                "Email sent successfully",
                message_id=message_id,
                to_address=to_address,
                subject=subject,
            )

            return message_id

        except aiosmtplib.SMTPException as e:
            logger.error(
                "SMTP error while sending email",
                error=str(e),
                error_type=type(e).__name__,
                to_address=to_address,
            )
            raise EmailError(
                message=f"SMTP error: {str(e)}",
                recipient=to_address,
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "smtp_host": self.host,
                    "smtp_port": self.port,
                },
            ) from e

        except OSError as e:
            logger.error(
                "Network error while sending email",
                error=str(e),
                error_type=type(e).__name__,
                to_address=to_address,
            )
            raise EmailError(
                message=f"Network error: {str(e)}",
                recipient=to_address,
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "smtp_host": self.host,
                    "smtp_port": self.port,
                },
            ) from e

        except Exception as e:
            logger.error(
                "Unexpected error while sending email",
                error=str(e),
                error_type=type(e).__name__,
                to_address=to_address,
            )
            raise EmailError(
                message=f"Unexpected error while sending email: {str(e)}",
                recipient=to_address,
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e

    def _create_mime_message(
        self,
        from_address: str,
        to_address: str,
        subject: str,
        body_text: str,
        message_id: str,
        thread_id: str | None = None,
    ) -> MIMEMultipart:
        """
        Create a MIME multipart message.

        Args:
            from_address: Sender email address.
            to_address: Recipient email address.
            subject: Email subject line.
            body_text: Plain text email body.
            message_id: Unique message identifier.
            thread_id: Optional thread ID for email threading.

        Returns:
            MIMEMultipart message ready to send.

        Raises:
            Exception: If message creation fails.
        """
        logger.debug(
            "Creating MIME message",
            from_address=from_address,
            to_address=to_address,
        )

        msg = MIMEMultipart("alternative")
        msg["From"] = from_address
        msg["To"] = to_address
        msg["Subject"] = subject
        msg["Message-ID"] = message_id
        msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

        # Add thread ID for email threading
        if thread_id:
            msg["In-Reply-To"] = thread_id
            msg["References"] = thread_id
            logger.debug("Added threading headers", thread_id=thread_id)

        # Add plain text body
        text_part = MIMEText(body_text, "plain")
        msg.attach(text_part)

        logger.debug("MIME message created with all parts")

        return msg

    async def test_connection(self) -> bool:
        """
        Test SMTP server connectivity.

        Returns:
            True if connection successful, False otherwise.

        Raises:
            EmailError: If connection test fails with error details.
        """
        logger.info("Testing SMTP connection", host=self.host, port=self.port)

        try:
            async with aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                timeout=self.timeout,
            ) as smtp:
                logger.debug("Connected to SMTP server")
                response = await smtp.noop()
                logger.debug("NOOP response received", response=response)

            logger.info("SMTP connection test successful")
            return True

        except aiosmtplib.SMTPException as e:
            logger.error(
                "SMTP connection test failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"SMTP connection test failed: {str(e)}",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "smtp_host": self.host,
                    "smtp_port": self.port,
                },
            ) from e

        except OSError as e:
            logger.error(
                "Network error during connection test",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"Network error: {str(e)}",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "smtp_host": self.host,
                    "smtp_port": self.port,
                },
            ) from e

        except Exception as e:
            logger.error(
                "Unexpected error during connection test",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise EmailError(
                message=f"Unexpected connection error: {str(e)}",
                details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            ) from e
