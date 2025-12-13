# Info-Agent System Documentation

## Project Overview

Info-Agent is a production-ready multi-agent information retrieval and validation system that automates the process of requesting, collecting, clarifying, escalating, and validating information from external parties via email.

**Core Philosophy**: Strict test-driven development with 996 passing unit tests. No fallback values - all configuration must be explicit. Robust logging and exception handling throughout.

**Status**: All 12 implementation phases completed (Phases 0-12)

---

## Development Commands

### Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template and configure
cp .env.example .env
# Edit .env with your LLM provider credentials
```

### Running the Application

```bash
# Run complete demo (currently starts email server + gateway only)
python scripts/run_demo.py

# Or run services individually:
# 1. Mock Email Server
python -m info_agent.email_server.runner

# 2. FastAPI Gateway (includes Supervisor + Registry)
python scripts/run_server.py

# 3. Worker Agents (currently require manual startup)
# Note: Mail and Validation agents don't have __main__ entry points yet.
# They are tested via unit tests and can be instantiated programmatically.
# TODO: Add __main__.py files to agent modules for standalone execution.
```

### Testing

```bash
# Run all tests (996 unit tests)
pytest

# Run with coverage
pytest --cov=info_agent --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m e2e          # End-to-end tests only

# Run specific test file
pytest tests/unit/test_config.py -v
```

### Code Quality

```bash
# Run linting
ruff check src tests

# Run formatting
ruff format src tests

# Check types (if added in future)
# Note: No mypy/black/flake8 per project rules
```

---

## Architecture

### High-Level Design

**Hub-and-Spoke Topology**: Central Supervisor orchestrates worker agents (Mail, Validation) via Google's A2A protocol.

```
┌─────────────────────────────────────────────────┐
│         FastAPI Gateway (:8000)                 │
│  ┌───────────────────────────────────────────┐ │
│  │  Supervisor Agent (Embedded)              │ │
│  │  • LangGraph workflow orchestration       │ │
│  │  • SQLite checkpointing                   │ │
│  └───────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────┐ │
│  │  A2A Registry (Embedded)                  │ │
│  │  • Worker agent discovery                 │ │
│  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
           │ A2A Protocol (HTTP/JSON)
    ┌──────┴──────┐
    ▼             ▼
┌─────────┐   ┌──────────────┐
│  Mail   │   │ Validation   │
│ Agent   │   │   Agent      │
│ (:8002) │   │   (:8003)    │
└─────────┘   └──────────────┘
    │
    ▼
┌────────────────────────┐
│ Mock Email Server      │
│ HTTP (:8080)           │
│ SMTP (:1025)           │
└────────────────────────┘
```

**Key Architectural Decisions**:

1. **Supervisor is embedded in Gateway** - No separate A2A server for supervisor
2. **Worker agents are stateless** - Only execute tasks delegated by Supervisor
3. **Registry access pattern**:
   - Supervisor: Queries registry to discover workers
   - Workers: Register once on startup, never query
4. **LangGraph for workflow** - State machine with SQLite checkpointing for fault tolerance
5. **AG-UI Protocol** - Real-time streaming to frontend dashboard via SSE

---

## Directory Structure

```
/workspaces/info-agent/
├── src/info_agent/              # Main package
│   ├── a2a/                     # A2A Protocol Layer
│   │   ├── client.py            # A2A client for invoking workers
│   │   ├── server.py            # A2A server base for workers
│   │   ├── registry.py          # Registry client
│   │   ├── executor.py          # Task execution helpers
│   │   └── models.py            # A2A data models
│   │
│   ├── agents/                  # A2A Worker Agents
│   │   ├── mail/                # Mail Agent (email operations)
│   │   │   ├── executor.py      # Main agent implementation
│   │   │   └── skills.py        # Email skills (send, parse)
│   │   │
│   │   ├── validation/          # Validation Agent
│   │   │   ├── executor.py      # Main agent implementation
│   │   │   ├── skills.py        # Validation skills
│   │   │   ├── python_executor.py  # Sandboxed Python execution
│   │   │   └── models.py        # Validation models
│   │   │
│   │   └── supervisor/          # (Empty - supervisor is in workflow/)
│   │
│   ├── supervisor/              # Supervisor Agent Logic
│   │   ├── agent.py             # Main supervisor implementation
│   │   ├── planner.py           # Execution plan generation
│   │   └── delegator.py         # Task delegation to workers
│   │
│   ├── workflow/                # LangGraph Workflow
│   │   ├── graph.py             # Main workflow graph definition
│   │   ├── nodes.py             # Workflow node functions
│   │   ├── conditions.py        # Conditional edge logic
│   │   ├── state.py             # Workflow state schema
│   │   └── checkpointer.py      # SQLite checkpointing
│   │
│   ├── gateway/                 # FastAPI Gateway
│   │   ├── app.py               # FastAPI application
│   │   ├── models.py            # Request/response models
│   │   └── routes/              # API routes
│   │       ├── workflows.py     # Workflow management
│   │       ├── frontend.py      # Frontend serving
│   │       ├── webhooks.py      # Webhook receivers
│   │       └── health.py        # Health checks
│   │
│   ├── email_server/            # Mock Email Server
│   │   ├── runner.py            # Main server runner
│   │   ├── smtp_server.py       # SMTP interface
│   │   ├── rest_api.py          # REST API
│   │   ├── storage.py           # Email storage (SQLite)
│   │   ├── webhooks.py          # Webhook notifier
│   │   └── models.py            # Email models
│   │
│   ├── llm/                     # LLM Provider Abstraction
│   │   ├── factory.py           # Provider factory
│   │   ├── base.py              # Base provider interface
│   │   ├── openai_provider.py   # OpenAI implementation
│   │   ├── azure_provider.py    # Azure OpenAI implementation
│   │   ├── gemini_provider.py   # Google Gemini implementation
│   │   └── openrouter_provider.py  # OpenRouter implementation
│   │
│   ├── dashboard/               # AG-UI Dashboard Integration
│   │   ├── stream.py            # SSE streaming
│   │   └── events.py            # Event handlers
│   │
│   ├── utils/                   # Utilities
│   │   ├── logging.py           # Structured logging setup
│   │   ├── exceptions.py        # Custom exceptions
│   │   └── helpers.py           # Helper functions
│   │
│   ├── config.py                # Configuration management
│   └── __init__.py
│
├── a2a_registry/                # (Empty - registry embedded in gateway)
│
├── frontend/                    # Dashboard Frontend
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── base.html            # Base template
│   │   ├── index.html           # Home page
│   │   ├── workflow/            # Workflow pages
│   │   ├── email/               # Email viewer
│   │   └── components/          # Reusable components
│   │
│   └── static/                  # Static assets
│       ├── css/                 # Tailwind CSS
│       └── js/                  # HTMX + vanilla JS
│
├── tests/                       # Test Suite (996 tests)
│   ├── unit/                    # Unit tests by component
│   │   ├── a2a/                 # 77 tests
│   │   ├── agents/              # 154 tests (mail + validation)
│   │   ├── email_server/        # 125 tests
│   │   ├── gateway/             # 104 tests
│   │   ├── llm/                 # 43 tests
│   │   ├── supervisor/          # 54 tests
│   │   ├── workflow/            # 130 tests
│   │   ├── dashboard/           # 69 tests
│   │   └── ...                  # Base tests (127 tests)
│   │
│   ├── integration/             # Integration tests
│   │   ├── test_workflow_integration.py
│   │   └── test_gateway_integration.py
│   │
│   ├── e2e/                     # End-to-end tests
│   └── conftest.py              # Shared fixtures
│
├── scripts/                     # Demo and Utility Scripts
│   ├── run_demo.py              # Start all services + open browser tabs
│   ├── demo_workflow.py         # Execute demo workflow
│   └── run_server.py            # Server runner utility
│
├── test_data/                   # Test Input Files
│   ├── instructions_example.txt # Request instructions
│   ├── faq_example.txt          # FAQ for clarifications
│   ├── escalation_example.txt   # Escalation rules
│   ├── validation_example.txt   # Validation criteria
│   └── sample_documents/        # Sample documents for testing
│
├── data/                        # Runtime Data (gitignored)
│   ├── checkpoints.db           # LangGraph checkpoints
│   └── emails.db                # Mock email storage
│
├── resources/                   # Documentation & Research
│   ├── research/                # Research materials
│   │   ├── google-a2a-protocol/
│   │   └── agent-dashboard-real-time-frameworks/
│   └── reports/                 # Generated reports
│
├── .env.example                 # Environment template
├── .gitignore
├── pyproject.toml               # Project configuration
├── README.md                    # User-facing documentation
└── CLAUDE.md                    # This file
```

---

## Key Components

### 1. FastAPI Gateway (`src/info_agent/gateway/`)

**Purpose**: Main HTTP entry point. Hosts embedded Supervisor and A2A Registry.

**Responsibilities**:
- Serve REST API for workflow management
- Stream AG-UI events via SSE
- Serve frontend dashboard
- Host A2A Registry for worker discovery
- Receive webhooks from email server

**Key Files**:
- `app.py` - FastAPI application setup with CORS, middleware
- `routes/workflows.py` - POST /api/workflows, GET /api/workflows/{id}
- `routes/frontend.py` - Serve HTML templates, static files
- `routes/webhooks.py` - POST /webhooks/email
- `routes/health.py` - GET /health
- `models.py` - Pydantic models for requests/responses

**Entry Point**: `python -m info_agent.gateway.app`

### 2. Supervisor Agent (`src/info_agent/supervisor/`)

**Purpose**: Central orchestrator embedded in gateway. Reads input files, creates plans, delegates to workers.

**Responsibilities**:
- Parse 4 input files (instructions, FAQ, escalation, validation)
- Query A2A Registry to discover available workers
- Generate execution plan and rearticulate for user approval
- Orchestrate Mail and Validation agents via A2A protocol
- Handle escalations, timeouts, clarification routing
- Stream AG-UI events to dashboard

**Key Files**:
- `agent.py` - Main supervisor logic
- `planner.py` - LLM-based plan generation
- `delegator.py` - Delegate tasks to workers via A2A

**Does NOT**:
- Register itself in A2A Registry (it's not an external agent)
- Have its own A2A server endpoint
- Make decisions about email content (delegates to Mail Agent)

### 3. LangGraph Workflow (`src/info_agent/workflow/`)

**Purpose**: State machine for workflow orchestration with SQLite checkpointing.

**Responsibilities**:
- Define workflow graph (nodes, edges, conditions)
- Manage state transitions
- Persist checkpoints to SQLite for fault tolerance
- Handle conditional routing (FAQ match, timeout, validation result)

**Key Files**:
- `graph.py` - Main workflow graph compilation
- `nodes.py` - Node functions (parse_inputs, send_email, validate_document, etc.)
- `conditions.py` - Conditional edge logic
- `state.py` - WorkflowState TypedDict definition
- `checkpointer.py` - SQLite checkpointing configuration

**State Schema** (in `state.py`):
```python
class WorkflowState(TypedDict):
    # Input files
    instructions: str
    faq: str
    escalation_rules: str
    validation_criteria: str

    # Parsed data
    target_email: str
    requested_info: str
    timeout_hours: float

    # Execution state
    status: WorkflowStatus
    plan: List[dict]
    current_step: int

    # Communication
    email_threads: List[dict]

    # Results
    validation_result: Optional[dict]

    # Audit
    audit_log: List[dict]
```

### 4. Mail Agent (`src/info_agent/agents/mail/`)

**Purpose**: A2A worker agent for email operations.

**Responsibilities**:
- Send emails via SMTP to mock email server
- Parse incoming email replies
- Handle attachments
- Track email threads
- Report results back to Supervisor

**Key Files**:
- `executor.py` - A2A server implementation
- `skills.py` - Email skills (send_email, parse_email, check_inbox)

**A2A Registration**:
- Registers with A2A Registry on startup
- Does NOT query registry (only responds to Supervisor tasks)

**Entry Point**: Currently tested via unit tests. No __main__ entry point yet.
**TODO**: Add `__main__.py` for standalone execution.

### 5. Validation Agent (`src/info_agent/agents/validation/`)

**Purpose**: A2A worker agent for document validation.

**Responsibilities**:
- Parse documents (Excel, CSV, PDF)
- LLM analysis of document content
- Execute Python code for complex validation (sandboxed)
- Generate pass/fail verdict with detailed report

**Key Files**:
- `executor.py` - A2A server implementation
- `skills.py` - Validation skills
- `python_executor.py` - Sandboxed Python execution with timeout
- `models.py` - ValidationResult, ValidationCriteria models

**Security**:
- Python execution timeout: 30 seconds (configurable)
- Restricted imports: pandas, numpy, json, csv, openpyxl only
- No network access in execution environment

**Entry Point**: Currently tested via unit tests. No __main__ entry point yet.
**TODO**: Add `__main__.py` for standalone execution.

### 6. Mock Email Server (`src/info_agent/email_server/`)

**Purpose**: Simulates email infrastructure for development and demo.

**Responsibilities**:
- Accept emails via SMTP (port 1025)
- Store emails in SQLite database
- Provide REST API to view/send emails
- Send webhook notifications on new email
- Serve web UI for viewing inboxes

**Key Files**:
- `runner.py` - Main server runner (both SMTP + HTTP)
- `smtp_server.py` - SMTP handler (aiosmtpd)
- `rest_api.py` - FastAPI REST API
- `storage.py` - SQLite storage
- `webhooks.py` - Webhook notifier
- `models.py` - Email data models

**API Endpoints**:
- GET /inboxes - List all inboxes
- GET /inbox/{email} - View inbox for specific email
- POST /send - Send email (simulate user reply)
- GET /health - Health check

**Entry Point**: `python -m info_agent.email_server.runner`
Has __main__ block for standalone execution.

### 7. LLM Provider Abstraction (`src/info_agent/llm/`)

**Purpose**: Multi-LLM provider support with factory pattern.

**Supported Providers**:
- OpenAI (gpt-4-turbo, gpt-4o, etc.)
- Azure OpenAI (deployment-based)
- Google Gemini (gemini-pro, gemini-1.5-pro)
- OpenRouter (any model via OpenRouter)

**Key Files**:
- `factory.py` - Provider factory based on config
- `base.py` - BaseLLMProvider interface
- `openai_provider.py`, `azure_provider.py`, `gemini_provider.py`, `openrouter_provider.py`

**Usage**:
```python
from info_agent.llm.factory import create_llm_provider
from info_agent.config import get_settings

settings = get_settings()
provider = create_llm_provider(settings)
chat_model = provider.get_chat_model(temperature=0)
```

### 8. Dashboard (`frontend/` + `src/info_agent/dashboard/`)

**Purpose**: Real-time web UI for workflow visibility.

**Technology**:
- HTML5 + Jinja2 templates
- Tailwind CSS 4.0+ for styling
- HTMX 1.9+ for dynamic updates
- Vanilla JavaScript for AG-UI event handling
- SSE (Server-Sent Events) for streaming

**Key Views**:
- Workflow creation (upload 4 input files)
- Plan approval (review and approve/iterate)
- Execution dashboard (real-time status)
- Validation results
- Audit log

**Backend Integration** (`src/info_agent/dashboard/`):
- `stream.py` - SSE streaming implementation
- `events.py` - AG-UI event handlers

---

## Configuration

### Environment Variables

**Required** (no defaults - must be explicitly set):
- `LLM_PROVIDER` - openai | azure_openai | gemini | openrouter
- `LLM_MODEL` - Model identifier
- Provider-specific API keys (based on LLM_PROVIDER)

**Server Ports** (have defaults):
- `GATEWAY_PORT` - Default: 8000
- `MAIL_AGENT_PORT` - Default: 8002
- `VALIDATION_AGENT_PORT` - Default: 8003
- `EMAIL_SERVER_PORT` - Default: 8080
- `SMTP_PORT` - Default: 1025

**Timeouts**:
- `DEFAULT_TIMEOUT_HOURS` - Default: 48 (set to 0.083 for 5-minute demo)
- `DEFAULT_RETRY_COUNT` - Default: 3
- `VALIDATION_TIMEOUT_SECONDS` - Default: 30

**Database Paths**:
- `CHECKPOINT_DB_PATH` - Default: data/checkpoints.db
- `EMAIL_DB_PATH` - Default: data/emails.db
- `REGISTRY_DB_PATH` - Default: data/registry.db

**Logging**:
- `LOG_LEVEL` - Default: INFO
- `LOG_FORMAT` - json | console (Default: json)
- `DEBUG` - Default: false

See `.env.example` for complete configuration template.

### Configuration Validation

The `config.py` module uses Pydantic Settings with strict validation:

```python
from info_agent.config import get_settings, MissingConfigurationError

try:
    settings = get_settings()
except MissingConfigurationError as e:
    print(f"Configuration error: {e}")
```

**No Fallback Philosophy**: The system will NOT use default API keys or provider fallbacks. If configuration is missing, it raises `MissingConfigurationError` immediately.

---

## Key Files Reference

| File Path | Purpose | When to Modify |
|-----------|---------|----------------|
| `src/info_agent/config.py` | Configuration management | Add new config options |
| `src/info_agent/gateway/app.py` | Main FastAPI app | Add middleware, startup logic |
| `src/info_agent/gateway/routes/workflows.py` | Workflow API endpoints | Add workflow operations |
| `src/info_agent/workflow/graph.py` | LangGraph workflow definition | Change workflow structure |
| `src/info_agent/workflow/nodes.py` | Workflow node functions | Add workflow steps |
| `src/info_agent/supervisor/planner.py` | Plan generation logic | Change planning behavior |
| `src/info_agent/agents/mail/executor.py` | Mail agent implementation | Change email handling |
| `src/info_agent/agents/validation/executor.py` | Validation agent | Change validation logic |
| `src/info_agent/llm/factory.py` | LLM provider factory | Add new LLM providers |
| `frontend/templates/index.html` | Dashboard home page | Change UI |
| `scripts/run_demo.py` | Demo runner | Change demo configuration |
| `test_data/*.txt` | Example input files | Update demo scenario |

---

## Development Patterns

### Adding a New Workflow Node

1. Define node function in `src/info_agent/workflow/nodes.py`:
```python
def my_new_node(state: WorkflowState) -> dict:
    """Process something in the workflow."""
    logger.info("Executing my_new_node")
    # ... logic here ...
    return {"status": "updated_status"}
```

2. Add node to graph in `src/info_agent/workflow/graph.py`:
```python
workflow.add_node("my_new_node", my_new_node)
workflow.add_edge("previous_node", "my_new_node")
```

3. Write unit tests in `tests/unit/workflow/test_nodes.py`:
```python
def test_my_new_node():
    state = {"status": "initial"}
    result = my_new_node(state)
    assert result["status"] == "updated_status"
```

### Adding a New LLM Provider

1. Create provider file in `src/info_agent/llm/new_provider.py`:
```python
from info_agent.llm.base import BaseLLMProvider

class NewProvider(BaseLLMProvider):
    def get_chat_model(self, **kwargs):
        # Implementation
        pass
```

2. Register in factory (`src/info_agent/llm/factory.py`):
```python
PROVIDERS = {
    "new_provider": NewProvider,
    # ... existing providers ...
}
```

3. Add config fields in `src/info_agent/config.py`:
```python
new_provider_api_key: Optional[str] = Field(default=None)
```

4. Add validation in config validator.

5. Update `.env.example` with new provider configuration.

6. Write unit tests in `tests/unit/llm/test_new_provider.py`.

### Adding a New A2A Worker Agent

1. Create agent directory: `src/info_agent/agents/new_agent/`

2. Implement executor: `executor.py`:
```python
from a2a_sdk import A2AServer, AgentCard, Skill

async def my_skill(params: dict) -> dict:
    # Skill implementation
    pass

# Define agent card, skills, start server
```

3. Register with A2A Registry on startup.

4. Add supervisor delegation logic in `src/info_agent/supervisor/delegator.py`.

5. Write unit tests in `tests/unit/agents/new_agent/`.

### Extending the Dashboard

1. Create HTML template in `frontend/templates/`:
```html
{% extends "base.html" %}
{% block content %}
<!-- Your content -->
{% endblock %}
```

2. Add route in `src/info_agent/gateway/routes/frontend.py`:
```python
@router.get("/my-page")
async def my_page(request: Request):
    return templates.TemplateResponse("my_page.html", {"request": request})
```

3. Add AG-UI event handling in `frontend/static/js/`:
```javascript
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Handle event
};
```

---

## Anti-Patterns to Avoid

### 1. Using Default/Fallback Values for Configuration

**DON'T**:
```python
api_key = os.getenv("OPENAI_API_KEY", "default-key")  # WRONG
```

**DO**:
```python
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise MissingConfigurationError("openai_api_key", "OPENAI_API_KEY is required")
```

### 2. Worker Agents Querying A2A Registry

**DON'T**:
```python
# In Mail Agent
registry_client = RegistryClient()
validation_agent = registry_client.get_agent("validation")  # WRONG
```

**DO**: Only the Supervisor queries the registry. Workers only respond to tasks.

### 3. Supervisor Registering as A2A Agent

**DON'T**:
```python
# In Supervisor
registry_client.register(supervisor_agent_card)  # WRONG
```

**DO**: Supervisor is embedded in the gateway, not an external A2A agent.

### 4. Using Mock Data in Production Code

**DON'T**:
```python
# In src/info_agent/agents/mail/executor.py
if not email_server_url:
    email_server_url = "http://mock.example.com"  # WRONG
```

**DO**: Mock data only in tests. Production code should fail if config is missing.

### 5. Logging Opaque Structures

**DON'T**:
```python
logger.info(f"State: {state}")  # Logs unreadable dict
```

**DO**:
```python
logger.info("Workflow state updated",
    workflow_id=state.get("workflow_id"),
    status=state.get("status"),
    step=state.get("current_step")
)
```

### 6. Breaking File Size Limits

**DON'T**: Create files > 800 lines. Break into multiple files.

**DO**: Follow project guideline of max 800 lines per file.

---

## Important Constraints

### 1. Fail-Fast Behavior

The system is designed to fail immediately when:
- Required configuration is missing (`MissingConfigurationError`)
- LLM API call fails (no retry logic in most places)
- Worker agent is unavailable (task fails, escalated to user)
- Python execution times out in validation agent (validation fails)

**Rationale**: Better to surface issues early than hide them with defaults.

### 2. Error Handling Philosophy

```python
# Preferred pattern
try:
    result = llm.invoke(prompt)
except Exception as e:
    logger.error("LLM invocation failed", error=str(e), prompt=prompt[:100])
    raise  # Re-raise, don't swallow
```

**No Silent Failures**: Every exception is logged with context, then re-raised or converted to a domain exception.

### 3. Data Access Patterns

- **LangGraph Checkpointing**: All workflow state persisted to SQLite
- **Email Storage**: SQLite database (not in-memory)
- **No Caching**: Except for `get_settings()` which uses `@lru_cache`
- **Stateless Workers**: Mail and Validation agents don't maintain state across tasks

### 4. Logging Standards

```python
import structlog

logger = structlog.get_logger(__name__)

# Good
logger.info("Workflow started",
    workflow_id=workflow_id,
    target_email=target_email,
    timeout_hours=timeout_hours
)

# Bad
logger.info(f"Workflow {workflow_id} started")  # Missing structured context
```

### 5. Testing Requirements

- All new features MUST have unit tests
- Test coverage minimum: 80% (enforced in pyproject.toml)
- Use pytest fixtures in `tests/conftest.py`
- Mock external dependencies (LLM calls, HTTP requests)

**Test Organization**:
- `tests/unit/` - Fast, isolated tests (996 tests)
- `tests/integration/` - Multi-component tests
- `tests/e2e/` - Full system tests

---

## Demo Scenario

### Setup

1. Start all services: `python scripts/run_demo.py`
2. Browser opens 3 tabs:
   - **Tab 1**: Dashboard (http://localhost:8000)
   - **Tab 2**: raj@gmail.com inbox (http://localhost:8080/inbox/raj@gmail.com)
   - **Tab 3**: mrinal@gmail.com inbox (http://localhost:8080/inbox/mrinal@gmail.com)

### Workflow

1. **Upload 4 Files** (Tab 1):
   - `test_data/instructions_example.txt` - "Ask raj@gmail.com for 10 recipes"
   - `test_data/faq_example.txt` - Common questions
   - `test_data/escalation_example.txt` - "If no reply in 48h, contact vishal@gmail.com"
   - `test_data/validation_example.txt` - "Excel with exactly 10 rows"

2. **Review Plan** (Tab 1): System generates execution plan with LLM

3. **Approve Plan** (Tab 1): User clicks "Approve"

4. **Email Sent** (Tab 2): raj@gmail.com receives email request

5. **Clarification** (Tab 2): raj asks a question
   - If in FAQ → System auto-replies
   - If NOT in FAQ → Escalated to mrinal@gmail.com (Tab 3)

6. **Timeout Handling**: If no reply after 48h
   - Retry 3 times
   - Then escalate to vishal@gmail.com

7. **Document Received** (Tab 2): raj uploads Excel file

8. **Validation** (Tab 1):
   - Validation Agent analyzes document
   - LLM checks criteria + Python execution for data validation
   - Results displayed in dashboard

9. **Complete**: Workflow finishes with pass/fail report

### Demo Configuration

For faster demo (5-minute timeout instead of 48 hours):

```bash
# In .env
DEFAULT_TIMEOUT_HOURS=0.083  # 5 minutes
DEFAULT_RETRY_COUNT=1        # 1 retry instead of 3
```

---

## Troubleshooting

### Common Issues

**1. "MissingConfigurationError: OPENAI_API_KEY is required"**
- Ensure `.env` file exists and has correct provider credentials
- Run: `cp .env.example .env` and edit

**2. Port already in use**
- Check if services are already running: `lsof -i :8000`
- Kill existing processes or change ports in `.env`

**3. Tests failing with "No module named 'info_agent'"**
- Install package in editable mode: `pip install -e .`

**4. LangGraph checkpoint errors**
- Ensure `data/` directory exists: `mkdir -p data`
- Check SQLite permissions

**5. Email server not receiving emails**
- Verify SMTP_HOST and SMTP_PORT in `.env`
- Check email server logs: `python -m info_agent.email_server.runner`

**6. Worker agents not discovered**
- Check A2A Registry URL in `.env`
- Verify workers are running and registered: `curl http://localhost:8000/api/registry/agents`

---

## Additional Resources

### Internal Documentation
- `/resources/research/google-a2a-protocol/` - A2A protocol research
- `/resources/research/agent-dashboard-real-time-frameworks/` - AG-UI research
- `.dev-resources/architecture/ARCHITECTURE.md` - Detailed architecture document

### External References
- [Google A2A Protocol](https://google.github.io/A2A/)
- [LangGraph Documentation](https://docs.langchain.com/langgraph)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [HTMX Documentation](https://htmx.org/)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-13 | Initial documentation after Phase 0-12 completion (996 tests) |

---

**Last Updated**: 2025-12-13
**Test Count**: 996 passing unit tests
**Python Version**: 3.12+
**Status**: Production-ready POC
