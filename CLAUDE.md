# Info-Agent - Developer Documentation

## Project Overview

Info-Agent is a multi-agent system for automated information retrieval via email communication. The system uses AI-powered agents to orchestrate email-based workflows, leveraging Google's A2A (Agent-to-Agent) protocol for inter-agent communication and LangGraph for workflow orchestration.

**Current Status**: Phase 1 MVP Backend (Completed)

**Core Philosophy**:
- Agent-based architecture with clear separation of concerns
- LLM-powered decision making and content generation
- State persistence with SQLite checkpointing
- Comprehensive testing with 91.5% test pass rate (911 passing out of 996 tests)
- Extensive logging and error handling

---

## Quick Start

### Prerequisites
- Python 3.12+
- Google Gemini API key
- SQLite (built-in with Python)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd info-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .

# Set up environment
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Running the System

```bash
# Start all services (recommended)
python scripts/run_all_services.py

# OR start services individually:

# Terminal 1: Start Mock Email Server (SMTP + REST API)
python scripts/run_email_server.py

# Terminal 2: Start FastAPI Gateway (Main API)
python scripts/run_gateway.py

# Note: Mail Agent is currently embedded in the Gateway (not a separate service)
# A separate Mail Agent server (port 8001) is planned for Phase 2
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=info_agent --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_workflow_graph.py -v
```

---

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Gateway (Port 8000)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Supervisor Agent (LangGraph Orchestration)            │ │
│  │  - Parses instructions                                 │ │
│  │  - Generates execution plans (LLM)                     │ │
│  │  - Coordinates Mail Agent                              │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Mail Agent (Embedded)                                 │ │
│  │  - Composes emails using LLM                           │ │
│  │  - Parses incoming emails                              │ │
│  │  - SMTP client for sending                             │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  A2A Registry (Agent Discovery)                        │ │
│  │  - Agent registration                                  │ │
│  │  - Agent discovery                                     │ │
│  │  - SQLite persistence                                  │ │
│  └────────────────────────────────────────────────────────┘ │
│  API Routes: /api/workflows, /webhooks/email, /health      │
└─────────────────────────────────────────────────────────────┘
                            ↓ SMTP (Port 1025)
┌─────────────────────────────────────────────────────────────┐
│         Mock Email Server (Ports 1025, 8025)                │
│  - SMTP interface (receive emails)                          │
│  - REST API (inbox management)                              │
│  - Webhook notifications                                    │
│  - SQLite storage                                           │
└─────────────────────────────────────────────────────────────┘

Note: Mail Agent is currently embedded in Gateway.
Separate A2A worker service on port 8001 is planned for Phase 2.
```

### Component Interaction Flow

1. **User creates workflow** → FastAPI Gateway
2. **Gateway initializes Supervisor Agent** → LangGraph workflow
3. **Supervisor parses instructions** → Gemini LLM
4. **Supervisor generates execution plan** → Gemini LLM
5. **User approves plan** → Gateway API
6. **Supervisor discovers Mail Agent** → A2A Registry
7. **Supervisor delegates email task** → Mail Agent (A2A protocol)
8. **Mail Agent composes email** → Gemini LLM
9. **Mail Agent sends email** → Mock Email Server (SMTP)
10. **Email Server sends webhook** → Gateway
11. **Supervisor updates workflow state** → SQLite checkpoint

### Port Assignments

| Component | Port | Purpose | Status |
|-----------|------|---------|--------|
| FastAPI Gateway | 8000 | Main API entry point | Active |
| Mail Agent | 8001 | A2A worker server | Planned (Phase 2) |
| Mock Email Server (REST) | 8025 | Email inbox REST API | Active |
| Mock Email Server (SMTP) | 1025 | SMTP interface | Active |

Note: In Phase 1, Mail Agent is embedded in the Gateway. Standalone service planned for Phase 2.

---

## Directory Structure

```
/workspaces/info-agent/
├── src/info_agent/                    # Main application source
│   ├── __init__.py
│   ├── config.py                      # Settings (Pydantic BaseSettings)
│   ├── main.py                        # FastAPI Gateway entry point
│   │
│   ├── a2a/                           # A2A Protocol Implementation
│   │   ├── __init__.py
│   │   ├── client.py                  # A2A client for sending tasks
│   │   ├── models.py                  # A2A data models (AgentCard, etc.)
│   │   ├── registry.py                # Agent registry endpoints
│   │   └── storage.py                 # SQLite storage for agents
│   │
│   ├── agents/                        # AI Agents
│   │   ├── mail/                      # Mail Agent (A2A Worker)
│   │   │   ├── agent.py               # FastAPI A2A server
│   │   │   ├── composer.py            # LLM email composition
│   │   │   ├── parser.py              # Email parsing logic
│   │   │   ├── smtp_client.py         # SMTP client wrapper
│   │   │   └── state.py               # Mail agent state schema
│   │   │
│   │   └── supervisor/                # Supervisor Agent (Orchestrator)
│   │       ├── agent.py               # Supervisor logic and workflow
│   │       ├── planner.py             # LLM-based plan generation
│   │       └── state.py               # Supervisor state schema
│   │
│   ├── api/                           # REST API Layer
│   │   ├── models/
│   │   │   ├── requests.py            # Request Pydantic models
│   │   │   └── responses.py           # Response Pydantic models
│   │   └── routes/
│   │       ├── health.py              # Health check endpoint
│   │       ├── webhooks.py            # Email webhook receiver
│   │       └── workflows.py           # Workflow CRUD endpoints
│   │
│   ├── email/                         # Mock Email Server
│   │   ├── api.py                     # REST API endpoints
│   │   ├── models.py                  # Email data models
│   │   ├── server.py                  # Email server main
│   │   ├── smtp.py                    # SMTP handler (aiosmtpd)
│   │   ├── storage.py                 # SQLite email storage
│   │   └── webhook.py                 # Webhook notification sender
│   │
│   ├── llm/                           # LLM Integration
│   │   ├── README.md                  # LLM module documentation
│   │   ├── factory.py                 # Singleton factory functions
│   │   └── gemini_provider.py         # Gemini LLM wrapper
│   │
│   ├── utils/                         # Utilities
│   │   ├── exceptions.py              # Custom exception classes
│   │   └── logging.py                 # Structured logging setup
│   │
│   └── workflow/                      # LangGraph Workflow Engine
│       ├── checkpointer.py            # SQLite checkpointing
│       ├── graph.py                   # Workflow graph definition
│       ├── nodes.py                   # Node implementations
│       └── state.py                   # Workflow state schema
│
├── tests/                             # Test Suite (996 tests, 911 passing)
│   ├── conftest.py                    # Shared pytest fixtures
│   ├── integration/                   # Integration tests
│   │   ├── test_a2a_protocol.py
│   │   ├── test_api_gateway.py
│   │   ├── test_email_system.py
│   │   └── test_workflow_execution.py
│   └── unit/                          # Unit tests (34 files)
│       ├── test_a2a_*.py              # A2A module tests
│       ├── test_api_*.py              # API tests
│       ├── test_email_*.py            # Email system tests
│       ├── test_llm.py                # LLM integration tests
│       ├── test_mail_agent*.py        # Mail agent tests
│       ├── test_supervisor_*.py       # Supervisor tests
│       └── test_workflow_*.py         # Workflow tests
│
├── scripts/                           # Utility Scripts
│   ├── run_all_services.py            # Start all services
│   ├── run_email_server.py            # Start email server
│   ├── run_gateway.py                 # Start gateway
│   ├── test_a2a_module.py             # Test A2A manually
│   ├── test_llm_module.py             # Test LLM manually
│   └── test_workflow_basic.py         # Test workflow manually
│
├── test_data/                         # Test Input Files
│   ├── sample_email_response.json
│   ├── sample_instructions_*.txt
│   └── workflow_creation_request.json
│
├── data/                              # Runtime Data (gitignored)
│   └── checkpoints.db                 # LangGraph state persistence
│
├── .env.example                       # Environment template
├── .gitignore
├── pyproject.toml                     # Project config & dependencies
└── uv.lock                            # Dependency lock file
```

---

## Key Components

### 1. Configuration (`config.py`)

- **Type**: Pydantic Settings with environment variable support
- **Purpose**: Centralized configuration management
- **Key Settings**:
  - LLM configuration (API key, model, temperature)
  - Server ports (gateway, mail agent, email server)
  - Database paths (checkpoints, emails, registry, workflows)
  - A2A registry URL
  - Logging configuration

**Usage**:
```python
from info_agent.config import get_settings

settings = get_settings()
print(f"Using model: {settings.llm_model}")
```

### 2. A2A Protocol (`a2a/`)

- **Purpose**: Google A2A protocol integration using official a2a-sdk v0.3.21
- **Technology**: Official a2a-sdk from Google + custom registry
- **Components**:
  - `sdk_client_wrapper.py`: Simplified SDK client wrapper (441 lines)
  - `registry_models.py`: Registry-specific response models (46 lines)
  - `registry.py`: Agent registration and discovery endpoints
  - `storage.py`: SQLite persistence for registered agents

**Key Features**:
- Official SDK integration (100% spec-compliant)
- JSON-RPC 2.0 protocol (SDK-managed)
- Server: Uses SDK's `RequestHandler` and `A2ARESTFastAPIApplication`
- Client: Uses SDK's `ClientFactory` via `SDKClientWrapper`
- All models from SDK: `AgentCard`, `AgentSkill`, `Message`, `Task`, `TaskStatus`
- Custom SQLite-backed registry (not part of A2A spec)
- 76.7% code reduction from custom implementation (1,675 → 390 lines)

### 3. Supervisor Agent (`agents/supervisor/`)

- **Purpose**: Central orchestrator for workflow execution
- **Technology**: LangGraph workflow engine with Gemini LLM
- **Responsibilities**:
  - Parse user instructions
  - Generate execution plans
  - Discover and delegate to Mail Agent
  - Track workflow state
  - Handle approvals and responses

**State Schema** (`state.py`):
```python
class SupervisorState(TypedDict):
    workflow_id: str
    instructions: str
    target_email: str
    target_name: str
    requested_info: str
    status: WorkflowStatus
    plan: List[dict]
    current_step: int
    email_thread_id: Optional[str]
    received_response: Optional[str]
    audit_log: List[dict]
    error: Optional[str]
```

### 4. Mail Agent (`agents/mail/`)

- **Purpose**: Email operations specialist agent
- **Technology**: FastAPI A2A server with aiosmtplib
- **Components**:
  - `agent.py`: A2A server with skill endpoints
  - `composer.py`: LLM-powered email composition
  - `parser.py`: Email content parsing
  - `smtp_client.py`: SMTP client wrapper

**Skills**:
- `send-email`: Compose and send emails
- `parse-email`: Parse incoming email content

### 5. Workflow Engine (`workflow/`)

- **Purpose**: LangGraph-based state machine for workflow execution
- **Components**:
  - `graph.py`: Workflow graph definition with nodes and edges
  - `nodes.py`: Node implementations (parse, plan, execute, etc.)
  - `state.py`: Workflow state TypedDict schema
  - `checkpointer.py`: SQLite checkpointing for state persistence

**Workflow Nodes**:
- `parse_instructions`: Extract requirements from instructions
- `generate_plan`: Create execution plan using LLM
- `wait_for_approval`: Pause for user approval
- `execute_step`: Execute current plan step
- `send_email`: Delegate to Mail Agent
- `wait_for_response`: Wait for email reply
- `process_response`: Handle received response

### 6. LLM Integration (`llm/`)

- **Purpose**: Google Gemini LLM integration via LangChain
- **Components**:
  - `gemini_provider.py`: Gemini wrapper with lazy initialization
  - `factory.py`: Singleton factory pattern

**Features**:
- Lazy initialization (client created on first use)
- Singleton pattern for resource efficiency
- Configuration from settings
- Override support for custom parameters
- Comprehensive logging and error handling

**Usage**:
```python
from info_agent.llm import get_gemini_llm

llm = get_gemini_llm()
response = await llm.ainvoke("Create an email requesting...")
```

### 7. Email System (`email/`)

- **Purpose**: Mock email server for development and testing
- **Components**:
  - `server.py`: Main server coordinating SMTP and REST
  - `smtp.py`: SMTP handler using aiosmtpd
  - `api.py`: REST API for inbox management
  - `storage.py`: SQLite email storage
  - `webhook.py`: Webhook notification sender

**Capabilities**:
- Accept emails via SMTP
- Store emails in SQLite
- Provide REST API for inbox access
- Send webhook notifications for new emails

### 8. API Gateway (`api/`, `main.py`)

- **Purpose**: Main REST API entry point
- **Technology**: FastAPI with Pydantic validation
- **Routes**:
  - `/api/workflows` - Workflow CRUD operations
  - `/api/workflows/{id}/files` - File upload
  - `/api/workflows/{id}/approve` - Approve execution plan
  - `/webhooks/email` - Receive email notifications
  - `/a2a/agents` - A2A registry endpoints
  - `/health` - Health check

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# LLM Configuration
GOOGLE_API_KEY=your-google-api-key-here
LLM_MODEL=gemini-2.5-flash
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

# Server Configuration
HOST=0.0.0.0
GATEWAY_PORT=8000
MAIL_AGENT_PORT=8001
EMAIL_SERVER_PORT=8025
SMTP_PORT=1025
DEBUG=true

# A2A Registry
A2A_REGISTRY_URL=http://localhost:8000/a2a

# Mock Email Server
SMTP_HOST=localhost
EMAIL_WEBHOOK_URL=http://localhost:8000/webhooks/email

# Database Paths
CHECKPOINT_DB_PATH=data/checkpoints.db
EMAIL_DB_PATH=data/emails.db
REGISTRY_DB_PATH=data/registry.db
WORKFLOW_DB_PATH=data/workflows.db

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=console  # or json
```

**IMPORTANT**: Never commit `.env` to version control. The `.gitignore` already excludes it.

---

## Development Commands

### Running Services

```bash
# Individual services
python scripts/run_gateway.py        # FastAPI Gateway (port 8000)
python scripts/run_mail_agent.py     # Mail Agent (port 8001)
python scripts/run_email_server.py   # Email Server (ports 1025, 8025)

# All services at once
python scripts/run_all_services.py
```

### Testing

```bash
# All tests
pytest

# With coverage report
pytest --cov=info_agent --cov-report=html
open htmlcov/index.html  # View coverage report

# Specific test categories
pytest tests/unit/                    # Unit tests only
pytest tests/integration/             # Integration tests only
pytest -m unit                        # Tests marked as unit
pytest -m integration                 # Tests marked as integration

# Specific modules
pytest tests/unit/test_workflow_graph.py -v
pytest tests/unit/test_llm.py -v
pytest tests/integration/test_api_gateway.py -v

# With detailed output
pytest -vv --tb=short

# Run specific test
pytest tests/unit/test_llm.py::test_get_gemini_llm -v
```

### Manual Testing

```bash
# Test LLM integration
python scripts/test_llm_module.py

# Test A2A protocol
python scripts/test_a2a_module.py

# Test basic workflow
python scripts/test_workflow_basic.py
```

### API Testing with cURL

```bash
# Health check
curl http://localhost:8000/health

# Create workflow
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Workflow", "description": "Testing"}'

# List workflows
curl http://localhost:8000/api/workflows

# Get workflow status
curl http://localhost:8000/api/workflows/{workflow_id}/status

# Approve workflow
curl -X POST http://localhost:8000/api/workflows/{workflow_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

### Database Management

```bash
# View checkpoints database
sqlite3 data/checkpoints.db
> .tables
> SELECT * FROM checkpoints;

# View emails database
sqlite3 data/emails.db
> .tables
> SELECT * FROM emails;

# View registry database
sqlite3 data/registry.db
> .tables
> SELECT * FROM agents;
```

---

## Development Patterns

### Adding a New Workflow Node

1. **Define node function** in `workflow/nodes.py`:
```python
async def my_new_node(state: SupervisorState) -> dict:
    """Node description."""
    logger.info(f"Executing my_new_node for workflow {state['workflow_id']}")

    # Perform logic
    result = await do_something(state)

    # Update state
    return {
        "status": WorkflowStatus.EXECUTING,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "my_new_node",
            "details": "Node executed successfully"
        }]
    }
```

2. **Add node to graph** in `workflow/graph.py`:
```python
workflow.add_node("my_new_node", my_new_node)
workflow.add_edge("previous_node", "my_new_node")
```

3. **Update state schema** if needed in `workflow/state.py`:
```python
class SupervisorState(TypedDict):
    # ... existing fields ...
    my_new_field: Optional[str]
```

4. **Write tests** in `tests/unit/test_workflow_nodes.py`:
```python
@pytest.mark.asyncio
async def test_my_new_node():
    state = {
        "workflow_id": "test-123",
        "audit_log": []
    }
    result = await my_new_node(state)
    assert result["status"] == WorkflowStatus.EXECUTING
```

### Adding a New API Endpoint

1. **Create route** in `api/routes/`:
```python
from fastapi import APIRouter, HTTPException
from info_agent.api.models.requests import MyRequest
from info_agent.api.models.responses import MyResponse

router = APIRouter(prefix="/api/my-resource", tags=["my-resource"])

@router.post("/", response_model=MyResponse)
async def create_resource(request: MyRequest):
    """Create a new resource."""
    # Implementation
    return MyResponse(...)
```

2. **Include router** in `main.py`:
```python
from info_agent.api.routes.my_resource import router as my_resource_router

app.include_router(my_resource_router)
```

3. **Write tests** in `tests/unit/test_api_routes_my_resource.py`:
```python
@pytest.mark.asyncio
async def test_create_resource(test_client):
    response = await test_client.post(
        "/api/my-resource",
        json={"field": "value"}
    )
    assert response.status_code == 200
```

### Adding a New Agent

1. **Create agent directory** in `agents/`:
```
agents/
└── my_agent/
    ├── __init__.py
    ├── agent.py      # FastAPI A2A server
    ├── skills.py     # Skill implementations
    └── state.py      # Agent state schema
```

2. **Implement A2A server** in `agent.py`:
```python
from fastapi import FastAPI
from info_agent.a2a.models import AgentCard, Skill

app = FastAPI(title="My Agent")

AGENT_CARD = AgentCard(
    name="my-agent",
    description="My agent description",
    version="1.0.0",
    url="http://localhost:8002",
    skills=[
        Skill(
            id="my-skill",
            name="My Skill",
            description="Skill description"
        )
    ]
)

@app.get("/.well-known/agent.json")
async def get_agent_card():
    return AGENT_CARD

@app.post("/a2a/tasks")
async def handle_task(request: A2ATaskRequest):
    # Handle tasks
    pass
```

3. **Register with A2A Registry** on startup
4. **Write comprehensive tests**

### Working with LLM

```python
from info_agent.llm import get_gemini_llm
from info_agent.utils.exceptions import LLMError

async def my_llm_function():
    try:
        llm = get_gemini_llm()

        prompt = """
        System instructions here.

        User input: {user_input}
        """

        response = await llm.ainvoke(prompt)
        return response.content

    except LLMError as e:
        logger.error(f"LLM error: {e.message}", details=e.details)
        raise
```

---

## Anti-Patterns to Avoid

### 1. DON'T Modify .env File Programmatically
```python
# BAD - Never write to .env
with open(".env", "w") as f:
    f.write(f"API_KEY={key}")

# GOOD - Use environment variables or settings
os.environ["API_KEY"] = key
```

### 2. DON'T Create Files Over 800 Lines
Break large files into smaller modules:
```python
# BAD - 1200 line file
# workflow/all_nodes.py (1200 lines)

# GOOD - Split by responsibility
# workflow/nodes/parsing.py (200 lines)
# workflow/nodes/planning.py (250 lines)
# workflow/nodes/execution.py (180 lines)
```

### 3. DON'T Use Fallback/Default Values for Critical Config
```python
# BAD - Silent failure
api_key = settings.google_api_key or "default-key"

# GOOD - Fail fast
if not settings.google_api_key:
    raise ConfigurationError("GOOGLE_API_KEY is required")
```

### 4. DON'T Skip Logging
```python
# BAD - No logging
def process_data(data):
    result = complex_operation(data)
    return result

# GOOD - Comprehensive logging
def process_data(data):
    logger.info(f"Processing data of size {len(data)}")
    try:
        result = complex_operation(data)
        logger.info(f"Processing completed, result size: {len(result)}")
        return result
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise
```

### 5. DON'T Test Against Real APIs in Unit Tests
```python
# BAD - Real API call
@pytest.mark.asyncio
async def test_llm():
    llm = get_gemini_llm()
    response = await llm.ainvoke("test")  # Real API call

# GOOD - Mock external dependencies
@pytest.mark.asyncio
async def test_llm(mock_gemini):
    llm = get_gemini_llm()
    response = await llm.ainvoke("test")
    mock_gemini.assert_called_once()
```

---

## Important Constraints

### File Size Limits
- **Maximum lines per file**: 800 lines
- **Recommended function size**: 30-50 lines
- **Maximum function size**: 80 lines
- **Recommended class size**: 200-300 lines

### Error Handling Philosophy
- **Fail fast**: Raise exceptions for invalid configuration or states
- **No silent failures**: Always log errors
- **No default fallbacks**: Require explicit configuration
- **Comprehensive logging**: Log at all key points

### Testing Requirements
- **Test-driven development**: Write tests before/with code
- **Mock external dependencies**: Never call real APIs in tests
- **High coverage target**: Aim for >85% code coverage
- **Test all edge cases**: Success, failure, timeout, invalid input

### Data Persistence
- **All state persisted**: LangGraph checkpoints in SQLite
- **Resume after restart**: Workflows can be resumed
- **Audit trails**: All actions logged to audit_log
- **No in-memory-only state**: Everything must be recoverable

### Development Workflow
- **Keep root clean**: Use `scripts/` for temporary scripts
- **Test data in `test_data/`**: All test inputs centralized
- **Outputs in `resources/reports/`**: Generated reports/outputs
- **Never commit data/**: Runtime data is gitignored

---

## Testing Strategy

### Test Coverage

**Current Status** (as of latest run):
- **Total tests**: 996
- **Passing**: 911 (91.5%)
- **Failed**: 64 (6.4%)
- **Errors**: 21 (2.1%)

### Test Organization

```
tests/
├── conftest.py                     # Shared fixtures
├── unit/                           # Unit tests (fast, isolated)
│   ├── test_a2a_*.py               # A2A protocol tests
│   ├── test_api_*.py               # API endpoint tests
│   ├── test_email_*.py             # Email system tests
│   ├── test_llm.py                 # LLM integration tests
│   ├── test_mail_agent*.py         # Mail agent tests
│   ├── test_supervisor_*.py        # Supervisor tests
│   └── test_workflow_*.py          # Workflow tests
└── integration/                    # Integration tests (slower, multi-component)
    ├── test_a2a_protocol.py
    ├── test_api_gateway.py
    ├── test_email_system.py
    └── test_workflow_execution.py
```

### Fixtures (conftest.py)

Key fixtures available:
- `test_client`: AsyncClient for API testing
- `mock_llm`: Mocked LLM for testing
- `mock_registry`: Mocked A2A registry
- `temp_db`: Temporary SQLite database
- `sample_workflow_state`: Pre-populated workflow state

### Writing Tests

**Unit Test Example**:
```python
import pytest
from info_agent.workflow.nodes import parse_instructions

@pytest.mark.asyncio
async def test_parse_instructions(mock_llm):
    state = {
        "workflow_id": "test-123",
        "instructions": "Send email to john@example.com",
        "audit_log": []
    }

    result = await parse_instructions(state)

    assert result["target_email"] == "john@example.com"
    assert "audit_log" in result
```

**Integration Test Example**:
```python
import pytest
from httpx import AsyncClient
from info_agent.main import app

@pytest.mark.asyncio
async def test_create_workflow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/workflows",
            json={"name": "Test", "description": "Test workflow"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test"
```

---

## Troubleshooting

### Common Issues

#### 1. "GOOGLE_API_KEY is required"
**Cause**: Missing or invalid API key in `.env`

**Solution**:
```bash
# Get API key from https://aistudio.google.com/apikey
echo "GOOGLE_API_KEY=your-actual-key" >> .env
```

#### 2. "Port already in use"
**Cause**: Service already running on port

**Solution**:
```bash
# Find process using port
lsof -i :8000  # or :8001, :8025, :1025

# Kill process
kill -9 <PID>
```

#### 3. "Database locked"
**Cause**: Multiple processes accessing SQLite database

**Solution**:
```bash
# Stop all services
pkill -f "python scripts/run"

# Delete lock file
rm data/*.db-shm data/*.db-wal

# Restart services
python scripts/run_all_services.py
```

#### 4. Tests failing with "Agent not found"
**Cause**: A2A registry not properly initialized in test

**Solution**:
```python
# Use proper fixtures
@pytest.mark.asyncio
async def test_my_feature(mock_registry):
    # mock_registry fixture handles initialization
    pass
```

#### 5. "Module not found" errors
**Cause**: Package not installed in editable mode

**Solution**:
```bash
# Reinstall in editable mode
pip install -e .
```

---

## Production Readiness Checklist

**Phase 1 (Current) - MVP Backend**: ✅ Complete

**Phase 2 (Future) - Full Backend**:
- [ ] Validation Agent implementation
- [ ] Clarification/FAQ matching
- [ ] Escalation and timeout handling
- [ ] Multi-provider LLM support
- [ ] Advanced error handling and retry logic

**Phase 3 (Future) - MVP UI**:
- [ ] Frontend dashboard
- [ ] Real-time workflow monitoring
- [ ] Email inbox UI

**Phase 4 (Future) - Full UI**:
- [ ] Advanced analytics
- [ ] Configuration UI
- [ ] User management

---

## Key Files Reference

| File | Purpose | When to Modify |
|------|---------|----------------|
| `config.py` | Application settings | Adding new configuration options |
| `main.py` | FastAPI Gateway entry | Adding new routers, middleware |
| `workflow/graph.py` | Workflow graph definition | Adding/modifying workflow nodes |
| `workflow/nodes.py` | Node implementations | Implementing new workflow steps |
| `agents/supervisor/planner.py` | LLM plan generation | Changing planning logic |
| `agents/mail/composer.py` | Email composition | Modifying email templates |
| `a2a/registry.py` | Agent registry | Changing agent discovery |
| `llm/factory.py` | LLM instance management | Adding new LLM providers |
| `.env.example` | Configuration template | Adding new env variables |
| `pyproject.toml` | Dependencies & metadata | Adding dependencies |

---

## Dependencies

### Core Dependencies
- `fastapi` (0.104+): Web framework for APIs
- `uvicorn` (0.24+): ASGI server
- `pydantic` (2.0+): Data validation
- `langchain` (0.3+): LLM framework
- `langchain-google-genai` (2.0+): Gemini integration
- `langgraph` (0.2+): Workflow orchestration
- `langgraph-checkpoint-sqlite` (2.0+): State persistence
- `a2a-sdk` (0.3+): A2A protocol
- `httpx` (0.25+): Async HTTP client
- `aiosmtpd` (1.4+): SMTP server
- `aiosmtplib` (3.0+): SMTP client
- `aiosqlite` (0.19+): Async SQLite
- `structlog` (23.0+): Structured logging

### Dev Dependencies
- `pytest` (7.0+): Testing framework
- `pytest-asyncio` (0.23+): Async test support
- `pytest-cov` (4.0+): Coverage reporting
- `pytest-mock` (3.12+): Mocking support
- `ruff` (0.1+): Linting

See `pyproject.toml` for complete list with version constraints.

---

## Contributing Guidelines

### Code Style
- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use descriptive variable names

### Commit Messages
- Use conventional commits format
- Include scope: `feat(workflow): add timeout handling`
- Keep first line under 72 characters

### Pull Requests
- Write comprehensive tests
- Update documentation
- Ensure all tests pass
- Keep PRs focused (single feature/fix)

### Documentation
- Update CLAUDE.md for architecture changes
- Update README.md for user-facing changes
- Add docstrings to all functions/classes
- Include usage examples

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-13 | Initial documentation for Phase 1 MVP Backend completion |

---

## Additional Resources

- **Architecture Documents**: `.dev-resources/architecture/`
- **Research Materials**: `resources/research/`
- **LLM Module Docs**: `src/info_agent/llm/README.md`
- **Test Data**: `test_data/`
- **Scripts**: `scripts/`
