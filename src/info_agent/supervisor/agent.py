"""
Main Supervisor Agent implementation.

The Supervisor Agent is the central orchestrator that coordinates
worker agents and manages the information retrieval workflow.
"""

import logging
from pathlib import Path
from typing import Any, AsyncIterator

from info_agent.a2a.registry import AgentRegistry
from info_agent.llm import BaseLLMProvider
from info_agent.supervisor.delegator import TaskDelegator, StubTaskDelegator
from info_agent.supervisor.planner import PlanGenerator
from info_agent.workflow import (
    InfoAgentWorkflow,
    SupervisorState,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """
    Central orchestrator for the Info-Agent system.

    The Supervisor Agent coordinates the multi-agent workflow:
    1. Parses input requirements
    2. Generates execution plans using LLM
    3. Delegates tasks to worker agents via A2A
    4. Manages workflow state with LangGraph
    5. Handles escalations and retries
    """

    def __init__(
        self,
        workflow: InfoAgentWorkflow | None = None,
        planner: PlanGenerator | None = None,
        delegator: TaskDelegator | StubTaskDelegator | None = None,
        registry: AgentRegistry | None = None,
        llm_provider: BaseLLMProvider | None = None,
        use_llm: bool = False,
        use_stub_delegator: bool = True,
    ) -> None:
        """
        Initialize the Supervisor Agent.

        Args:
            workflow: Optional pre-configured workflow.
            planner: Optional pre-configured plan generator.
            delegator: Optional pre-configured task delegator.
            registry: Optional pre-configured agent registry.
            llm_provider: Optional LLM provider for plan generation.
            use_llm: Whether to use LLM for planning.
            use_stub_delegator: Whether to use stub delegator (for testing).
        """
        logger.info("Initializing SupervisorAgent")

        # Initialize workflow
        if workflow is not None:
            self._workflow = workflow
        else:
            self._workflow = InfoAgentWorkflow()

        # Initialize planner
        if planner is not None:
            self._planner = planner
        else:
            self._planner = PlanGenerator(
                llm_provider=llm_provider,
                use_llm=use_llm,
            )

        # Initialize delegator
        if delegator is not None:
            self._delegator = delegator
        elif use_stub_delegator:
            self._delegator = StubTaskDelegator()
        else:
            self._delegator = TaskDelegator()

        # Initialize registry (optional - for discovering agents)
        self._registry = registry

        logger.info("SupervisorAgent initialized")

    @classmethod
    async def create(
        cls,
        checkpoint_db_path: str | Path | None = None,
        llm_provider: BaseLLMProvider | None = None,
        use_llm: bool = False,
        use_stub_delegator: bool = True,
        registry: AgentRegistry | None = None,
    ) -> "SupervisorAgent":
        """
        Async factory method for creating SupervisorAgent.

        Args:
            checkpoint_db_path: Optional path for checkpoint database.
            llm_provider: Optional LLM provider for plan generation.
            use_llm: Whether to use LLM for planning.
            use_stub_delegator: Whether to use stub delegator.
            registry: Optional pre-configured agent registry.

        Returns:
            Configured SupervisorAgent instance.
        """
        # Create workflow with checkpointing
        if checkpoint_db_path is not None:
            workflow = await InfoAgentWorkflow.create(
                checkpoint_db_path=checkpoint_db_path,
            )
        else:
            workflow = InfoAgentWorkflow()

        return cls(
            workflow=workflow,
            llm_provider=llm_provider,
            use_llm=use_llm,
            use_stub_delegator=use_stub_delegator,
            registry=registry,
        )

    @property
    def workflow(self) -> InfoAgentWorkflow:
        """Get the underlying workflow."""
        return self._workflow

    @property
    def planner(self) -> PlanGenerator:
        """Get the plan generator."""
        return self._planner

    @property
    def delegator(self) -> TaskDelegator | StubTaskDelegator:
        """Get the task delegator."""
        return self._delegator

    async def start_workflow(
        self,
        workflow_id: str,
        instructions: str,
        faq: str,
        escalation_rules: str,
        validation_criteria: str,
    ) -> SupervisorState:
        """
        Start a new workflow execution.

        Args:
            workflow_id: Unique workflow identifier.
            instructions: Raw instructions content.
            faq: Raw FAQ content.
            escalation_rules: Raw escalation rules content.
            validation_criteria: Raw validation criteria content.

        Returns:
            Final workflow state.
        """
        logger.info("Starting workflow: workflow_id=%s", workflow_id)

        result = await self._workflow.run(
            workflow_id=workflow_id,
            instructions=instructions,
            faq=faq,
            escalation_rules=escalation_rules,
            validation_criteria=validation_criteria,
        )

        logger.info(
            "Workflow completed: workflow_id=%s, status=%s",
            workflow_id,
            result.get("status"),
        )

        return result

    async def stream_workflow(
        self,
        workflow_id: str,
        instructions: str,
        faq: str,
        escalation_rules: str,
        validation_criteria: str,
    ) -> AsyncIterator[tuple[str, SupervisorState]]:
        """
        Stream workflow execution events.

        Args:
            workflow_id: Unique workflow identifier.
            instructions: Raw instructions content.
            faq: Raw FAQ content.
            escalation_rules: Raw escalation rules content.
            validation_criteria: Raw validation criteria content.

        Yields:
            Tuples of (node_name, state) for each step.
        """
        logger.info("Streaming workflow: workflow_id=%s", workflow_id)

        async for node_name, state in self._workflow.stream(
            workflow_id=workflow_id,
            instructions=instructions,
            faq=faq,
            escalation_rules=escalation_rules,
            validation_criteria=validation_criteria,
        ):
            yield node_name, state

    async def generate_plan(
        self,
        instructions: str,
        faq: str,
        escalation_rules: str,
        validation_criteria: str,
        available_agents: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate an execution plan using LLM.

        Args:
            instructions: Raw instructions content.
            faq: Raw FAQ content.
            escalation_rules: Raw escalation rules content.
            validation_criteria: Raw validation criteria content.
            available_agents: Optional list of available agents.

        Returns:
            List of plan step dictionaries.
        """
        logger.info("Generating execution plan")

        # Get available agents from registry if not provided
        if available_agents is None:
            if self._registry is not None:
                agents = await self._get_agents_from_registry()
                available_agents = agents
            else:
                # Default agents
                available_agents = self._get_default_agents()

        plan = await self._planner.generate_plan(
            instructions=instructions,
            faq=faq,
            escalation_rules=escalation_rules,
            validation_criteria=validation_criteria,
            available_agents=available_agents,
        )

        logger.info("Generated plan with %d steps", len(plan))
        return plan

    def rearticulate_plan(self, plan: list[dict[str, Any]]) -> str:
        """
        Rearticulate plan in human-readable format.

        Args:
            plan: List of plan step dictionaries.

        Returns:
            Human-readable plan description.
        """
        return self._planner.rearticulate_plan(plan)

    async def approve_plan(self, workflow_id: str) -> SupervisorState:
        """
        Approve the execution plan for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            Updated state after approval.
        """
        logger.info("Approving plan: workflow_id=%s", workflow_id)
        return await self._workflow.approve_plan(workflow_id)

    async def reject_plan(
        self,
        workflow_id: str,
        reason: str,
    ) -> SupervisorState:
        """
        Reject the execution plan for a workflow.

        Args:
            workflow_id: Workflow identifier.
            reason: Reason for rejection.

        Returns:
            Updated state after rejection.
        """
        logger.info("Rejecting plan: workflow_id=%s, reason=%s", workflow_id, reason)
        return await self._workflow.reject_plan(workflow_id, reason)

    async def get_workflow_state(self, workflow_id: str) -> SupervisorState | None:
        """
        Get current state for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            Current state or None if not found.
        """
        return await self._workflow.get_state(workflow_id)

    async def delegate_to_mail_agent(
        self,
        agent_endpoint: str,
        skill_id: str,
        parameters: dict[str, Any],
    ) -> Any:
        """
        Delegate a task to the Mail Agent.

        Args:
            agent_endpoint: Mail Agent endpoint URL.
            skill_id: Skill to invoke (send_email, parse_email, etc.).
            parameters: Parameters for the skill.

        Returns:
            Task result.
        """
        logger.info("Delegating to Mail Agent: skill=%s", skill_id)

        task = await self._delegator.delegate_task(
            agent_endpoint=agent_endpoint,
            skill_id=skill_id,
            parameters=parameters,
        )

        return task

    async def delegate_to_validation_agent(
        self,
        agent_endpoint: str,
        skill_id: str,
        parameters: dict[str, Any],
    ) -> Any:
        """
        Delegate a task to the Validation Agent.

        Args:
            agent_endpoint: Validation Agent endpoint URL.
            skill_id: Skill to invoke (validate_document, execute_python, etc.).
            parameters: Parameters for the skill.

        Returns:
            Task result.
        """
        logger.info("Delegating to Validation Agent: skill=%s", skill_id)

        task = await self._delegator.delegate_task(
            agent_endpoint=agent_endpoint,
            skill_id=skill_id,
            parameters=parameters,
        )

        return task

    async def _get_agents_from_registry(self) -> list[dict[str, Any]]:
        """Get available agents from the A2A registry."""
        if self._registry is None:
            return self._get_default_agents()

        agents = await self._registry.list_agents()

        return [
            {
                "name": agent.name,
                "description": agent.description,
                "endpoint": agent.endpoint,
                "skills": [
                    {"id": s.id, "name": s.name}
                    for s in (agent.skills or [])
                ],
            }
            for agent in agents
        ]

    def _get_default_agents(self) -> list[dict[str, Any]]:
        """Get default agent configuration."""
        return [
            {
                "name": "mail-agent",
                "description": "Email communication agent for sending and receiving messages",
                "endpoint": "http://localhost:8001",
                "skills": [
                    {"id": "send_email", "name": "Send Email"},
                    {"id": "parse_email", "name": "Parse Email"},
                    {"id": "search_emails", "name": "Search Emails"},
                ],
            },
            {
                "name": "validation-agent",
                "description": "Document validation agent with Python execution capabilities",
                "endpoint": "http://localhost:8002",
                "skills": [
                    {"id": "validate_document", "name": "Validate Document"},
                    {"id": "execute_python", "name": "Execute Python"},
                    {"id": "generate_report", "name": "Generate Report"},
                ],
            },
        ]

    async def close(self) -> None:
        """Close the supervisor and release resources."""
        await self._workflow.close()
        logger.info("SupervisorAgent closed")
