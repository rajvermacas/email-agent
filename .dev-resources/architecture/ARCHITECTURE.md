# Info-Agent: Multi-Channel Information Retrieval System

## Architecture Document

**Version**: 1.0
**Date**: December 2025
**Status**: Finalized Design

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Overview](#2-system-overview)
3. [Functional Requirements](#3-functional-requirements)
4. [Architecture Design](#4-architecture-design)
5. [Component Details](#5-component-details)
6. [Data Flow](#6-data-flow)
7. [Technology Stack](#7-technology-stack)
8. [Integration Points](#8-integration-points)
9. [State Management](#9-state-management)
10. [Security Considerations](#10-security-considerations)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Best Practices](#12-best-practices)
13. [Anti-Patterns to Avoid](#13-anti-patterns-to-avoid)

---

## 1. Executive Summary

Info-Agent is a multi-channel agentic system designed to retrieve information through **Email** and **SharePoint** channels. The system enables autonomous, multi-turn conversations where an AI agent can:

- Send emails to employees requesting specific information
- Handle clarifying questions from both sides (agent and recipient)
- Automatically escalate to line managers when employees are on leave
- Query SharePoint lists and documents when explicitly requested by the user

**Key Design Decisions**:
- Channel selection (Email vs SharePoint) is **explicitly user-driven**, not agent-decided
- Email conversations are **fully autonomous** with multi-turn support
- Maximum 3 retries for failed email sends
- Maximum 5 conversation exchanges before escalation
- All interactions are audited

---

## 2. System Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                    CopilotKit + React (AG-UI Protocol)                    │  │
│  │                    useCoAgent hook for streaming responses                │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COPILOTKIT RUNTIME (FastAPI)                           │
│                           AG-UI Protocol Handler                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           LANGGRAPH ORCHESTRATION                                │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                         SUPERVISOR AGENT                                   │  │
│  │  • Parses user intent (Email vs SharePoint - user-driven)                 │  │
│  │  • Routes to appropriate channel agent                                    │  │
│  │  • Manages conversation lifecycle                                         │  │
│  │  • Tracks request state (pending, in-progress, completed, failed)         │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                        │                                         │
│          ┌─────────────────────────────┼─────────────────────────────┐          │
│          ▼                             ▼                             ▼          │
│  ┌───────────────┐           ┌───────────────┐            ┌───────────────┐     │
│  │  EMAIL AGENT  │           │  SHAREPOINT   │            │  DIRECTORY    │     │
│  │  (Subgraph)   │           │    AGENT      │            │    AGENT      │     │
│  │               │           │               │            │               │     │
│  │ • Compose     │           │ • Query Lists │            │ • Lookup User │     │
│  │ • Send        │           │ • Search Docs │            │ • Get Manager │     │
│  │ • Converse    │           │ • Parse Data  │            │ • Check OOO   │     │
│  │ • Extract     │           │               │            │               │     │
│  │ • Retry (3x)  │           │               │            │               │     │
│  └───────────────┘           └───────────────┘            └───────────────┘     │
│          │                                                       │              │
│          │              A2A Protocol (Inter-Agent)               │              │
│          └───────────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PERSISTENCE LAYER                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │  PostgresSaver  │  │   Audit Log     │  │     Email Thread Store          │  │
│  │  (Checkpoints)  │  │                 │  │   (Conversation Context)        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          MICROSOFT GRAPH API                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Outlook   │  │ SharePoint  │  │  Azure AD   │  │  Calendar   │            │
│  │    Mail     │  │    Sites    │  │   (Entra)   │  │   (OOO)     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │     Webhook Subscriptions + Delta Query Fallback (Hybrid Pattern)       │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Principles

1. **User-Driven Channel Selection**: The agent does NOT decide whether to use Email or SharePoint. The user explicitly specifies the channel.
2. **Autonomous Conversations**: The email agent can autonomously handle multi-turn conversations with recipients.
3. **Graceful Degradation**: If email fails, retry up to 3 times. If recipient is unavailable, escalate to manager.
4. **Full Context Preservation**: All conversation history is maintained to prevent LLM performance degradation.
5. **Audit Everything**: All requests, responses, and actions are logged for compliance.

---

## 3. Functional Requirements

### 3.1 Email Channel

| Requirement | Description |
|-------------|-------------|
| **Send Request** | Compose and send professional email requesting specific information |
| **Monitor Replies** | Real-time monitoring via webhooks + delta query fallback |
| **Parse Responses** | LLM-based extraction of relevant information from replies |
| **Handle Clarifications** | Agent can answer clarifying questions from recipient |
| **Ask Follow-ups** | Agent can request more information if response is insufficient |
| **Escalation** | Auto-forward to line manager if recipient is OOO |
| **Retry Logic** | 3 retries for failed email sends |
| **Timeout** | 48-hour timeout, then escalate or notify user |
| **Error Notification** | Email user on failures |

### 3.2 SharePoint Channel

| Requirement | Description |
|-------------|-------------|
| **Query Lists** | Retrieve data from SharePoint lists |
| **Search Documents** | Search document libraries |
| **Parse Content** | Extract relevant information from results |

### 3.3 Directory Services

| Requirement | Description |
|-------------|-------------|
| **User Lookup** | Resolve user names to email addresses |
| **Manager Hierarchy** | Get user's direct manager for escalation |
| **OOO Status** | Check calendar for Out-of-Office status |

### 3.4 Audit & Logging

| Requirement | Description |
|-------------|-------------|
| **Request Logging** | Who requested what information from whom |
| **Action Logging** | All emails sent, responses received |
| **Error Logging** | All failures with context |

---

## 4. Architecture Design

### 4.1 Protocol Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    PROTOCOL RELATIONSHIPS                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  AG-UI Protocol                                             │
│  └── User ←→ Frontend ←→ Backend                           │
│      (Streaming responses, state sync, UI events)          │
│                                                             │
│  A2A Protocol                                               │
│  └── Agent ←→ Agent                                        │
│      (Email Agent ←→ Directory Agent)                      │
│      (Supervisor ←→ Specialized Agents)                    │
│                                                             │
│  Microsoft Graph API                                        │
│  └── Agent ←→ Microsoft 365                                │
│      (Email, SharePoint, Calendar, Azure AD)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Agent Architecture Pattern

**Selected Pattern**: Supervisor + Specialized Agents + Subgraphs

```
                    ┌─────────────────┐
                    │   Supervisor    │
                    │    (LangGraph)  │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
       ┌────▼─────┐  ┌──────▼──────┐  ┌─────▼────┐
       │  Email   │  │ SharePoint  │  │Directory │
       │  Agent   │  │   Agent     │  │  Agent   │
       │(Subgraph)│  │             │  │          │
       └────┬─────┘  └──────┬──────┘  └─────┬────┘
            │                │                │
            └────────────────┼────────────────┘
                             │
                    ┌────────▼────────┐
                    │ Consolidated    │
                    │    Response     │
                    └─────────────────┘
```

**Why This Pattern**:
- Clear task specialization
- Agents have focused responsibilities
- Supervisor maintains oversight
- Subgraphs provide modularity
- Easy to add new channels

---

## 5. Component Details

### 5.1 Supervisor Agent

**Responsibilities**:
- Parse user intent to determine channel and target
- Route requests to appropriate channel agent
- Track overall request lifecycle
- Aggregate final response to user
- Handle cross-cutting concerns (timeout, escalation)

**Routing Logic**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER REQUEST PARSING                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User: "Get employee list from Raj"                             │
│         └──────────────────────────┘                            │
│                    │                                            │
│                    ▼                                            │
│         ┌─────────────────────┐                                 │
│         │   INTENT PARSER     │                                 │
│         │   (LLM extracts)    │                                 │
│         └─────────────────────┘                                 │
│                    │                                            │
│         ┌─────────┴─────────┐                                   │
│         ▼                   ▼                                   │
│  ┌─────────────┐     ┌─────────────┐                            │
│  │  Channel:   │     │  Channel:   │                            │
│  │   EMAIL     │     │ SHAREPOINT  │                            │
│  │             │     │             │                            │
│  │ Keywords:   │     │ Keywords:   │                            │
│  │ "from Raj"  │     │ "from SP"   │                            │
│  │ "ask X"     │     │ "in SharePoint"                          │
│  │ "email to"  │     │ "SP list"   │                            │
│  │ "contact"   │     │ "document"  │                            │
│  └─────────────┘     └─────────────┘                            │
│                                                                 │
│  KEY: Channel is determined by USER'S explicit instruction      │
│       NOT by agent's decision                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Email Agent (Subgraph)

**Responsibilities**:
- Compose contextual, professional emails
- Send emails via Microsoft Graph
- Monitor for replies (webhook + delta query)
- Parse responses using LLM
- Handle multi-turn conversations autonomously
- Retry failed sends (max 3)
- Escalate to manager if recipient OOO

**State Machine**:

```
                              ┌─────────────────┐
                              │     START       │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ COMPOSE_EMAIL   │
                              │ (LLM generates  │
                              │  contextual     │
                              │  request)       │
                              └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  SEND_EMAIL     │◀──────────────────┐
                              │  (Graph API)    │                   │
                              └────────┬────────┘                   │
                                       │                            │
                          ┌────────────┴────────────┐               │
                          ▼                         ▼               │
                   ┌─────────────┐          ┌─────────────┐         │
                   │   SUCCESS   │          │   FAILED    │         │
                   └──────┬──────┘          └──────┬──────┘         │
                          │                        │                │
                          │                        ▼                │
                          │               ┌─────────────┐           │
                          │               │   RETRY     │           │
                          │               │ (max 3x)    │───────────┘
                          │               └──────┬──────┘
                          │                      │ (exhausted)
                          │                      ▼
                          │               ┌─────────────┐
                          │               │NOTIFY_USER_ │
                          │               │  FAILURE    │
                          │               └─────────────┘
                          ▼
                 ┌─────────────────┐
                 │ AWAIT_REPLY    │
                 │ (Webhook/Poll) │
                 │ Timeout: 48hrs │
                 └────────┬───────┘
                          │
            ┌─────────────┼─────────────┐
            ▼             │             ▼
    ┌─────────────┐       │     ┌─────────────┐
    │  TIMEOUT    │       │     │REPLY_RECEIVED│
    │ (Escalate   │       │     └──────┬──────┘
    │ to Manager) │       │            │
    └─────────────┘       │            ▼
                          │   ┌─────────────────┐
                          │   │ ANALYZE_REPLY   │
                          │   │ (LLM parsing)   │
                          │   └────────┬────────┘
                          │            │
                          │  ┌─────────┴─────────┬────────────────┐
                          │  ▼                   ▼                ▼
                          │ ┌──────────┐  ┌──────────────┐  ┌──────────────┐
                          │ │SATISFACTORY│ │CLARIFICATION│  │INSUFFICIENT  │
                          │ │ ANSWER    │  │ NEEDED BY   │  │ RESPONSE     │
                          │ │           │  │  RECIPIENT  │  │              │
                          │ └─────┬─────┘  └──────┬──────┘  └──────┬───────┘
                          │       │               │                │
                          │       ▼               ▼                ▼
                          │ ┌──────────┐  ┌──────────────┐  ┌──────────────┐
                          │ │ EXTRACT  │  │ AUTO_REPLY   │  │ ASK_MORE     │
                          │ │ & RETURN │  │ (Answer      │  │ (Agent asks  │
                          │ │ TO USER  │  │  recipient's │  │ recipient    │
                          │ └──────────┘  │  questions)  │  │ for more)    │
                          │               └──────┬───────┘  └──────┬───────┘
                          │                      │                 │
                          │                      └────────┬────────┘
                          │                               │
                          └───────────────────────────────┘
                                    (Loop back to AWAIT_REPLY)
                                    (Max 5 exchanges)
```

### 5.3 SharePoint Agent

**Responsibilities**:
- Query SharePoint lists based on user criteria
- Search document libraries
- Parse and extract relevant data
- Return structured results

**Invocation**: Only when user explicitly requests SharePoint

### 5.4 Directory Agent

**Responsibilities**:
- Resolve user names to email addresses (Azure AD)
- Fetch manager hierarchy for escalation
- Check OOO/calendar status

**Used By**: Email Agent (before sending, for escalation)

---

## 6. Data Flow

### 6.1 Email Channel Flow (Happy Path)

```
User                 Supervisor         Email Agent        Directory Agent      MS Graph
 │                       │                   │                   │                 │
 │  "Get employee        │                   │                   │                 │
 │   list from Raj"      │                   │                   │                 │
 │──────────────────────▶│                   │                   │                 │
 │                       │                   │                   │                 │
 │                       │  Route to Email   │                   │                 │
 │                       │──────────────────▶│                   │                 │
 │                       │                   │                   │                 │
 │                       │                   │  Resolve "Raj"    │                 │
 │                       │                   │──────────────────▶│                 │
 │                       │                   │                   │  Azure AD Query │
 │                       │                   │                   │────────────────▶│
 │                       │                   │                   │◀────────────────│
 │                       │                   │◀──────────────────│  raj@company.com│
 │                       │                   │                   │                 │
 │                       │                   │  Check OOO        │                 │
 │                       │                   │──────────────────▶│                 │
 │                       │                   │                   │  Calendar Query │
 │                       │                   │                   │────────────────▶│
 │                       │                   │◀──────────────────│  Available      │
 │                       │                   │                   │                 │
 │                       │                   │  Compose & Send Email              │
 │                       │                   │─────────────────────────────────────▶│
 │                       │                   │                                     │
 │                       │                   │  [AWAIT REPLY - Webhook]            │
 │                       │                   │◀─────────────────────────────────────│
 │                       │                   │                   │  Reply received │
 │                       │                   │                   │                 │
 │                       │                   │  Parse & Extract  │                 │
 │                       │                   │  (LLM)            │                 │
 │                       │                   │                   │                 │
 │                       │◀──────────────────│  Satisfactory     │                 │
 │                       │                   │                   │                 │
 │◀──────────────────────│  Return Result    │                   │                 │
 │  "Employee list:..."  │                   │                   │                 │
```

### 6.2 Email Channel Flow (Escalation Path)

```
User                 Supervisor         Email Agent        Directory Agent      MS Graph
 │                       │                   │                   │                 │
 │  "Get info from Raj"  │                   │                   │                 │
 │──────────────────────▶│                   │                   │                 │
 │                       │──────────────────▶│                   │                 │
 │                       │                   │──────────────────▶│                 │
 │                       │                   │◀──────────────────│  raj@company.com│
 │                       │                   │──────────────────▶│                 │
 │                       │                   │◀──────────────────│  OOO = TRUE     │
 │                       │                   │                   │                 │
 │                       │                   │  Get Manager      │                 │
 │                       │                   │──────────────────▶│                 │
 │                       │                   │◀──────────────────│ manager@co.com  │
 │                       │                   │                   │                 │
 │                       │                   │  Check Manager OOO│                 │
 │                       │                   │──────────────────▶│                 │
 │                       │                   │◀──────────────────│  Available      │
 │                       │                   │                   │                 │
 │                       │                   │  Send to Manager  │                 │
 │                       │                   │─────────────────────────────────────▶│
 │                       │                   │  (Note: Raj is OOO)                 │
 │                       │                   │                   │                 │
 │                       │                   │  ... continue flow ...              │
```

### 6.3 Multi-Turn Conversation Flow

```
Email Agent                          Raj (Recipient)                    LLM
    │                                      │                             │
    │  Email: "Please provide             │                             │
    │   employee list for Engineering"     │                             │
    │─────────────────────────────────────▶│                             │
    │                                      │                             │
    │  Reply: "Which location?            │                             │
    │   We have NY, SF, and London"        │                             │
    │◀─────────────────────────────────────│                             │
    │                                      │                             │
    │  Analyze Reply ─────────────────────────────────────────────────────▶│
    │◀─────────────────────────────────────────────────────────────────────│
    │  Result: CLARIFICATION_NEEDED        │                             │
    │                                      │                             │
    │  [Agent uses original context        │                             │
    │   to formulate response]             │                             │
    │                                      │                             │
    │  Reply: "All locations please"      │                             │
    │─────────────────────────────────────▶│                             │
    │                                      │                             │
    │  Reply: "Here's the list:           │                             │
    │   NY: Alice, Bob...                  │                             │
    │   SF: Carol, Dave..."                │                             │
    │◀─────────────────────────────────────│                             │
    │                                      │                             │
    │  Analyze Reply ─────────────────────────────────────────────────────▶│
    │◀─────────────────────────────────────────────────────────────────────│
    │  Result: SATISFACTORY                │                             │
    │                                      │                             │
    │  Extract & Return to User            │                             │
```

---

## 7. Technology Stack

### 7.1 Core Technologies

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Frontend** | React | 18+ | User interface |
| **Frontend Framework** | CopilotKit | CoAgents v0.2 | Agent UI components, AG-UI protocol |
| **Backend** | FastAPI | Latest | API server, webhook handler |
| **Orchestration** | LangGraph | v0.2+ | Agent orchestration, state machine |
| **Agent Protocol** | A2A | v1.0.0 | Inter-agent communication |
| **UI Protocol** | AG-UI | Latest | Frontend-agent streaming |
| **State Persistence** | PostgreSQL | 15+ | Checkpointing, audit logs |
| **Checkpointer** | PostgresSaver | Latest | LangGraph state persistence |
| **Observability** | LangSmith | Latest | Tracing, debugging |
| **LLM** | Azure OpenAI | GPT-4 | Intent parsing, email composition |

### 7.2 Microsoft Integration

| Service | API | Purpose |
|---------|-----|---------|
| **Outlook** | Microsoft Graph | Send/receive emails |
| **SharePoint** | Microsoft Graph | Query lists, search docs |
| **Azure AD (Entra)** | Microsoft Graph | User lookup, manager hierarchy |
| **Calendar** | Microsoft Graph | OOO status |

### 7.3 Python Dependencies

```
langgraph>=0.2.0
langchain>=0.1.0
langchain-openai>=0.0.5
copilotkit>=0.1.0
fastapi>=0.109.0
uvicorn>=0.27.0
msgraph-sdk>=1.0.0
azure-identity>=1.15.0
psycopg2-binary>=2.9.9
sqlalchemy>=2.0.0
pydantic>=2.5.0
python-dotenv>=1.0.0
```

### 7.4 Frontend Dependencies

```json
{
  "@copilotkit/react-core": "^0.1.72",
  "@copilotkit/react-ui": "^0.1.72",
  "react": "^18.2.0",
  "react-dom": "^18.2.0"
}
```

---

## 8. Integration Points

### 8.1 Integration Summary

| Integration | Protocol/API | Direction | Purpose |
|-------------|--------------|-----------|---------|
| User → System | REST + AG-UI (SSE) | Bidirectional | User requests, streaming responses |
| System → Outlook | Microsoft Graph | Bidirectional | Send/receive emails |
| Outlook → System | Graph Webhooks | Inbound | Real-time email notifications |
| System → SharePoint | Microsoft Graph | Outbound | Query data |
| System → Azure AD | Microsoft Graph | Outbound | User/manager lookup |
| System → Calendar | Microsoft Graph | Outbound | OOO status |
| Agent → Agent | A2A Protocol | Bidirectional | Inter-agent communication |
| System → LLM | Azure OpenAI API | Outbound | NLU, composition, extraction |
| System → DB | PostgreSQL | Bidirectional | State, audit logs |

### 8.2 Email Webhook Pattern (Hybrid)

```
┌────────────────────────────────────────────────────────────────┐
│                     EMAIL MONITORING STRATEGY                   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  PRIMARY: Webhook Subscription                                 │
│  ├── Resource: /users/{email}/mailFolders/inbox/messages      │
│  ├── Change Types: created, updated                           │
│  ├── Expiration: 3 days max                                    │
│  ├── Renewal: 1 day before expiration                         │
│  └── Validation: clientState parameter                        │
│                                                                │
│  FALLBACK: Delta Query                                         │
│  ├── Frequency: Every 5-10 minutes                            │
│  ├── Purpose: Catch missed webhook notifications              │
│  └── Recovery: If token expires, retries for 4 hours          │
│                                                                │
│  WHY HYBRID?                                                   │
│  • Webhooks expire in 3-4 days                                 │
│  • Webhooks fail if OAuth token expires                        │
│  • Delta queries provide reliable fallback                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 8.3 Authentication

**Pattern**: App-Only Authentication (Daemon App)

```python
from azure.identity import ClientSecretCredential
from msgraph.generated import GraphServiceClient

credential = ClientSecretCredential(
    tenant_id=os.getenv("AZURE_TENANT_ID"),
    client_id=os.getenv("AZURE_CLIENT_ID"),
    client_secret=os.getenv("AZURE_CLIENT_SECRET")
)

client = GraphServiceClient(credential=credential)
```

**Required Permissions** (Application):
- `Mail.ReadWrite` - Read/send emails
- `Mail.Send` - Send emails on behalf of users
- `Calendars.Read` - Check OOO status
- `User.Read.All` - User lookup
- `Directory.Read.All` - Manager hierarchy
- `Sites.Read.All` - SharePoint queries

---

## 9. State Management

### 9.1 LangGraph State Schema

```python
from typing import TypedDict, Annotated, Literal
from langchain_core.messages import BaseMessage
import operator

class InfoAgentState(TypedDict):
    """Main state for the Info-Agent system"""

    # Conversation messages (auto-appending)
    messages: Annotated[list[BaseMessage], operator.add]

    # Request metadata
    request_id: str
    user_id: str
    channel: Literal["email", "sharepoint"]
    target_person: str | None
    target_location: str | None
    information_needed: str

    # Email-specific state
    email_thread_id: str | None
    email_threads: list[dict]
    recipient_email: str | None
    escalation_chain: list[str]
    retry_count: int
    exchange_count: int

    # Request lifecycle
    status: Literal["pending", "in_progress", "awaiting_reply",
                    "completed", "failed", "escalated"]

    # Results
    extracted_information: str | None
    error_message: str | None


class EmailConversationState(TypedDict):
    """State for email subgraph"""

    messages: Annotated[list[BaseMessage], operator.add]
    thread_id: str
    thread_history: list[dict]  # Full email thread
    current_recipient: str
    original_request: str
    draft_response: str | None
    analysis_result: Literal["satisfactory", "clarification_needed",
                             "insufficient", "off_topic"]
    exchange_count: int
    max_exchanges: int  # Default: 5
```

### 9.2 Checkpointing

```python
from langgraph.checkpoint.postgres import PostgresSaver

# Production checkpointer
checkpointer = PostgresSaver(
    conn_string="postgresql://user:password@localhost:5432/info_agent"
)

# Compile graph with checkpointer
graph = graph_builder.compile(checkpointer=checkpointer)

# Use with thread ID for persistence
config = {"configurable": {"thread_id": f"request-{request_id}"}}
result = graph.invoke(initial_state, config=config)
```

### 9.3 Audit Log Schema

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL,  -- 'request_created', 'email_sent', 'reply_received', etc.
    channel VARCHAR(20),          -- 'email', 'sharepoint'
    target VARCHAR(255),          -- recipient email or SharePoint location
    details JSONB,                -- additional context
    status VARCHAR(20),           -- 'success', 'failure'
    error_message TEXT
);

CREATE INDEX idx_audit_request_id ON audit_logs(request_id);
CREATE INDEX idx_audit_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp);
```

---

## 10. Security Considerations

### 10.1 Authentication & Authorization

| Layer | Mechanism |
|-------|-----------|
| User → API | API Key / OAuth 2.0 |
| API → Microsoft Graph | App-Only OAuth 2.0 (Client Credentials) |
| Webhook Validation | clientState parameter verification |

### 10.2 Security Checklist

- [ ] Store secrets in environment variables (never in code)
- [ ] Use Azure Key Vault for production secrets
- [ ] Validate `clientState` on all webhook callbacks
- [ ] Implement rate limiting on API endpoints
- [ ] Sanitize user inputs to prevent prompt injection
- [ ] Use HTTPS for all communications
- [ ] Implement request timeouts
- [ ] Log security events (auth failures, suspicious activity)
- [ ] Rotate credentials regularly
- [ ] Encrypt PII at rest and in transit

### 10.3 Input Validation

```python
import re

def sanitize_user_input(user_input: str) -> str:
    """Prevent prompt injection and validate input"""

    if not user_input:
        raise ValueError("Input cannot be empty")

    if len(user_input) > 10000:
        raise ValueError("Input exceeds maximum length")

    # Basic character validation (adjust as needed)
    if not re.match(r"^[\w\s.,!?()'\"-@]+$", user_input):
        raise ValueError("Input contains invalid characters")

    return user_input.strip()
```

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

| Task | Description |
|------|-------------|
| Project setup | Create Python project structure, dependencies |
| LangGraph core | Implement basic graph with PostgresSaver |
| State schemas | Define all state types |
| Supervisor agent | Implement intent parsing and routing |
| Basic tests | Unit tests for core components |

**Deliverable**: Running LangGraph with state persistence

### Phase 2: Email Agent (Week 3-4)

| Task | Description |
|------|-------------|
| Email composition | LLM-based email drafting |
| Graph API integration | Send emails via Microsoft Graph |
| Webhook setup | Email notification subscriptions |
| Delta query fallback | Implement hybrid monitoring |
| Reply parsing | LLM-based response analysis |
| Multi-turn logic | Conversation state machine |

**Deliverable**: Functional email agent with multi-turn support

### Phase 3: Directory & SharePoint (Week 5-6)

| Task | Description |
|------|-------------|
| Directory agent | User lookup, manager hierarchy |
| OOO detection | Calendar API integration |
| Escalation logic | Auto-forward to manager |
| SharePoint agent | List queries, document search |
| Integration tests | End-to-end tests |

**Deliverable**: Complete backend with all agents

### Phase 4: Frontend (Week 7-8)

| Task | Description |
|------|-------------|
| CopilotKit setup | React + CopilotKit integration |
| AG-UI streaming | Real-time response streaming |
| UI components | Chat interface, status indicators |
| State sync | Frontend-backend state synchronization |
| Error handling UI | User-friendly error messages |

**Deliverable**: Functional web UI

### Phase 5: Production Hardening (Week 9-10)

| Task | Description |
|------|-------------|
| Audit logging | Complete audit trail |
| Error handling | Comprehensive error recovery |
| Monitoring | LangSmith integration, metrics |
| Security review | Penetration testing, code review |
| Load testing | Performance validation |
| Documentation | API docs, runbooks |

**Deliverable**: Production-ready system

---

## 12. Best Practices

### 12.1 Agent Design

```
DO:
├── Each agent has single, well-defined responsibility
├── Agent prompts are clear, concise, and specific
├── Agents have appropriate tools for their domain
├── Agent failures are isolated (don't cascade)
└── Agents provide clear reasoning for decisions

DON'T:
├── Single agent with 50+ tools
├── Vague instructions like "research the topic"
├── Agents making decisions outside their domain
└── Swallowing errors silently
```

### 12.2 State Management

```python
# DO: Use reducer for message lists
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]

# DO: Return only changed keys
def my_node(state: AgentState):
    return {"messages": [new_message]}  # Only messages updated

# DON'T: Return entire state
def bad_node(state: AgentState):
    return {**state, "messages": state["messages"] + [new_message]}
```

### 12.3 Email Context

```
CRITICAL: LLMs experience 39% performance drop in multi-turn conversations
          without full context.

DO:
├── Include FULL thread history in LLM context
├── Maintain structured thread metadata
├── Preserve sender relationships
└── Use checkpointing to avoid re-processing

DON'T:
├── Pass only the latest email to LLM
├── Lose thread context between turns
└── Forget who said what
```

### 12.4 Webhook Management

```
DO:
├── Track subscription IDs and expiration times
├── Renew subscriptions 1 day before expiration
├── Implement delta query as fallback
├── Validate clientState on every callback
└── Handle lifecycle notifications

DON'T:
├── Create webhook and forget about expiration
├── Trust webhooks without validation
├── Rely solely on webhooks (they can fail)
└── Ignore token expiration
```

---

## 13. Anti-Patterns to Avoid

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| **Last-message-only context** | 39% LLM performance drop | Include full thread history |
| **Monolithic agent** | Unmanageable complexity | Separate specialized agents |
| **Webhook-only monitoring** | Missed notifications | Hybrid webhook + delta query |
| **No checkpointing** | Lost state on failures | PostgresSaver in production |
| **Hardcoded config** | Security risk, inflexible | Environment variables |
| **Silent failures** | Hidden bugs | Comprehensive logging |
| **Agent decides channel** | User confusion | User explicitly chooses |
| **Infinite conversation loops** | Resource waste | Max 5 exchanges limit |
| **No audit trail** | Compliance issues | Log all actions |
| **Synchronous webhook handler** | Timeouts | Async processing |

---

## Appendix A: Environment Variables

```bash
# Azure AD / Microsoft Graph
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

# OpenAI / Azure OpenAI
OPENAI_API_KEY=your-api-key
# OR for Azure OpenAI:
AZURE_OPENAI_API_KEY=your-azure-openai-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/info_agent

# LangSmith (Observability)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=info-agent

# Application
WEBHOOK_BASE_URL=https://your-domain.com/api/webhooks
API_KEY=your-api-key-for-clients
```

---

## Appendix B: API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/copilotkit` | POST | CopilotKit Runtime (AG-UI) |
| `/api/webhooks/email` | POST | Microsoft Graph email notifications |
| `/api/health` | GET | Health check |
| `/api/requests/{id}` | GET | Get request status |
| `/api/requests/{id}/cancel` | POST | Cancel pending request |

---

## Appendix C: References

### Official Documentation
- [LangGraph Documentation](https://www.langchain.com/langgraph)
- [A2A Protocol](https://a2a-protocol.org/)
- [AG-UI Protocol](https://docs.ag-ui.com/)
- [CopilotKit Documentation](https://docs.copilotkit.ai/)
- [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/)

### Research Documents
- [Multi-Agent Systems Research (2024-2025)](/workspaces/info-agent/resources/research/multi-agent-agentic-systems/)

---

*Document generated as part of Info-Agent architecture design session.*
