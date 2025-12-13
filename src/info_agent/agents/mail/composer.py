"""
Email composer using LLM for professional email generation.

This module provides an LLM-powered email composer that generates
professional email content based on instructions. It uses structured
prompts to ensure consistent, high-quality email composition.

All operations are async using LangChain's async API.
No fallback/default values - missing instructions raise exceptions.

Usage:
    from info_agent.agents.mail.composer import EmailComposer

    composer = EmailComposer()

    # Compose email with instructions
    result = await composer.compose_email(
        to_address="client@example.com",
        instructions="Write a professional email requesting a meeting next week"
    )
    print(result["subject"])
    print(result["body"])

    # Compose email with custom subject
    result = await composer.compose_email(
        to_address="team@example.com",
        instructions="Inform the team about the project update",
        subject="Project Update - Q4 2025"
    )
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from info_agent.llm import get_gemini_llm
from info_agent.utils.exceptions import LLMError, ValidationError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class EmailComposer:
    """
    LLM-powered email composer for generating professional emails.

    This composer uses structured prompts and JSON output to ensure
    consistent, high-quality email generation from natural language
    instructions.

    The composer can:
    - Generate email subject lines based on content
    - Compose professional email bodies from instructions
    - Maintain appropriate tone and formatting
    - Handle custom subjects when provided
    """

    SYSTEM_PROMPT = """You are a professional email composer assistant.

Your task is to compose professional, clear, and well-structured emails based on the user's instructions.

Guidelines:
1. Use a professional and courteous tone
2. Keep emails concise and to the point
3. Include appropriate greetings and closings
4. Use proper grammar and punctuation
5. Structure longer emails with paragraphs
6. If a subject is not provided, generate an appropriate one based on the content

Output Format:
Respond with a JSON object containing exactly two fields:
{
  "subject": "Email subject line (if not provided by user)",
  "body": "Complete email body with greeting, content, and closing"
}

Important:
- The body should be complete and ready to send
- Include "Best regards" or similar professional closing
- Do NOT include placeholder text like [Your Name] - leave signature open
- Generate clear, specific subject lines that summarize the email purpose
- Ensure the subject is concise (ideally under 60 characters)
"""

    def __init__(self) -> None:
        """
        Initialize the email composer.

        The LLM instance is lazily initialized on first use via the
        singleton factory pattern.
        """
        logger.info("EmailComposer initialized")

    async def compose_email(
        self,
        to_address: str,
        instructions: str,
        subject: str | None = None,
    ) -> dict[str, str]:
        """
        Compose a professional email using LLM.

        Args:
            to_address: Recipient email address (required).
            instructions: Natural language instructions for email content (required).
            subject: Optional pre-defined subject line. If not provided,
                    the LLM will generate an appropriate subject.

        Returns:
            Dictionary with "subject" and "body" keys containing the composed email.

        Raises:
            ValidationError: If required parameters are missing or invalid.
            LLMError: If email composition fails.

        Example:
            result = await composer.compose_email(
                to_address="client@example.com",
                instructions="Request a meeting next Tuesday at 2pm to discuss the project",
                subject="Meeting Request"  # Optional
            )
        """
        logger.info(
            "Composing email",
            to_address=to_address,
            has_custom_subject=subject is not None,
        )

        # Validate required parameters
        if not to_address:
            logger.error("Recipient address is required but not provided")
            raise ValidationError(
                message="Recipient address (to_address) is required",
                field="to_address",
            )

        if not instructions:
            logger.error("Email instructions are required but not provided")
            raise ValidationError(
                message="Email instructions are required",
                field="instructions",
            )

        if not instructions.strip():
            logger.error("Email instructions cannot be empty or whitespace")
            raise ValidationError(
                message="Email instructions cannot be empty or whitespace",
                field="instructions",
                value=instructions,
            )

        # Build user prompt
        user_prompt = self._build_user_prompt(
            to_address=to_address,
            instructions=instructions.strip(),
            custom_subject=subject,
        )

        logger.debug("User prompt created", prompt_length=len(user_prompt))

        # Get LLM instance
        try:
            llm = get_gemini_llm(temperature=0.7)
            logger.debug("LLM instance obtained")

        except Exception as e:
            logger.error(
                "Failed to get LLM instance",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise LLMError(
                message=f"Failed to initialize LLM for email composition: {str(e)}",
                original_error=e,
            ) from e

        # Invoke LLM
        try:
            logger.info("Invoking LLM for email composition")

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
                message=f"Failed to generate email content: {str(e)}",
                original_error=e,
            ) from e

        # Parse LLM response
        try:
            composed_email = self._parse_llm_response(response_text)
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

        # Override subject if provided
        if subject:
            logger.debug("Using custom subject", subject=subject)
            composed_email["subject"] = subject

        # Validate composed email
        if not composed_email.get("subject"):
            logger.error("LLM failed to generate subject")
            raise LLMError(
                message="LLM failed to generate email subject",
                details={"response": response_text[:200]},
            )

        if not composed_email.get("body"):
            logger.error("LLM failed to generate body")
            raise LLMError(
                message="LLM failed to generate email body",
                details={"response": response_text[:200]},
            )

        logger.info(
            "Email composition successful",
            subject=composed_email["subject"],
            body_length=len(composed_email["body"]),
        )

        return composed_email

    def _build_user_prompt(
        self,
        to_address: str,
        instructions: str,
        custom_subject: str | None = None,
    ) -> str:
        """
        Build the user prompt for LLM.

        Args:
            to_address: Recipient email address.
            instructions: Email composition instructions.
            custom_subject: Optional custom subject line.

        Returns:
            Formatted user prompt string.
        """
        logger.debug("Building user prompt")

        prompt_parts = [
            f"Compose an email to: {to_address}",
            "",
            f"Instructions: {instructions}",
        ]

        if custom_subject:
            prompt_parts.extend([
                "",
                f"Use this subject line: {custom_subject}",
            ])

        prompt = "\n".join(prompt_parts)

        logger.debug("User prompt built", prompt_length=len(prompt))

        return prompt

    def _parse_llm_response(self, response_text: str) -> dict[str, str]:
        """
        Parse LLM response to extract subject and body.

        The LLM should return a JSON object with "subject" and "body" fields.

        Args:
            response_text: Raw LLM response text.

        Returns:
            Dictionary with "subject" and "body" keys.

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

        # Validate required fields
        if "subject" not in parsed:
            logger.error("LLM response missing 'subject' field")
            raise KeyError("LLM response missing required field: 'subject'")

        if "body" not in parsed:
            logger.error("LLM response missing 'body' field")
            raise KeyError("LLM response missing required field: 'body'")

        # Validate field types
        if not isinstance(parsed["subject"], str):
            logger.error("Subject is not a string", subject_type=type(parsed["subject"]))
            raise ValueError("Subject must be a string")

        if not isinstance(parsed["body"], str):
            logger.error("Body is not a string", body_type=type(parsed["body"]))
            raise ValueError("Body must be a string")

        # Validate field content
        if not parsed["subject"].strip():
            logger.error("Subject is empty")
            raise ValueError("Subject cannot be empty")

        if not parsed["body"].strip():
            logger.error("Body is empty")
            raise ValueError("Body cannot be empty")

        logger.debug("LLM response validation successful")

        return {
            "subject": parsed["subject"].strip(),
            "body": parsed["body"].strip(),
        }
