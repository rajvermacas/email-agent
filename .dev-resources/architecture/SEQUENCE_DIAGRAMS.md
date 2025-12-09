# Info-Agent: Sequence Flow Diagrams

This document contains detailed sequence diagrams for the Info-Agent system's core workflows.

---

## Table of Contents

1. [Email Channel - Happy Path](#1-email-channel---happy-path)
2. [Email Channel - Escalation Path (OOO)](#2-email-channel---escalation-path-ooo)
3. [Email Channel - Multi-Turn Conversation](#3-email-channel---multi-turn-conversation)
4. [Email Channel - Retry Flow](#4-email-channel---retry-flow)
5. [SharePoint Channel Flow](#5-sharepoint-channel-flow)
6. [Complete System Overview](#6-complete-system-overview)

---

## 1. Email Channel - Happy Path

This diagram shows the successful flow when a user requests information via email and receives a satisfactory response.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant UI as CopilotKit UI
    participant CR as CopilotKit Runtime
    participant S as Supervisor Agent
    participant E as Email Agent
    participant D as Directory Agent
    participant MG as Microsoft Graph API
    participant R as Recipient (Raj)

    U->>UI: "Get employee list from Raj"
    UI->>CR: HTTP POST (AG-UI Protocol)
    CR->>S: Route request

    Note over S: Parse intent<br/>Channel: EMAIL<br/>Target: Raj

    S->>E: Delegate to Email Agent

    E->>D: Resolve "Raj" to email
    D->>MG: Azure AD Query
    MG-->>D: raj@company.com
    D-->>E: raj@company.com

    E->>D: Check OOO status
    D->>MG: Calendar Query
    MG-->>D: Available (not OOO)
    D-->>E: Available

    Note over E: Compose contextual<br/>professional email

    E->>MG: Send Email (Graph API)
    MG-->>E: Email Sent (Message ID)

    Note over E: Status: AWAITING_REPLY<br/>Create Webhook Subscription

    E->>MG: Create Webhook Subscription
    MG-->>E: Subscription Created

    Note over MG,R: Email delivered to Raj

    R->>MG: Reply with employee list
    MG->>E: Webhook Notification (Reply Received)

    Note over E: Analyze Reply (LLM)<br/>Result: SATISFACTORY

    E->>E: Extract Information
    E-->>S: Return extracted data
    S-->>CR: Consolidated response
    CR-->>UI: Stream response (AG-UI)
    UI-->>U: "Employee list: Alice, Bob, Carol..."
```

---

## 2. Email Channel - Escalation Path (OOO)

This diagram shows the flow when the target recipient is Out-of-Office and the system escalates to their manager.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant S as Supervisor Agent
    participant E as Email Agent
    participant D as Directory Agent
    participant MG as Microsoft Graph API
    participant R as Raj (OOO)
    participant M as Manager

    U->>S: "Get info from Raj"
    S->>E: Delegate to Email Agent

    E->>D: Resolve "Raj" to email
    D->>MG: Azure AD Query
    MG-->>D: raj@company.com
    D-->>E: raj@company.com

    E->>D: Check OOO status
    D->>MG: Calendar Query
    MG-->>D: OOO = TRUE (Until Dec 20)
    D-->>E: OOO Status Confirmed

    Note over E: Recipient unavailable<br/>Initiate Escalation

    E->>D: Get Manager for Raj
    D->>MG: Directory Query (manager)
    MG-->>D: manager@company.com
    D-->>E: manager@company.com

    E->>D: Check Manager OOO status
    D->>MG: Calendar Query
    MG-->>D: Available
    D-->>E: Manager Available

    Note over E: Compose email to Manager<br/>Include: "Raj is OOO until Dec 20"

    E->>MG: Send Email to Manager
    MG-->>E: Email Sent

    Note over E: Log escalation in audit

    E->>MG: Create Webhook Subscription

    M->>MG: Reply with requested info
    MG->>E: Webhook Notification

    Note over E: Analyze Reply (LLM)<br/>Result: SATISFACTORY

    E-->>S: Return extracted data
    S-->>U: Response + "Note: Escalated to manager (Raj OOO)"
```

---

## 3. Email Channel - Multi-Turn Conversation

This diagram shows autonomous multi-turn conversation handling when the recipient needs clarification.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant E as Email Agent
    participant LLM as LLM (GPT-4)
    participant MG as Microsoft Graph API
    participant R as Raj (Recipient)

    U->>E: "Get Engineering employee list from Raj"

    Note over E: Compose initial request

    E->>MG: Send Email<br/>"Please provide Engineering employee list"
    MG-->>R: Email delivered

    R->>MG: Reply: "Which location?<br/>We have NY, SF, and London"
    MG->>E: Webhook: Reply received

    E->>LLM: Analyze reply
    Note over LLM: Classification:<br/>CLARIFICATION_NEEDED<br/>(Recipient asking question)
    LLM-->>E: CLARIFICATION_NEEDED

    Note over E: Exchange Count: 1/5<br/>Agent formulates response<br/>using original context

    E->>LLM: Generate clarification response
    LLM-->>E: "All locations please"

    E->>MG: Send Reply<br/>"All locations please"
    MG-->>R: Reply delivered

    R->>MG: Reply: "Here's the list:<br/>NY: Alice, Bob<br/>SF: Carol, Dave<br/>London: Eve, Frank"
    MG->>E: Webhook: Reply received

    E->>LLM: Analyze reply
    Note over LLM: Classification:<br/>SATISFACTORY<br/>(Complete answer received)
    LLM-->>E: SATISFACTORY

    Note over E: Exchange Count: 2/5<br/>Extract & Return

    E->>LLM: Extract structured data
    LLM-->>E: Parsed employee list

    E-->>U: Return complete employee list
```

---

## 4. Email Channel - Retry Flow

This diagram shows the retry mechanism when email sending fails.

```mermaid
sequenceDiagram
    autonumber
    participant E as Email Agent
    participant MG as Microsoft Graph API
    participant U as User
    participant AL as Audit Log

    E->>MG: Send Email (Attempt 1)
    MG--xE: Error: Service Unavailable (503)

    E->>AL: Log failure (attempt 1)

    Note over E: Retry Count: 1/3<br/>Wait with exponential backoff

    E->>MG: Send Email (Attempt 2)
    MG--xE: Error: Rate Limited (429)

    E->>AL: Log failure (attempt 2)

    Note over E: Retry Count: 2/3<br/>Wait with exponential backoff

    E->>MG: Send Email (Attempt 3)
    MG--xE: Error: Timeout

    E->>AL: Log failure (attempt 3)

    Note over E: Retry Count: 3/3<br/>Max retries exhausted

    E->>AL: Log permanent failure

    E->>MG: Send failure notification to User
    MG-->>U: "Failed to send email after 3 attempts"

    E-->>E: Update status: FAILED
```

---

## 5. SharePoint Channel Flow

This diagram shows the flow when a user explicitly requests information from SharePoint.

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant S as Supervisor Agent
    participant SP as SharePoint Agent
    participant MG as Microsoft Graph API
    participant LLM as LLM (GPT-4)

    U->>S: "Get project list from SharePoint"

    Note over S: Parse intent<br/>Channel: SHAREPOINT<br/>Keywords: "from SharePoint"

    S->>SP: Delegate to SharePoint Agent

    SP->>MG: Query SharePoint Sites
    MG-->>SP: Site list

    SP->>MG: Query Lists in target site
    MG-->>SP: List data

    SP->>LLM: Parse and extract relevant data
    LLM-->>SP: Structured project list

    SP-->>S: Return structured data
    S-->>U: "Projects: Project A, Project B..."
```

---

## 6. Complete System Overview

This diagram provides a high-level overview of all system components and their interactions.

```mermaid
sequenceDiagram
    autonumber
    box User Interface
        participant U as User
        participant UI as React + CopilotKit
    end

    box Backend Services
        participant CR as CopilotKit Runtime<br/>(FastAPI)
        participant S as Supervisor Agent
    end

    box Specialized Agents
        participant E as Email Agent
        participant SP as SharePoint Agent
        participant D as Directory Agent
    end

    box External Services
        participant MG as Microsoft Graph
        participant DB as PostgreSQL
    end

    U->>UI: Submit request
    UI->>CR: AG-UI Protocol (SSE)
    CR->>S: Process request

    S->>DB: Create audit log entry
    S->>DB: Save checkpoint (PostgresSaver)

    alt Email Channel
        S->>E: Route to Email Agent
        E->>D: User lookup (A2A Protocol)
        D->>MG: Azure AD / Calendar
        MG-->>D: User info + OOO status
        D-->>E: Resolved user data
        E->>MG: Send email / Create webhook
        MG-->>E: Confirmation

        loop Multi-turn (max 5)
            MG->>E: Webhook: Reply received
            E->>E: Analyze & respond
        end

        E-->>S: Extracted information
    else SharePoint Channel
        S->>SP: Route to SharePoint Agent
        SP->>MG: Query lists/documents
        MG-->>SP: Data
        SP-->>S: Parsed results
    end

    S->>DB: Update audit log
    S->>DB: Save final checkpoint
    S-->>CR: Response
    CR-->>UI: Stream response
    UI-->>U: Display result
```

---

## Webhook Lifecycle Sequence

This diagram details the webhook subscription management for email monitoring.

```mermaid
sequenceDiagram
    autonumber
    participant E as Email Agent
    participant MG as Microsoft Graph
    participant WH as Webhook Handler<br/>(FastAPI)
    participant DB as PostgreSQL

    Note over E: After sending email

    E->>MG: POST /subscriptions<br/>Resource: /users/{id}/mailFolders/inbox/messages<br/>changeType: created<br/>expirationDateTime: +3 days
    MG->>WH: Validation request (validationToken)
    WH-->>MG: Return validationToken
    MG-->>E: Subscription created (subscriptionId)

    E->>DB: Store subscription metadata<br/>(id, expiration, thread_id)

    Note over MG: Email reply arrives

    MG->>WH: POST /webhooks/email<br/>changeType: created<br/>resourceData: message
    WH->>WH: Validate clientState
    WH->>E: Notify: New reply
    WH-->>MG: 202 Accepted

    Note over E: Process reply...

    loop Daily Renewal Check
        E->>DB: Check expiring subscriptions
        DB-->>E: Subscriptions expiring in <24h
        E->>MG: PATCH /subscriptions/{id}<br/>Extend expirationDateTime
        MG-->>E: Subscription renewed
        E->>DB: Update expiration
    end

    Note over E: Fallback: Delta Query

    loop Every 5-10 minutes
        E->>MG: GET /users/{id}/messages/delta
        MG-->>E: Changed messages since last sync
        E->>E: Process any missed replies
    end
```

---

## Legend

| Symbol | Meaning |
|--------|---------|
| `->>`  | Synchronous request |
| `-->>` | Response |
| `--x`  | Failed request |
| `Note` | Important state or action |
| `alt`  | Alternative paths |
| `loop` | Repeated action |
| `box`  | Logical grouping |

---

## References

- [Architecture Document](./ARCHITECTURE.md)
- [LangGraph Documentation](https://www.langchain.com/langgraph)
- [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/)
- [Mermaid Sequence Diagram Syntax](https://mermaid.js.org/syntax/sequenceDiagram.html)
