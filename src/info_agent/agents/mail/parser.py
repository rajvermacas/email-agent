"""
Email parser for extracting structured data from email content.

This module provides an LLM-powered email parser that extracts
structured information from email text. It's used to process
incoming emails and extract key data points.

All operations are async using LangChain's async API.
No fallback/default values - missing content raises exceptions.

Usage:
    from info_agent.agents.mail.parser import EmailParser

    parser = EmailParser()

    # Parse email content
    result = await parser.parse_email(
        from_address="client@example.com",
        subject="Meeting Request - Next Week",
        body="Hi, I'd like to schedule a meeting next Tuesday at 2pm..."
    )

    # Access parsed data
    print(result["intent"])
    print(result["key_points"])
    print(result["requires_action"])
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from info_agent.llm import get_gemini_llm
from info_agent.utils.exceptions import LLMError, ValidationError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class EmailParser:
    """
    LLM-powered email parser for extracting structured data.

    This parser uses structured prompts and JSON output to ensure
    consistent extraction of key information from email content.

    The parser extracts:
    - Email intent/purpose
    - Key points and topics
    - Action items or requests
    - Sentiment/tone
    - Important dates or deadlines
    - Contact information
    """

    SYSTEM_PROMPT = """You are an email analysis assistant that extracts structured information from emails.

Your task is to analyze email content and extract key information in a structured format.

Extract the following information:
1. Intent: The primary purpose of the email (e.g., "meeting_request", "information_query", "status_update", "complaint", "thank_you", "other")
2. Key Points: List of main points or topics mentioned (3-5 items max)
3. Action Items: Specific actions requested or needed (if any)
4. Requires Response: Whether the email requires a response (true/false)
5. Sentiment: Overall tone (e.g., "positive", "neutral", "negative", "urgent")
6. Important Dates: Any dates or deadlines mentioned (if any)
7. Contact Info: Any additional contact information mentioned (if any)
8. Summary: Brief 1-2 sentence summary of the email

Output Format:
Respond with a JSON object with the following structure:
{
  "intent": "meeting_request",
  "key_points": ["Point 1", "Point 2", "Point 3"],
  "action_items": ["Action 1", "Action 2"],
  "requires_response": true,
  "sentiment": "positive",
  "important_dates": ["2025-12-20", "Next Tuesday 2pm"],
  "contact_info": [],
  "summary": "Brief summary of email content"
}

Important:
- Be concise and specific
- Extract actual information, don't invent details
- Use empty lists [] for sections with no data
- Sentiment should be one of: "positive", "neutral", "negative", "urgent"
- Intent should be descriptive but concise
"""

    def __init__(self) -> None:
        """
        Initialize the email parser.

        The LLM instance is lazily initialized on first use via the
        singleton factory pattern.
        """
        logger.info("EmailParser initialized")

    async def parse_email(
        self,
        from_address: str,
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        """
        Parse an email and extract structured data.

        Args:
            from_address: Sender email address (required).
            subject: Email subject line (required).
            body: Email body text (required).

        Returns:
            Dictionary with extracted structured data including:
            - intent: Primary purpose of the email
            - key_points: List of main topics
            - action_items: List of requested actions
            - requires_response: Boolean indicating if response needed
            - sentiment: Overall tone
            - important_dates: List of dates/deadlines
            - contact_info: List of additional contact info
            - summary: Brief summary

        Raises:
            ValidationError: If required parameters are missing or invalid.
            LLMError: If email parsing fails.

        Example:
            result = await parser.parse_email(
                from_address="client@example.com",
                subject="Project Update",
                body="Here's the latest on the project..."
            )
        """
        logger.info(
            "Parsing email",
            from_address=from_address,
            subject=subject,
        )

        # Validate required parameters
        if not from_address:
            logger.error("Sender address is required but not provided")
            raise ValidationError(
                message="Sender address (from_address) is required",
                field="from_address",
            )

        if not subject:
            logger.error("Email subject is required but not provided")
            raise ValidationError(
                message="Email subject is required",
                field="subject",
            )

        if not body:
            logger.error("Email body is required but not provided")
            raise ValidationError(
                message="Email body is required",
                field="body",
            )

        if not body.strip():
            logger.error("Email body cannot be empty or whitespace")
            raise ValidationError(
                message="Email body cannot be empty or whitespace",
                field="body",
                value=body,
            )

        # Build user prompt
        user_prompt = self._build_user_prompt(
            from_address=from_address,
            subject=subject,
            body=body.strip(),
        )

        logger.debug("User prompt created", prompt_length=len(user_prompt))

        # Get LLM instance
        try:
            llm = get_gemini_llm(temperature=0.3)  # Lower temperature for more consistent parsing
            logger.debug("LLM instance obtained")

        except Exception as e:
            logger.error(
                "Failed to get LLM instance",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise LLMError(
                message=f"Failed to initialize LLM for email parsing: {str(e)}",
                original_error=e,
            ) from e

        # Invoke LLM
        try:
            logger.info("Invoking LLM for email parsing")

            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]

            response = await llm.ainvoke(messages)
            response_text = response.content

            logger.debug(
                "LLM response received",
                response_length=len(response_text),
            )

        except Exception as e:
            logger.error(
                "LLM invocation failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise LLMError(
                message=f"Failed to parse email content: {str(e)}",
                original_error=e,
            ) from e

        # Parse LLM response
        try:
            parsed_data = self._parse_llm_response(response_text)
            logger.debug("LLM response parsed successfully")

        except Exception as e:
            logger.error(
                "Failed to parse LLM response",
                error=str(e),
                response_text=response_text[:200],
            )
            raise LLMError(
                message=f"Failed to parse LLM output: {str(e)}",
                details={
                    "response_preview": response_text[:200],
                    "error": str(e),
                },
                original_error=e,
            ) from e

        # Validate parsed data
        self._validate_parsed_data(parsed_data)

        logger.info(
            "Email parsing successful",
            intent=parsed_data.get("intent"),
            key_points_count=len(parsed_data.get("key_points", [])),
            requires_response=parsed_data.get("requires_response"),
        )

        return parsed_data

    def _build_user_prompt(
        self,
        from_address: str,
        subject: str,
        body: str,
    ) -> str:
        """
        Build the user prompt for LLM.

        Args:
            from_address: Sender email address.
            subject: Email subject line.
            body: Email body text.

        Returns:
            Formatted user prompt string.
        """
        logger.debug("Building user prompt")

        prompt = f"""Analyze this email and extract structured information:

From: {from_address}
Subject: {subject}

Body:
{body}

Extract and return the structured data as specified in the system prompt."""

        logger.debug("User prompt built", prompt_length=len(prompt))

        return prompt

    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse LLM response to extract structured data.

        The LLM should return a JSON object with all required fields.

        Args:
            response_text: Raw LLM response text.

        Returns:
            Dictionary with parsed email data.

        Raises:
            ValueError: If response cannot be parsed.
            KeyError: If required fields are missing.
        """
        logger.debug("Parsing LLM response", response_length=len(response_text))

        # Clean response text
        cleaned_text = response_text.strip()

        # Try to extract JSON from markdown code blocks if present
        if "```json" in cleaned_text:
            logger.debug("Detected JSON code block in response")
            start = cleaned_text.find("```json") + 7
            end = cleaned_text.find("```", start)
            if end > start:
                cleaned_text = cleaned_text[start:end].strip()
                logger.debug("Extracted JSON from code block")

        elif "```" in cleaned_text:
            logger.debug("Detected generic code block in response")
            start = cleaned_text.find("```") + 3
            end = cleaned_text.find("```", start)
            if end > start:
                cleaned_text = cleaned_text[start:end].strip()
                logger.debug("Extracted content from code block")

        # Parse JSON
        try:
            parsed = json.loads(cleaned_text)
            logger.debug("JSON parsed successfully", keys=list(parsed.keys()))

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON",
                error=str(e),
                text_preview=cleaned_text[:200],
            )
            raise ValueError(
                f"LLM response is not valid JSON: {str(e)}"
            ) from e

        return parsed

    def _validate_parsed_data(self, data: dict[str, Any]) -> None:
        """
        Validate parsed email data has required fields.

        Args:
            data: Parsed data dictionary.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If field values are invalid.
        """
        logger.debug("Validating parsed data", keys=list(data.keys()))

        required_fields = [
            "intent",
            "key_points",
            "action_items",
            "requires_response",
            "sentiment",
            "important_dates",
            "contact_info",
            "summary",
        ]

        # Check for missing fields
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error("Parsed data missing required fields", missing=missing_fields)
            raise KeyError(f"Missing required fields: {missing_fields}")

        # Validate field types
        if not isinstance(data["intent"], str):
            logger.error("Intent is not a string", intent_type=type(data["intent"]))
            raise ValueError("Intent must be a string")

        if not isinstance(data["key_points"], list):
            logger.error("Key points is not a list", key_points_type=type(data["key_points"]))
            raise ValueError("Key points must be a list")

        if not isinstance(data["action_items"], list):
            logger.error("Action items is not a list", action_items_type=type(data["action_items"]))
            raise ValueError("Action items must be a list")

        if not isinstance(data["requires_response"], bool):
            logger.error("Requires response is not a boolean", requires_response_type=type(data["requires_response"]))
            raise ValueError("Requires response must be a boolean")

        if not isinstance(data["sentiment"], str):
            logger.error("Sentiment is not a string", sentiment_type=type(data["sentiment"]))
            raise ValueError("Sentiment must be a string")

        if not isinstance(data["important_dates"], list):
            logger.error("Important dates is not a list", important_dates_type=type(data["important_dates"]))
            raise ValueError("Important dates must be a list")

        if not isinstance(data["contact_info"], list):
            logger.error("Contact info is not a list", contact_info_type=type(data["contact_info"]))
            raise ValueError("Contact info must be a list")

        if not isinstance(data["summary"], str):
            logger.error("Summary is not a string", summary_type=type(data["summary"]))
            raise ValueError("Summary must be a string")

        # Validate field content
        if not data["intent"].strip():
            logger.error("Intent is empty")
            raise ValueError("Intent cannot be empty")

        if not data["summary"].strip():
            logger.error("Summary is empty")
            raise ValueError("Summary cannot be empty")

        logger.debug("Parsed data validation successful")
