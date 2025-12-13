"""
A2A Agent Server implementation.

Provides FastAPI-based HTTP server for A2A agents.
"""

from typing import Any

import structlog
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from info_agent.a2a.executor import BaseAgentExecutor
from info_agent.a2a.models import (
    AgentCard,
    Task,
    TaskRequest,
    TaskState,
)
from info_agent.utils.helpers import get_current_timestamp

logger = structlog.get_logger(__name__)


class TaskStore:
    """
    Simple in-memory task storage.

    Stores tasks for retrieval during polling.
    """

    def __init__(self) -> None:
        """Initialize empty task store."""
        self._tasks: dict[str, Task] = {}

    def store(self, task: Task) -> None:
        """Store a task."""
        self._tasks[task.id] = task

    def get(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def delete(self, task_id: str) -> bool:
        """Delete a task."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def list_all(self) -> list[Task]:
        """List all tasks."""
        return list(self._tasks.values())

    def count(self) -> int:
        """Count tasks."""
        return len(self._tasks)

    def clear(self) -> int:
        """Clear all tasks."""
        count = len(self._tasks)
        self._tasks.clear()
        return count


def create_agent_router(
    executor: BaseAgentExecutor,
    task_store: TaskStore | None = None,
) -> APIRouter:
    """
    Create FastAPI router for an A2A agent.

    Args:
        executor: Agent executor instance.
        task_store: Optional task store (created if not provided).

    Returns:
        Configured APIRouter.
    """
    router = APIRouter(tags=["a2a"])
    store = task_store or TaskStore()

    @router.get("/.well-known/agent.json")
    async def get_agent_card() -> AgentCard:
        """Get the agent card."""
        return executor.agent_card

    @router.get("/agent.json")
    async def get_agent_card_alt() -> AgentCard:
        """Get agent card (alternative path)."""
        return executor.agent_card

    @router.post("/tasks", status_code=201)
    async def create_task(request: TaskRequest) -> Task:
        """Create and execute a new task."""
        logger.info(
            "api_create_task",
            skill_id=request.skill_id,
        )

        task = await executor.handle_task(request)
        store.store(task)

        return task

    @router.get("/tasks/{task_id}")
    async def get_task(task_id: str) -> Task:
        """Get task by ID."""
        task = store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @router.post("/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str) -> Task:
        """Cancel a running task."""
        task = store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
            raise HTTPException(
                status_code=400,
                detail=f"Task already in terminal state: {task.state.value}",
            )

        task = await executor.on_cancel(task)
        store.store(task)

        return task

    @router.post("/tasks/{task_id}/input")
    async def provide_input(task_id: str, input_data: dict[str, Any]) -> Task:
        """Provide input for a task waiting for input."""
        task = store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.state != TaskState.INPUT_REQUIRED:
            raise HTTPException(
                status_code=400,
                detail=f"Task not waiting for input: {task.state.value}",
            )

        # Update task input and re-execute
        task.input.update(input_data)
        task.transition_to(TaskState.WORKING)

        # Create new request with updated input
        request = TaskRequest(
            skill_id=task.skill_id,
            input=task.input,
            metadata=task.metadata,
        )

        # Re-execute
        updated_task = await executor.handle_task(request)
        updated_task.id = task.id  # Preserve original ID
        store.store(updated_task)

        return updated_task

    @router.get("/tasks")
    async def list_tasks(
        state: TaskState | None = None,
        limit: int = 100,
    ) -> list[Task]:
        """List all tasks, optionally filtered by state."""
        tasks = store.list_all()

        if state:
            tasks = [t for t in tasks if t.state == state]

        return tasks[:limit]

    @router.get("/health")
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return await executor.health_check()

    @router.get("/stats")
    async def get_stats() -> dict[str, Any]:
        """Get agent statistics."""
        tasks = store.list_all()

        state_counts: dict[str, int] = {}
        for task in tasks:
            state = task.state.value
            state_counts[state] = state_counts.get(state, 0) + 1

        return {
            "agent_id": executor.agent_card.id,
            "agent_name": executor.agent_card.name,
            "total_tasks": len(tasks),
            "state_counts": state_counts,
            "skills": [s.id for s in executor.agent_card.skills],
            "timestamp": get_current_timestamp(),
        }

    return router


def create_agent_app(
    executor: BaseAgentExecutor,
    task_store: TaskStore | None = None,
    prefix: str = "",
) -> FastAPI:
    """
    Create FastAPI application for an A2A agent.

    Args:
        executor: Agent executor instance.
        task_store: Optional task store.
        prefix: URL prefix for the agent routes.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title=f"A2A Agent: {executor.agent_card.name}",
        description=executor.agent_card.description,
        version="1.0.0",
    )

    router = create_agent_router(executor, task_store)
    app.include_router(router, prefix=prefix)

    # Store executor and task store for access
    app.state.executor = executor
    app.state.task_store = task_store or TaskStore()

    logger.info(
        "agent_app_created",
        agent_id=executor.agent_card.id,
        agent_name=executor.agent_card.name,
    )

    return app


class AgentServer:
    """
    A2A Agent server wrapper.

    Provides lifecycle management for running an agent.
    """

    def __init__(
        self,
        executor: BaseAgentExecutor,
        host: str = "localhost",
        port: int = 8000,
    ) -> None:
        """
        Initialize agent server.

        Args:
            executor: Agent executor instance.
            host: Host to bind to.
            port: Port to listen on.
        """
        self._executor = executor
        self._host = host
        self._port = port
        self._app: FastAPI | None = None

        logger.info(
            "agent_server_initialized",
            agent_id=executor.agent_card.id,
            host=host,
            port=port,
        )

    @property
    def app(self) -> FastAPI:
        """Get or create the FastAPI app."""
        if not self._app:
            self._app = create_agent_app(self._executor)
        return self._app

    @property
    def executor(self) -> BaseAgentExecutor:
        """Get the agent executor."""
        return self._executor

    @property
    def host(self) -> str:
        """Get server host."""
        return self._host

    @property
    def port(self) -> int:
        """Get server port."""
        return self._port

    def run(self) -> None:
        """
        Run the agent server (blocking).

        Uses uvicorn to serve the application.
        """
        import uvicorn

        logger.info(
            "starting_agent_server",
            agent_id=self._executor.agent_card.id,
            host=self._host,
            port=self._port,
        )

        uvicorn.run(
            self.app,
            host=self._host,
            port=self._port,
            log_level="info",
        )
