# A2A SDK Migration Mapping

**Migration Date**: 2025-12-13
**From**: Custom A2A Implementation (~1,675 lines)
**To**: Official a2a-sdk v0.3.21

---

## Class Mapping

| Custom Class | SDK Replacement | Import Change |
|-------------|-----------------|---------------|
| `info_agent.a2a.models.AgentCard` | `a2a.types.AgentCard` | `from a2a.types import AgentCard` |
| `info_agent.a2a.models.AgentSkill` | `a2a.types.AgentSkill` | `from a2a.types import AgentSkill` |
| `info_agent.a2a.models.A2ATaskRequest` | `a2a.types.Message` | `from a2a.types import Message` |
| `info_agent.a2a.models.A2ATaskResponse` | `a2a.types.Task` | `from a2a.types import Task` |
| `info_agent.a2a.client.A2AClient` | `a2a.client.Client` (via ClientFactory) | `from a2a.client.client_factory import ClientFactory` |
| `info_agent.a2a.models.RegisterAgentResponse` | Keep custom (registry-specific) | No change |

---

## Field Name Changes

### AgentCard
| Custom Field | SDK Field | Type |
|-------------|-----------|------|
| `defaultInputModes` | `default_input_modes` | snake_case |
| `defaultOutputModes` | `default_output_modes` | snake_case |
| All other fields | Same | No change |

### Task States
| Custom Status | SDK Status | Notes |
|--------------|------------|-------|
| `"submitted"` | `TaskStatus.submitted` | Enum |
| `"working"` | `TaskStatus.working` | Enum |
| `"completed"` | `TaskStatus.completed` | Enum |
| `"failed"` | `TaskStatus.failed` | Enum |
| `"cancelled"` | `TaskStatus.cancelled` | Enum |
| Missing | `TaskStatus.input_required` | NEW |
| Missing | `TaskStatus.rejected` | NEW |

---

## Method Signature Changes

### A2AClient → SDK Client

**Custom**:
```python
client = A2AClient(base_url="http://localhost:8001")
result = await client.send_task(
    agent_name="mail-agent",
    skill_id="send-email",
    payload={"to": "user@example.com"}
)
```

**SDK**:
```python
from a2a.client.client_factory import ClientFactory, ClientConfig
from a2a.types import Message, DataPart, Role

# Get agent card first
agent_card = await fetch_agent_card("http://localhost:8001")

# Create client
factory = ClientFactory(ClientConfig())
client = factory.create(agent_card)

# Send message (not task)
message = Message(
    role=Role.user,
    parts=[DataPart(data={"to": "user@example.com"})]
)

async for event in client.send_message(message):
    if isinstance(event, tuple) and isinstance(event[0], Task):
        task, update = event
        if task.status == TaskStatus.completed:
            result = task.history[-1].parts[0].data
```

---

## Endpoint Changes

| Custom Endpoint | SDK Endpoint | Protocol |
|----------------|--------------|----------|
| `POST /tasks` | JSON-RPC 2.0 via standard paths | JSON-RPC |
| `GET /.well-known/agent.json` | Same | HTTP |

---

## Components to Keep Custom

1. **Registry** (`a2a/registry.py`, `a2a/storage.py`)
   - Reason: A2A spec doesn't define centralized registry
   - Change: Update to use SDK models

2. **RegisterAgentResponse** model
   - Reason: Registry-specific response format
   - Change: None

---

## Files Affected by Migration

### Delete (4 files):
- `src/info_agent/a2a/models.py` (381 lines)
- `src/info_agent/a2a/client.py` (409 lines)
- `tests/unit/test_a2a_models.py` (~500 lines)
- `tests/unit/test_a2a_client.py` (~800 lines)

### Modify (15 files):
- `src/info_agent/agents/mail/agent.py` - Server migration
- `src/info_agent/agents/supervisor/agent.py` - Client migration
- `src/info_agent/workflow/nodes.py` - Client migration + fix bugs
- `src/info_agent/a2a/storage.py` - Use SDK models
- `src/info_agent/a2a/registry.py` - Use SDK models
- `src/info_agent/a2a/__init__.py` - Re-export SDK types
- Plus 9 test files

### Create (2 files):
- `src/info_agent/agents/mail/adapters.py` - Temporary adapter
- `.dev-resources/migration/a2a-sdk-migration-notes.md` - Documentation

---

## Breaking Changes

1. **Task Request/Response Format**: REST → JSON-RPC 2.0
2. **Client API**: Synchronous `send_task()` → Async iterator `send_message()`
3. **Field Names**: camelCase → snake_case
4. **Status Types**: String literals → Enum
5. **Endpoint Paths**: `/tasks` → JSON-RPC paths

---

## Migration Status

- [x] Phase 1: Preparation complete
- [ ] Phase 2: Mail Agent server
- [ ] Phase 3: Supervisor client
- [ ] Phase 4: Models
- [ ] Phase 5: Cleanup
- [ ] Phase 6: Bug fixes
- [ ] Phase 7: Testing
- [ ] Phase 8: Documentation
