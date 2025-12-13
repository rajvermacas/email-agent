# Google A2A Protocol: Quick Start Guide

## Installation

### Official SDK

```bash
# Basic installation
pip install a2a-sdk

# With HTTP server (recommended)
pip install "a2a-sdk[http-server]"

# All features including gRPC and database support
pip install "a2a-sdk[all]"

# Python version requirement
python --version  # Must be 3.10+, 3.12+ recommended
```

### Alternative SDK (python-a2a)

```bash
pip install python-a2a
```

## Core Concepts Quick Reference

### 1. Agent Card
```json
{
  "id": "agent-123",
  "name": "Currency Converter",
  "description": "Converts between currencies",
  "endpoint": "https://agent.example.com/a2a",
  "protocol_version": "1.0",
  "skills": [
    {
      "id": "convert",
      "name": "Convert Currency",
      "description": "Convert amount from one currency to another",
      "input_schema": {
        "type": "object",
        "properties": {
          "amount": {"type": "number"},
          "from": {"type": "string"},
          "to": {"type": "string"}
        },
        "required": ["amount", "from", "to"]
      }
    }
  ]
}
```

### 2. Task Lifecycle
```
submitted → working → input_required? → completed
                   ↓
                 failed or cancelled
```

### 3. Message Parts
```python
# Text message
{"type": "text", "text": "Hello agent"}

# Structured data
{"type": "data", "data": {"key": "value"}}

# File reference
{"type": "file", "file": {"path": "s3://bucket/file", "mime_type": "text/plain"}}
```

## Simple Example: Currency Converter Agent

### Step 1: Create Agent Executor

```python
from a2a.server import AgentExecutor, RequestContext, EventQueue
from a2a.types import Artifact, Part
import logging

logger = logging.getLogger(__name__)

class CurrencyAgentExecutor(AgentExecutor):
    """Simple currency converter agent."""

    # Mock exchange rates (use real API in production)
    RATES = {
        "USD": 1.0,
        "EUR": 0.92,
        "GBP": 0.79,
        "JPY": 149.50
    }

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """Execute task request."""
        try:
            task = context.request.task
            logger.info(f"Processing task: {task.id}")

            # Extract input
            input_data = task.input
            amount = float(input_data.get("amount", 0))
            from_currency = input_data.get("from_currency", "USD").upper()
            to_currency = input_data.get("to_currency", "EUR").upper()

            # Validate
            if amount <= 0:
                await event_queue.send_error("Amount must be positive")
                return

            if from_currency not in self.RATES or to_currency not in self.RATES:
                await event_queue.send_error(f"Unsupported currency")
                return

            # Convert
            amount_in_usd = amount / self.RATES[from_currency]
            converted_amount = amount_in_usd * self.RATES[to_currency]

            # Create artifact response
            text_part = Part(
                type="text",
                text=f"{amount} {from_currency} = {converted_amount:.2f} {to_currency}"
            )

            data_part = Part(
                type="data",
                data={
                    "original_amount": amount,
                    "original_currency": from_currency,
                    "converted_amount": round(converted_amount, 2),
                    "target_currency": to_currency,
                    "rate": round(converted_amount / amount, 6)
                }
            )

            artifact = Artifact(parts=[text_part, data_part])
            await event_queue.send_artifact(artifact)

            logger.info(f"Task {task.id} completed successfully")

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            await event_queue.send_error(f"Conversion failed: {str(e)}")

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """Handle task cancellation."""
        logger.info(f"Task {context.request.task.id} cancelled")
```

### Step 2: Create Agent Card

```python
from a2a.types import AgentCard, Skill

def get_agent_card() -> AgentCard:
    """Generate agent card describing capabilities."""

    convert_skill = Skill(
        id="convert_currency",
        name="Convert Currency",
        description="Converts amount from source to target currency",
        input_schema={
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": "Amount to convert",
                    "minimum": 0.01
                },
                "from_currency": {
                    "type": "string",
                    "description": "Source currency (USD, EUR, GBP, JPY)",
                    "enum": ["USD", "EUR", "GBP", "JPY"]
                },
                "to_currency": {
                    "type": "string",
                    "description": "Target currency",
                    "enum": ["USD", "EUR", "GBP", "JPY"]
                }
            },
            "required": ["amount", "from_currency", "to_currency"]
        },
        example_prompts=[
            "Convert 100 USD to EUR",
            "What is 50 pounds in dollars?"
        ]
    )

    return AgentCard(
        id="currency-agent-v1",
        name="Currency Converter",
        description="Converts amounts between multiple currencies with current rates",
        protocol_version="1.0",
        endpoint="https://agent.example.com/a2a",
        skills=[convert_skill]
    )
```

### Step 3: Create Server

```python
from a2a.server import Server
from fastapi import FastAPI
import uvicorn

# Create executor
executor = CurrencyAgentExecutor()

# Create A2A server
a2a_server = Server(
    executor=executor,
    agent_card=get_agent_card()
)

# Optional: Mount on FastAPI
app = FastAPI()
app.include_router(a2a_server.router, prefix="/a2a")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
```

### Step 4: Run Agent

```bash
python currency_agent.py
```

### Step 5: Test Agent Card

```bash
curl http://localhost:8000/a2a/.well-known/agent.json
```

Expected response:
```json
{
  "id": "currency-agent-v1",
  "name": "Currency Converter",
  "endpoint": "https://agent.example.com/a2a",
  "skills": [
    {
      "id": "convert_currency",
      "name": "Convert Currency"
    }
  ]
}
```

## Client Example: Invoking a Remote Agent

```python
from a2a.client import A2AClient
import asyncio

async def test_currency_agent():
    """Test invoking the currency agent."""

    # Create client pointing to agent
    client = A2AClient("http://localhost:8000/a2a")

    # Create synchronous task (wait for result)
    task = await client.create_task(
        skill="convert_currency",
        input={
            "amount": 100,
            "from_currency": "USD",
            "to_currency": "EUR"
        },
        blocking=True  # Wait for completion
    )

    # Check result
    print(f"Task status: {task.status}")
    print(f"Artifacts: {task.artifacts}")

    # Get final artifact
    if task.artifacts:
        artifact = task.artifacts[0]
        for part in artifact.parts:
            if part.type == "text":
                print(f"Result: {part.text}")
            elif part.type == "data":
                print(f"Data: {part.data}")

# Run test
asyncio.run(test_currency_agent())
```

## LangGraph Integration Example

### Using LangGraph with A2A

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import StreamWriter
from typing import TypedDict
from a2a.langgraph import expose_as_a2a

# Define agent state
class AgentState(TypedDict):
    messages: list
    currency_from: str
    currency_to: str
    amount: float

# Create graph
builder = StateGraph(AgentState)

# Define nodes
async def process_conversion(state):
    """Process currency conversion."""
    amount = state["amount"]
    from_curr = state["currency_from"]
    to_curr = state["currency_to"]

    # Your conversion logic here
    result = amount * 0.92  # Mock conversion

    state["messages"].append({
        "role": "agent",
        "content": f"{amount} {from_curr} = {result} {to_curr}"
    })
    return state

# Add nodes and edges
builder.add_node("process", process_conversion)
builder.add_edge(START, "process")
builder.add_edge("process", END)

# Compile graph
graph = builder.compile()

# Expose via A2A (automatic agent card generation!)
server = expose_as_a2a(graph)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(server, host="0.0.0.0", port=8000)
```

## Async Task Example (Non-Blocking)

```python
from a2a.client import A2AClient
import asyncio
import time

async def test_async_task():
    """Test non-blocking task with webhook callback."""

    client = A2AClient("http://localhost:8000/a2a")

    # Create non-blocking task
    task = await client.create_task(
        skill="convert_currency",
        input={
            "amount": 100,
            "from_currency": "USD",
            "to_currency": "EUR"
        },
        blocking=False,  # Return immediately
        webhook_url="https://callback.example.com/done"
    )

    print(f"Task created: {task.id}")
    print(f"Task status: {task.status}")  # Should be "working"

    # Poll for completion (or wait for webhook)
    while True:
        task = await client.get_task(task.id)

        if task.status in ["completed", "failed", "cancelled"]:
            break

        print(f"Status: {task.status}")
        await asyncio.sleep(2)

    print(f"Final status: {task.status}")

# Run
asyncio.run(test_async_task())
```

## Security: Authentication Setup

### OAuth 2.0 Configuration

```python
from a2a.security import OAuth2Config, AuthProvider
from fastapi import Depends

# Configure OAuth2
oauth_config = OAuth2Config(
    client_id="my-agent-id",
    client_secret="secret-key",
    token_endpoint="https://auth.example.com/token"
)

# Create auth provider
auth_provider = AuthProvider(oauth_config)

# Use in requests
async def authenticated_task(
    context: RequestContext,
    auth: str = Depends(auth_provider.verify)
):
    """Only authenticated requests can create tasks."""
    # Process task...
    pass
```

### Input Validation

```python
from pydantic import BaseModel, Field, validator

class ConvertInput(BaseModel):
    amount: float = Field(gt=0, lt=1e10)
    from_currency: str = Field(regex="^[A-Z]{3}$")
    to_currency: str = Field(regex="^[A-Z]{3}$")

    @validator("from_currency", "to_currency")
    def validate_currency(cls, v):
        valid = ["USD", "EUR", "GBP", "JPY"]
        if v not in valid:
            raise ValueError(f"Currency must be in {valid}")
        return v

# Use in executor
class ValidatedExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        try:
            validated = ConvertInput(**context.request.task.input)
            # Process with validated input...
        except ValidationError as e:
            await event_queue.send_error(f"Invalid input: {e}")
```

## Logging Best Practices

```python
import logging
import json
from datetime import datetime

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

logger = logging.getLogger(__name__)

def log_event(level: str, message: str, **kwargs):
    """Log structured event."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
        **kwargs
    }
    logger.info(json.dumps(entry))

# Usage in agent
class LoggingExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        task = context.request.task

        log_event("INFO", "Task started", task_id=task.id, skill=task.skill_id)

        try:
            result = await self.process_task(task)
            log_event("INFO", "Task completed", task_id=task.id, duration_ms=100)
        except Exception as e:
            log_event("ERROR", "Task failed", task_id=task.id, error=str(e))
            await event_queue.send_error(str(e))
```

## Testing Example

```python
import pytest
from unittest.mock import AsyncMock
from a2a.server import RequestContext, EventQueue

@pytest.mark.asyncio
async def test_currency_conversion():
    """Test currency conversion."""
    executor = CurrencyAgentExecutor()

    # Mock context
    context = AsyncMock(spec=RequestContext)
    context.request.task.skill_id = "convert_currency"
    context.request.task.input = {
        "amount": 100,
        "from_currency": "USD",
        "to_currency": "EUR"
    }

    # Mock event queue
    event_queue = AsyncMock(spec=EventQueue)

    # Execute
    await executor.execute(context, event_queue)

    # Verify
    assert event_queue.send_artifact.called
    artifact = event_queue.send_artifact.call_args[0][0]
    assert "100" in str(artifact)

@pytest.mark.asyncio
async def test_invalid_currency():
    """Test with invalid currency."""
    executor = CurrencyAgentExecutor()

    context = AsyncMock(spec=RequestContext)
    context.request.task.input = {
        "amount": 100,
        "from_currency": "INVALID",
        "to_currency": "EUR"
    }

    event_queue = AsyncMock(spec=EventQueue)

    await executor.execute(context, event_queue)

    # Should error
    assert event_queue.send_error.called
```

## Deployment: Docker Example

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run agent
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

requirements.txt:
```
a2a-sdk[http-server]==1.0.0
fastapi==0.104.0
uvicorn==0.24.0
pydantic==2.5.0
python-dotenv==1.0.0
```

## Common Issues and Solutions

### Issue: Agent Card Not Found
```
Error: GET /.well-known/agent.json returned 404
```

**Solution**: Ensure server exposes agent card endpoint
```python
from a2a.server import DefaultRequestHandler

handler = DefaultRequestHandler(
    executor=executor,
    agent_card=get_agent_card()
)
```

### Issue: Task Never Completes
**Solution**: Ensure `send_artifact()` or `send_error()` called
```python
async def execute(self, context, event_queue):
    try:
        result = process(context.request.task)
        await event_queue.send_artifact(result)  # Required!
    except Exception as e:
        await event_queue.send_error(str(e))  # Or error
```

### Issue: WebHook Not Called
**Solution**: Verify webhook URL is HTTPS and accessible
```python
task = await client.create_task(
    skill="task",
    blocking=False,
    webhook_url="https://callback.example.com/webhook"  # Must be HTTPS!
)
```

## Useful Resources

- Official Documentation: https://a2a-protocol.org/latest/
- Python SDK: https://github.com/a2aproject/a2a-python
- Examples: https://github.com/a2aproject/a2a-samples
- LangGraph Integration: https://docs.langchain.com/langgraph-platform/server-a2a
