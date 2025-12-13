# Info-Agent

A multi-agent information retrieval and validation system that automates the process of requesting, collecting, clarifying, escalating, and validating information from external parties via email.

## Overview

Info-Agent enables end users to automate information collection workflows:

1. **Send email requests** to target recipients
2. **Handle clarifications** using pre-defined FAQ or escalate to the end user
3. **Escalate unresponsive requests** after configurable timeouts
4. **Validate received documents** against specified criteria
5. **Provide real-time visibility** via a dashboard

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FASTAPI GATEWAY (:8000)                          │
│   ┌───────────────────────────────────────────────────────────┐    │
│   │              SUPERVISOR AGENT (Embedded)                   │    │
│   │    • LangGraph workflow with SQLite checkpointing         │    │
│   │    • Orchestrates Mail/Validation agents via A2A          │    │
│   └───────────────────────────────────────────────────────────┘    │
│   ┌───────────────────────────────────────────────────────────┐    │
│   │              A2A REGISTRY (Embedded)                       │    │
│   └───────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                    │ A2A Protocol
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────────┐   ┌───────────────────┐
│   MAIL AGENT      │   │ VALIDATION AGENT  │
│    (:8002)        │   │    (:8003)        │
└───────────────────┘   └───────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                    MOCK EMAIL SERVER (:8080)                       │
└───────────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-LLM Support**: OpenAI, Azure OpenAI, Google Gemini, OpenRouter (configurable)
- **A2A Protocol**: Google's Agent-to-Agent communication standard
- **AG-UI Protocol**: Real-time streaming to frontend dashboard via SSE
- **LangGraph Workflow**: State machine with SQLite checkpointing for fault tolerance
- **Configurable Timeouts**: 48h default, 3 retries before escalation (configurable for demo)
- **Document Validation**: LLM analysis + sandboxed Python code execution
- **996 Unit Tests**: Comprehensive test coverage with strict TDD approach
- **No Fallback Values**: Explicit configuration required - fail fast on missing config

## Quick Start

### Prerequisites

- Python 3.12+
- An API key for at least one LLM provider

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/info-agent.git
cd info-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

### Configuration

Edit `.env` with your LLM provider credentials:

```bash
# For OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4-turbo
OPENAI_API_KEY=sk-your-key-here

# OR for Azure OpenAI
LLM_PROVIDER=azure_openai
LLM_MODEL=gpt-4
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment

# OR for Google Gemini
LLM_PROVIDER=gemini
LLM_MODEL=gemini-pro
GOOGLE_API_KEY=your-key

# OR for OpenRouter
LLM_PROVIDER=openrouter
LLM_MODEL=anthropic/claude-3-opus
OPENROUTER_API_KEY=sk-or-your-key
```

### Running the Demo

```bash
# Start all services
python scripts/run_demo.py
```

This will:
1. Start all services (Gateway, Mail Agent, Validation Agent, Email Server)
2. Open 3 browser tabs:
   - **Tab 1**: System Dashboard (http://localhost:8000)
   - **Tab 2**: Target Inbox - raj@gmail.com (http://localhost:8080/inbox/raj@gmail.com)
   - **Tab 3**: End User Inbox - mrinal@gmail.com (http://localhost:8080/inbox/mrinal@gmail.com)

### Running Individual Services

```bash
# 1. Start Mock Email Server (SMTP + REST API)
python -m info_agent.email_server.runner

# 2. Start FastAPI Gateway (includes Supervisor + Registry)
python scripts/run_server.py

# Note: Worker agents (Mail, Validation) currently require programmatic instantiation
# They are tested via unit tests but don't have __main__ entry points yet
```

## Project Structure

```
info-agent/
├── src/info_agent/           # Main package
│   ├── gateway/              # FastAPI gateway
│   │   ├── routes/           # API routes
│   │   ├── app.py            # Main FastAPI app
│   │   └── models.py         # Request/response models
│   ├── supervisor/           # Supervisor agent logic
│   ├── agents/               # A2A worker agents
│   │   ├── mail/             # Mail Agent (A2A worker)
│   │   └── validation/       # Validation Agent (A2A worker)
│   ├── workflow/             # LangGraph workflow
│   ├── llm/                  # Multi-LLM provider support
│   ├── a2a/                  # A2A protocol layer
│   ├── email_server/         # Mock email server
│   ├── dashboard/            # AG-UI streaming
│   ├── utils/                # Utilities
│   └── config.py             # Configuration management
├── frontend/                 # HTML/Tailwind/HTMX templates
│   ├── templates/            # Jinja2 templates
│   └── static/               # CSS/JS assets
├── tests/                    # Test suite (996 tests)
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── e2e/                  # End-to-end tests
├── test_data/                # Test input files
├── scripts/                  # Utility scripts
│   ├── run_demo.py           # Demo runner
│   ├── run_server.py         # Server runner
│   └── demo_workflow.py      # Demo workflow
├── data/                     # Runtime data (gitignored)
└── resources/                # Documentation and research
```

## Demo Scenario

1. **Create Workflow**: Upload 4 input files (instructions, FAQ, escalation, validation)
2. **Approve Plan**: Review and approve the execution plan
3. **Email Sent**: System emails raj@gmail.com requesting recipes
4. **Clarification**: If raj asks a question:
   - Check FAQ → Reply automatically if found
   - Escalate to mrinal@gmail.com if not in FAQ
5. **Timeout**: If no response after 48h (or 3 retries), escalate to vishal@gmail.com
6. **Validation**: When document received, validate against criteria
7. **Results**: Dashboard shows pass/fail with detailed report

## Input File Examples

See `test_data/` for example input files:

- `instructions_example.txt` - What to request
- `faq_example.txt` - Common questions and answers
- `escalation_example.txt` - Escalation contacts and rules
- `validation_example.txt` - Document validation criteria

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=info_agent --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m e2e           # End-to-end tests only
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run linting
ruff check src tests

# Run formatting
ruff format src tests
```

## Configuration Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LLM_PROVIDER` | LLM provider (openai, azure_openai, gemini, openrouter) | None | Yes |
| `LLM_MODEL` | Model identifier | None | Yes |
| Provider API Keys | Provider-specific API keys | None | Yes (based on provider) |
| `GATEWAY_PORT` | FastAPI gateway port | 8000 | No |
| `MAIL_AGENT_PORT` | Mail agent port | 8002 | No |
| `VALIDATION_AGENT_PORT` | Validation agent port | 8003 | No |
| `EMAIL_SERVER_PORT` | Mock email server HTTP port | 8080 | No |
| `SMTP_PORT` | Mock email server SMTP port | 1025 | No |
| `DEFAULT_TIMEOUT_HOURS` | Email response timeout (hours) | 48 | No |
| `DEFAULT_RETRY_COUNT` | Retries before escalation | 3 | No |
| `VALIDATION_TIMEOUT_SECONDS` | Python execution timeout | 30 | No |
| `LOG_LEVEL` | Logging level | INFO | No |
| `LOG_FORMAT` | Log format (json, console) | json | No |
| `DEBUG` | Debug mode | false | No |

**Important**: Required configuration MUST be provided. The system will raise `MissingConfigurationError` if required fields are missing - no fallback values are used.

See `.env.example` for full configuration template with all options.

## API Documentation

When the gateway is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Technology Stack

- **Python 3.12+** - Runtime
- **FastAPI** - Web framework
- **LangGraph** - Workflow orchestration
- **A2A SDK** - Agent communication
- **AG-UI Protocol** - Frontend streaming
- **Tailwind CSS** - Styling
- **HTMX** - Dynamic updates
- **SQLite** - State persistence

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## References

- [Google A2A Protocol](https://google.github.io/A2A/)
- [AG-UI Protocol](https://docs.ag-ui.com/)
- [LangGraph Documentation](https://docs.langchain.com/langgraph)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## Execution steps
# 1. Email Server (port 8080 HTTP, 1025 SMTP)
  python -m info_agent.email_server.runner

  # 2. Gateway (port 8000)
  python scripts/run_server.py

  # 3. Mail Agent (port 8002)
  python -m info_agent.agents.mail

  # 4. Validation Agent (port 8003)
  python -m info_agent.agents.validation

  # Or run everything with the demo:
  python scripts/run_demo.py