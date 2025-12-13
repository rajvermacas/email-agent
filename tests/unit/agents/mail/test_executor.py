"""
Unit tests for Mail Agent executor.
"""

import pytest

from info_agent.a2a.executor import EventQueue, RequestContext
from info_agent.a2a.models import AgentCard, Artifact, Task, TaskRequest, TaskState
from info_agent.agents.mail.executor import (
    MailAgentExecutor,
    create_mail_agent_card,
)
from info_agent.agents.mail.skills import MAIL_AGENT_SKILLS
from info_agent.email_server.models import Email, EmailAddress, EmailStatus
from info_agent.email_server.storage import EmailStorage
from info_agent.email_server.webhooks import WebhookManager


class TestCreateMailAgentCard:
    """Tests for create_mail_agent_card function."""

    def test_default_values(self) -> None:
        """Test default agent card values."""
        card = create_mail_agent_card()

        assert card.id == "mail-agent"
        assert card.endpoint == "http://localhost:8001/a2a"

    def test_custom_agent_id(self) -> None:
        """Test custom agent ID."""
        card = create_mail_agent_card(agent_id="custom-mail-agent")

        assert card.id == "custom-mail-agent"

    def test_custom_endpoint(self) -> None:
        """Test custom endpoint."""
        card = create_mail_agent_card(endpoint="http://custom:9000/a2a")

        assert card.endpoint == "http://custom:9000/a2a"

    def test_agent_name(self) -> None:
        """Test agent name."""
        card = create_mail_agent_card()

        assert card.name == "Mail Agent"

    def test_agent_description(self) -> None:
        """Test agent has description."""
        card = create_mail_agent_card()

        assert card.description is not None
        assert "email" in card.description.lower()

    def test_skills_included(self) -> None:
        """Test skills are included."""
        card = create_mail_agent_card()

        assert card.skills == MAIL_AGENT_SKILLS
        assert len(card.skills) == 4

    def test_capabilities(self) -> None:
        """Test capabilities are set."""
        card = create_mail_agent_card()

        assert "streaming" in card.capabilities

    def test_metadata(self) -> None:
        """Test metadata is set."""
        card = create_mail_agent_card()

        assert card.metadata is not None
        assert "version" in card.metadata
        assert "author" in card.metadata


class TestMailAgentExecutorInit:
    """Tests for MailAgentExecutor initialization."""

    def test_basic_initialization(self) -> None:
        """Test basic initialization."""
        storage = EmailStorage()
        executor = MailAgentExecutor(storage)

        assert executor.storage is storage
        assert executor.agent_card.id == "mail-agent"

    def test_custom_parameters(self) -> None:
        """Test custom initialization parameters."""
        storage = EmailStorage()
        webhook_manager = WebhookManager()

        executor = MailAgentExecutor(
            storage=storage,
            webhook_manager=webhook_manager,
            default_from_address="custom@test.com",
            agent_id="custom-agent",
            endpoint="http://custom:8000/a2a",
        )

        assert executor._webhook_manager is webhook_manager
        assert executor._default_from_address == "custom@test.com"
        assert executor.agent_card.id == "custom-agent"
        assert executor.agent_card.endpoint == "http://custom:8000/a2a"

    def test_storage_property(self) -> None:
        """Test storage property."""
        storage = EmailStorage()
        executor = MailAgentExecutor(storage)

        assert executor.storage is storage


class TestMailAgentSendEmail:
    """Tests for send_email skill."""

    @pytest.fixture
    def storage(self) -> EmailStorage:
        """Create test storage."""
        return EmailStorage()

    @pytest.fixture
    def executor(self, storage: EmailStorage) -> MailAgentExecutor:
        """Create test executor."""
        return MailAgentExecutor(storage)

    @pytest.mark.asyncio
    async def test_send_email_success(
        self, executor: MailAgentExecutor, storage: EmailStorage
    ) -> None:
        """Test successful email send."""
        request = TaskRequest(
            skill_id="send_email",
            input={
                "to_address": "recipient@example.com",
                "subject": "Test Subject",
                "body": "Test body content",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        assert len(result.artifacts) == 1

        # Check artifact content
        artifact = result.artifacts[0]
        assert artifact.type == "application/json"
        assert artifact.data["success"] is True
        assert artifact.data["to_address"] == "recipient@example.com"
        assert artifact.data["subject"] == "Test Subject"
        assert "email_id" in artifact.data
        assert "thread_id" in artifact.data

        # Check email was stored
        stats = storage.get_stats()
        assert stats["total_emails"] == 2  # Sent + inbox copy

    @pytest.mark.asyncio
    async def test_send_email_with_custom_from(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test send with custom from address."""
        request = TaskRequest(
            skill_id="send_email",
            input={
                "to_address": "recipient@example.com",
                "subject": "Test",
                "body": "Body",
                "from_address": "custom@sender.com",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["success"] is True

    @pytest.mark.asyncio
    async def test_send_email_with_cc(
        self, executor: MailAgentExecutor, storage: EmailStorage
    ) -> None:
        """Test send with CC addresses."""
        request = TaskRequest(
            skill_id="send_email",
            input={
                "to_address": "recipient@example.com",
                "subject": "Test",
                "body": "Body",
                "cc_addresses": ["cc1@example.com", "cc2@example.com"],
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED

    @pytest.mark.asyncio
    async def test_send_email_with_thread_id(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test send with specified thread ID."""
        request = TaskRequest(
            skill_id="send_email",
            input={
                "to_address": "recipient@example.com",
                "subject": "Test",
                "body": "Body",
                "thread_id": "custom-thread-123",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["thread_id"] == "custom-thread-123"

    @pytest.mark.asyncio
    async def test_send_email_missing_to_address(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test error when to_address is missing."""
        request = TaskRequest(
            skill_id="send_email",
            input={
                "subject": "Test",
                "body": "Body",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert result.error is not None
        assert "to_address" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_email_missing_subject(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test error when subject is missing."""
        request = TaskRequest(
            skill_id="send_email",
            input={
                "to_address": "recipient@example.com",
                "body": "Body",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert result.error is not None
        assert "subject" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_email_missing_body(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test error when body is missing."""
        request = TaskRequest(
            skill_id="send_email",
            input={
                "to_address": "recipient@example.com",
                "subject": "Test",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert result.error is not None
        assert "body" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_email_with_webhook(
        self, storage: EmailStorage
    ) -> None:
        """Test send with webhook notification."""
        webhook_manager = WebhookManager()
        events_dispatched = []

        # Register a webhook to track dispatches
        webhook_manager.register(
            url="http://test.com/webhook",
            events=[WebhookManager.EVENT_EMAIL_SENT],
            secret="test-secret",
        )

        executor = MailAgentExecutor(
            storage=storage,
            webhook_manager=webhook_manager,
        )

        request = TaskRequest(
            skill_id="send_email",
            input={
                "to_address": "recipient@example.com",
                "subject": "Test",
                "body": "Body",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED


class TestMailAgentCheckInbox:
    """Tests for check_inbox skill."""

    @pytest.fixture
    def storage(self) -> EmailStorage:
        """Create test storage with sample emails."""
        storage = EmailStorage()

        # Add some test emails
        for i in range(5):
            email = Email(
                from_address=EmailAddress(address=f"sender{i}@example.com"),
                to_addresses=[EmailAddress(address="test@example.com")],
                subject=f"Test Email {i}",
                body_text=f"Body content {i}",
                status=EmailStatus.DELIVERED,
                mailbox="inbox",
            )
            storage.store(email)

        return storage

    @pytest.fixture
    def executor(self, storage: EmailStorage) -> MailAgentExecutor:
        """Create test executor."""
        return MailAgentExecutor(storage)

    @pytest.mark.asyncio
    async def test_check_inbox_success(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test successful inbox check."""
        request = TaskRequest(
            skill_id="check_inbox",
            input={"address": "test@example.com"},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        assert len(result.artifacts) == 1

        artifact = result.artifacts[0]
        assert artifact.data["address"] == "test@example.com"
        assert artifact.data["total_emails"] == 5
        assert len(artifact.data["emails"]) == 5

    @pytest.mark.asyncio
    async def test_check_inbox_with_limit(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test inbox check with limit."""
        request = TaskRequest(
            skill_id="check_inbox",
            input={
                "address": "test@example.com",
                "limit": 2,
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["total_emails"] <= 2

    @pytest.mark.asyncio
    async def test_check_inbox_unread_only(
        self, storage: EmailStorage
    ) -> None:
        """Test inbox check with unread_only filter."""
        # Add a read email
        read_email = Email(
            from_address=EmailAddress(address="read@example.com"),
            to_addresses=[EmailAddress(address="test@example.com")],
            subject="Read Email",
            body_text="Already read",
            status=EmailStatus.READ,
            mailbox="inbox",
        )
        storage.store(read_email)

        executor = MailAgentExecutor(storage)

        request = TaskRequest(
            skill_id="check_inbox",
            input={
                "address": "test@example.com",
                "unread_only": True,
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        # All returned emails should be DELIVERED (unread)
        for email in artifact.data["emails"]:
            assert email["status"] == EmailStatus.DELIVERED.value

    @pytest.mark.asyncio
    async def test_check_inbox_all_emails(
        self, storage: EmailStorage
    ) -> None:
        """Test inbox check including read emails."""
        # Add a read email
        read_email = Email(
            from_address=EmailAddress(address="read@example.com"),
            to_addresses=[EmailAddress(address="test@example.com")],
            subject="Read Email",
            body_text="Already read",
            status=EmailStatus.READ,
            mailbox="inbox",
        )
        storage.store(read_email)

        executor = MailAgentExecutor(storage)

        request = TaskRequest(
            skill_id="check_inbox",
            input={
                "address": "test@example.com",
                "unread_only": False,
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["total_emails"] == 6  # 5 unread + 1 read

    @pytest.mark.asyncio
    async def test_check_inbox_with_thread_filter(
        self, storage: EmailStorage
    ) -> None:
        """Test inbox check filtered by thread."""
        # Add email with specific thread
        thread_email = Email(
            from_address=EmailAddress(address="thread@example.com"),
            to_addresses=[EmailAddress(address="test@example.com")],
            subject="Thread Email",
            body_text="Part of thread",
            status=EmailStatus.DELIVERED,
            mailbox="inbox",
            thread_id="specific-thread-123",
        )
        storage.store(thread_email)

        executor = MailAgentExecutor(storage)

        request = TaskRequest(
            skill_id="check_inbox",
            input={
                "address": "test@example.com",
                "thread_id": "specific-thread-123",
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["total_emails"] == 1
        assert artifact.data["emails"][0]["thread_id"] == "specific-thread-123"

    @pytest.mark.asyncio
    async def test_check_inbox_missing_address(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test error when address is missing."""
        request = TaskRequest(
            skill_id="check_inbox",
            input={},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert result.error is not None
        assert "address" in result.error.lower()

    @pytest.mark.asyncio
    async def test_check_inbox_empty(self) -> None:
        """Test checking empty inbox."""
        storage = EmailStorage()
        executor = MailAgentExecutor(storage)

        request = TaskRequest(
            skill_id="check_inbox",
            input={"address": "empty@example.com"},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["total_emails"] == 0
        assert artifact.data["emails"] == []


class TestMailAgentGetThread:
    """Tests for get_thread skill."""

    @pytest.fixture
    def storage(self) -> EmailStorage:
        """Create test storage with thread emails."""
        storage = EmailStorage()

        # Create a conversation thread
        thread_id = "conversation-123"

        for i in range(3):
            email = Email(
                from_address=EmailAddress(
                    address="sender@example.com" if i % 2 == 0 else "recipient@example.com"
                ),
                to_addresses=[
                    EmailAddress(
                        address="recipient@example.com" if i % 2 == 0 else "sender@example.com"
                    )
                ],
                subject=f"Re: Test Thread ({i})",
                body_text=f"Message {i} in thread",
                thread_id=thread_id,
                status=EmailStatus.DELIVERED,
                mailbox="inbox",
            )
            storage.store(email)

        return storage

    @pytest.fixture
    def executor(self, storage: EmailStorage) -> MailAgentExecutor:
        """Create test executor."""
        return MailAgentExecutor(storage)

    @pytest.mark.asyncio
    async def test_get_thread_success(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test successful thread retrieval."""
        request = TaskRequest(
            skill_id="get_thread",
            input={"thread_id": "conversation-123"},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        assert len(result.artifacts) == 1

        artifact = result.artifacts[0]
        assert artifact.data["thread_id"] == "conversation-123"
        assert artifact.data["message_count"] == 3
        assert len(artifact.data["messages"]) == 3

    @pytest.mark.asyncio
    async def test_get_thread_message_content(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test thread messages contain expected fields."""
        request = TaskRequest(
            skill_id="get_thread",
            input={"thread_id": "conversation-123"},
        )

        result = await executor.handle_task(request)

        artifact = result.artifacts[0]
        for message in artifact.data["messages"]:
            assert "id" in message
            assert "from_address" in message
            assert "to_addresses" in message
            assert "subject" in message
            assert "body" in message
            assert "status" in message
            assert "mailbox" in message
            assert "created_at" in message

    @pytest.mark.asyncio
    async def test_get_thread_not_found(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test error when thread not found."""
        request = TaskRequest(
            skill_id="get_thread",
            input={"thread_id": "nonexistent-thread"},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert result.error is not None
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_thread_missing_thread_id(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test error when thread_id is missing."""
        request = TaskRequest(
            skill_id="get_thread",
            input={},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert result.error is not None
        assert "thread_id" in result.error.lower()


class TestMailAgentSearchEmails:
    """Tests for search_emails skill."""

    @pytest.fixture
    def storage(self) -> EmailStorage:
        """Create test storage with searchable emails."""
        storage = EmailStorage()

        # Add emails with various content
        emails_data = [
            ("sender1@example.com", "Invoice Payment", "Please pay invoice #123"),
            ("sender2@example.com", "Meeting Request", "Can we schedule a meeting?"),
            ("sender3@example.com", "Invoice Reminder", "Reminder for invoice #456"),
            ("sender4@example.com", "Project Update", "Here is the latest update"),
        ]

        for from_addr, subject, body in emails_data:
            email = Email(
                from_address=EmailAddress(address=from_addr),
                to_addresses=[EmailAddress(address="test@example.com")],
                subject=subject,
                body_text=body,
                status=EmailStatus.DELIVERED,
                mailbox="inbox",
            )
            storage.store(email)

        return storage

    @pytest.fixture
    def executor(self, storage: EmailStorage) -> MailAgentExecutor:
        """Create test executor."""
        return MailAgentExecutor(storage)

    @pytest.mark.asyncio
    async def test_search_emails_by_subject(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test search by subject content."""
        request = TaskRequest(
            skill_id="search_emails",
            input={"query": "Invoice"},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["query"] == "Invoice"
        assert artifact.data["result_count"] == 2
        for email in artifact.data["results"]:
            assert "invoice" in email["subject"].lower()

    @pytest.mark.asyncio
    async def test_search_emails_by_body(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test search by body content."""
        request = TaskRequest(
            skill_id="search_emails",
            input={"query": "meeting"},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["result_count"] >= 1

    @pytest.mark.asyncio
    async def test_search_emails_with_limit(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test search with limit."""
        request = TaskRequest(
            skill_id="search_emails",
            input={
                "query": "Invoice",
                "limit": 1,
            },
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["result_count"] <= 1

    @pytest.mark.asyncio
    async def test_search_emails_no_results(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test search with no matching results."""
        request = TaskRequest(
            skill_id="search_emails",
            input={"query": "nonexistent-query-xyz"},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.COMPLETED
        artifact = result.artifacts[0]
        assert artifact.data["result_count"] == 0
        assert artifact.data["results"] == []

    @pytest.mark.asyncio
    async def test_search_emails_missing_query(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test error when query is missing."""
        request = TaskRequest(
            skill_id="search_emails",
            input={},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert result.error is not None
        assert "query" in result.error.lower()

    @pytest.mark.asyncio
    async def test_search_result_fields(
        self, executor: MailAgentExecutor
    ) -> None:
        """Test search results contain expected fields."""
        request = TaskRequest(
            skill_id="search_emails",
            input={"query": "Invoice"},
        )

        result = await executor.handle_task(request)

        artifact = result.artifacts[0]
        for email in artifact.data["results"]:
            assert "id" in email
            assert "from_address" in email
            assert "subject" in email
            assert "preview" in email
            assert "mailbox" in email
            assert "thread_id" in email
            assert "created_at" in email


class TestMailAgentUnknownSkill:
    """Tests for unknown skill handling."""

    @pytest.fixture
    def executor(self) -> MailAgentExecutor:
        """Create test executor."""
        return MailAgentExecutor(EmailStorage())

    @pytest.mark.asyncio
    async def test_unknown_skill(self, executor: MailAgentExecutor) -> None:
        """Test handling of unknown skill."""
        request = TaskRequest(
            skill_id="unknown_skill",
            input={},
        )

        result = await executor.handle_task(request)

        assert result.state == TaskState.FAILED
        assert result.error is not None
        assert "unknown" in result.error.lower()


class TestMailAgentHealthCheck:
    """Tests for health check."""

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test health check includes storage stats."""
        storage = EmailStorage()

        # Add some emails
        for i in range(3):
            email = Email(
                from_address=EmailAddress(address=f"sender{i}@example.com"),
                to_addresses=[EmailAddress(address="test@example.com")],
                subject=f"Test {i}",
                body_text="Body",
                mailbox="inbox",
            )
            storage.store(email)

        executor = MailAgentExecutor(storage)

        health = await executor.health_check()

        assert health["status"] == "healthy"
        assert health["agent_id"] == "mail-agent"
        assert "storage" in health
        assert health["storage"]["total_emails"] == 3
