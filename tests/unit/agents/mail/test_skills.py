"""
Unit tests for Mail Agent skill definitions.
"""

import pytest

from info_agent.a2a.models import AgentSkill, SkillInputSchema
from info_agent.agents.mail.skills import (
    CHECK_INBOX_SKILL,
    GET_THREAD_SKILL,
    MAIL_AGENT_SKILLS,
    SEARCH_EMAILS_SKILL,
    SEND_EMAIL_SKILL,
)


class TestSendEmailSkill:
    """Tests for send_email skill definition."""

    def test_skill_id(self) -> None:
        """Test skill ID."""
        assert SEND_EMAIL_SKILL.id == "send_email"

    def test_skill_name(self) -> None:
        """Test skill name."""
        assert SEND_EMAIL_SKILL.name == "Send Email"

    def test_skill_description(self) -> None:
        """Test skill has description."""
        assert SEND_EMAIL_SKILL.description is not None
        assert len(SEND_EMAIL_SKILL.description) > 0

    def test_skill_input_schema(self) -> None:
        """Test skill has input schema."""
        assert SEND_EMAIL_SKILL.input_schema is not None
        assert isinstance(SEND_EMAIL_SKILL.input_schema, SkillInputSchema)

    def test_required_fields(self) -> None:
        """Test required fields are defined."""
        schema = SEND_EMAIL_SKILL.input_schema
        assert schema is not None
        assert "to_address" in schema.required
        assert "subject" in schema.required
        assert "body" in schema.required

    def test_optional_fields(self) -> None:
        """Test optional fields are defined."""
        schema = SEND_EMAIL_SKILL.input_schema
        assert schema is not None
        properties = schema.properties
        assert "from_address" in properties
        assert "cc_addresses" in properties
        assert "in_reply_to" in properties
        assert "thread_id" in properties

    def test_skill_tags(self) -> None:
        """Test skill has tags."""
        assert SEND_EMAIL_SKILL.tags is not None
        assert "email" in SEND_EMAIL_SKILL.tags
        assert "send" in SEND_EMAIL_SKILL.tags


class TestCheckInboxSkill:
    """Tests for check_inbox skill definition."""

    def test_skill_id(self) -> None:
        """Test skill ID."""
        assert CHECK_INBOX_SKILL.id == "check_inbox"

    def test_skill_name(self) -> None:
        """Test skill name."""
        assert CHECK_INBOX_SKILL.name == "Check Inbox"

    def test_required_fields(self) -> None:
        """Test required fields."""
        schema = CHECK_INBOX_SKILL.input_schema
        assert schema is not None
        assert "address" in schema.required

    def test_optional_fields(self) -> None:
        """Test optional fields."""
        schema = CHECK_INBOX_SKILL.input_schema
        assert schema is not None
        properties = schema.properties
        assert "unread_only" in properties
        assert "limit" in properties
        assert "thread_id" in properties

    def test_skill_tags(self) -> None:
        """Test skill has tags."""
        assert CHECK_INBOX_SKILL.tags is not None
        assert "email" in CHECK_INBOX_SKILL.tags
        assert "inbox" in CHECK_INBOX_SKILL.tags


class TestGetThreadSkill:
    """Tests for get_thread skill definition."""

    def test_skill_id(self) -> None:
        """Test skill ID."""
        assert GET_THREAD_SKILL.id == "get_thread"

    def test_skill_name(self) -> None:
        """Test skill name."""
        assert GET_THREAD_SKILL.name == "Get Email Thread"

    def test_required_fields(self) -> None:
        """Test required fields."""
        schema = GET_THREAD_SKILL.input_schema
        assert schema is not None
        assert "thread_id" in schema.required

    def test_skill_tags(self) -> None:
        """Test skill has tags."""
        assert GET_THREAD_SKILL.tags is not None
        assert "email" in GET_THREAD_SKILL.tags
        assert "thread" in GET_THREAD_SKILL.tags


class TestSearchEmailsSkill:
    """Tests for search_emails skill definition."""

    def test_skill_id(self) -> None:
        """Test skill ID."""
        assert SEARCH_EMAILS_SKILL.id == "search_emails"

    def test_skill_name(self) -> None:
        """Test skill name."""
        assert SEARCH_EMAILS_SKILL.name == "Search Emails"

    def test_required_fields(self) -> None:
        """Test required fields."""
        schema = SEARCH_EMAILS_SKILL.input_schema
        assert schema is not None
        assert "query" in schema.required

    def test_optional_fields(self) -> None:
        """Test optional fields."""
        schema = SEARCH_EMAILS_SKILL.input_schema
        assert schema is not None
        properties = schema.properties
        assert "address" in properties
        assert "mailbox" in properties
        assert "limit" in properties

    def test_skill_tags(self) -> None:
        """Test skill has tags."""
        assert SEARCH_EMAILS_SKILL.tags is not None
        assert "email" in SEARCH_EMAILS_SKILL.tags
        assert "search" in SEARCH_EMAILS_SKILL.tags


class TestMailAgentSkillsList:
    """Tests for the aggregated skills list."""

    def test_contains_all_skills(self) -> None:
        """Test list contains all skills."""
        assert len(MAIL_AGENT_SKILLS) == 4
        assert SEND_EMAIL_SKILL in MAIL_AGENT_SKILLS
        assert CHECK_INBOX_SKILL in MAIL_AGENT_SKILLS
        assert GET_THREAD_SKILL in MAIL_AGENT_SKILLS
        assert SEARCH_EMAILS_SKILL in MAIL_AGENT_SKILLS

    def test_all_are_agent_skills(self) -> None:
        """Test all items are AgentSkill instances."""
        for skill in MAIL_AGENT_SKILLS:
            assert isinstance(skill, AgentSkill)

    def test_unique_skill_ids(self) -> None:
        """Test all skill IDs are unique."""
        skill_ids = [skill.id for skill in MAIL_AGENT_SKILLS]
        assert len(skill_ids) == len(set(skill_ids))
