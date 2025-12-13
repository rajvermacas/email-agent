"""
Execution plan generator for Supervisor Agent.

This module provides LLM-based planning capabilities that generate
step-by-step execution plans for information retrieval workflows.

The planner analyzes user instructions and creates structured plans
that orchestrate email communications and response handling.

Usage:
    from info_agent.agents.supervisor.planner import ExecutionPlanner

    planner = ExecutionPlanner()
    plan = await planner.generate_plan(
        target_email="john@example.com",
        target_name="John Doe",
        requested_info="Q3 2024 financial reports"
    )
"""

import json
import re
from typing import Any

from info_agent.llm import get_gemini_llm
from info_agent.utils.exceptions import LLMError, ValidationError
from info_agent.utils.logging import get_logger
from info_agent.workflow.state import PlanStep

logger = get_logger(__name__)


class ExecutionPlanner:
    """
    LLM-based execution planner for information retrieval workflows.

    This class uses an LLM to generate structured execution plans based on
    the user's requirements. Plans consist of sequential steps that orchestrate
    email sending, response waiting, and information collection.

    Attributes:
        llm: The LLM instance used for plan generation.
    """

    # Available actions that can be included in plans
    AVAILABLE_ACTIONS = {
        "send_email": "Send an email to request information",
        "wait_response": "Wait for email reply from target",
        "process_response": "Process and extract information from reply",
    }

    def __init__(self) -> None:
        """
        Initialize the execution planner.

        Raises:
            LLMError: If LLM initialization fails.
        """
        logger.info("Initializing ExecutionPlanner")

        try:
            self.llm = get_gemini_llm()
            logger.info("ExecutionPlanner initialized successfully")

        except Exception as e:
            logger.error(
                "Failed to initialize ExecutionPlanner",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise LLMError(
                message="Failed to initialize ExecutionPlanner",
                original_error=e,
            ) from e

    async def generate_plan(
        self,
        target_email: str,
        target_name: str,
        requested_info: str,
        instructions: str | None = None,
        feedback: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate an execution plan for information retrieval.

        This method uses the LLM to create a structured plan based on the
        target recipient and requested information. The plan includes
        sequential steps with actions and descriptions.

        Args:
            target_email: Email address of the information source (required).
            target_name: Name of the target person (required).
            requested_info: Description of requested information (required).
            instructions: Optional original instruction text for context.
            feedback: Optional feedback from previous plan rejection.

        Returns:
            Dictionary containing:
                - plan: List of PlanStep dictionaries
                - summary: Brief summary of the plan
                - email_subject: Suggested email subject
                - email_body: Suggested email body

        Raises:
            ValidationError: If required parameters are missing or invalid.
            LLMError: If plan generation fails.

        Example:
            planner = ExecutionPlanner()
            result = await planner.generate_plan(
                target_email="john@example.com",
                target_name="John Doe",
                requested_info="Q3 2024 financial reports"
            )
            plan_steps = result["plan"]
            email_subject = result["email_subject"]
        """
        logger.info(
            "Generating execution plan",
            target_email=target_email,
            target_name=target_name,
        )

        # Validate required parameters
        if not target_email:
            logger.error("target_email is required")
            raise ValidationError(
                message="target_email is required for plan generation",
                field="target_email",
            )

        if "@" not in target_email:
            logger.error("Invalid email address format", email=target_email)
            raise ValidationError(
                message="Invalid email address format",
                field="target_email",
                value=target_email,
            )

        if not target_name:
            logger.error("target_name is required")
            raise ValidationError(
                message="target_name is required for plan generation",
                field="target_name",
            )

        if not requested_info:
            logger.error("requested_info is required")
            raise ValidationError(
                message="requested_info is required for plan generation",
                field="requested_info",
            )

        # Build the planning prompt
        prompt = self._build_planning_prompt(
            target_email=target_email,
            target_name=target_name,
            requested_info=requested_info,
            instructions=instructions,
            feedback=feedback,
        )

        logger.debug("Invoking LLM for plan generation")

        try:
            response = await self.llm.ainvoke(prompt)
            response_text = response.content.strip()

            logger.debug("LLM response received", response_length=len(response_text))

            # Parse the JSON response
            plan_data = self._parse_plan_response(response_text)

            # Validate the plan structure
            self._validate_plan(plan_data)

            logger.info(
                "Plan generated successfully",
                step_count=len(plan_data["plan"]),
                has_email_content=bool(plan_data.get("email_subject")),
            )

            return plan_data

        except (ValidationError, LLMError):
            # Re-raise our custom exceptions
            raise

        except Exception as e:
            logger.error(
                "Failed to generate execution plan",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise LLMError(
                message=f"Failed to generate execution plan: {str(e)}",
                original_error=e,
            ) from e

    def _build_planning_prompt(
        self,
        target_email: str,
        target_name: str,
        requested_info: str,
        instructions: str | None = None,
        feedback: str | None = None,
    ) -> str:
        """
        Build the LLM prompt for plan generation.

        Args:
            target_email: Email address of the information source.
            target_name: Name of the target person.
            requested_info: Description of requested information.
            instructions: Optional original instruction text.
            feedback: Optional feedback from previous plan rejection.

        Returns:
            Formatted prompt string for the LLM.
        """
        logger.debug("Building planning prompt")

        # Base prompt structure
        prompt_parts = [
            "You are an AI assistant helping to create an execution plan for information retrieval via email.\n",
            f"\nTarget Recipient:",
            f"- Name: {target_name}",
            f"- Email: {target_email}\n",
            f"\nRequested Information:",
            f"{requested_info}\n",
        ]

        # Add original instructions if provided
        if instructions:
            prompt_parts.extend([
                "\nOriginal Instructions:",
                f"{instructions}\n",
            ])

        # Add feedback if this is a plan revision
        if feedback:
            prompt_parts.extend([
                "\nFeedback on Previous Plan:",
                f"{feedback}",
                "\nPlease revise the plan based on the feedback above.\n",
            ])

        # Add available actions
        prompt_parts.extend([
            "\nAvailable Actions:",
        ])
        for action, description in self.AVAILABLE_ACTIONS.items():
            prompt_parts.append(f"- {action}: {description}")

        # Add output format requirements
        prompt_parts.extend([
            "\n\nCreate a step-by-step execution plan to collect the requested information.",
            "The plan should include sending an email and waiting for a response.",
            "\nRespond with ONLY a valid JSON object in this exact format:",
            "{",
            '  "plan": [',
            '    {"step": 1, "action": "send_email", "description": "Send email requesting information", "status": "pending"},',
            '    {"step": 2, "action": "wait_response", "description": "Wait for email reply", "status": "pending"}',
            '  ],',
            '  "summary": "Brief summary of the overall plan",',
            '  "email_subject": "Suggested subject line for the email",',
            '  "email_body": "Suggested email body text (professional and polite)"',
            "}",
            "\nIMPORTANT:",
            "- Return ONLY valid JSON, no markdown code blocks or extra text",
            "- Each step must have: step (number), action (string), description (string), status (always 'pending')",
            "- Actions must be from the available actions list",
            "- Email body should be professional, polite, and clearly state what information is needed",
        ])

        prompt = "\n".join(prompt_parts)

        logger.debug("Planning prompt built", prompt_length=len(prompt))

        return prompt

    def _parse_plan_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse the LLM's JSON response into a structured plan.

        This method handles various JSON response formats, including
        responses wrapped in markdown code blocks.

        Args:
            response_text: Raw LLM response text.

        Returns:
            Parsed plan data as a dictionary.

        Raises:
            LLMError: If response cannot be parsed as valid JSON.
        """
        logger.debug("Parsing plan response", response_length=len(response_text))

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
            logger.debug("Extracted JSON from markdown code block")
        else:
            # Try to find JSON object directly
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                logger.debug("Extracted JSON object from response")
            else:
                json_text = response_text

        # Parse JSON
        try:
            plan_data = json.loads(json_text)
            logger.debug("Successfully parsed JSON response")
            return plan_data

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse LLM response as JSON",
                error=str(e),
                response_preview=response_text[:200],
            )
            raise LLMError(
                message=f"LLM returned invalid JSON: {str(e)}",
                details={
                    "parse_error": str(e),
                    "response_preview": response_text[:500],
                },
            ) from e

    def _validate_plan(self, plan_data: dict[str, Any]) -> None:
        """
        Validate the structure and content of the generated plan.

        Args:
            plan_data: Parsed plan data to validate.

        Raises:
            ValidationError: If plan structure is invalid or incomplete.
        """
        logger.debug("Validating plan structure")

        # Check required fields
        required_fields = ["plan", "summary", "email_subject", "email_body"]
        missing_fields = [field for field in required_fields if field not in plan_data]

        if missing_fields:
            logger.error(
                "Plan missing required fields",
                missing_fields=missing_fields,
            )
            raise ValidationError(
                message=f"Generated plan missing required fields: {missing_fields}",
                details={"missing_fields": missing_fields},
            )

        # Validate plan is a list
        plan = plan_data["plan"]
        if not isinstance(plan, list):
            logger.error("Plan is not a list", plan_type=type(plan).__name__)
            raise ValidationError(
                message="Plan must be a list of steps",
                field="plan",
                details={"actual_type": type(plan).__name__},
            )

        # Validate plan is not empty
        if not plan:
            logger.error("Plan is empty")
            raise ValidationError(
                message="Plan must contain at least one step",
                field="plan",
            )

        # Validate each step
        for idx, step in enumerate(plan):
            self._validate_step(step, idx)

        # Validate email content is not empty
        if not plan_data.get("email_subject", "").strip():
            logger.error("Email subject is empty")
            raise ValidationError(
                message="Email subject cannot be empty",
                field="email_subject",
            )

        if not plan_data.get("email_body", "").strip():
            logger.error("Email body is empty")
            raise ValidationError(
                message="Email body cannot be empty",
                field="email_body",
            )

        logger.debug("Plan validation successful", step_count=len(plan))

    def _validate_step(self, step: dict[str, Any], index: int) -> None:
        """
        Validate a single plan step.

        Args:
            step: Step data to validate.
            index: Step index for error reporting.

        Raises:
            ValidationError: If step is invalid.
        """
        # Check required step fields
        required_step_fields = ["step", "action", "description", "status"]
        missing_fields = [
            field for field in required_step_fields if field not in step
        ]

        if missing_fields:
            logger.error(
                "Step missing required fields",
                step_index=index,
                missing_fields=missing_fields,
            )
            raise ValidationError(
                message=f"Step {index} missing required fields: {missing_fields}",
                field=f"plan[{index}]",
                details={"missing_fields": missing_fields},
            )

        # Validate action is in available actions
        action = step["action"]
        if action not in self.AVAILABLE_ACTIONS:
            logger.error(
                "Invalid action in step",
                step_index=index,
                action=action,
                valid_actions=list(self.AVAILABLE_ACTIONS.keys()),
            )
            raise ValidationError(
                message=f"Step {index} has invalid action: {action}",
                field=f"plan[{index}].action",
                value=action,
                details={"valid_actions": list(self.AVAILABLE_ACTIONS.keys())},
            )

        # Validate status is 'pending'
        if step["status"] != "pending":
            logger.error(
                "Invalid status in step",
                step_index=index,
                status=step["status"],
            )
            raise ValidationError(
                message=f"Step {index} must have status 'pending', got: {step['status']}",
                field=f"plan[{index}].status",
                value=step["status"],
            )

        logger.debug("Step validation successful", step_index=index, action=action)


async def generate_email_content(
    target_name: str,
    requested_info: str,
    custom_instructions: str | None = None,
) -> dict[str, str]:
    """
    Generate email subject and body using LLM.

    This is a standalone helper function for generating email content
    without creating a full execution plan.

    Args:
        target_name: Name of the recipient.
        requested_info: Description of what information is needed.
        custom_instructions: Optional specific instructions for the email.

    Returns:
        Dictionary with 'subject' and 'body' keys.

    Raises:
        ValidationError: If required parameters are missing.
        LLMError: If email generation fails.
    """
    logger.info("Generating email content", target_name=target_name)

    # Validate required parameters
    if not target_name:
        logger.error("target_name is required")
        raise ValidationError(
            message="target_name is required for email generation",
            field="target_name",
        )

    if not requested_info:
        logger.error("requested_info is required")
        raise ValidationError(
            message="requested_info is required for email generation",
            field="requested_info",
        )

    try:
        llm = get_gemini_llm()

        prompt_parts = [
            "Generate a professional email to request information.\n",
            f"\nRecipient: {target_name}",
            f"Requested Information: {requested_info}\n",
        ]

        if custom_instructions:
            prompt_parts.extend([
                "\nAdditional Instructions:",
                f"{custom_instructions}\n",
            ])

        prompt_parts.extend([
            "\nGenerate a professional, polite email with:",
            "- A clear, concise subject line",
            "- A professional greeting",
            "- A clear explanation of what information is needed and why",
            "- A polite closing\n",
            "\nRespond with ONLY a valid JSON object:",
            "{",
            '  "subject": "Email subject line",',
            '  "body": "Full email body text"',
            "}",
        ])

        prompt = "\n".join(prompt_parts)

        logger.debug("Invoking LLM for email generation")
        response = await llm.ainvoke(prompt)
        response_text = response.content.strip()

        # Parse JSON response
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not json_match:
            logger.error("No JSON found in LLM response")
            raise LLMError(
                message="LLM did not return valid JSON",
                details={"response_preview": response_text[:200]},
            )

        email_data = json.loads(json_match.group(0))

        # Validate required fields
        if "subject" not in email_data or "body" not in email_data:
            logger.error("Email data missing required fields")
            raise ValidationError(
                message="Generated email missing subject or body",
                details={"email_data": email_data},
            )

        logger.info("Email content generated successfully")

        return {
            "subject": email_data["subject"],
            "body": email_data["body"],
        }

    except (ValidationError, LLMError):
        raise

    except Exception as e:
        logger.error(
            "Failed to generate email content",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise LLMError(
            message=f"Failed to generate email content: {str(e)}",
            original_error=e,
        ) from e
