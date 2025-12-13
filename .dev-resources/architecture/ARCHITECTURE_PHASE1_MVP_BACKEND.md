# Info-Agent Phase 1: MVP Backend Architecture

## Executive Summary

This document describes the **Minimum Viable Product (MVP) Backend** for the Info-Agent system. This phase implements the core infrastructure required to execute a basic email request workflow without any UI.

### Phase 1 Goals

1. Establish project structure and foundation
2. Implement FastAPI Gateway with basic endpoints
3. Create Supervisor Agent with LangGraph orchestration
4. Build Mail Agent for email operations
5. Set up Mock Email Server (SMTP + REST API, no Web UI)
6. Implement A2A Registry for agent discovery
7. Integrate Gemini 2.5 Flash as the LLM provider
8. Configure SQLite checkpointing for state persistence

### What This Phase Delivers

- A working backend that can:
  - Accept workflow creation requests via API
  - Parse input instruction files
  - Generate an execution plan using LLM
  - Send emails to target recipients via Mock Email Server
  - Receive email replies via webhook
  - Persist workflow state across restarts

### What This Phase Does NOT Include

- Validation Agent (Phase 2)
- Clarification/FAQ matching (Phase 2)
- Escalation/timeout handling (Phase 2)
- AG-UI event streaming (Phase 2)
- Frontend dashboard (Phase 3)
- Mock Email Web UI (Phase 3)
- Multi-provider LLM support (Phase 2)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI GATEWAY (Port 8000)                        │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ /api/workflows  │  │ /webhooks/email │  │ /health         │             │
│  │ (CRUD + files)  │  │ (receive notif) │  │ (health check)  │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      SUPERVISOR AGENT (Embedded)                        ││
│  │  ┌───────────────────────────────────────────────────────────────────┐ ││
│  │  │                 LangGraph Orchestration Engine                     │ ││
│  │  │                 (with SQLite Checkpointing)                        │ ││
│  │  └───────────────────────────────────────────────────────────────────┘ ││
│  │                                                                         ││
│  │  • Parse input instruction files                                       ││
│  │  • Query A2A Registry for available agents                             ││
│  │  • Generate execution plan via Gemini 2.5 Flash                        ││
│  │  • Orchestrate Mail Agent via A2A protocol                             ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                     │                                        │
│                            Queries  │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        A2A REGISTRY (Embedded)                          ││
│  │                                                                         ││
│  │  • Agent registration endpoint                                         ││
│  │  • Agent discovery endpoint                                            ││
│  │  • In-memory storage (SQLite for persistence)                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ A2A Protocol (HTTP/JSON)
                                     ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                         MAIL AGENT (Port 8001)                                 │
│                         (A2A Worker Server)                                    │
│                                                                                │
│  • Registers with A2A Registry on startup                                     │
│  • Receives tasks from Supervisor only                                        │
│  • Composes and sends emails via SMTP                                         │
│  • Parses incoming email notifications                                        │
│  • Tracks email threads                                                       │
└───────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ SMTP (Port 1025)
                                     ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                       MOCK EMAIL SERVER (Port 8025)                            │
│                                                                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │ SMTP Interface  │  │ REST API        │  │ Webhook Notifier│               │
│  │ (aiosmtpd)      │  │ (inbox access)  │  │ (new mail event)│               │
│  │ Port 1025       │  │ Port 8025       │  │                 │               │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘               │
│                                                                                │
│  Storage: SQLite (data/emails.db)                                             │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Port Assignments

| Component | Port | Purpose |
|-----------|------|---------|
| FastAPI Gateway | 8000 | Main API entry point |
| Mail Agent | 8001 | A2A worker server |
| Mock Email Server (REST) | 8025 | Email inbox REST API |
| Mock Email Server (SMTP) | 1025 | SMTP interface |

---

## Component Specifications

### 1. FastAPI Gateway

**Purpose**: Main entry point for the system. Hosts the Supervisor Agent and A2A Registry.

**Technology**:
- Python 3.12+
- FastAPI 0.104+
- Pydantic 2.0+ for validation

**Responsibilities**:
1. Expose REST API endpoints for workflow management
2. Host embedded Supervisor Agent
3. Host embedded A2A Registry
4. Receive email webhook notifications
5. Serve health check endpoint

**API Endpoints**:

```python
# Workflow Management
POST   /api/workflows              # Create new workflow
GET    /api/workflows              # List all workflows
GET    /api/workflows/{id}         # Get workflow details
GET    /api/workflows/{id}/status  # Get current status
POST   /api/workflows/{id}/approve # Approve execution plan

# File Management
POST   /api/workflows/{id}/files   # Upload input files
GET    /api/workflows/{id}/files   # List uploaded files

# Webhook Receivers
POST   /webhooks/email             # Receive email notifications

# A2A Registry (Embedded)
POST   /a2a/agents/register        # Register agent
GET    /a2a/agents                 # List agents
GET    /a2a/agents/{agent_id}      # Get agent details

# Health
GET    /health                     # System health check
```

**Request/Response Models**:

```python
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from enum import Enum
from datetime import datetime

class WorkflowStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    WAITING_FOR_RESPONSE = "waiting_for_response"
    COMPLETED = "completed"
    FAILED = "failed"

class CreateWorkflowRequest(BaseModel):
    """Request to create a new workflow."""
    name: str
    description: Optional[str] = None

class WorkflowResponse(BaseModel):
    """Workflow details response."""
    id: str
    name: str
    description: Optional[str]
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime

class UploadFilesRequest(BaseModel):
    """Metadata for file upload."""
    file_type: str  # instructions, faq, escalation, validation

class WorkflowStatusResponse(BaseModel):
    """Current workflow status."""
    id: str
    status: WorkflowStatus
    current_step: Optional[str]
    plan: Optional[List[dict]]
    error: Optional[str]

class ApproveWorkflowRequest(BaseModel):
    """Request to approve or reject execution plan."""
    approved: bool
    feedback: Optional[str] = None

class EmailWebhookPayload(BaseModel):
    """Incoming email notification."""
    message_id: str
    thread_id: str
    from_address: str
    to_address: str
    subject: str
    body: str
    attachments: List[dict]
    received_at: datetime

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    components: dict
    version: str
```

---

### 2. Supervisor Agent (Embedded)

**Purpose**: Central orchestrator that reads input files, creates execution plans, and coordinates the Mail Agent.

**Deployment**: Embedded within FastAPI Gateway (same process)

**Technology**:
- LangGraph for workflow orchestration
- LangChain for LLM integration
- Gemini 2.5 Flash as the LLM

**Responsibilities**:

1. **Input Processing**:
   - Read uploaded instruction files
   - Extract target email, requested information, and requirements

2. **Plan Generation**:
   - Query A2A Registry to discover Mail Agent
   - Use Gemini 2.5 Flash to generate execution plan
   - Present plan for user approval

3. **Orchestration**:
   - Execute approved plan step by step
   - Delegate email tasks to Mail Agent via A2A protocol
   - Update workflow state after each step

**State Schema**:

```python
from typing import TypedDict, List, Optional
from enum import Enum

class WorkflowStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    WAITING_FOR_RESPONSE = "waiting_for_response"
    COMPLETED = "completed"
    FAILED = "failed"

class SupervisorState(TypedDict):
    """State managed by the Supervisor Agent."""

    # Workflow identification
    workflow_id: str

    # Input files content
    instructions: str

    # Parsed requirements (extracted by LLM)
    target_email: str
    target_name: str
    requested_info: str

    # Execution state
    status: WorkflowStatus
    plan: List[dict]
    current_step: int

    # Communication tracking
    email_thread_id: Optional[str]
    sent_email_id: Optional[str]

    # Results
    received_response: Optional[str]
    received_attachments: List[dict]

    # Audit
    audit_log: List[dict]
    created_at: str
    updated_at: str

    # Error handling
    error: Optional[str]
```

**LangGraph Workflow (Phase 1 - Basic)**:

```python
from langgraph.graph import StateGraph, END

# Define the basic workflow graph
workflow = StateGraph(SupervisorState)

# Add nodes
workflow.add_node("parse_inputs", parse_input_files)
workflow.add_node("lookup_agents", query_a2a_registry)
workflow.add_node("generate_plan", create_execution_plan)
workflow.add_node("await_approval", wait_for_user_approval)
workflow.add_node("execute_step", execute_current_step)
workflow.add_node("send_email", invoke_mail_agent_send)
workflow.add_node("wait_response", wait_for_email_response)
workflow.add_node("process_response", handle_email_response)

# Define edges
workflow.set_entry_point("parse_inputs")

workflow.add_edge("parse_inputs", "lookup_agents")
workflow.add_edge("lookup_agents", "generate_plan")
workflow.add_edge("generate_plan", "await_approval")

workflow.add_conditional_edges(
    "await_approval",
    check_approval_status,
    {
        "approved": "execute_step",
        "rejected": "generate_plan",
        "cancelled": END
    }
)

workflow.add_conditional_edges(
    "execute_step",
    determine_next_action,
    {
        "send_email": "send_email",
        "complete": END
    }
)

workflow.add_edge("send_email", "wait_response")

workflow.add_conditional_edges(
    "wait_response",
    check_response_received,
    {
        "received": "process_response",
        "waiting": "wait_response"
    }
)

workflow.add_edge("process_response", END)
```

**Node Implementations**:

```python
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def parse_input_files(state: SupervisorState) -> Dict[str, Any]:
    """Parse instruction files and extract requirements."""
    logger.info(f"Parsing input files for workflow {state['workflow_id']}")

    instructions = state["instructions"]

    # Use LLM to extract structured data from instructions
    llm = get_gemini_llm()

    extraction_prompt = f"""
    Extract the following information from these instructions:

    Instructions:
    {instructions}

    Extract:
    1. target_email: The email address to send the request to
    2. target_name: The name of the person (if mentioned)
    3. requested_info: What information/documents are being requested

    Respond in JSON format:
    {{
        "target_email": "...",
        "target_name": "...",
        "requested_info": "..."
    }}
    """

    response = await llm.ainvoke(extraction_prompt)
    extracted = parse_json_response(response.content)

    logger.info(f"Extracted requirements: {extracted}")

    return {
        "target_email": extracted["target_email"],
        "target_name": extracted.get("target_name", ""),
        "requested_info": extracted["requested_info"],
        "status": WorkflowStatus.PLANNING,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "parse_inputs",
            "details": "Extracted requirements from instructions"
        }]
    }

async def query_a2a_registry(state: SupervisorState) -> Dict[str, Any]:
    """Query A2A Registry to discover available agents."""
    logger.info("Querying A2A Registry for available agents")

    registry_client = get_registry_client()
    agents = await registry_client.list_agents()

    mail_agent = next(
        (a for a in agents if a["name"] == "mail-agent"),
        None
    )

    if not mail_agent:
        raise Exception("Mail Agent not found in registry")

    logger.info(f"Found Mail Agent at {mail_agent['endpoint']}")

    return {
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "lookup_agents",
            "details": f"Found Mail Agent at {mail_agent['endpoint']}"
        }]
    }

async def create_execution_plan(state: SupervisorState) -> Dict[str, Any]:
    """Generate execution plan using LLM."""
    logger.info(f"Generating execution plan for workflow {state['workflow_id']}")

    llm = get_gemini_llm()

    plan_prompt = f"""
    Create an execution plan to collect the following information:

    Target: {state['target_name']} ({state['target_email']})
    Requested Information: {state['requested_info']}

    Available Actions:
    1. send_email - Send an email to the target requesting information
    2. wait_response - Wait for email reply from target

    Create a step-by-step plan. Respond in JSON format:
    {{
        "plan": [
            {{"step": 1, "action": "send_email", "description": "..."}},
            {{"step": 2, "action": "wait_response", "description": "..."}}
        ],
        "summary": "Brief summary of the plan"
    }}
    """

    response = await llm.ainvoke(plan_prompt)
    plan_data = parse_json_response(response.content)

    logger.info(f"Generated plan with {len(plan_data['plan'])} steps")

    return {
        "plan": plan_data["plan"],
        "status": WorkflowStatus.AWAITING_APPROVAL,
        "current_step": 0,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "generate_plan",
            "details": plan_data["summary"]
        }]
    }

async def wait_for_user_approval(state: SupervisorState) -> Dict[str, Any]:
    """Wait for user to approve the execution plan."""
    logger.info(f"Waiting for approval of workflow {state['workflow_id']}")

    # This node will be interrupted until user approves via API
    # The approval status is set externally via /api/workflows/{id}/approve

    return {
        "status": WorkflowStatus.AWAITING_APPROVAL
    }

def check_approval_status(state: SupervisorState) -> str:
    """Check if plan was approved, rejected, or cancelled."""
    # This is determined by external API call
    # For now, we check a flag in state
    if state.get("plan_approved") is True:
        return "approved"
    elif state.get("plan_rejected") is True:
        return "rejected"
    elif state.get("plan_cancelled") is True:
        return "cancelled"
    return "approved"  # Default for basic flow

async def execute_current_step(state: SupervisorState) -> Dict[str, Any]:
    """Execute the current step in the plan."""
    current_step = state["current_step"]
    plan = state["plan"]

    if current_step >= len(plan):
        return {"status": WorkflowStatus.COMPLETED}

    step = plan[current_step]
    logger.info(f"Executing step {current_step + 1}: {step['action']}")

    return {
        "status": WorkflowStatus.EXECUTING,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "execute_step",
            "details": f"Executing step {current_step + 1}: {step['description']}"
        }]
    }

def determine_next_action(state: SupervisorState) -> str:
    """Determine the next action based on current plan step."""
    current_step = state["current_step"]
    plan = state["plan"]

    if current_step >= len(plan):
        return "complete"

    step = plan[current_step]
    return step["action"]

async def invoke_mail_agent_send(state: SupervisorState) -> Dict[str, Any]:
    """Invoke Mail Agent to send email."""
    logger.info(f"Invoking Mail Agent to send email to {state['target_email']}")

    a2a_client = get_a2a_client()

    # Compose email content using LLM
    llm = get_gemini_llm()

    compose_prompt = f"""
    Compose a professional email requesting the following information:

    To: {state['target_name']} ({state['target_email']})
    Request: {state['requested_info']}

    The email should be polite, clear, and professional.
    Include a clear call to action.

    Respond with just the email body (no subject line).
    """

    response = await llm.ainvoke(compose_prompt)
    email_body = response.content.strip()

    # Send via Mail Agent
    task_result = await a2a_client.send_task(
        agent_name="mail-agent",
        skill_id="send-email",
        payload={
            "to": state["target_email"],
            "subject": f"Information Request: {state['requested_info'][:50]}...",
            "body": email_body
        }
    )

    logger.info(f"Email sent, message_id: {task_result['message_id']}")

    return {
        "sent_email_id": task_result["message_id"],
        "email_thread_id": task_result["thread_id"],
        "current_step": state["current_step"] + 1,
        "status": WorkflowStatus.WAITING_FOR_RESPONSE,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "send_email",
            "details": f"Sent email to {state['target_email']}, thread_id: {task_result['thread_id']}"
        }]
    }

async def wait_for_email_response(state: SupervisorState) -> Dict[str, Any]:
    """Wait for email response from target."""
    logger.info(f"Waiting for response to thread {state['email_thread_id']}")

    # This node will be interrupted until webhook notification arrives
    # The response is set externally via /webhooks/email

    return {
        "status": WorkflowStatus.WAITING_FOR_RESPONSE
    }

def check_response_received(state: SupervisorState) -> str:
    """Check if email response has been received."""
    if state.get("received_response"):
        return "received"
    return "waiting"

async def handle_email_response(state: SupervisorState) -> Dict[str, Any]:
    """Process received email response."""
    logger.info(f"Processing response for workflow {state['workflow_id']}")

    return {
        "current_step": state["current_step"] + 1,
        "status": WorkflowStatus.COMPLETED,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "process_response",
            "details": "Email response received and processed"
        }]
    }
```

---

### 3. Mail Agent (A2A Worker Server)

**Purpose**: Handles all email operations. Runs as a separate A2A server process.

**Deployment**: Separate process on port 8001

**Technology**:
- Python 3.12+
- FastAPI for A2A server
- aiosmtplib for SMTP sending

**A2A Registration**:
- Registers with A2A Registry on startup
- Does NOT query the registry
- Receives tasks only from Supervisor

**Agent Card**:

```json
{
  "name": "mail-agent",
  "description": "Email communication agent for sending and receiving messages",
  "version": "1.0.0",
  "url": "http://localhost:8001",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "skills": [
    {
      "id": "send-email",
      "name": "Send Email",
      "description": "Sends email to specified recipient"
    },
    {
      "id": "parse-email",
      "name": "Parse Email",
      "description": "Parses incoming email content"
    }
  ],
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text"]
}
```

**State Schema**:

```python
from typing import TypedDict, List, Optional

class EmailMessage(TypedDict):
    """Email message structure."""
    id: str
    thread_id: str
    from_address: str
    to_address: str
    subject: str
    body: str
    attachments: List[dict]
    sent_at: Optional[str]
    received_at: Optional[str]
    is_reply: bool
    in_reply_to: Optional[str]

class MailAgentState(TypedDict):
    """State maintained by Mail Agent."""
    sent_emails: List[EmailMessage]
    active_threads: dict  # thread_id -> thread metadata
```

**A2A Task Handlers**:

```python
import logging
import uuid
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def handle_send_email(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle send-email skill invocation."""
    logger.info(f"Sending email to {payload['to']}")

    message_id = str(uuid.uuid4())
    thread_id = payload.get("thread_id") or str(uuid.uuid4())

    # Compose email
    email = {
        "id": message_id,
        "thread_id": thread_id,
        "from_address": "system@info-agent.local",
        "to_address": payload["to"],
        "subject": payload["subject"],
        "body": payload["body"],
        "attachments": payload.get("attachments", []),
        "sent_at": datetime.utcnow().isoformat(),
        "is_reply": payload.get("in_reply_to") is not None,
        "in_reply_to": payload.get("in_reply_to")
    }

    # Send via SMTP to Mock Email Server
    smtp_client = get_smtp_client()
    await smtp_client.send_email(
        from_addr=email["from_address"],
        to_addr=email["to_address"],
        subject=email["subject"],
        body=email["body"]
    )

    logger.info(f"Email sent successfully, message_id: {message_id}")

    return {
        "status": "sent",
        "message_id": message_id,
        "thread_id": thread_id
    }

async def handle_parse_email(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle parse-email skill invocation."""
    logger.info(f"Parsing email {payload['message_id']}")

    raw_email = payload.get("raw_content", "")

    # Extract structured data from email
    parsed = {
        "message_id": payload["message_id"],
        "from_address": payload.get("from_address", ""),
        "to_address": payload.get("to_address", ""),
        "subject": payload.get("subject", ""),
        "body": payload.get("body", raw_email),
        "attachments": payload.get("attachments", []),
        "is_reply": "Re:" in payload.get("subject", "")
    }

    logger.info(f"Email parsed successfully")

    return {
        "status": "parsed",
        "parsed_email": parsed
    }
```

**Mail Agent Server**:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Mail Agent", version="1.0.0")

class A2ATaskRequest(BaseModel):
    """A2A task request structure."""
    task_id: str
    skill_id: str
    payload: Dict[str, Any]

class A2ATaskResponse(BaseModel):
    """A2A task response structure."""
    task_id: str
    status: str
    result: Dict[str, Any]

@app.on_event("startup")
async def register_with_registry():
    """Register with A2A Registry on startup."""
    logger.info("Registering Mail Agent with A2A Registry")

    registry_url = get_settings().a2a_registry_url
    agent_card = get_agent_card()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{registry_url}/a2a/agents/register",
            json=agent_card
        )
        response.raise_for_status()

    logger.info("Mail Agent registered successfully")

@app.get("/.well-known/agent.json")
async def get_agent_card_endpoint():
    """Return agent card for A2A discovery."""
    return get_agent_card()

@app.post("/a2a/tasks")
async def handle_task(request: A2ATaskRequest) -> A2ATaskResponse:
    """Handle incoming A2A task."""
    logger.info(f"Received task {request.task_id}, skill: {request.skill_id}")

    handlers = {
        "send-email": handle_send_email,
        "parse-email": handle_parse_email
    }

    handler = handlers.get(request.skill_id)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown skill: {request.skill_id}"
        )

    result = await handler(request.payload)

    return A2ATaskResponse(
        task_id=request.task_id,
        status="completed",
        result=result
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "mail-agent"}
```

---

### 4. Mock Email Server

**Purpose**: Simulates email infrastructure for development and testing.

**Deployment**: Separate process - SMTP on port 1025, REST API on port 8025

**Technology**:
- Python 3.12+
- aiosmtpd for SMTP interface
- FastAPI for REST API
- SQLite for email storage

**Components**:

1. **SMTP Interface** (Port 1025): Accepts outgoing emails
2. **REST API** (Port 8025): Inbox access, reply simulation
3. **Webhook Notifier**: Notifies gateway of new emails

**REST API Endpoints**:

```
GET    /inboxes                      # List all inboxes
GET    /inboxes/{email}/messages     # Get messages for inbox
GET    /messages/{message_id}        # Get specific message
POST   /messages                     # Create message (simulate incoming)
POST   /messages/{message_id}/reply  # Send reply (simulate target person)
DELETE /messages/{message_id}        # Delete message
```

**Email Storage Schema**:

```python
from typing import TypedDict, List, Optional

class StoredEmail(TypedDict):
    """Email stored in Mock Email Server."""
    id: str
    inbox: str  # recipient email address
    thread_id: str
    from_address: str
    to_address: str
    subject: str
    body_text: str
    attachments: List[dict]
    received_at: str
    read: bool

# SQLite Schema
"""
CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    inbox TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_text TEXT NOT NULL,
    attachments TEXT,  -- JSON array
    received_at TEXT NOT NULL,
    read INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_inbox ON emails(inbox);
CREATE INDEX IF NOT EXISTS idx_thread_id ON emails(thread_id);
"""
```

**SMTP Handler**:

```python
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope, Session, SMTP
import logging
import json
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailHandler:
    """Handle incoming SMTP messages."""

    def __init__(self, storage, webhook_notifier):
        self.storage = storage
        self.webhook_notifier = webhook_notifier

    async def handle_DATA(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope
    ) -> str:
        """Process incoming email data."""
        logger.info(f"Received email from {envelope.mail_from} to {envelope.rcpt_tos}")

        # Parse email content
        message_id = str(uuid.uuid4())
        thread_id = self._extract_thread_id(envelope) or str(uuid.uuid4())

        email = {
            "id": message_id,
            "inbox": envelope.rcpt_tos[0],
            "thread_id": thread_id,
            "from_address": envelope.mail_from,
            "to_address": envelope.rcpt_tos[0],
            "subject": self._extract_subject(envelope),
            "body_text": envelope.content.decode("utf-8", errors="replace"),
            "attachments": [],
            "received_at": datetime.utcnow().isoformat(),
            "read": False
        }

        # Store email
        await self.storage.save_email(email)
        logger.info(f"Email stored with id: {message_id}")

        # Send webhook notification
        await self.webhook_notifier.notify(email)

        return "250 OK"

    def _extract_subject(self, envelope: Envelope) -> str:
        """Extract subject from email content."""
        content = envelope.content.decode("utf-8", errors="replace")
        for line in content.split("\n"):
            if line.lower().startswith("subject:"):
                return line[8:].strip()
        return "(No Subject)"

    def _extract_thread_id(self, envelope: Envelope) -> Optional[str]:
        """Extract thread ID from email headers."""
        content = envelope.content.decode("utf-8", errors="replace")
        for line in content.split("\n"):
            if line.lower().startswith("x-thread-id:"):
                return line[12:].strip()
        return None

def start_smtp_server(host: str, port: int, handler: EmailHandler):
    """Start SMTP server."""
    controller = Controller(handler, hostname=host, port=port)
    controller.start()
    logger.info(f"SMTP server started on {host}:{port}")
    return controller
```

**Webhook Notifier**:

```python
import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class WebhookNotifier:
    """Send webhook notifications for new emails."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def notify(self, email: Dict[str, Any]) -> None:
        """Send webhook notification for new email."""
        logger.info(f"Sending webhook notification for email {email['id']}")

        payload = {
            "event": "email.received",
            "message_id": email["id"],
            "thread_id": email["thread_id"],
            "from_address": email["from_address"],
            "to_address": email["to_address"],
            "subject": email["subject"],
            "body": email["body_text"],
            "attachments": email["attachments"],
            "received_at": email["received_at"]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
            logger.info(f"Webhook notification sent successfully")
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
```

---

### 5. A2A Registry (Embedded)

**Purpose**: Central registry for agent discovery. Embedded within the FastAPI Gateway.

**Storage**: In-memory with SQLite persistence

**API Endpoints**:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/a2a", tags=["A2A Registry"])

class AgentCard(BaseModel):
    """A2A Agent Card structure."""
    name: str
    description: str
    version: str
    url: str
    capabilities: Dict[str, Any]
    skills: List[Dict[str, Any]]
    defaultInputModes: List[str]
    defaultOutputModes: List[str]

class RegisterAgentRequest(BaseModel):
    """Request to register an agent."""
    agent_card: AgentCard

# In-memory storage (backed by SQLite)
registered_agents: Dict[str, AgentCard] = {}

@router.post("/agents/register")
async def register_agent(request: AgentCard) -> Dict[str, str]:
    """Register a new agent."""
    logger.info(f"Registering agent: {request.name}")

    registered_agents[request.name] = request

    # Persist to SQLite
    await persist_agent(request)

    logger.info(f"Agent {request.name} registered successfully")
    return {"status": "registered", "agent_name": request.name}

@router.get("/agents")
async def list_agents() -> List[AgentCard]:
    """List all registered agents."""
    logger.info(f"Listing {len(registered_agents)} registered agents")
    return list(registered_agents.values())

@router.get("/agents/{agent_name}")
async def get_agent(agent_name: str) -> AgentCard:
    """Get agent details by name."""
    agent = registered_agents.get(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    return agent

@router.delete("/agents/{agent_name}")
async def deregister_agent(agent_name: str) -> Dict[str, str]:
    """Deregister an agent."""
    if agent_name not in registered_agents:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")

    del registered_agents[agent_name]
    await delete_agent_from_db(agent_name)

    logger.info(f"Agent {agent_name} deregistered")
    return {"status": "deregistered", "agent_name": agent_name}
```

---

### 6. LLM Integration (Gemini 2.5 Flash)

**Purpose**: Provide LLM capabilities for plan generation and email composition.

**Technology**:
- LangChain `langchain-google-genai`
- Google Gemini 2.5 Flash model

**Configuration**:

```python
from pydantic_settings import BaseSettings
from typing import Optional

class LLMSettings(BaseSettings):
    """LLM configuration settings."""

    google_api_key: str
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    class Config:
        env_file = ".env"
```

**Provider Implementation**:

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class GeminiProvider:
    """Gemini LLM provider using LangChain."""

    def __init__(self, settings: LLMSettings):
        self.api_key = settings.google_api_key
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self._client: Optional[ChatGoogleGenerativeAI] = None

    def get_chat_model(self, **kwargs) -> ChatGoogleGenerativeAI:
        """Get or create the chat model instance."""
        if self._client is None:
            logger.info(f"Initializing Gemini model: {self.model}")
            self._client = ChatGoogleGenerativeAI(
                google_api_key=self.api_key,
                model=self.model,
                temperature=kwargs.get("temperature", self.temperature),
                max_output_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
        return self._client

# Factory function
_llm_instance: Optional[GeminiProvider] = None

def get_gemini_llm() -> ChatGoogleGenerativeAI:
    """Get the configured Gemini LLM instance."""
    global _llm_instance

    if _llm_instance is None:
        settings = LLMSettings()
        _llm_instance = GeminiProvider(settings)

    return _llm_instance.get_chat_model()
```

---

### 7. SQLite Checkpointing

**Purpose**: Persist LangGraph workflow state for resumption after restarts.

**Implementation**:

```python
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def create_checkpointer(db_path: str) -> SqliteSaver:
    """Create SQLite checkpointer for LangGraph."""
    logger.info(f"Initializing SQLite checkpointer at {db_path}")

    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Create connection
    conn = sqlite3.connect(db_path, check_same_thread=False)

    # Create tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT NOT NULL,
            checkpoint_id TEXT NOT NULL,
            parent_id TEXT,
            checkpoint BLOB NOT NULL,
            metadata BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (thread_id, checkpoint_id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id
        ON checkpoints(thread_id)
    """)

    conn.commit()
    logger.info("SQLite checkpointer initialized")

    return SqliteSaver(conn)

# Usage with LangGraph
def compile_workflow(workflow: StateGraph, db_path: str):
    """Compile workflow with checkpointing."""
    checkpointer = create_checkpointer(db_path)
    return workflow.compile(checkpointer=checkpointer)
```

---

## Configuration

### Environment Variables

```bash
# .env file for Phase 1

# ===================
# LLM Configuration
# ===================
GOOGLE_API_KEY=your-google-api-key-here
LLM_MODEL=gemini-2.5-flash
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

# ===================
# Server Configuration
# ===================
HOST=0.0.0.0
GATEWAY_PORT=8000
MAIL_AGENT_PORT=8001
EMAIL_SERVER_PORT=8025
SMTP_PORT=1025

DEBUG=true

# ===================
# A2A Registry
# ===================
A2A_REGISTRY_URL=http://localhost:8000/a2a

# ===================
# Mock Email Server
# ===================
SMTP_HOST=localhost
EMAIL_WEBHOOK_URL=http://localhost:8000/webhooks/email

# ===================
# Database Paths
# ===================
CHECKPOINT_DB_PATH=data/checkpoints.db
EMAIL_DB_PATH=data/emails.db

# ===================
# Logging
# ===================
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Pydantic Settings

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings with validation."""

    # LLM
    google_api_key: str
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # Server
    host: str = "0.0.0.0"
    gateway_port: int = 8000
    mail_agent_port: int = 8001
    email_server_port: int = 8025
    smtp_port: int = 1025
    debug: bool = False

    # A2A
    a2a_registry_url: str = "http://localhost:8000/a2a"

    # Email
    smtp_host: str = "localhost"
    email_webhook_url: str = "http://localhost:8000/webhooks/email"

    # Database
    checkpoint_db_path: str = "data/checkpoints.db"
    email_db_path: str = "data/emails.db"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
```

---

## Directory Structure

```
info-agent/
├── src/
│   └── info_agent/
│       ├── __init__.py
│       ├── main.py                      # FastAPI Gateway entry point
│       ├── config.py                    # Settings and configuration
│       │
│       ├── api/                         # API Layer
│       │   ├── __init__.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── workflows.py         # Workflow CRUD endpoints
│       │   │   ├── webhooks.py          # Webhook receivers
│       │   │   └── health.py            # Health check
│       │   └── models/
│       │       ├── __init__.py
│       │       ├── requests.py          # Request models
│       │       └── responses.py         # Response models
│       │
│       ├── agents/                      # A2A Agents
│       │   ├── __init__.py
│       │   ├── supervisor/
│       │   │   ├── __init__.py
│       │   │   ├── agent.py             # Supervisor agent logic
│       │   │   ├── planner.py           # Plan generation
│       │   │   └── state.py             # State definitions
│       │   └── mail/
│       │       ├── __init__.py
│       │       ├── agent.py             # Mail agent A2A server
│       │       ├── composer.py          # Email composition
│       │       ├── parser.py            # Email parsing
│       │       └── state.py             # State definitions
│       │
│       ├── workflow/                    # LangGraph Workflow
│       │   ├── __init__.py
│       │   ├── graph.py                 # Workflow graph definition
│       │   ├── nodes.py                 # Node implementations
│       │   ├── state.py                 # Workflow state
│       │   └── checkpointer.py          # SQLite checkpointing
│       │
│       ├── llm/                         # LLM Integration
│       │   ├── __init__.py
│       │   ├── factory.py               # LLM factory
│       │   └── gemini_provider.py       # Gemini implementation
│       │
│       ├── a2a/                         # A2A Protocol
│       │   ├── __init__.py
│       │   ├── registry.py              # Registry endpoints
│       │   ├── client.py                # A2A client
│       │   └── models.py                # A2A data models
│       │
│       ├── email/                       # Mock Email Server
│       │   ├── __init__.py
│       │   ├── server.py                # Email server main
│       │   ├── smtp.py                  # SMTP handler
│       │   ├── api.py                   # REST API endpoints
│       │   ├── storage.py               # SQLite storage
│       │   ├── webhook.py               # Webhook notifier
│       │   └── models.py                # Email models
│       │
│       └── utils/                       # Utilities
│           ├── __init__.py
│           ├── logging.py               # Logging setup
│           └── exceptions.py            # Custom exceptions
│
├── tests/                               # Test Suite
│   ├── __init__.py
│   ├── conftest.py                      # Test fixtures
│   └── unit/
│       ├── __init__.py
│       ├── test_supervisor.py
│       ├── test_mail_agent.py
│       ├── test_workflow.py
│       └── test_llm.py
│
├── test_data/                           # Test Input Files
│   ├── instructions_example.txt
│   └── sample_documents/
│
├── scripts/                             # Utility Scripts
│   ├── run_gateway.py                   # Start gateway server
│   ├── run_mail_agent.py                # Start mail agent
│   ├── run_email_server.py              # Start mock email server
│   └── test_workflow.py                 # Test basic workflow
│
├── data/                                # Runtime Data (gitignored)
│   ├── checkpoints.db
│   ├── emails.db
│   └── logs/
│
├── .env.example                         # Environment template
├── .gitignore
├── pyproject.toml                       # Project configuration
└── README.md                            # Project documentation
```

---

## Data Flow

### Basic Workflow Flow

```
1. User creates workflow via POST /api/workflows
   │
   ▼
2. User uploads instruction file via POST /api/workflows/{id}/files
   │
   ▼
3. Supervisor parses instructions, extracts requirements (LLM)
   │
   ▼
4. Supervisor queries A2A Registry, finds Mail Agent
   │
   ▼
5. Supervisor generates execution plan (LLM)
   │
   ▼
6. User approves plan via POST /api/workflows/{id}/approve
   │
   ▼
7. Supervisor invokes Mail Agent via A2A protocol
   │
   ▼
8. Mail Agent sends email via Mock Email Server (SMTP)
   │
   ▼
9. Mock Email Server stores email, sends webhook to Gateway
   │
   ▼
10. Target person replies (simulated via POST /messages/{id}/reply)
    │
    ▼
11. Mock Email Server sends webhook notification to Gateway
    │
    ▼
12. Supervisor updates workflow state to COMPLETED
```

### Sequence Diagram

```
┌──────┐     ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌─────────────┐
│ User │     │ Gateway │     │Supervisor│     │Mail Agent│     │Email Server │
└──┬───┘     └────┬────┘     └────┬─────┘     └────┬─────┘     └──────┬──────┘
   │              │               │                │                   │
   │ POST /workflows              │                │                   │
   │─────────────▶│               │                │                   │
   │              │               │                │                   │
   │ POST /workflows/{id}/files   │                │                   │
   │─────────────▶│               │                │                   │
   │              │               │                │                   │
   │              │ Parse inputs  │                │                   │
   │              │──────────────▶│                │                   │
   │              │               │                │                   │
   │              │   Query registry               │                   │
   │              │◀──────────────│                │                   │
   │              │               │                │                   │
   │              │ Generate plan (LLM)            │                   │
   │              │──────────────▶│                │                   │
   │              │               │                │                   │
   │◀─────────────│ Return plan   │                │                   │
   │              │               │                │                   │
   │ POST /approve│               │                │                   │
   │─────────────▶│               │                │                   │
   │              │               │                │                   │
   │              │ Execute plan  │                │                   │
   │              │──────────────▶│                │                   │
   │              │               │                │                   │
   │              │               │ A2A: send-email│                   │
   │              │               │───────────────▶│                   │
   │              │               │                │                   │
   │              │               │                │ SMTP send         │
   │              │               │                │──────────────────▶│
   │              │               │                │                   │
   │              │               │                │◀──────────────────│
   │              │               │◀───────────────│                   │
   │              │               │                │                   │
   │              │◀──────────────│                │                   │
   │              │               │                │                   │
   │              │   Webhook: email.received      │                   │
   │              │◀────────────────────────────────────────────────────│
   │              │               │                │                   │
   │              │ Update state  │                │                   │
   │              │──────────────▶│                │                   │
   │              │               │                │                   │
   │◀─────────────│ Workflow complete              │                   │
   │              │               │                │                   │
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_supervisor.py
import pytest
from unittest.mock import AsyncMock, patch
from info_agent.agents.supervisor.agent import SupervisorAgent
from info_agent.workflow.state import SupervisorState

@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    mock = AsyncMock()
    mock.ainvoke.return_value.content = '{"target_email": "test@example.com", "target_name": "Test", "requested_info": "Test info"}'
    return mock

@pytest.mark.asyncio
async def test_parse_input_files(mock_llm):
    """Test parsing of instruction files."""
    with patch("info_agent.agents.supervisor.agent.get_gemini_llm", return_value=mock_llm):
        state = {
            "workflow_id": "test-123",
            "instructions": "Send email to test@example.com asking for test info",
            "audit_log": []
        }

        result = await parse_input_files(state)

        assert result["target_email"] == "test@example.com"
        assert result["target_name"] == "Test"
        assert result["requested_info"] == "Test info"

# tests/unit/test_mail_agent.py
import pytest
from unittest.mock import AsyncMock, patch
from info_agent.agents.mail.agent import handle_send_email

@pytest.mark.asyncio
async def test_send_email():
    """Test email sending."""
    with patch("info_agent.agents.mail.agent.get_smtp_client") as mock_smtp:
        mock_smtp.return_value.send_email = AsyncMock()

        payload = {
            "to": "test@example.com",
            "subject": "Test Subject",
            "body": "Test body"
        }

        result = await handle_send_email(payload)

        assert result["status"] == "sent"
        assert "message_id" in result
        assert "thread_id" in result

# tests/unit/test_workflow.py
import pytest
from info_agent.workflow.graph import create_workflow
from info_agent.workflow.state import SupervisorState

def test_workflow_creation():
    """Test workflow graph creation."""
    workflow = create_workflow()

    # Verify nodes exist
    assert "parse_inputs" in workflow.nodes
    assert "lookup_agents" in workflow.nodes
    assert "generate_plan" in workflow.nodes
    assert "await_approval" in workflow.nodes
    assert "send_email" in workflow.nodes
```

### Integration Tests

```python
# tests/integration/test_basic_flow.py
import pytest
from httpx import AsyncClient
from info_agent.main import app

@pytest.mark.asyncio
async def test_create_workflow():
    """Test workflow creation endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/workflows",
            json={"name": "Test Workflow"}
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Workflow"
        assert data["status"] == "created"

@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
```

---

## Running the System

### Prerequisites

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .
```

### Starting Services

```bash
# Terminal 1: Start Mock Email Server
python scripts/run_email_server.py

# Terminal 2: Start Mail Agent
python scripts/run_mail_agent.py

# Terminal 3: Start FastAPI Gateway
python scripts/run_gateway.py
```

### Testing Basic Workflow

```bash
# Create workflow
curl -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Workflow"}'

# Upload instruction file
curl -X POST http://localhost:8000/api/workflows/{id}/files \
  -F "file=@test_data/instructions_example.txt" \
  -F "file_type=instructions"

# Check status
curl http://localhost:8000/api/workflows/{id}/status

# Approve plan
curl -X POST http://localhost:8000/api/workflows/{id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

---

## Dependencies (pyproject.toml)

```toml
[project]
name = "info-agent"
version = "0.1.0"
description = "Multi-agent information retrieval system"
requires-python = ">=3.12"
dependencies = [
    # Web Framework
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",

    # LangChain & LLM
    "langchain>=0.1.0",
    "langchain-google-genai>=1.0.0",
    "langgraph>=0.1.0",

    # HTTP Client
    "httpx>=0.25.0",

    # Email
    "aiosmtpd>=1.4.0",
    "aiosmtplib>=3.0.0",

    # Database
    # SQLite is built-in

    # Logging
    "structlog>=23.0.0",

    # Utilities
    "python-multipart>=0.0.6",  # File uploads
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "httpx>=0.25.0",  # For testing
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Logging Configuration

```python
# src/info_agent/utils/logging.py
import logging
import structlog
from info_agent.config import get_settings

def setup_logging():
    """Configure structured logging."""
    settings = get_settings()

    # Set log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.log_format == "json"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set root logger level
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
    )

    return structlog.get_logger()
```

---

## Error Handling

```python
# src/info_agent/utils/exceptions.py
from typing import Optional

class InfoAgentError(Exception):
    """Base exception for Info-Agent."""

    def __init__(self, message: str, code: str, details: Optional[dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

class WorkflowNotFoundError(InfoAgentError):
    """Workflow not found."""

    def __init__(self, workflow_id: str):
        super().__init__(
            message=f"Workflow not found: {workflow_id}",
            code="WORKFLOW_NOT_FOUND",
            details={"workflow_id": workflow_id}
        )

class AgentNotFoundError(InfoAgentError):
    """Agent not found in registry."""

    def __init__(self, agent_name: str):
        super().__init__(
            message=f"Agent not found: {agent_name}",
            code="AGENT_NOT_FOUND",
            details={"agent_name": agent_name}
        )

class LLMError(InfoAgentError):
    """LLM invocation error."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"LLM error: {message}",
            code="LLM_ERROR",
            details={"original_error": str(original_error) if original_error else None}
        )

class A2AError(InfoAgentError):
    """A2A protocol error."""

    def __init__(self, message: str, agent_name: str):
        super().__init__(
            message=f"A2A error with {agent_name}: {message}",
            code="A2A_ERROR",
            details={"agent_name": agent_name}
        )
```

---

## Phase 1 Completion Criteria

- [ ] FastAPI Gateway running on port 8000
- [ ] A2A Registry endpoints functional
- [ ] Mail Agent running on port 8001 and registered
- [ ] Mock Email Server running (SMTP 1025, REST 8025)
- [ ] Gemini 2.5 Flash LLM integration working
- [ ] Basic LangGraph workflow executing
- [ ] SQLite checkpointing saving state
- [ ] Webhook notifications flowing from Email Server to Gateway
- [ ] Unit tests passing
- [ ] Basic workflow test (create → upload → approve → send email) working

---

## Next Phase Preview

**Phase 2: Full Backend** will add:
- Validation Agent with Python execution
- Clarification/FAQ matching flow
- Escalation and timeout handling
- AG-UI event streaming endpoint
- Multi-provider LLM support
- Advanced error handling and retry logic

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-13 | Claude | Initial Phase 1 architecture document |
