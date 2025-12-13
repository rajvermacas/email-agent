"""
SQLite storage for A2A agent registry.

This module provides async SQLite storage for managing agent registration
and discovery in the A2A protocol.

All database operations are async using aiosqlite.
No fallback/default values - missing data raises exceptions.

Usage:
    from info_agent.a2a.storage import A2AStorage
    from info_agent.a2a.models import AgentCard

    storage = A2AStorage()
    await storage.init_db()

    # Save agent
    await storage.save_agent(agent_card)

    # Get agent
    agent = await storage.get_agent("currency-agent")

    # List all agents
    agents = await storage.list_agents()

    # Delete agent
    await storage.delete_agent("currency-agent")
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from a2a.types import AgentCard, AgentSkill
from info_agent.config import get_settings
from info_agent.utils.exceptions import AgentNotFoundError, StorageError
from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


class A2AStorage:
    """
    Async SQLite storage for A2A agent registry.

    This class provides CRUD operations for agent cards in the registry.
    All operations are async and use transactions for data integrity.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str | None = None) -> None:
        """
        Initialize storage with database path.

        Args:
            db_path: Optional path to database file. If not provided,
                    uses registry_db_path from settings.

        Raises:
            StorageError: If database path cannot be determined.
        """
        if db_path is None:
            settings = get_settings()
            db_path = settings.registry_db_path
            logger.info("Using registry database path from settings", db_path=db_path)

        if not db_path:
            raise StorageError(
                message="Database path not provided and not found in settings",
                operation="init",
                entity_type="a2a_registry",
            )

        self.db_path = db_path
        logger.info("A2AStorage initialized", db_path=self.db_path)

    async def init_db(self) -> None:
        """
        Initialize the database schema.

        Creates the agents table with proper indexes if it doesn't exist.

        Raises:
            StorageError: If database initialization fails.
        """
        logger.info("Initializing A2A registry database", db_path=self.db_path)

        # Ensure parent directory exists
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("Database directory ensured", directory=str(db_file.parent))

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agents (
                        name TEXT PRIMARY KEY,
                        description TEXT NOT NULL,
                        version TEXT NOT NULL,
                        url TEXT NOT NULL,
                        capabilities TEXT NOT NULL,
                        skills TEXT NOT NULL,
                        default_input_modes TEXT NOT NULL,
                        default_output_modes TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )

                # Create indexes for common queries
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_agents_created_at ON agents(created_at)"
                )
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_agents_updated_at ON agents(updated_at)"
                )

                await db.commit()
                logger.info("A2A registry database initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise StorageError(
                message=f"Database initialization failed: {e}",
                operation="init_db",
                entity_type="a2a_registry",
                details={"db_path": self.db_path, "error": str(e)},
            ) from e

    async def save_agent(self, agent_card: AgentCard) -> None:
        """
        Save or update an agent card in the registry.

        Args:
            agent_card: Agent card to save.

        Raises:
            StorageError: If save operation fails.
        """
        logger.info("Saving agent to registry", agent_name=agent_card.name)

        if not agent_card.name:
            raise StorageError(
                message="Agent name is required",
                operation="save",
                entity_type="agent",
            )

        now = datetime.now(timezone.utc).isoformat()
        # SDK AgentCard doesn't have created_at, so use current time for new records
        created_at = now

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO agents (
                        name, description, version, url, capabilities,
                        skills, default_input_modes, default_output_modes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        description = excluded.description,
                        version = excluded.version,
                        url = excluded.url,
                        capabilities = excluded.capabilities,
                        skills = excluded.skills,
                        default_input_modes = excluded.default_input_modes,
                        default_output_modes = excluded.default_output_modes,
                        updated_at = excluded.updated_at
                    """,
                    (
                        agent_card.name,
                        agent_card.description,
                        agent_card.version,
                        agent_card.url,
                        # SDK AgentCapabilities is an object, need to serialize it
                        json.dumps(agent_card.capabilities.model_dump() if agent_card.capabilities else {}),
                        json.dumps([skill.model_dump() for skill in agent_card.skills]),
                        json.dumps(agent_card.default_input_modes or []),
                        json.dumps(agent_card.default_output_modes or []),
                        created_at,
                        now,
                    ),
                )
                await db.commit()
                logger.info(
                    "Agent saved successfully",
                    agent_name=agent_card.name,
                    version=agent_card.version,
                )

        except Exception as e:
            logger.error(
                "Failed to save agent",
                agent_name=agent_card.name,
                error=str(e),
            )
            raise StorageError(
                message=f"Failed to save agent: {e}",
                operation="save",
                entity_type="agent",
                entity_id=agent_card.name,
                details={"error": str(e)},
            ) from e

    async def get_agent(self, name: str) -> AgentCard:
        """
        Retrieve an agent card by name.

        Args:
            name: Name of the agent to retrieve.

        Returns:
            AgentCard instance.

        Raises:
            AgentNotFoundError: If agent is not found.
            StorageError: If retrieval operation fails.
        """
        logger.info("Retrieving agent from registry", agent_name=name)

        if not name:
            raise StorageError(
                message="Agent name is required",
                operation="get",
                entity_type="agent",
            )

        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT name, description, version, url, capabilities,
                           skills, default_input_modes, default_output_modes,
                           created_at
                    FROM agents
                    WHERE name = ?
                    """,
                    (name,),
                ) as cursor:
                    row = await cursor.fetchone()

                    if not row:
                        logger.warning("Agent not found", agent_name=name)
                        raise AgentNotFoundError(
                            agent_name=name,
                            details={"searched_in": "registry_database"},
                        )

                    # Deserialize JSON fields
                    skills_data = json.loads(row["skills"])
                    skills = [AgentSkill(**skill) for skill in skills_data]

                    # SDK AgentCard uses snake_case and doesn't have created_at
                    agent_card = AgentCard(
                        name=row["name"],
                        description=row["description"],
                        version=row["version"],
                        url=row["url"],
                        capabilities=json.loads(row["capabilities"]),
                        skills=skills,
                        default_input_modes=json.loads(row["default_input_modes"]),
                        default_output_modes=json.loads(row["default_output_modes"]),
                    )

                    logger.info(
                        "Agent retrieved successfully",
                        agent_name=name,
                        version=agent_card.version,
                    )
                    return agent_card

        except AgentNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to retrieve agent", agent_name=name, error=str(e))
            raise StorageError(
                message=f"Failed to retrieve agent: {e}",
                operation="get",
                entity_type="agent",
                entity_id=name,
                details={"error": str(e)},
            ) from e

    async def list_agents(self) -> list[AgentCard]:
        """
        List all registered agents.

        Returns:
            List of AgentCard instances.

        Raises:
            StorageError: If list operation fails.
        """
        logger.info("Listing all agents from registry")

        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT name, description, version, url, capabilities,
                           skills, default_input_modes, default_output_modes,
                           created_at
                    FROM agents
                    ORDER BY created_at DESC
                    """
                ) as cursor:
                    rows = await cursor.fetchall()

                    agents = []
                    for row in rows:
                        skills_data = json.loads(row["skills"])
                        skills = [AgentSkill(**skill) for skill in skills_data]

                        # SDK AgentCard uses snake_case and doesn't have created_at
                        agent_card = AgentCard(
                            name=row["name"],
                            description=row["description"],
                            version=row["version"],
                            url=row["url"],
                            capabilities=json.loads(row["capabilities"]),
                            skills=skills,
                            default_input_modes=json.loads(row["default_input_modes"]),
                            default_output_modes=json.loads(row["default_output_modes"]),
                        )
                        agents.append(agent_card)

                    logger.info("Agents listed successfully", agent_count=len(agents))
                    return agents

        except Exception as e:
            logger.error("Failed to list agents", error=str(e))
            raise StorageError(
                message=f"Failed to list agents: {e}",
                operation="list",
                entity_type="agent",
                details={"error": str(e)},
            ) from e

    async def delete_agent(self, name: str) -> None:
        """
        Delete an agent from the registry.

        Args:
            name: Name of the agent to delete.

        Raises:
            AgentNotFoundError: If agent is not found.
            StorageError: If delete operation fails.
        """
        logger.info("Deleting agent from registry", agent_name=name)

        if not name:
            raise StorageError(
                message="Agent name is required",
                operation="delete",
                entity_type="agent",
            )

        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM agents WHERE name = ?",
                    (name,),
                )
                await db.commit()

                if cursor.rowcount == 0:
                    logger.warning("Agent not found for deletion", agent_name=name)
                    raise AgentNotFoundError(
                        agent_name=name,
                        details={"operation": "delete", "searched_in": "registry_database"},
                    )

                logger.info("Agent deleted successfully", agent_name=name)

        except AgentNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to delete agent", agent_name=name, error=str(e))
            raise StorageError(
                message=f"Failed to delete agent: {e}",
                operation="delete",
                entity_type="agent",
                entity_id=name,
                details={"error": str(e)},
            ) from e
