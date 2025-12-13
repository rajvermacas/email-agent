# Info-Agent

**Multi-agent information retrieval system using A2A protocol and LangGraph**

Info-Agent is an AI-powered system that automates information gathering through email communication. It uses intelligent agents to understand your request, compose professional emails, and manage the entire communication workflow.

[![Tests](https://img.shields.io/badge/tests-911%2F996%20passing-green)]()
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688)]()
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2%2B-purple)]()

---

## Features

- **Intelligent Orchestration**: LangGraph-based workflow engine with state persistence
- **LLM-Powered**: Uses Google Gemini for plan generation and email composition
- **Agent-to-Agent Communication**: Uses official Google A2A SDK v0.3.21 for spec-compliant inter-agent coordination
- **Email Automation**: Automated email sending, receiving, and parsing
- **Workflow Management**: Create, approve, and track multi-step workflows
- **State Persistence**: SQLite-backed checkpointing allows workflows to resume after restart
- **Mock Email Server**: Built-in email server for development and testing
- **REST API**: Comprehensive FastAPI-based API for all operations
- **Webhook Support**: Real-time notifications for email events
- **Extensive Logging**: Structured logging for debugging and monitoring

---

## Quick Start

### Prerequisites

- Python 3.12 or higher
- Google Gemini API key ([Get one here](https://aistudio.google.com/apikey))
- Git

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd info-agent

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
pip install -e .

# Copy and configure environment file
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Configuration

Edit `.env` file and set at minimum:

```bash
GOOGLE_API_KEY=your-google-api-key-here
```

See [Configuration](#configuration) section for all available options.

### Running the System

**Option 1: Run all services together (recommended)**

```bash
python scripts/run_all_services.py
```

**Option 2: Run services individually**

```bash
# Terminal 1: Mock Email Server
python scripts/run_email_server.py

# Terminal 2: FastAPI Gateway
python scripts/run_gateway.py

# Note: Mail Agent is currently embedded in the Gateway
# Separate Mail Agent service (port 8001) planned for Phase 2
```

### Verify Installation

```bash
# Check health
curl http://localhost:8000/health

# Should return: {"status":"healthy","components":{...}}
```

---

## Architecture Overview

Info-Agent consists of two main components:

```
┌──────────────────────────────────────────────────┐
│         FastAPI Gateway (Port 8000)              │
│  • Workflow Management API                       │
│  • Supervisor Agent (LangGraph + A2A SDK Client) │
│  • Mail Agent (A2A SDK Server - Embedded)        │
│  • A2A Agent Registry (Custom SQLite)            │
└──────────────────────────────────────────────────┘
                      ↓ SMTP
┌──────────────────────────────────────────────────┐
│    Mock Email Server (Ports 1025, 8025)          │
│  • SMTP Interface                                │
│  • REST API for Inbox                            │
│  • Webhook Notifications                         │
└──────────────────────────────────────────────────┘

Note: Using official a2a-sdk v0.3.21 for A2A protocol.
Mail Agent is embedded in Gateway (Phase 1).
Separate A2A service on port 8001 planned for Phase 2.
```

### Workflow Execution

1. **Create Workflow**: User creates a workflow via API
2. **Upload Instructions**: User provides natural language instructions
3. **Generate Plan**: Supervisor Agent uses LLM to create execution plan
4. **User Approval**: Plan is presented for user approval
5. **Execute**: Mail Agent composes and sends email via SMTP
6. **Wait for Response**: System monitors for email replies
7. **Process Response**: Response is parsed and workflow completes

---

## Usage

### Basic Workflow Example

```bash
# 1. Create a workflow
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Request Q3 Report",
    "description": "Get quarterly report from finance team"
  }'

# Response: {"id": "wf-123", "status": "created", ...}

# 2. Upload instruction file
curl -X POST http://localhost:8000/api/workflows/wf-123/files \
  -F "file=@instructions.txt" \
  -F "file_type=instructions"

# 3. Check status (workflow auto-generates plan)
curl http://localhost:8000/api/workflows/wf-123/status

# Response: {"status": "awaiting_approval", "plan": [...], ...}

# 4. Approve the plan
curl -X POST http://localhost:8000/api/workflows/wf-123/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'

# 5. Monitor status
curl http://localhost:8000/api/workflows/wf-123/status

# Status will progress: executing → waiting_for_response → completed
```

### Sample Instruction File

Create `instructions.txt`:

```
Please send an email to john.smith@finance.example.com requesting the Q3 2024
financial report. Ask for both the summary report and detailed breakdowns.
Mention that this is needed for the board meeting next week.
```

### Python SDK Example

```python
import httpx
import asyncio

async def create_workflow():
    async with httpx.AsyncClient() as client:
        # Create workflow
        response = await client.post(
            "http://localhost:8000/api/workflows",
            json={
                "name": "Get Report",
                "description": "Request financial report"
            }
        )
        workflow = response.json()
        workflow_id = workflow["id"]

        # Upload instructions
        with open("instructions.txt", "rb") as f:
            await client.post(
                f"http://localhost:8000/api/workflows/{workflow_id}/files",
                files={"file": f},
                data={"file_type": "instructions"}
            )

        # Wait for plan generation
        await asyncio.sleep(5)

        # Get status
        response = await client.get(
            f"http://localhost:8000/api/workflows/{workflow_id}/status"
        )
        status = response.json()
        print(f"Plan: {status['plan']}")

        # Approve plan
        await client.post(
            f"http://localhost:8000/api/workflows/{workflow_id}/approve",
            json={"approved": True}
        )

        print(f"Workflow {workflow_id} started!")

asyncio.run(create_workflow())
```

---

## API Reference

### Workflows

#### Create Workflow

```http
POST /api/workflows
Content-Type: application/json

{
  "name": "Workflow Name",
  "description": "Optional description"
}
```

**Response**: `201 Created`

```json
{
  "id": "wf-abc123",
  "name": "Workflow Name",
  "description": "Optional description",
  "status": "created",
  "created_at": "2025-12-13T10:00:00Z",
  "updated_at": "2025-12-13T10:00:00Z"
}
```

#### List Workflows

```http
GET /api/workflows
```

**Response**: `200 OK`

```json
{
  "workflows": [
    {
      "id": "wf-abc123",
      "name": "Workflow Name",
      "status": "completed",
      ...
    }
  ],
  "total": 1
}
```

#### Get Workflow

```http
GET /api/workflows/{workflow_id}
```

#### Get Workflow Status

```http
GET /api/workflows/{workflow_id}/status
```

**Response**: `200 OK`

```json
{
  "id": "wf-abc123",
  "status": "awaiting_approval",
  "current_step": "generate_plan",
  "plan": [
    {
      "step": 1,
      "action": "send_email",
      "description": "Send email to john@example.com requesting Q3 report"
    }
  ],
  "error": null
}
```

#### Upload Files

```http
POST /api/workflows/{workflow_id}/files
Content-Type: multipart/form-data

file: <file>
file_type: instructions
```

#### Approve Workflow

```http
POST /api/workflows/{workflow_id}/approve
Content-Type: application/json

{
  "approved": true,
  "feedback": "Optional feedback message"
}
```

### Webhooks

#### Email Webhook (Internal)

```http
POST /webhooks/email
Content-Type: application/json

{
  "event": "email.received",
  "message_id": "msg-123",
  "thread_id": "thread-456",
  "from_address": "sender@example.com",
  "to_address": "recipient@example.com",
  "subject": "Re: Information Request",
  "body": "Email body content",
  "attachments": [],
  "received_at": "2025-12-13T10:30:00Z"
}
```

### Health Check

```http
GET /health
```

**Response**: `200 OK`

```json
{
  "status": "healthy",
  "components": {
    "gateway": "healthy",
    "supervisor": "healthy",
    "registry": "healthy"
  },
  "version": "0.1.0"
}
```

---

## Configuration

### Environment Variables

All configuration is done via environment variables in `.env` file:

#### LLM Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Google Gemini API key (required) | - |
| `LLM_MODEL` | Gemini model name | `gemini-2.5-flash` |
| `LLM_TEMPERATURE` | LLM temperature (0.0-1.0) | `0.7` |
| `LLM_MAX_TOKENS` | Max tokens per response | `4096` |

#### Server Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Host to bind to | `0.0.0.0` |
| `GATEWAY_PORT` | FastAPI Gateway port | `8000` |
| `MAIL_AGENT_PORT` | Mail Agent port | `8001` |
| `EMAIL_SERVER_PORT` | Email Server REST API port | `8025` |
| `SMTP_PORT` | Email Server SMTP port | `1025` |
| `DEBUG` | Debug mode | `true` |

#### A2A Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `A2A_REGISTRY_URL` | A2A Registry URL | `http://localhost:8000/a2a` |

#### Email Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SMTP_HOST` | SMTP host for sending | `localhost` |
| `EMAIL_WEBHOOK_URL` | Webhook for email events | `http://localhost:8000/webhooks/email` |

#### Database Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CHECKPOINT_DB_PATH` | LangGraph checkpoints DB | `data/checkpoints.db` |
| `EMAIL_DB_PATH` | Email storage DB | `data/emails.db` |
| `REGISTRY_DB_PATH` | Agent registry DB | `data/registry.db` |
| `WORKFLOW_DB_PATH` | Workflow storage DB | `data/workflows.db` |

#### Logging Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `LOG_FORMAT` | Log format (console, json) | `console` |

### Example .env

See [.env.example](./.env.example) for a complete example configuration.

---

## Development

### Project Structure

```
info-agent/
├── src/info_agent/          # Main application source
│   ├── a2a/                 # A2A SDK integration + custom registry
│   ├── agents/              # AI agents (supervisor, mail)
│   ├── api/                 # REST API routes and models
│   ├── email/               # Mock email server
│   ├── llm/                 # LLM integration (Gemini)
│   ├── utils/               # Utilities (logging, exceptions)
│   └── workflow/            # LangGraph workflow engine
├── tests/                   # Test suite
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── scripts/                 # Utility scripts
├── test_data/               # Test input files
└── data/                    # Runtime data (gitignored)
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=info_agent --cov-report=html

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_workflow_graph.py -v
```

**Current Test Status**: 911 passing out of 996 tests (91.5% pass rate)

### Manual Testing Scripts

```bash
# Test LLM integration
python scripts/test_llm_module.py

# Test A2A protocol
python scripts/test_a2a_module.py

# Test basic workflow
python scripts/test_workflow_basic.py
```

### Code Quality

```bash
# Lint with ruff
ruff check src/

# Format with ruff
ruff format src/
```

---

## Testing the Mock Email Server

### Send Test Email

```bash
# Using Python
python3 << EOF
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Test email body")
msg["Subject"] = "Test Subject"
msg["From"] = "sender@example.com"
msg["To"] = "recipient@example.com"

with smtplib.SMTP("localhost", 1025) as server:
    server.send_message(msg)
    print("Email sent!")
EOF
```

### Access Inbox via REST API

```bash
# List all inboxes
curl http://localhost:8025/inboxes

# Get messages for an inbox
curl http://localhost:8025/inboxes/recipient@example.com/messages

# Get specific message
curl http://localhost:8025/messages/{message_id}
```

---

## Troubleshooting

### Common Issues

#### 1. Missing API Key

**Error**: `LLMError: GOOGLE_API_KEY is required`

**Solution**: Add your API key to `.env`:
```bash
echo "GOOGLE_API_KEY=your-actual-key-here" >> .env
```

Get an API key from: https://aistudio.google.com/apikey

#### 2. Port Already in Use

**Error**: `OSError: [Errno 48] Address already in use`

**Solution**: Kill the process using the port:
```bash
# Find process
lsof -i :8000  # Or :8001, :8025, :1025

# Kill process
kill -9 <PID>
```

#### 3. Module Not Found

**Error**: `ModuleNotFoundError: No module named 'info_agent'`

**Solution**: Install package in editable mode:
```bash
pip install -e .
```

#### 4. Database Locked

**Error**: `sqlite3.OperationalError: database is locked`

**Solution**: Stop all services and restart:
```bash
# Stop all
pkill -f "python scripts/run"

# Remove lock files
rm data/*.db-shm data/*.db-wal

# Restart
python scripts/run_all_services.py
```

#### 5. Tests Failing

**Solution**: Ensure dependencies are up to date:
```bash
pip install -e ".[dev]"
pytest tests/unit/ -v  # Run unit tests first
```

---

## Production Deployment

### Security Considerations

1. **API Keys**: Never commit `.env` to version control
2. **SMTP**: Use real SMTP server (not mock) in production
3. **Authentication**: Add API authentication (not implemented in Phase 1)
4. **HTTPS**: Use HTTPS for all external endpoints
5. **Rate Limiting**: Implement rate limiting on API endpoints

### Recommended Setup

```bash
# Use production SMTP server
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Use production database
CHECKPOINT_DB_PATH=/var/lib/info-agent/checkpoints.db

# Disable debug mode
DEBUG=false

# Use JSON logging
LOG_FORMAT=json
LOG_LEVEL=WARNING
```

### Docker Deployment (Coming Soon)

```bash
# Build image
docker build -t info-agent:latest .

# Run
docker-compose up -d
```

---

## Roadmap

### Phase 1 (Current) - MVP Backend ✅

- FastAPI Gateway with REST API
- Supervisor Agent with LangGraph
- Mail Agent with email composition
- Mock Email Server
- **Official A2A SDK integration (v0.3.21)** - 100% spec-compliant
- Google Gemini LLM integration
- SQLite checkpointing
- 76.7% code reduction from custom A2A implementation

### Phase 2 - Full Backend

- Validation Agent with Python execution
- Clarification/FAQ matching
- Escalation and timeout handling
- Multi-provider LLM support (OpenAI, Anthropic)
- Advanced error handling and retry logic
- Event streaming endpoint

### Phase 3 - MVP UI

- Web dashboard for workflow management
- Real-time workflow monitoring
- Email inbox UI (replacing mock server UI)

### Phase 4 - Full UI

- Advanced analytics and reporting
- Configuration management UI
- User management and permissions
- Multi-tenant support

---

## Contributing

We welcome contributions! Please see our contribution guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Maximum line length: 100 characters
- Maximum file size: 800 lines (split larger files)
- Write comprehensive tests (aim for >85% coverage)
- Use type hints
- Add docstrings to all functions/classes
- Update documentation for user-facing changes

---

## License

MIT License - see LICENSE file for details

---

## Support

- **Documentation**: See [CLAUDE.md](./CLAUDE.md) for detailed developer documentation
- **Issues**: Report bugs via GitHub Issues
- **Questions**: Open a discussion on GitHub

---

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Orchestrated with [LangGraph](https://langchain-ai.github.io/langgraph/)
- Powered by [Google Gemini](https://ai.google.dev/)
- Uses [Official A2A SDK v0.3.21](https://github.com/google/a2a-sdk-python) for agent communication
- Implements [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)

---

## Project Statistics

- **Lines of Code**: ~15,000
- **Source Files**: 45
- **Test Files**: 34
- **Total Tests**: 996 (911 passing)
- **Test Coverage**: 84%
- **Python Version**: 3.12+

---

**Built with ❤️ by the Info-Agent Team**
