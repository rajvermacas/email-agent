"""
Registry-specific models for A2A agent registration.

This module contains custom Pydantic models used by the A2A registry API.
These are not part of the official A2A SDK but are specific to our registry implementation.
"""

from typing import Literal

from pydantic import BaseModel, Field


class RegisterAgentResponse(BaseModel):
    """
    Response from registering an agent.

    Attributes:
        status: Status of the registration (required).
        agent_name: Name of the registered agent (required).
        message: Additional information about the registration (optional).
    """

    status: Literal["registered", "updated", "failed"] = Field(
        ...,
        description="Status of the registration",
    )
    agent_name: str = Field(
        ...,
        description="Name of the registered agent",
        min_length=1,
    )
    message: str | None = Field(
        default=None,
        description="Additional information about the registration",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "registered",
                "agent_name": "currency-agent",
                "message": "Agent successfully registered",
            }
        }
    }
