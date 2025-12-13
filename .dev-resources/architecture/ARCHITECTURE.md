# Info-Agent System Architecture

## Executive Summary

Info-Agent is a multi-agent information retrieval and validation system that automates the process of requesting, collecting, clarifying, escalating, and validating information from external parties via email.

### System Purpose

When an end user needs to collect specific information (documents, data, files) from another person:
1. The system sends an email request to the target person
2. Handles clarification questions using FAQ or escalates to the end user
3. Escalates if the target person doesn't respond within configurable timeouts
4. Validates received documents against specified criteria
5. Provides real-time visibility into the entire process via a dashboard

### Key Capabilities

- **Automated Email Communication**: Send requests, handle replies, manage threads
- **Intelligent Clarification**: Answer questions using FAQ, escalate unknown queries
- **Configurable Escalation**: Timeout-based escalation with retry logic (3 retries before escalate)
- **Document Validation**: Validate received documents using LLM + Python execution
- **Real-Time Dashboard**: Live visibility into agent execution and workflow state
- **Full Audit Trail**: Complete history of all communications and decisions

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              END USER INTERFACE                              │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Real-Time Dashboard (AG-UI)                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │ │
│  │  │ Plan View    │  │ Execution    │  │ Audit Log    │                 │ │
│  │  │ & Approval   │  │ Status       │  │ & History    │                 │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    │ AG-UI Events (SSE)                      │
│                                    ▼                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ HTTP/SSE
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI GATEWAY                                    │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ /api/submit     │  │ /api/stream     │  │ /api/status     │             │
│  │ (Start workflow)│  │ (AG-UI events)  │  │ (Query state)   │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      SUPERVISOR AGENT (Embedded)                        ││
│  │  ┌───────────────────────────────────────────────────────────────────┐ ││
│  │  │                 LangGraph Orchestration Engine                     │ ││
│  │  │                 (with SQLite Checkpointing)                        │ ││
│  │  └───────────────────────────────────────────────────────────────────┘ ││
│  │                                                                         ││
│  │  • Read & parse input files (instructions, FAQ, escalation, validation)││
│  │  • Query A2A Registry to discover available worker agents              ││
│  │  • Generate execution plan & rearticulate for user approval            ││
│  │  • Orchestrate worker agents (Mail, Validation) via A2A protocol       ││
│  │  • Handle escalations, timeouts, and clarification routing             ││
│  │  • Stream AG-UI events to frontend dashboard                           ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                     │                                        │
│                            Queries  │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        A2A REGISTRY SERVER                              ││
│  │                                                                         ││
│  │  • Maintains registry of available worker agents                       ││
│  │  • Agent Cards (/.well-known/agent.json) for each agent                ││
│  │  • Health monitoring and agent discovery                               ││
│  │  • Only Supervisor queries this registry                               ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ A2A Protocol (HTTP/JSON)
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ▼                                 ▼
┌───────────────────────────────────┐ ┌───────────────────────────────────────┐
│         MAIL AGENT                │ │         VALIDATION AGENT              │
│         (A2A Server)              │ │         (A2A Server)                  │
│                                   │ │                                       │
│  Worker agent - does NOT query    │ │  Worker agent - does NOT query        │
│  A2A Registry. Only receives      │ │  A2A Registry. Only receives          │
│  tasks from Supervisor.           │ │  tasks from Supervisor.               │
│                                   │ │                                       │
│  Responsibilities:                │ │  Responsibilities:                    │
│  • Send emails via SMTP           │ │  • Validate received documents        │
│  • Parse incoming email replies   │ │  • LLM analysis of content            │
│  • Handle attachments             │ │  • Execute Python for complex         │
│  • Track email threads            │ │    validation (large datasets)        │
│  • Report results to Supervisor   │ │  • Generate validation reports        │
│                                   │ │  • Report pass/fail to Supervisor     │
│  Registers with A2A Registry      │ │                                       │
│  on startup (one-time)            │ │  Registers with A2A Registry          │
│                                   │ │  on startup (one-time)                │
└───────────────────────────────────┘ └───────────────────────────────────────┘
           │                                        │
           │                                        │
           ▼                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MOCK EMAIL SERVER                                     │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ SMTP Interface  │  │ Inbox Storage   │  │ Webhook Notifier│             │
│  │ (Send emails)   │  │ (Per-user)      │  │ (New mail event)│             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  Web UI: View inboxes for raj@gmail.com, mrinal@gmail.com, etc.            │
│                                                                              │
│  Webhook notifications sent to Supervisor (via FastAPI Gateway)             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Architecture Key Points

1. **Supervisor Agent is INSIDE the FastAPI Gateway**: The Supervisor is not a separate A2A server. It is embedded within the FastAPI Gateway and uses LangGraph for workflow orchestration. This eliminates unnecessary network hops and simplifies deployment.

2. **Hub-and-Spoke Topology**: The Supervisor acts as the central hub. Mail Agent and Validation Agent are worker spokes that only respond to tasks delegated by the Supervisor.

3. **A2A Registry Access Pattern**:
   - **Supervisor** → Queries the registry to discover available worker agents
   - **Mail Agent** → Registers on startup, does NOT query the registry
   - **Validation Agent** → Registers on startup, does NOT query the registry

4. **Worker Agents are Stateless Task Executors**: Mail Agent and Validation Agent receive task requests from the Supervisor, execute them, and return results. They do not maintain complex state or make decisions about workflow progression.

---

## Component Specifications

### 1. Supervisor Agent (Embedded in FastAPI Gateway)

**Purpose**: Central orchestrator that reads input files, creates execution plans, and coordinates worker agents. The Supervisor is **embedded within the FastAPI Gateway**, not a separate A2A server.

**Deployment**: Embedded within FastAPI Gateway (same process)

**Technology**:
- Python 3.12+
- LangGraph for workflow orchestration
- LLM: OpenAI, Azure OpenAI, Google Gemini, or OpenRouter (configurable)
- A2A SDK client for invoking worker agents

**A2A Registry Interaction**:
- **Queries** the A2A Registry to discover available worker agents
- Does NOT register itself (it's not an external A2A server)
- Uses discovered agent endpoints to delegate tasks

**Responsibilities**:
1. **Input Processing**:
   - Read and parse 4 input files (instructions, FAQ, escalation, validation)
   - Extract structured requirements from natural language

2. **Plan Generation**:
   - Query A2A Registry to discover available worker agents
   - Create step-by-step execution plan showing which agents will be invoked
   - Rearticulate requirements for user approval
   - Allow user iteration on plan before execution

3. **Orchestration**:
   - Execute plan by delegating tasks to worker agents (Mail, Validation)
   - Invoke agents via A2A protocol (HTTP/JSON)
   - Handle inter-agent communication routing
   - Manage state transitions via LangGraph
   - Process escalation triggers

4. **Escalation Handling**:
   - Monitor timeout conditions (configurable, default 48 hours)
   - Retry failed operations (3 times before escalate)
   - Route escalations to appropriate contacts
   - Handle clarification questions not in FAQ

**Note**: The Supervisor does NOT have its own Agent Card since it is embedded within the gateway, not exposed as an A2A server.

**State Schema**:
```python
from typing import TypedDict, List, Optional
from enum import Enum

class WorkflowStatus(str, Enum):
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    WAITING_FOR_RESPONSE = "waiting_for_response"
    ESCALATED = "escalated"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"

class SupervisorState(TypedDict):
    # Input files content
    instructions: str
    faq: str
    escalation_rules: str
    validation_criteria: str

    # Parsed requirements
    target_email: str
    target_name: str
    requested_info: str
    timeout_hours: int
    retry_count: int
    max_retries: int

    # Execution state
    status: WorkflowStatus
    plan: List[dict]
    current_step: int

    # Communication tracking
    email_threads: List[dict]
    clarification_history: List[dict]

    # Results
    received_documents: List[dict]
    validation_result: Optional[dict]

    # Audit
    audit_log: List[dict]
    created_at: str
    updated_at: str
```

---

### 2. Mail Agent (Worker A2A Server)

**Purpose**: Handles all email operations including sending, receiving, parsing, and attachment handling. This is a **worker agent** that receives tasks from the Supervisor.

**Deployment**: Separate A2A server (independent process)

**Technology**:
- Python 3.12+
- A2A SDK for agent protocol (server mode)
- Mock SMTP client for email sending
- Email parsing libraries (email, mimetypes)

**A2A Registry Interaction**:
- **Registers** with the A2A Registry on startup (one-time)
- Does **NOT query** the registry (only the Supervisor does that)
- Receives tasks exclusively from the Supervisor via A2A protocol

**Responsibilities**:
1. **Email Sending**:
   - Compose and send emails based on templates
   - Handle multiple recipients (parallel requests)
   - Track sent messages with unique thread IDs

2. **Email Receiving** (via webhook from Mock Email Server → Supervisor):
   - Process incoming email notifications forwarded by Supervisor
   - Parse email content and attachments
   - Extract structured data from replies

3. **Thread Management**:
   - Maintain conversation threads
   - Track reply chains
   - Identify clarification questions vs. final responses

4. **Attachment Handling**:
   - Download and store attachments
   - Extract file metadata
   - Support all file types (no size limits for POC)

**Agent Card**:
```json
{
  "name": "mail-agent",
  "description": "Email communication agent for sending and receiving messages",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    {
      "id": "send-email",
      "name": "Send Email",
      "description": "Sends email to specified recipient with optional attachments"
    },
    {
      "id": "parse-email",
      "name": "Parse Email",
      "description": "Parses incoming email content and attachments"
    },
    {
      "id": "check-inbox",
      "name": "Check Inbox",
      "description": "Checks for new emails in monitored inbox"
    }
  ],
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text", "file"]
}
```

**State Schema**:
```python
class EmailMessage(TypedDict):
    id: str
    thread_id: str
    from_address: str
    to_address: str
    subject: str
    body: str
    html_body: Optional[str]
    attachments: List[dict]
    sent_at: str
    received_at: Optional[str]
    is_reply: bool
    in_reply_to: Optional[str]

class MailAgentState(TypedDict):
    pending_sends: List[EmailMessage]
    sent_emails: List[EmailMessage]
    received_emails: List[EmailMessage]
    active_threads: dict  # thread_id -> thread metadata
    attachment_storage: str  # path to attachment storage
```

---

### 3. Validation Agent (Worker A2A Server)

**Purpose**: Validates received documents against specified criteria using LLM analysis and Python execution. This is a **worker agent** that receives tasks from the Supervisor.

**Deployment**: Separate A2A server (independent process)

**Technology**:
- Python 3.12+
- A2A SDK for agent protocol (server mode)
- LLM for document analysis
- Subprocess with timeout for Python execution
- Restricted imports for security

**A2A Registry Interaction**:
- **Registers** with the A2A Registry on startup (one-time)
- Does **NOT query** the registry (only the Supervisor does that)
- Receives tasks exclusively from the Supervisor via A2A protocol

**Responsibilities**:
1. **Document Analysis**:
   - Parse document content (Excel, CSV, PDF, etc.)
   - Extract structure and metadata
   - Summarize large documents using LLM

2. **Criteria Validation**:
   - Compare document against validation criteria
   - Check for required fields, row counts, data types
   - Generate detailed validation report

3. **Python Execution**:
   - Write and execute Python scripts for complex validation
   - Analyze large datasets programmatically
   - Timeout protection (30 seconds default)
   - Restricted imports (pandas, numpy, json, csv only)

4. **Result Reporting**:
   - Generate pass/fail verdict with justification
   - Create detailed validation report
   - Return results to Supervisor (who notifies end user)

**Agent Card**:
```json
{
  "name": "validation-agent",
  "description": "Document validation agent with Python execution capabilities",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    {
      "id": "validate-document",
      "name": "Validate Document",
      "description": "Validates document against specified criteria"
    },
    {
      "id": "execute-python",
      "name": "Execute Python",
      "description": "Executes Python code for complex validation logic"
    },
    {
      "id": "generate-report",
      "name": "Generate Report",
      "description": "Generates detailed validation report"
    }
  ],
  "defaultInputModes": ["text", "file"],
  "defaultOutputModes": ["text"]
}
```

**State Schema**:
```python
class ValidationResult(TypedDict):
    document_id: str
    document_name: str
    criteria_checked: List[dict]
    passed: bool
    score: float  # 0.0 to 1.0
    issues: List[str]
    recommendations: List[str]
    python_analysis: Optional[str]
    validated_at: str

class ValidationAgentState(TypedDict):
    pending_validations: List[dict]
    completed_validations: List[ValidationResult]
    python_execution_log: List[dict]
```

---

### 4. A2A Registry Server

**Purpose**: Central registry that maintains information about all available worker agents and their capabilities. Embedded within the FastAPI Gateway.

**Deployment**: Embedded within FastAPI Gateway (same process as Supervisor)

**Technology**:
- Python 3.12+
- FastAPI for HTTP endpoints
- In-memory storage (SQLite for persistence)

**Access Pattern**:
- **Supervisor** → Queries the registry to discover worker agents
- **Worker Agents** (Mail, Validation) → Register on startup, never query
- Worker agents call `POST /agents/register` once on startup

**Responsibilities**:
1. **Agent Registration** (called by Worker Agents):
   - Accept agent registration with Agent Cards
   - Validate Agent Card schema
   - Store agent metadata and endpoints

2. **Agent Discovery** (called by Supervisor only):
   - Provide searchable list of registered worker agents
   - Filter by capabilities and skills
   - Return agent endpoints and metadata

3. **Health Monitoring**:
   - Track agent availability via periodic health checks
   - Remove stale registrations
   - Provide health status

**API Endpoints**:
```
POST   /agents/register       - Register new agent (Worker Agents call this)
GET    /agents                - List all agents (Supervisor calls this)
GET    /agents/{agent_id}     - Get agent details (Supervisor calls this)
GET    /agents/search?skill=  - Search by skill (Supervisor calls this)
DELETE /agents/{agent_id}     - Deregister agent
GET    /health                - Registry health check
```

---

### 5. Mock Email Server

**Purpose**: Simulates email infrastructure for development and demo purposes.

**Technology**:
- Python 3.12+
- FastAPI for HTTP/REST API
- aiosmtpd for SMTP interface
- SQLite for email storage
- WebSocket for real-time inbox updates

**Components**:

1. **SMTP Interface** (Port 1025):
   - Accept outgoing emails from Mail Agent
   - Store in recipient's inbox
   - Trigger webhook notifications

2. **REST API**:
   ```
   GET    /inboxes                    - List all inboxes
   GET    /inboxes/{email}/messages   - Get messages for inbox
   GET    /messages/{message_id}      - Get specific message
   POST   /messages/{message_id}/reply - Send reply (simulate user)
   DELETE /messages/{message_id}      - Delete message
   GET    /attachments/{attachment_id} - Download attachment
   ```

3. **Webhook Notifier**:
   - POST to configured webhook URL on new email
   - Payload includes message metadata and thread info
   - Retry logic for failed deliveries

4. **Web UI** (for demo):
   - View all inboxes (raj@gmail.com, mrinal@gmail.com, etc.)
   - Read emails with formatting
   - Compose and send replies
   - Upload attachments
   - Real-time updates via WebSocket

**Email Storage Schema**:
```python
class StoredEmail(TypedDict):
    id: str
    inbox: str  # email address
    thread_id: str
    from_address: str
    to_address: str
    subject: str
    body_text: str
    body_html: Optional[str]
    attachments: List[dict]  # [{id, filename, content_type, size, path}]
    received_at: str
    read: bool
    starred: bool
    labels: List[str]
```

---

### 6. FastAPI Gateway

**Purpose**: Main entry point for the system, handles HTTP requests and streams AG-UI events.

**Technology**:
- Python 3.12+
- FastAPI 0.104+
- AG-UI SDK (ag-ui-protocol, ag-ui-langgraph)
- LangGraph for workflow management
- SQLite for checkpointing

**Endpoints**:

```python
# Workflow Management
POST   /api/workflows              - Create new workflow
GET    /api/workflows              - List all workflows
GET    /api/workflows/{id}         - Get workflow details
POST   /api/workflows/{id}/approve - Approve execution plan
POST   /api/workflows/{id}/cancel  - Cancel workflow

# Real-time Streaming (AG-UI)
POST   /api/workflows/{id}/stream  - Stream AG-UI events (SSE)

# Status and Queries
GET    /api/workflows/{id}/status  - Get current status
GET    /api/workflows/{id}/audit   - Get audit log
GET    /api/workflows/{id}/emails  - Get email history

# File Management
POST   /api/workflows/{id}/files   - Upload input files
GET    /api/workflows/{id}/files   - List uploaded files
GET    /api/files/{file_id}        - Download file

# Webhook Receivers
POST   /webhooks/email             - Receive email notifications
POST   /webhooks/agent             - Receive agent notifications

# Health
GET    /health                     - System health check
```

---

### 7. Real-Time Dashboard (Frontend)

**Purpose**: Provides real-time visibility into workflow execution for end users.

**Technology**:
- HTML5 + Tailwind CSS 4.0+
- HTMX 1.9+ for dynamic updates
- Vanilla JavaScript for AG-UI event handling
- Server-Sent Events (SSE) for streaming

**Views**:

1. **Workflow Creation View**:
   - File upload for 4 input files
   - Preview parsed requirements
   - Submit for planning

2. **Plan Approval View**:
   - Display rearticulated requirements
   - Show execution plan steps
   - Approve/Request Changes buttons
   - Iterate on plan before execution

3. **Execution Dashboard View**:
   - Real-time status updates
   - Current step indicator
   - Agent activity log
   - Email thread viewer
   - Countdown timer for timeouts

4. **Validation Results View**:
   - Pass/Fail status
   - Detailed validation report
   - Document preview
   - Issues and recommendations

5. **Audit Log View**:
   - Complete history of all actions
   - Filter by event type
   - Export functionality

**AG-UI Event Handling**:
```javascript
// Connect to AG-UI event stream
const eventSource = new EventSource(`/api/workflows/${workflowId}/stream`);

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch(data.type) {
        case 'RUN_STARTED':
            showExecutionStarted();
            break;
        case 'TEXT_MESSAGE_CONTENT':
            appendAgentMessage(data.content);
            break;
        case 'TOOL_CALL_START':
            showToolExecution(data.tool_name);
            break;
        case 'STATE_DELTA':
            updateWorkflowState(data.delta);
            break;
        case 'RUN_FINISHED':
            showExecutionComplete();
            break;
        case 'RUN_ERROR':
            showError(data.error);
            break;
    }
};
```

---

## Data Flow Diagrams

### Flow 1: Workflow Creation and Planning

```
┌──────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│ End User │────▶│ Dashboard UI │────▶│ FastAPI Gateway │────▶│  Supervisor  │
└──────────┘     └──────────────┘     └─────────────────┘     │    Agent     │
     │                                        │                └──────────────┘
     │ 1. Upload 4 files                      │                       │
     │    (instructions, FAQ,                 │                       │
     │     escalation, validation)            │                       │
     │                                        │                       │
     │                                        │ 2. Store files        │
     │                                        │    Create workflow    │
     │                                        │                       │
     │                                        │ 3. Invoke Supervisor ─┘
     │                                        │
     │                                        │         ┌─────────────────┐
     │                                        │◀────────│  A2A Registry   │
     │                                        │         │  (Agent lookup) │
     │                                        │         └─────────────────┘
     │                                        │
     │ 4. Stream plan via AG-UI              │◀──────── Plan generated
     │◀───────────────────────────────────────│
     │                                        │
     │ 5. Review & Approve/Iterate            │
     │────────────────────────────────────────▶
```

### Flow 2: Email Request and Response

```
┌─────────────────┐     ┌─────────────┐     ┌────────────────┐     ┌─────────────┐
│   Supervisor    │────▶│ Mail Agent  │────▶│ Mock Email Srv │────▶│  Target     │
│     Agent       │     │             │     │                │     │  Person     │
└─────────────────┘     └─────────────┘     └────────────────┘     │ (raj@...)   │
                                                   │                └─────────────┘
1. Request send email                              │                      │
   to raj@gmail.com                                │                      │
                        2. Compose email           │                      │
                           Send via SMTP           │                      │
                                                   │                      │
                                            3. Store in inbox            │
                                               Trigger webhook           │
                                                   │                      │
                                                   │  4. View email       │
                                                   │◀─────────────────────│
                                                   │                      │
                                                   │  5. Reply with       │
                                                   │     attachment       │
                                                   │◀─────────────────────│
                                                   │
                        6. Webhook notification    │
                        ◀──────────────────────────│

7. Process reply
   Extract attachment
   Notify Supervisor
```

### Flow 3: Clarification Handling

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────────┐     ┌──────────┐
│   Mail Agent    │────▶│ Supervisor  │────▶│   Dashboard     │────▶│ End User │
│  (receives Q)   │     │   Agent     │     │   (AG-UI)       │     │ (mrinal) │
└─────────────────┘     └─────────────┘     └─────────────────┘     └──────────┘
        │                      │                     │                    │
        │ 1. Receive question  │                     │                    │
        │    from raj@gmail    │                     │                    │
        │─────────────────────▶│                     │                    │
        │                      │                     │                    │
        │               2. Check FAQ                 │                    │
        │               ┌──────┴──────┐              │                    │
        │               │             │              │                    │
        │          Found?        Not Found           │                    │
        │               │             │              │                    │
        │               ▼             ▼              │                    │
        │         3a. Answer    3b. Escalate         │                    │
        │◀──────── from FAQ     to end user ────────▶│                    │
        │                             │              │                    │
        │                             │         4. Notify                 │
        │                             │            via AG-UI ────────────▶│
        │                             │              │                    │
        │                             │              │    5. Provide      │
        │                             │              │       answer       │
        │                             │              │◀───────────────────│
        │                             │              │                    │
        │◀────────────────────────────│──────────────│                    │
        │         6. Send answer                     │                    │
        │            to raj@gmail                    │                    │
```

### Flow 4: Timeout and Escalation

```
┌─────────────────┐     ┌───────────────┐     ┌─────────────────┐
│   Supervisor    │────▶│  Escalation   │────▶│   Mail Agent    │
│     Agent       │     │    Logic      │     │                 │
└─────────────────┘     └───────────────┘     └─────────────────┘
        │                      │                       │
        │ 1. Monitor timeout   │                       │
        │    (48 hours cfg)    │                       │
        │──────────────────────▶                       │
        │                      │                       │
        │               2. Timeout reached             │
        │                      │                       │
        │               3. Check retry count           │
        │               ┌──────┴──────┐                │
        │               │             │                │
        │          < 3 retries   >= 3 retries          │
        │               │             │                │
        │               ▼             ▼                │
        │         4a. Retry     4b. Escalate           │
        │         same person   to vishal@gmail ──────▶│
        │               │             │                │
        │               │       5. Send escalation     │
        │               │          email               │
        │◀──────────────│◀─────────────────────────────│
        │                                              │
        │ 6. Update state, log audit                   │
```

### Flow 5: Document Validation

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Supervisor    │────▶│  Validation    │────▶│   Dashboard     │
│     Agent       │     │    Agent       │     │   (Results)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                      │                       │
        │ 1. Send document     │                       │
        │    + criteria        │                       │
        │──────────────────────▶                       │
        │                      │                       │
        │               2. Parse document              │
        │                      │                       │
        │               3. LLM Analysis                │
        │                  (structure, content)        │
        │                      │                       │
        │               4. Python Execution            │
        │                  (if needed for             │
        │                   large datasets)           │
        │                      │                       │
        │               5. Compare vs criteria         │
        │                      │                       │
        │               6. Generate report             │
        │                  ┌───┴───┐                   │
        │                  │       │                   │
        │               PASS     FAIL                  │
        │                  │       │                   │
        │◀─────────────────┴───────┘                   │
        │                                              │
        │ 7. Stream results via AG-UI ─────────────────▶
        │                                              │
        │ 8. If FAIL: Email end user                   │
        │    with validation report                    │
```

---

## LangGraph Workflow Design

### Main Workflow Graph

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

# Define the workflow graph
workflow = StateGraph(SupervisorState)

# Add nodes
workflow.add_node("parse_inputs", parse_input_files)
workflow.add_node("lookup_agents", query_a2a_registry)
workflow.add_node("generate_plan", create_execution_plan)
workflow.add_node("await_approval", wait_for_user_approval)
workflow.add_node("execute_step", execute_current_step)
workflow.add_node("send_email", invoke_mail_agent)
workflow.add_node("wait_response", wait_for_email_response)
workflow.add_node("handle_clarification", process_clarification)
workflow.add_node("check_timeout", evaluate_timeout)
workflow.add_node("escalate", perform_escalation)
workflow.add_node("validate_document", invoke_validation_agent)
workflow.add_node("report_results", generate_final_report)

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
        "rejected": "generate_plan",  # Allow iteration
        "cancelled": END
    }
)

workflow.add_conditional_edges(
    "execute_step",
    determine_next_action,
    {
        "send_email": "send_email",
        "validate": "validate_document",
        "complete": "report_results"
    }
)

workflow.add_edge("send_email", "wait_response")

workflow.add_conditional_edges(
    "wait_response",
    check_response_type,
    {
        "document_received": "validate_document",
        "clarification_needed": "handle_clarification",
        "timeout": "check_timeout",
        "error": "escalate"
    }
)

workflow.add_conditional_edges(
    "handle_clarification",
    check_faq_match,
    {
        "found_in_faq": "send_email",  # Reply with FAQ answer
        "not_in_faq": "escalate"  # Escalate to end user
    }
)

workflow.add_conditional_edges(
    "check_timeout",
    evaluate_retry_count,
    {
        "retry": "send_email",  # Retry (< 3 attempts)
        "escalate": "escalate"  # Escalate (>= 3 attempts)
    }
)

workflow.add_edge("escalate", "wait_response")

workflow.add_conditional_edges(
    "validate_document",
    check_validation_result,
    {
        "passed": "report_results",
        "failed": "report_results"  # Report failure
    }
)

workflow.add_edge("report_results", END)

# Configure checkpointing with SQLite
checkpointer = SqliteSaver.from_conn_string("sqlite:///data/checkpoints.db")

# Compile workflow
app = workflow.compile(checkpointer=checkpointer)
```

### Checkpointing Configuration

```python
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3

# Initialize SQLite checkpointer
def create_checkpointer():
    """Create SQLite checkpointer for workflow state persistence."""
    conn = sqlite3.connect("data/checkpoints.db", check_same_thread=False)

    # Create tables if not exist
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
        CREATE INDEX IF NOT EXISTS idx_thread_id
        ON checkpoints(thread_id)
    """)

    conn.commit()

    return SqliteSaver(conn)

# Usage in FastAPI
checkpointer = create_checkpointer()

async def run_workflow(workflow_id: str, inputs: dict):
    """Run workflow with checkpointing."""
    config = {
        "configurable": {
            "thread_id": workflow_id
        }
    }

    async for event in app.astream(inputs, config):
        yield event  # Stream to AG-UI
```

---

## Technology Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Runtime | Python | 3.12+ | Primary language |
| Web Framework | FastAPI | 0.104+ | HTTP API, SSE streaming |
| Agent Protocol | Google A2A SDK | Latest | Agent-to-agent communication |
| Workflow Engine | LangGraph | 0.1+ | Workflow orchestration |
| Checkpointing | SQLite | 3.x | State persistence |
| LLM Integration | LangChain | Latest | LLM abstraction (multi-provider) |
| LLM Providers | OpenAI, Azure OpenAI, Gemini, OpenRouter | Latest | Configurable LLM backends |
| AG-UI Protocol | ag-ui-protocol | 0.4+ | Frontend event streaming |
| Email (Mock) | aiosmtpd | Latest | Mock SMTP server |
| Async | asyncio | Built-in | Async operations |
| Validation | Pydantic | 2.0+ | Data validation |

### Frontend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Markup | HTML5 | - | Structure |
| Styling | Tailwind CSS | 4.0+ | Utility-first CSS |
| Interactivity | HTMX | 1.9+ | Dynamic updates |
| Real-time | SSE (EventSource) | Native | AG-UI event streaming |
| JavaScript | Vanilla JS | ES6+ | Event handling |

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| Container | Docker | Deployment |
| Database | SQLite | Checkpoints, email storage |
| File Storage | Local filesystem | Attachments, documents |

---

## Configuration

### Environment Variables

```bash
# .env file

# LLM Configuration
LLM_PROVIDER=openai  # Options: openai, azure_openai, gemini, openrouter

# OpenAI
OPENAI_API_KEY=sk-...

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-01

# Google Gemini
GOOGLE_API_KEY=...

# OpenRouter
OPENROUTER_API_KEY=sk-or-...

LLM_MODEL=gpt-4-turbo  # Model name (varies by provider)

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true

# A2A Registry
A2A_REGISTRY_URL=http://localhost:8001

# Mock Email Server
SMTP_HOST=localhost
SMTP_PORT=1025
EMAIL_WEBHOOK_URL=http://localhost:8000/webhooks/email

# Database
CHECKPOINT_DB_PATH=data/checkpoints.db
EMAIL_DB_PATH=data/emails.db

# Timeouts (for testing, use short values)
DEFAULT_TIMEOUT_HOURS=48
DEFAULT_RETRY_COUNT=3
VALIDATION_TIMEOUT_SECONDS=30

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Configurable Parameters

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings with validation."""

    # LLM Provider Configuration
    llm_provider: str = "openai"  # openai, azure_openai, gemini, openrouter

    # OpenAI
    openai_api_key: Optional[str] = None

    # Azure OpenAI
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_deployment_name: Optional[str] = None
    azure_openai_api_version: str = "2024-02-01"

    # Google Gemini
    google_api_key: Optional[str] = None

    # OpenRouter
    openrouter_api_key: Optional[str] = None

    # Model name (varies by provider)
    llm_model: str = "gpt-4-turbo"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # A2A
    a2a_registry_url: str = "http://localhost:8001"

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_webhook_url: str = "http://localhost:8000/webhooks/email"

    # Database
    checkpoint_db_path: str = "data/checkpoints.db"
    email_db_path: str = "data/emails.db"

    # Timeouts (configurable per request)
    default_timeout_hours: int = 48
    default_retry_count: int = 3
    validation_timeout_seconds: int = 30

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
```

### LLM Provider Factory

The system uses a factory pattern to support multiple LLM providers:

```python
from abc import ABC, abstractmethod
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI as OpenRouterChat
from info_agent.config import Settings

class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def get_chat_model(self, **kwargs):
        """Return a LangChain chat model instance."""
        pass

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, settings: Settings):
        self.api_key = settings.openai_api_key
        self.model = settings.llm_model

    def get_chat_model(self, **kwargs):
        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            streaming=True,
            **kwargs
        )

class AzureOpenAIProvider(BaseLLMProvider):
    def __init__(self, settings: Settings):
        self.api_key = settings.azure_openai_api_key
        self.endpoint = settings.azure_openai_endpoint
        self.deployment = settings.azure_openai_deployment_name
        self.api_version = settings.azure_openai_api_version

    def get_chat_model(self, **kwargs):
        return AzureChatOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            azure_deployment=self.deployment,
            api_version=self.api_version,
            streaming=True,
            **kwargs
        )

class GeminiProvider(BaseLLMProvider):
    def __init__(self, settings: Settings):
        self.api_key = settings.google_api_key
        self.model = settings.llm_model or "gemini-pro"

    def get_chat_model(self, **kwargs):
        return ChatGoogleGenerativeAI(
            google_api_key=self.api_key,
            model=self.model,
            streaming=True,
            **kwargs
        )

class OpenRouterProvider(BaseLLMProvider):
    def __init__(self, settings: Settings):
        self.api_key = settings.openrouter_api_key
        self.model = settings.llm_model

    def get_chat_model(self, **kwargs):
        return ChatOpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
            model=self.model,
            streaming=True,
            **kwargs
        )

def create_llm(settings: Settings) -> BaseLLMProvider:
    """Factory function to create LLM provider based on configuration."""
    providers = {
        "openai": OpenAIProvider,
        "azure_openai": AzureOpenAIProvider,
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
    }

    provider_class = providers.get(settings.llm_provider)
    if not provider_class:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")

    return provider_class(settings)

# Usage in agents
settings = Settings()
llm_provider = create_llm(settings)
chat_model = llm_provider.get_chat_model(temperature=0)
```

**Supported Models by Provider**:

| Provider | Example Models |
|----------|---------------|
| OpenAI | `gpt-4-turbo`, `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo` |
| Azure OpenAI | Deployment name (e.g., `gpt-4`, `gpt-35-turbo`) |
| Google Gemini | `gemini-pro`, `gemini-1.5-pro`, `gemini-1.5-flash` |
| OpenRouter | Any model via OpenRouter (e.g., `anthropic/claude-3-opus`, `google/gemini-pro`) |

---

## Directory Structure

```
info-agent/
├── src/
│   └── info_agent/
│       ├── __init__.py
│       ├── main.py                    # FastAPI application entry
│       ├── config.py                  # Settings and configuration
│       │
│       ├── api/                       # API layer
│       │   ├── __init__.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── workflows.py       # Workflow endpoints
│       │   │   ├── files.py           # File management
│       │   │   ├── webhooks.py        # Webhook receivers
│       │   │   └── health.py          # Health checks
│       │   ├── models/
│       │   │   ├── __init__.py
│       │   │   ├── requests.py        # Request models
│       │   │   └── responses.py       # Response models
│       │   └── middleware/
│       │       ├── __init__.py
│       │       ├── logging.py         # Request logging
│       │       └── error_handler.py   # Error handling
│       │
│       ├── agents/                    # A2A Agents
│       │   ├── __init__.py
│       │   ├── base.py                # Base agent class
│       │   ├── supervisor/
│       │   │   ├── __init__.py
│       │   │   ├── agent.py           # Supervisor agent
│       │   │   ├── planner.py         # Plan generation
│       │   │   └── state.py           # State definitions
│       │   ├── mail/
│       │   │   ├── __init__.py
│       │   │   ├── agent.py           # Mail agent
│       │   │   ├── composer.py        # Email composition
│       │   │   ├── parser.py          # Email parsing
│       │   │   └── state.py           # State definitions
│       │   └── validation/
│       │       ├── __init__.py
│       │       ├── agent.py           # Validation agent
│       │       ├── analyzer.py        # Document analysis
│       │       ├── executor.py        # Python execution
│       │       └── state.py           # State definitions
│       │
│       ├── workflow/                  # LangGraph workflow
│       │   ├── __init__.py
│       │   ├── graph.py               # Main workflow graph
│       │   ├── nodes.py               # Workflow nodes
│       │   ├── conditions.py          # Conditional edges
│       │   ├── state.py               # Workflow state
│       │   └── checkpointer.py        # SQLite checkpointing
│       │
│       ├── llm/                       # LLM Provider Abstraction
│       │   ├── __init__.py
│       │   ├── factory.py             # LLM factory (provider selection)
│       │   ├── base.py                # Base LLM interface
│       │   ├── openai_provider.py     # OpenAI implementation
│       │   ├── azure_provider.py      # Azure OpenAI implementation
│       │   ├── gemini_provider.py     # Google Gemini implementation
│       │   └── openrouter_provider.py # OpenRouter implementation
│       │
│       ├── a2a/                       # A2A Protocol
│       │   ├── __init__.py
│       │   ├── registry.py            # Registry client
│       │   ├── client.py              # A2A client
│       │   ├── server.py              # A2A server base
│       │   └── models.py              # A2A data models
│       │
│       ├── email/                     # Mock Email Server
│       │   ├── __init__.py
│       │   ├── server.py              # Email server
│       │   ├── smtp.py                # SMTP handler
│       │   ├── storage.py             # Email storage
│       │   ├── webhook.py             # Webhook notifier
│       │   └── models.py              # Email models
│       │
│       ├── dashboard/                 # AG-UI Dashboard
│       │   ├── __init__.py
│       │   ├── stream.py              # AG-UI event streaming
│       │   └── events.py              # Event handlers
│       │
│       └── utils/                     # Utilities
│           ├── __init__.py
│           ├── logging.py             # Logging setup
│           ├── exceptions.py          # Custom exceptions
│           └── helpers.py             # Helper functions
│
├── a2a_registry/                      # A2A Registry Server
│   ├── __init__.py
│   ├── main.py                        # Registry application
│   ├── storage.py                     # Agent storage
│   └── models.py                      # Registry models
│
├── frontend/                          # Dashboard Frontend
│   ├── templates/
│   │   ├── base.html                  # Base template
│   │   ├── index.html                 # Home page
│   │   ├── workflow/
│   │   │   ├── create.html            # Create workflow
│   │   │   ├── plan.html              # View/approve plan
│   │   │   ├── execute.html           # Execution dashboard
│   │   │   └── results.html           # Validation results
│   │   └── components/
│   │       ├── header.html            # Header component
│   │       ├── sidebar.html           # Sidebar navigation
│   │       ├── status.html            # Status indicator
│   │       └── audit_log.html         # Audit log component
│   └── static/
│       ├── css/
│       │   └── app.css                # Custom styles
│       └── js/
│           ├── app.js                 # Main application
│           ├── ag-ui.js               # AG-UI event handler
│           └── utils.js               # Utility functions
│
├── tests/                             # Test suite
│   ├── __init__.py
│   ├── conftest.py                    # Test fixtures
│   ├── unit/
│   │   ├── test_supervisor.py
│   │   ├── test_mail_agent.py
│   │   ├── test_validation_agent.py
│   │   └── test_workflow.py
│   ├── integration/
│   │   ├── test_a2a_communication.py
│   │   ├── test_email_flow.py
│   │   └── test_full_workflow.py
│   └── e2e/
│       └── test_demo_scenario.py
│
├── test_data/                         # Test input files
│   ├── instructions_example.txt
│   ├── faq_example.txt
│   ├── escalation_example.txt
│   ├── validation_example.txt
│   └── sample_documents/
│       ├── valid_excel.xlsx
│       └── invalid_excel.xlsx
│
├── scripts/                           # Utility scripts
│   ├── run_demo.py                    # Demo runner
│   ├── seed_emails.py                 # Seed mock emails
│   └── test_agents.py                 # Test agent connectivity
│
├── data/                              # Runtime data (gitignored)
│   ├── checkpoints.db                 # SQLite checkpoints
│   ├── emails.db                      # Email storage
│   ├── attachments/                   # Attachment storage
│   └── logs/                          # Log files
│
├── resources/                         # Documentation & research
│   ├── research/                      # Research documents
│   └── reports/                       # Generated reports
│
├── .env.example                       # Environment template
├── .gitignore
├── pyproject.toml                     # Project configuration
├── README.md                          # Project documentation
├── ARCHITECTURE.md                    # This document
└── docker-compose.yml                 # Docker composition
```

---

## Demo Setup

### Three-Tab Browser Demo

As specified in requirements, the demo will have 3 browser tabs:

**Tab 1: System Dashboard** (http://localhost:8000)
- Real-time execution status
- Plan approval interface
- Agent activity log
- Validation results

**Tab 2: Target Person Inbox** (http://localhost:8080/inbox/raj@gmail.com)
- Mock email client for raj@gmail.com
- View received requests
- Compose and send replies
- Upload attachments

**Tab 3: End User Inbox** (http://localhost:8080/inbox/mrinal@gmail.com)
- Mock email client for mrinal@gmail.com
- Receive escalation notifications
- Answer clarification questions

### Demo Scenario

```
1. End User uploads 4 input files:
   - instructions.txt: "Send mail to raj@gmail.com asking for Excel with 10 food recipes"
   - faq.txt: Common questions and answers
   - escalation.txt: "If no reply in 48h, contact vishal@gmail.com"
   - validation.txt: "Excel file with exactly 10 rows of recipes"

2. System generates plan and shows to user (Tab 1)

3. User approves plan (Tab 1)

4. System sends email to raj@gmail.com (visible in Tab 2)

5. raj@gmail.com asks a clarification question (Tab 2)

6. System checks FAQ:
   - If found: Replies automatically
   - If not found: Escalates to mrinal@gmail.com (Tab 3)

7. mrinal@gmail.com provides answer (Tab 3)

8. System forwards answer to raj@gmail.com (Tab 2)

9. raj@gmail.com sends Excel attachment (Tab 2)

10. Validation Agent validates the document

11. Results displayed in dashboard (Tab 1)
    - If PASS: Workflow complete
    - If FAIL: Email sent to end user with report
```

### Demo Configuration

For demo purposes, use short timeouts:

```bash
# .env for demo
DEFAULT_TIMEOUT_HOURS=0.083  # 5 minutes instead of 48 hours
DEFAULT_RETRY_COUNT=1        # 1 retry instead of 3
VALIDATION_TIMEOUT_SECONDS=10
```

---

## Security Considerations

### Input Validation
- All user inputs validated with Pydantic
- File uploads scanned for type and size
- Email addresses validated with regex

### Python Execution (Validation Agent)
- Subprocess with timeout (30 seconds)
- Restricted imports whitelist:
  - `pandas`, `numpy`, `json`, `csv`, `openpyxl`
- No network access in execution environment
- Temporary directory for execution

### API Security
- Rate limiting on all endpoints
- CORS restricted to known origins
- Input sanitization for XSS prevention

### Data Protection
- No sensitive data in logs
- Attachment storage with random UUIDs
- Audit trail for compliance

---

## Error Handling

### Retry Logic
- Email sending: 3 retries with exponential backoff
- Agent communication: 3 retries
- Webhook delivery: 3 retries

### Graceful Degradation
- Agent unavailable: Queue request, retry later
- LLM timeout: Fallback to simpler prompts
- Database error: In-memory fallback for critical operations

### User Notification
- All errors surfaced via AG-UI events
- Detailed error messages in audit log
- Email notification for critical failures

---

## Monitoring and Observability

### Logging
```python
import structlog

logger = structlog.get_logger()

# Structured log format
logger.info(
    "workflow_started",
    workflow_id=workflow_id,
    user_id=user_id,
    input_files=len(files)
)
```

### Metrics
- Workflow completion rate
- Average execution time
- Email send/receive latency
- Validation success rate
- Agent response times

### Health Checks
```
GET /health
{
    "status": "healthy",
    "components": {
        "database": "ok",
        "a2a_registry": "ok",
        "email_server": "ok",
        "llm": "ok"
    },
    "version": "1.0.0"
}
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Project structure setup
- [ ] FastAPI gateway with basic endpoints
- [ ] SQLite checkpointing setup
- [ ] Mock email server (SMTP + REST API)
- [ ] Basic frontend with Tailwind

### Phase 2: Agents (Week 3-4)
- [ ] A2A Registry server
- [ ] Supervisor Agent (planning, orchestration)
- [ ] Mail Agent (send, receive, parse)
- [ ] Validation Agent (analyze, execute Python)

### Phase 3: Workflow (Week 5-6)
- [ ] LangGraph workflow implementation
- [ ] State management and transitions
- [ ] Escalation and timeout handling
- [ ] Clarification flow

### Phase 4: Dashboard (Week 7-8)
- [ ] AG-UI event streaming
- [ ] Real-time dashboard views
- [ ] Plan approval interface
- [ ] Audit log viewer

### Phase 5: Integration & Demo (Week 9-10)
- [ ] End-to-end testing
- [ ] Demo scenario setup
- [ ] Documentation
- [ ] Performance optimization

---

## Appendix

### A. Input File Examples

**instructions.txt**:
```
Send mail to raj@gmail.com asking for an Excel sheet containing 10 rows of food recipes.
The Excel should have columns: Recipe Name, Ingredients, Cooking Time, Difficulty Level.
```

**faq.txt**:
```
Q: What format should the recipes be in?
A: Please provide an Excel file (.xlsx) with columns for Recipe Name, Ingredients, Cooking Time, and Difficulty Level.

Q: How many recipes are needed?
A: We need exactly 10 recipes.

Q: What difficulty levels should be used?
A: Use Easy, Medium, or Hard for difficulty levels.
```

**escalation.txt**:
```
If raj@gmail.com is not available, out of office, or doesn't reply within 48 hours, reach out to vishal@gmail.com.

If the requested user has clarifying questions not covered in the FAQ, first email mrinal@gmail.com to get answers, then share with raj@gmail.com.
```

**validation.txt**:
```
The reply should have an attachment with:
1. An Excel file (.xlsx format)
2. Exactly 10 rows of food recipes
3. Columns: Recipe Name, Ingredients, Cooking Time, Difficulty Level
4. All cells should be filled (no empty values)
5. Difficulty Level should be one of: Easy, Medium, Hard
```

### B. AG-UI Event Types Used

```python
# Lifecycle Events
RUN_STARTED          # Workflow execution started
RUN_FINISHED         # Workflow completed successfully
RUN_ERROR            # Workflow failed with error

# Content Events
TEXT_MESSAGE_START   # Agent started generating text
TEXT_MESSAGE_CONTENT # Agent text content (streaming)
TEXT_MESSAGE_END     # Agent finished generating text

# Tool Events
TOOL_CALL_START      # Agent invoking a tool
TOOL_CALL_ARGS       # Tool arguments
TOOL_CALL_END        # Tool execution completed

# State Events
STATE_SNAPSHOT       # Full state snapshot
STATE_DELTA          # Incremental state update

# Custom Events (Info-Agent specific)
PLAN_GENERATED       # Execution plan ready for approval
PLAN_APPROVED        # User approved the plan
EMAIL_SENT           # Email was sent
EMAIL_RECEIVED       # Email was received
CLARIFICATION_NEEDED # Question requires escalation
VALIDATION_STARTED   # Document validation started
VALIDATION_COMPLETE  # Validation finished with result
```

### C. A2A Task Lifecycle

```
submitted → working → input-required → working → completed
                ↑                          ↓
                └──────── (user input) ────┘

submitted → working → failed
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-13 | Claude | Initial architecture document |

---

## References

1. [Google A2A Protocol Documentation](https://google.github.io/A2A/)
2. [AG-UI Protocol Documentation](https://docs.ag-ui.com/)
3. [LangGraph Documentation](https://docs.langchain.com/langgraph)
4. [FastAPI Documentation](https://fastapi.tiangolo.com/)
5. [HTMX Documentation](https://htmx.org/)
6. [Tailwind CSS Documentation](https://tailwindcss.com/)
