"""
LLM-powered plan generation for the Supervisor Agent.

This module provides LLM-based execution plan generation that analyzes
input requirements and creates step-by-step plans for worker agents.
"""

import logging
from typing import Any

from info_agent.llm import BaseLLMProvider, create_llm_provider
from info_agent.config import get_settings

logger = logging.getLogger(__name__)


PLAN_GENERATION_PROMPT = """You are a planning assistant for an information retrieval workflow.

Your task is to create an execution plan based on the provided requirements.

INPUT REQUIREMENTS:
- Instructions: {instructions}
- FAQ: {faq}
- Escalation Rules: {escalation_rules}
- Validation Criteria: {validation_criteria}

AVAILABLE AGENTS:
{available_agents}

TASK:
Create a step-by-step execution plan that:
1. Sends an initial email request to the target
2. Handles responses (documents, clarifications, timeouts)
3. Validates received documents
4. Generates final report

OUTPUT FORMAT:
Return a JSON array of plan steps. Each step should have:
- step_number: Integer starting from 1
- action: Short action name (e.g., "send_initial_request", "validate_response")
- agent: Agent name to use (e.g., "mail-agent", "validation-agent", "system")
- skill: Specific skill to invoke on the agent
- description: Human-readable description
- parameters: Dict of parameters for the skill

EXAMPLE OUTPUT:
[
  {{
    "step_number": 1,
    "action": "send_initial_request",
    "agent": "mail-agent",
    "skill": "send_email",
    "description": "Send email request to target@example.com",
    "parameters": {{"to": "target@example.com", "subject": "Information Request"}}
  }},
  {{
    "step_number": 2,
    "action": "wait_for_response",
    "agent": "system",
    "skill": "wait",
    "description": "Wait for response from target",
    "parameters": {{"timeout_hours": 48}}
  }}
]

Now generate the execution plan:"""


class PlanGenerator:
    """
    LLM-powered execution plan generator.

    Uses the configured LLM provider to analyze requirements and
    create step-by-step execution plans for the workflow.
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider | None = None,
        use_llm: bool = True,
    ) -> None:
        """
        Initialize the plan generator.

        Args:
            llm_provider: Optional pre-configured LLM provider.
                If not provided, creates one from environment.
            use_llm: Whether to use LLM for plan generation.
                If False, uses stub plan (for testing).
        """
        logger.info("Initializing PlanGenerator")

        self._use_llm = use_llm

        if use_llm:
            if llm_provider is not None:
                self._provider = llm_provider
            else:
                # Create provider from environment
                settings = get_settings()
                self._provider = create_llm_provider(settings)
            logger.info("PlanGenerator using LLM provider: %s", type(self._provider).__name__)
        else:
            self._provider = None
            logger.info("PlanGenerator using stub mode (no LLM)")

    async def generate_plan(
        self,
        instructions: str,
        faq: str,
        escalation_rules: str,
        validation_criteria: str,
        available_agents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Generate an execution plan based on requirements.

        Args:
            instructions: Raw instructions content.
            faq: Raw FAQ content.
            escalation_rules: Raw escalation rules content.
            validation_criteria: Raw validation criteria content.
            available_agents: List of available agent info dicts.

        Returns:
            List of plan step dictionaries.
        """
        logger.info("Generating execution plan")

        if not self._use_llm:
            return self._generate_stub_plan(
                instructions=instructions,
                faq=faq,
                escalation_rules=escalation_rules,
                validation_criteria=validation_criteria,
            )

        return await self._generate_llm_plan(
            instructions=instructions,
            faq=faq,
            escalation_rules=escalation_rules,
            validation_criteria=validation_criteria,
            available_agents=available_agents,
        )

    async def _generate_llm_plan(
        self,
        instructions: str,
        faq: str,
        escalation_rules: str,
        validation_criteria: str,
        available_agents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Generate plan using LLM.

        Args:
            instructions: Raw instructions content.
            faq: Raw FAQ content.
            escalation_rules: Raw escalation rules content.
            validation_criteria: Raw validation criteria content.
            available_agents: List of available agent info dicts.

        Returns:
            List of plan step dictionaries.
        """
        from langchain_core.messages import HumanMessage

        logger.info("Generating plan with LLM")

        if self._provider is None:
            raise ValueError("LLM provider not configured")

        # Format available agents
        agents_str = self._format_agents(available_agents)

        # Create prompt
        prompt = PLAN_GENERATION_PROMPT.format(
            instructions=instructions,
            faq=faq,
            escalation_rules=escalation_rules,
            validation_criteria=validation_criteria,
            available_agents=agents_str,
        )

        # Generate plan using LangChain chat model
        chat_model = self._provider.get_chat_model(
            temperature=0.2,  # Low temperature for consistent planning
        )

        messages = [HumanMessage(content=prompt)]
        response = await chat_model.ainvoke(messages)

        # Parse response
        import json
        try:
            content = response.content
            # Handle case where content is wrapped in a dict
            if content.startswith("{"):
                data = json.loads(content)
                plan = data.get("plan", data.get("steps", []))
            else:
                plan = json.loads(content)

            logger.info("Generated plan with %d steps", len(plan))
            return self._normalize_plan(plan)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM plan response: %s", e)
            # Fall back to stub plan
            return self._generate_stub_plan(
                instructions=instructions,
                faq=faq,
                escalation_rules=escalation_rules,
                validation_criteria=validation_criteria,
            )

    def _format_agents(self, available_agents: list[dict[str, Any]]) -> str:
        """Format available agents for the prompt."""
        lines = []
        for agent in available_agents:
            name = agent.get("name", "unknown")
            description = agent.get("description", "")
            skills = agent.get("skills", [])

            lines.append(f"- {name}: {description}")
            for skill in skills:
                skill_id = skill.get("id", "")
                skill_name = skill.get("name", "")
                lines.append(f"  - {skill_id}: {skill_name}")

        return "\n".join(lines)

    def _normalize_plan(self, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize plan steps to ensure consistent format."""
        normalized = []

        for i, step in enumerate(plan):
            normalized_step = {
                "step_number": step.get("step_number", i + 1),
                "action": step.get("action", f"step_{i + 1}"),
                "agent": step.get("agent", "system"),
                "skill": step.get("skill", ""),
                "description": step.get("description", ""),
                "parameters": step.get("parameters", {}),
                "status": "pending",
            }
            normalized.append(normalized_step)

        return normalized

    def _generate_stub_plan(
        self,
        instructions: str,
        faq: str,
        escalation_rules: str,
        validation_criteria: str,
    ) -> list[dict[str, Any]]:
        """
        Generate a stub plan without LLM.

        This is used for testing and when LLM is not available.

        Args:
            instructions: Raw instructions content.
            faq: Raw FAQ content.
            escalation_rules: Raw escalation rules content.
            validation_criteria: Raw validation criteria content.

        Returns:
            List of plan step dictionaries.
        """
        logger.info("Generating stub plan (no LLM)")

        # Extract target email from instructions
        import re
        email_pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
        emails = re.findall(email_pattern, instructions)
        target_email = emails[0] if emails else "unknown@example.com"

        # Extract timeout from escalation rules
        timeout_hours = 48
        timeout_match = re.search(r"(\d+)\s*hours?", escalation_rules.lower())
        if timeout_match:
            timeout_hours = int(timeout_match.group(1))

        plan = [
            {
                "step_number": 1,
                "action": "send_initial_request",
                "agent": "mail-agent",
                "skill": "send_email",
                "description": f"Send email request to {target_email}",
                "parameters": {
                    "to": target_email,
                    "request": instructions,
                },
                "status": "pending",
            },
            {
                "step_number": 2,
                "action": "wait_for_response",
                "agent": "system",
                "skill": "wait",
                "description": "Wait for response from target",
                "parameters": {
                    "timeout_hours": timeout_hours,
                },
                "status": "pending",
            },
            {
                "step_number": 3,
                "action": "validate_response",
                "agent": "validation-agent",
                "skill": "validate_document",
                "description": "Validate received document against criteria",
                "parameters": {
                    "criteria": validation_criteria,
                },
                "status": "pending",
            },
            {
                "step_number": 4,
                "action": "generate_report",
                "agent": "validation-agent",
                "skill": "generate_report",
                "description": "Generate validation report",
                "parameters": {},
                "status": "pending",
            },
        ]

        logger.info("Generated stub plan with %d steps", len(plan))
        return plan

    def rearticulate_plan(
        self,
        plan: list[dict[str, Any]],
    ) -> str:
        """
        Rearticulate the plan in human-readable format.

        Args:
            plan: List of plan step dictionaries.

        Returns:
            Human-readable plan description.
        """
        lines = ["## Execution Plan\n"]

        for step in plan:
            step_num = step.get("step_number", 0)
            description = step.get("description", "")
            agent = step.get("agent", "")
            skill = step.get("skill", "")

            lines.append(f"### Step {step_num}: {description}")
            lines.append(f"- Agent: {agent}")
            lines.append(f"- Skill: {skill}")
            lines.append("")

        return "\n".join(lines)
