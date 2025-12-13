# Info-Agent Phase 2: Full Backend Architecture

## Executive Summary

This document describes the **Full Backend** for the Info-Agent system. Building on Phase 1's foundation, this phase adds validation, escalation, clarification flows, AG-UI event streaming, and multi-provider LLM support.

### Phase 2 Goals

1. Implement Validation Agent with document analysis and Python execution
2. Add clarification flow with FAQ matching
3. Implement escalation and timeout handling
4. Add AG-UI event streaming endpoint for real-time updates
5. Support multiple LLM providers (OpenAI, Azure, Gemini, OpenRouter)
6. Enhance error handling with retry logic
7. Complete the LangGraph workflow with all conditional edges

### What This Phase Delivers

- A complete backend that can:
  - Validate received documents against criteria
  - Execute Python code for complex validation (sandboxed)
  - Match clarification questions against FAQ using LLM
  - Escalate unanswered questions to end user
  - Handle timeouts with configurable retry logic
  - Stream real-time events via AG-UI protocol (SSE)
  - Support multiple LLM providers

### Prerequisites

- Phase 1 fully implemented and working
- All Phase 1 tests passing

### What This Phase Does NOT Include

- Frontend dashboard (Phase 3)
- Mock Email Web UI (Phase 3)
- Full AG-UI frontend integration (Phase 4)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI GATEWAY (Port 8000)                        │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ /api/workflows  │  │ /api/stream     │  │ /webhooks       │             │
│  │ (CRUD + files)  │  │ (AG-UI SSE)     │  │ (email notif)   │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      SUPERVISOR AGENT (Embedded)                        ││
│  │  ┌───────────────────────────────────────────────────────────────────┐ ││
│  │  │                 LangGraph Orchestration Engine                     │ ││
│  │  │       (Full workflow with validation, escalation, clarification)   │ ││
│  │  └───────────────────────────────────────────────────────────────────┘ ││
│  │                                                                         ││
│  │  ┌───────────────────────────────────────────────────────────────────┐ ││
│  │  │                    AG-UI Event Streamer                            │ ││
│  │  │              (SSE streaming to frontend clients)                   │ ││
│  │  └───────────────────────────────────────────────────────────────────┘ ││
│  │                                                                         ││
│  │  • Parse input files (instructions, FAQ, escalation, validation)       ││
│  │  • Query A2A Registry for worker agents                                ││
│  │  • Generate and execute plans                                          ││
│  │  • Handle clarifications via FAQ matching                              ││
│  │  • Manage timeouts and escalations                                     ││
│  │  • Orchestrate Mail Agent and Validation Agent                         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                     │                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      LLM PROVIDER FACTORY                               ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               ││
│  │  │ OpenAI   │  │ Azure    │  │ Gemini   │  │OpenRouter│               ││
│  │  │ Provider │  │ Provider │  │ Provider │  │ Provider │               ││
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘               ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                     │                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        A2A REGISTRY (Embedded)                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ A2A Protocol (HTTP/JSON)
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ▼                                 ▼
┌───────────────────────────────────┐ ┌───────────────────────────────────────┐
│         MAIL AGENT                │ │         VALIDATION AGENT              │
│         (Port 8001)               │ │         (Port 8002)                   │
│                                   │ │                                       │
│  • Send/receive emails            │ │  • Parse documents (Excel, CSV, PDF)  │
│  • Track email threads            │ │  • LLM-based content analysis         │
│  • Handle attachments             │ │  • Python execution (sandboxed)       │
│  • Parse clarification questions  │ │  • Generate validation reports        │
│                                   │ │  • Pass/fail determination            │
└───────────────────────────────────┘ └───────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                       MOCK EMAIL SERVER (Port 8025/1025)                       │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Port Assignments (Phase 2)

| Component | Port | Purpose |
|-----------|------|---------|
| FastAPI Gateway | 8000 | Main API + AG-UI streaming |
| Mail Agent | 8001 | A2A worker server |
| Validation Agent | 8002 | A2A worker server (NEW) |
| Mock Email Server (REST) | 8025 | Email inbox REST API |
| Mock Email Server (SMTP) | 1025 | SMTP interface |

---

## New Component Specifications

### 1. Validation Agent (A2A Worker Server)

**Purpose**: Validates received documents against specified criteria using LLM analysis and Python execution.

**Deployment**: Separate A2A server on port 8002

**Technology**:
- Python 3.12+
- FastAPI for A2A server
- LangChain for LLM integration
- Subprocess for sandboxed Python execution
- openpyxl, pandas for document parsing

**A2A Registration**:
- Registers with A2A Registry on startup
- Does NOT query the registry
- Receives tasks only from Supervisor

**Agent Card**:

```json
{
  "name": "validation-agent",
  "description": "Document validation agent with LLM analysis and Python execution",
  "version": "1.0.0",
  "url": "http://localhost:8002",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "skills": [
    {
      "id": "validate-document",
      "name": "Validate Document",
      "description": "Validates document against specified criteria"
    },
    {
      "id": "analyze-document",
      "name": "Analyze Document",
      "description": "Analyzes document structure and content using LLM"
    },
    {
      "id": "execute-python",
      "name": "Execute Python",
      "description": "Executes Python code for complex validation logic"
    }
  ],
  "defaultInputModes": ["text", "file"],
  "defaultOutputModes": ["text"]
}
```

**State Schema**:

```python
from typing import TypedDict, List, Optional
from enum import Enum

class ValidationStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    EXECUTING_PYTHON = "executing_python"
    COMPLETED = "completed"
    FAILED = "failed"

class ValidationCriterion(TypedDict):
    """Single validation criterion."""
    id: str
    description: str
    check_type: str  # structure, content, count, value
    expected: str
    passed: Optional[bool]
    actual: Optional[str]
    message: Optional[str]

class ValidationResult(TypedDict):
    """Complete validation result."""
    document_id: str
    document_name: str
    document_type: str
    criteria_checked: List[ValidationCriterion]
    passed: bool
    score: float  # 0.0 to 1.0
    issues: List[str]
    recommendations: List[str]
    llm_analysis: Optional[str]
    python_output: Optional[str]
    validated_at: str

class ValidationAgentState(TypedDict):
    """State maintained by Validation Agent."""
    current_validation: Optional[dict]
    completed_validations: List[ValidationResult]
    python_execution_log: List[dict]
```

**Document Analyzer**:

```python
import logging
from typing import Dict, Any, List
from pathlib import Path
import pandas as pd
import json

logger = logging.getLogger(__name__)

class DocumentAnalyzer:
    """Analyzes documents using LLM and parsing libraries."""

    def __init__(self, llm):
        self.llm = llm

    async def analyze(
        self,
        document_path: str,
        criteria: str
    ) -> Dict[str, Any]:
        """Analyze document against criteria."""
        logger.info(f"Analyzing document: {document_path}")

        # Detect document type
        doc_type = self._detect_type(document_path)

        # Parse document content
        content = await self._parse_document(document_path, doc_type)

        # Use LLM to analyze
        analysis = await self._llm_analyze(content, criteria, doc_type)

        return {
            "document_type": doc_type,
            "content_summary": content.get("summary"),
            "structure": content.get("structure"),
            "analysis": analysis
        }

    def _detect_type(self, path: str) -> str:
        """Detect document type from extension."""
        ext = Path(path).suffix.lower()
        type_map = {
            ".xlsx": "excel",
            ".xls": "excel",
            ".csv": "csv",
            ".pdf": "pdf",
            ".txt": "text",
            ".json": "json"
        }
        doc_type = type_map.get(ext)
        if not doc_type:
            raise ValueError(f"Unsupported document type: {ext}")
        return doc_type

    async def _parse_document(
        self,
        path: str,
        doc_type: str
    ) -> Dict[str, Any]:
        """Parse document and extract content."""
        logger.info(f"Parsing {doc_type} document: {path}")

        if doc_type == "excel":
            return await self._parse_excel(path)
        elif doc_type == "csv":
            return await self._parse_csv(path)
        elif doc_type == "text":
            return await self._parse_text(path)
        elif doc_type == "json":
            return await self._parse_json(path)
        else:
            raise ValueError(f"Parser not implemented for: {doc_type}")

    async def _parse_excel(self, path: str) -> Dict[str, Any]:
        """Parse Excel file."""
        df = pd.read_excel(path)

        return {
            "summary": f"Excel file with {len(df)} rows and {len(df.columns)} columns",
            "structure": {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()}
            },
            "sample_data": df.head(5).to_dict(orient="records"),
            "full_data": df.to_dict(orient="records")
        }

    async def _parse_csv(self, path: str) -> Dict[str, Any]:
        """Parse CSV file."""
        df = pd.read_csv(path)

        return {
            "summary": f"CSV file with {len(df)} rows and {len(df.columns)} columns",
            "structure": {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()}
            },
            "sample_data": df.head(5).to_dict(orient="records"),
            "full_data": df.to_dict(orient="records")
        }

    async def _parse_text(self, path: str) -> Dict[str, Any]:
        """Parse text file."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        return {
            "summary": f"Text file with {len(lines)} lines and {len(content)} characters",
            "structure": {
                "line_count": len(lines),
                "char_count": len(content),
                "word_count": len(content.split())
            },
            "content": content
        }

    async def _parse_json(self, path: str) -> Dict[str, Any]:
        """Parse JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            summary = f"JSON array with {len(data)} items"
        elif isinstance(data, dict):
            summary = f"JSON object with {len(data)} keys"
        else:
            summary = f"JSON {type(data).__name__}"

        return {
            "summary": summary,
            "structure": {"type": type(data).__name__},
            "content": data
        }

    async def _llm_analyze(
        self,
        content: Dict[str, Any],
        criteria: str,
        doc_type: str
    ) -> Dict[str, Any]:
        """Use LLM to analyze content against criteria."""
        logger.info("Running LLM analysis")

        prompt = f"""
        Analyze this {doc_type} document against the validation criteria.

        Document Summary:
        {content.get('summary')}

        Document Structure:
        {json.dumps(content.get('structure'), indent=2)}

        Sample Data:
        {json.dumps(content.get('sample_data', content.get('content', ''))[:1000], indent=2)}

        Validation Criteria:
        {criteria}

        Analyze each criterion and determine if it passes or fails.
        For each criterion, provide:
        1. criterion_id: A unique identifier
        2. description: What is being checked
        3. passed: true or false
        4. actual: What was actually found
        5. message: Explanation

        Also provide:
        - overall_passed: true if ALL criteria pass
        - score: 0.0 to 1.0 (percentage of criteria passed)
        - issues: List of problems found
        - recommendations: List of suggestions to fix issues

        Respond in JSON format:
        {{
            "criteria_results": [...],
            "overall_passed": true/false,
            "score": 0.0-1.0,
            "issues": [...],
            "recommendations": [...]
        }}
        """

        response = await self.llm.ainvoke(prompt)
        return self._parse_json_response(response.content)

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response."""
        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return json.loads(content.strip())
```

**Python Executor (Sandboxed)**:

```python
import subprocess
import tempfile
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Whitelist of allowed imports
ALLOWED_IMPORTS = {
    "pandas",
    "numpy",
    "json",
    "csv",
    "openpyxl",
    "math",
    "datetime",
    "re",
    "collections"
}

class PythonExecutor:
    """Sandboxed Python code executor for validation."""

    def __init__(
        self,
        timeout_seconds: int = 30,
        max_output_size: int = 100000
    ):
        self.timeout = timeout_seconds
        self.max_output_size = max_output_size

    async def execute(
        self,
        code: str,
        data_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute Python code in sandboxed environment."""
        logger.info("Executing Python code in sandbox")

        # Validate code for security
        validation_result = self._validate_code(code)
        if not validation_result["valid"]:
            logger.warning(f"Code validation failed: {validation_result['reason']}")
            return {
                "success": False,
                "error": f"Security validation failed: {validation_result['reason']}",
                "output": None
            }

        # Create temporary directory for execution
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write code to file
            code_file = Path(tmpdir) / "validation_script.py"

            # Prepare code with data path injection
            prepared_code = self._prepare_code(code, data_path)
            code_file.write_text(prepared_code)

            # Copy data file if provided
            if data_path and os.path.exists(data_path):
                data_dest = Path(tmpdir) / Path(data_path).name
                import shutil
                shutil.copy(data_path, data_dest)

            # Execute in subprocess
            try:
                result = subprocess.run(
                    ["python", str(code_file)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=tmpdir,
                    env=self._get_restricted_env()
                )

                output = result.stdout[:self.max_output_size]
                error = result.stderr[:self.max_output_size] if result.stderr else None

                logger.info(f"Execution completed with return code: {result.returncode}")

                return {
                    "success": result.returncode == 0,
                    "output": output,
                    "error": error,
                    "return_code": result.returncode
                }

            except subprocess.TimeoutExpired:
                logger.error(f"Execution timed out after {self.timeout} seconds")
                return {
                    "success": False,
                    "error": f"Execution timed out after {self.timeout} seconds",
                    "output": None
                }
            except Exception as e:
                logger.error(f"Execution failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "output": None
                }

    def _validate_code(self, code: str) -> Dict[str, Any]:
        """Validate code for security concerns."""
        # Check for dangerous patterns
        dangerous_patterns = [
            "import os",
            "import sys",
            "import subprocess",
            "import socket",
            "import requests",
            "import urllib",
            "import http",
            "__import__",
            "eval(",
            "exec(",
            "compile(",
            "open(",  # We'll provide controlled file access
            "file(",
            "input(",
            "raw_input(",
        ]

        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in code_lower:
                return {
                    "valid": False,
                    "reason": f"Forbidden pattern detected: {pattern}"
                }

        # Check imports are in whitelist
        import_lines = [
            line.strip() for line in code.split("\n")
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]

        for line in import_lines:
            # Extract module name
            if line.startswith("import "):
                module = line.replace("import ", "").split()[0].split(".")[0]
            elif line.startswith("from "):
                module = line.replace("from ", "").split()[0].split(".")[0]
            else:
                continue

            if module not in ALLOWED_IMPORTS:
                return {
                    "valid": False,
                    "reason": f"Import not allowed: {module}. Allowed: {ALLOWED_IMPORTS}"
                }

        return {"valid": True, "reason": None}

    def _prepare_code(self, code: str, data_path: Optional[str]) -> str:
        """Prepare code with data path and safe file access."""
        header = """
# Auto-generated header for sandboxed execution
import pandas as pd
import numpy as np
import json
import csv
from pathlib import Path

# Data file path (if provided)
DATA_FILE = "{data_file}"

def read_data():
    \"\"\"Read the data file.\"\"\"
    if not DATA_FILE:
        return None
    path = Path(DATA_FILE).name  # Only filename, file is in current dir
    if path.endswith('.xlsx') or path.endswith('.xls'):
        return pd.read_excel(path)
    elif path.endswith('.csv'):
        return pd.read_csv(path)
    elif path.endswith('.json'):
        with open(path) as f:
            return json.load(f)
    else:
        with open(path) as f:
            return f.read()

# User code below
""".format(data_file=data_path or "")

        return header + "\n" + code

    def _get_restricted_env(self) -> Dict[str, str]:
        """Get restricted environment variables."""
        # Start with minimal environment
        env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": "",
            "HOME": "/tmp",
            "LANG": "en_US.UTF-8"
        }
        return env
```

**Validation Agent Server**:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

app = FastAPI(title="Validation Agent", version="1.0.0")

class ValidateDocumentRequest(BaseModel):
    """Request to validate a document."""
    document_path: str
    document_name: str
    criteria: str
    execute_python: bool = False
    python_code: Optional[str] = None

class ValidationResponse(BaseModel):
    """Validation result response."""
    document_id: str
    document_name: str
    passed: bool
    score: float
    issues: List[str]
    recommendations: List[str]
    details: Dict[str, Any]

class A2ATaskRequest(BaseModel):
    """A2A task request."""
    task_id: str
    skill_id: str
    payload: Dict[str, Any]

class A2ATaskResponse(BaseModel):
    """A2A task response."""
    task_id: str
    status: str
    result: Dict[str, Any]

# Initialize components
analyzer = None
executor = None

@app.on_event("startup")
async def startup():
    """Initialize components and register with A2A Registry."""
    global analyzer, executor

    logger.info("Starting Validation Agent")

    # Initialize LLM and components
    llm = get_llm()
    analyzer = DocumentAnalyzer(llm)
    executor = PythonExecutor(timeout_seconds=30)

    # Register with A2A Registry
    await register_with_registry()

    logger.info("Validation Agent started successfully")

async def register_with_registry():
    """Register with A2A Registry."""
    logger.info("Registering with A2A Registry")

    settings = get_settings()
    agent_card = {
        "name": "validation-agent",
        "description": "Document validation agent with LLM analysis and Python execution",
        "version": "1.0.0",
        "url": f"http://localhost:{settings.validation_agent_port}",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "skills": [
            {"id": "validate-document", "name": "Validate Document", "description": "Validates document against criteria"},
            {"id": "analyze-document", "name": "Analyze Document", "description": "Analyzes document structure"},
            {"id": "execute-python", "name": "Execute Python", "description": "Executes validation Python code"}
        ],
        "defaultInputModes": ["text", "file"],
        "defaultOutputModes": ["text"]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.a2a_registry_url}/agents/register",
            json=agent_card
        )
        response.raise_for_status()

    logger.info("Validation Agent registered successfully")

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """Return agent card."""
    settings = get_settings()
    return {
        "name": "validation-agent",
        "description": "Document validation agent with LLM analysis and Python execution",
        "version": "1.0.0",
        "url": f"http://localhost:{settings.validation_agent_port}",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "skills": [
            {"id": "validate-document", "name": "Validate Document", "description": "Validates document against criteria"},
            {"id": "analyze-document", "name": "Analyze Document", "description": "Analyzes document structure"},
            {"id": "execute-python", "name": "Execute Python", "description": "Executes validation Python code"}
        ],
        "defaultInputModes": ["text", "file"],
        "defaultOutputModes": ["text"]
    }

@app.post("/a2a/tasks")
async def handle_task(request: A2ATaskRequest) -> A2ATaskResponse:
    """Handle incoming A2A task."""
    logger.info(f"Received task {request.task_id}, skill: {request.skill_id}")

    handlers = {
        "validate-document": handle_validate_document,
        "analyze-document": handle_analyze_document,
        "execute-python": handle_execute_python
    }

    handler = handlers.get(request.skill_id)
    if not handler:
        raise HTTPException(status_code=400, detail=f"Unknown skill: {request.skill_id}")

    result = await handler(request.payload)

    return A2ATaskResponse(
        task_id=request.task_id,
        status="completed",
        result=result
    )

async def handle_validate_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle document validation."""
    logger.info(f"Validating document: {payload['document_name']}")

    # Analyze document
    analysis = await analyzer.analyze(
        document_path=payload["document_path"],
        criteria=payload["criteria"]
    )

    # Execute Python if requested
    python_output = None
    if payload.get("execute_python") and payload.get("python_code"):
        logger.info("Executing Python validation code")
        python_result = await executor.execute(
            code=payload["python_code"],
            data_path=payload["document_path"]
        )
        python_output = python_result

    # Build validation result
    result = {
        "document_id": payload.get("document_id", str(uuid.uuid4())),
        "document_name": payload["document_name"],
        "document_type": analysis["document_type"],
        "passed": analysis["analysis"]["overall_passed"],
        "score": analysis["analysis"]["score"],
        "criteria_results": analysis["analysis"]["criteria_results"],
        "issues": analysis["analysis"]["issues"],
        "recommendations": analysis["analysis"]["recommendations"],
        "llm_analysis": analysis["analysis"],
        "python_output": python_output,
        "validated_at": datetime.utcnow().isoformat()
    }

    logger.info(f"Validation complete: passed={result['passed']}, score={result['score']}")

    return result

async def handle_analyze_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle document analysis (without validation)."""
    logger.info(f"Analyzing document: {payload['document_path']}")

    analysis = await analyzer.analyze(
        document_path=payload["document_path"],
        criteria=payload.get("criteria", "Describe the document structure and content")
    )

    return analysis

async def handle_execute_python(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Python code execution."""
    logger.info("Executing Python code")

    result = await executor.execute(
        code=payload["code"],
        data_path=payload.get("data_path")
    )

    return result

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "validation-agent"}
```

---

### 2. AG-UI Event Streaming

**Purpose**: Stream real-time events from LangGraph workflow to frontend clients.

**Technology**:
- Server-Sent Events (SSE)
- AG-UI protocol event types

**Event Types**:

```python
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

class AGUIEventType(str, Enum):
    """AG-UI event types."""
    # Lifecycle
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"

    # Content
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"

    # Tool calls
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"

    # State
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA = "STATE_DELTA"

    # Custom (Info-Agent specific)
    PLAN_GENERATED = "PLAN_GENERATED"
    PLAN_APPROVED = "PLAN_APPROVED"
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_RECEIVED = "EMAIL_RECEIVED"
    CLARIFICATION_NEEDED = "CLARIFICATION_NEEDED"
    VALIDATION_STARTED = "VALIDATION_STARTED"
    VALIDATION_COMPLETE = "VALIDATION_COMPLETE"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"
    TIMEOUT_WARNING = "TIMEOUT_WARNING"

class AGUIEvent(BaseModel):
    """AG-UI event structure."""
    type: AGUIEventType
    timestamp: str
    workflow_id: str
    data: Dict[str, Any]
    sequence: int

    @classmethod
    def create(
        cls,
        event_type: AGUIEventType,
        workflow_id: str,
        data: Dict[str, Any],
        sequence: int
    ) -> "AGUIEvent":
        return cls(
            type=event_type,
            timestamp=datetime.utcnow().isoformat(),
            workflow_id=workflow_id,
            data=data,
            sequence=sequence
        )
```

**Event Streamer**:

```python
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

class AGUIEventStreamer:
    """Manages AG-UI event streaming to clients."""

    def __init__(self):
        # Workflow ID -> list of subscriber queues
        self._subscribers: Dict[str, list] = defaultdict(list)
        # Workflow ID -> event sequence counter
        self._sequences: Dict[str, int] = defaultdict(int)
        # Workflow ID -> event history (for replay)
        self._history: Dict[str, list] = defaultdict(list)

    async def subscribe(
        self,
        workflow_id: str,
        replay_from: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Subscribe to events for a workflow."""
        logger.info(f"New subscriber for workflow {workflow_id}")

        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[workflow_id].append(queue)

        try:
            # Replay historical events if requested
            if replay_from is not None:
                for event in self._history[workflow_id]:
                    if event.sequence >= replay_from:
                        yield self._format_sse(event)

            # Stream new events
            while True:
                event = await queue.get()
                if event is None:  # Sentinel for shutdown
                    break
                yield self._format_sse(event)

        finally:
            self._subscribers[workflow_id].remove(queue)
            logger.info(f"Subscriber disconnected from workflow {workflow_id}")

    async def emit(
        self,
        workflow_id: str,
        event_type: AGUIEventType,
        data: Dict[str, Any]
    ) -> AGUIEvent:
        """Emit an event to all subscribers."""
        sequence = self._sequences[workflow_id]
        self._sequences[workflow_id] += 1

        event = AGUIEvent.create(
            event_type=event_type,
            workflow_id=workflow_id,
            data=data,
            sequence=sequence
        )

        # Store in history
        self._history[workflow_id].append(event)

        # Broadcast to all subscribers
        for queue in self._subscribers[workflow_id]:
            await queue.put(event)

        logger.debug(f"Emitted {event_type} for workflow {workflow_id}")
        return event

    async def close_workflow(self, workflow_id: str):
        """Close all subscriptions for a workflow."""
        for queue in self._subscribers[workflow_id]:
            await queue.put(None)
        self._subscribers[workflow_id].clear()

    def _format_sse(self, event: AGUIEvent) -> str:
        """Format event as SSE data."""
        data = event.model_dump_json()
        return f"data: {data}\n\n"

# Global instance
event_streamer = AGUIEventStreamer()
```

**SSE Endpoint**:

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional

router = APIRouter()

@router.post("/api/workflows/{workflow_id}/stream")
async def stream_workflow_events(
    workflow_id: str,
    replay_from: Optional[int] = None
):
    """Stream AG-UI events for a workflow via SSE."""
    logger.info(f"Starting SSE stream for workflow {workflow_id}")

    # Verify workflow exists
    workflow = await get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    async def event_generator():
        async for event in event_streamer.subscribe(workflow_id, replay_from):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
```

**Integration with LangGraph Nodes**:

```python
async def parse_input_files(state: SupervisorState) -> Dict[str, Any]:
    """Parse input files with AG-UI event emission."""
    workflow_id = state["workflow_id"]

    # Emit start event
    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.TOOL_CALL_START,
        data={"tool": "parse_inputs", "description": "Parsing input files"}
    )

    # ... parsing logic ...

    # Emit completion event
    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.TOOL_CALL_END,
        data={"tool": "parse_inputs", "result": "success"}
    )

    # Emit state delta
    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.STATE_DELTA,
        data={
            "target_email": extracted["target_email"],
            "status": "planning"
        }
    )

    return {...}
```

---

### 3. Multi-Provider LLM Support

**Purpose**: Support multiple LLM providers with a unified interface.

**Base Interface**:

```python
from abc import ABC, abstractmethod
from typing import Any, Optional
from langchain_core.language_models import BaseChatModel

class BaseLLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def get_chat_model(self, **kwargs) -> BaseChatModel:
        """Return a LangChain chat model instance."""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate that required configuration is present."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass
```

**OpenAI Provider**:

```python
from langchain_openai import ChatOpenAI
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider."""

    def __init__(self, settings):
        self.api_key = settings.openai_api_key
        self.model = settings.llm_model or "gpt-4-turbo"
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self._client: Optional[ChatOpenAI] = None

    @property
    def provider_name(self) -> str:
        return "openai"

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.error("OpenAI API key not configured")
            return False
        return True

    def get_chat_model(self, **kwargs) -> ChatOpenAI:
        if self._client is None:
            if not self.validate_config():
                raise ValueError("OpenAI configuration invalid")

            logger.info(f"Initializing OpenAI model: {self.model}")
            self._client = ChatOpenAI(
                api_key=self.api_key,
                model=self.model,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                streaming=kwargs.get("streaming", True)
            )
        return self._client
```

**Azure OpenAI Provider**:

```python
from langchain_openai import AzureChatOpenAI
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AzureOpenAIProvider(BaseLLMProvider):
    """Azure OpenAI LLM provider."""

    def __init__(self, settings):
        self.api_key = settings.azure_openai_api_key
        self.endpoint = settings.azure_openai_endpoint
        self.deployment = settings.azure_openai_deployment_name
        self.api_version = settings.azure_openai_api_version
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self._client: Optional[AzureChatOpenAI] = None

    @property
    def provider_name(self) -> str:
        return "azure_openai"

    def validate_config(self) -> bool:
        if not all([self.api_key, self.endpoint, self.deployment]):
            logger.error("Azure OpenAI configuration incomplete")
            return False
        return True

    def get_chat_model(self, **kwargs) -> AzureChatOpenAI:
        if self._client is None:
            if not self.validate_config():
                raise ValueError("Azure OpenAI configuration invalid")

            logger.info(f"Initializing Azure OpenAI deployment: {self.deployment}")
            self._client = AzureChatOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.endpoint,
                azure_deployment=self.deployment,
                api_version=self.api_version,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                streaming=kwargs.get("streaming", True)
            )
        return self._client
```

**Gemini Provider**:

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider."""

    def __init__(self, settings):
        self.api_key = settings.google_api_key
        self.model = settings.llm_model or "gemini-2.5-flash"
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self._client: Optional[ChatGoogleGenerativeAI] = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.error("Google API key not configured")
            return False
        return True

    def get_chat_model(self, **kwargs) -> ChatGoogleGenerativeAI:
        if self._client is None:
            if not self.validate_config():
                raise ValueError("Gemini configuration invalid")

            logger.info(f"Initializing Gemini model: {self.model}")
            self._client = ChatGoogleGenerativeAI(
                google_api_key=self.api_key,
                model=self.model,
                temperature=kwargs.get("temperature", self.temperature),
                max_output_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
        return self._client
```

**OpenRouter Provider**:

```python
from langchain_openai import ChatOpenAI
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter LLM provider (access to multiple models)."""

    def __init__(self, settings):
        self.api_key = settings.openrouter_api_key
        self.model = settings.llm_model or "anthropic/claude-3-sonnet"
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self._client: Optional[ChatOpenAI] = None

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def validate_config(self) -> bool:
        if not self.api_key:
            logger.error("OpenRouter API key not configured")
            return False
        return True

    def get_chat_model(self, **kwargs) -> ChatOpenAI:
        if self._client is None:
            if not self.validate_config():
                raise ValueError("OpenRouter configuration invalid")

            logger.info(f"Initializing OpenRouter model: {self.model}")
            self._client = ChatOpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1",
                model=self.model,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                streaming=kwargs.get("streaming", True)
            )
        return self._client
```

**LLM Factory**:

```python
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class LLMFactory:
    """Factory for creating LLM providers."""

    _providers = {
        "openai": OpenAIProvider,
        "azure_openai": AzureOpenAIProvider,
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider
    }

    _instance: Optional[BaseLLMProvider] = None

    @classmethod
    def create(cls, settings) -> BaseLLMProvider:
        """Create LLM provider based on configuration."""
        provider_name = settings.llm_provider

        if provider_name not in cls._providers:
            raise ValueError(
                f"Unknown LLM provider: {provider_name}. "
                f"Available: {list(cls._providers.keys())}"
            )

        provider_class = cls._providers[provider_name]
        provider = provider_class(settings)

        if not provider.validate_config():
            raise ValueError(f"Invalid configuration for provider: {provider_name}")

        logger.info(f"Created LLM provider: {provider_name}")
        return provider

    @classmethod
    def get_llm(cls, settings=None):
        """Get or create the configured LLM instance."""
        if cls._instance is None:
            if settings is None:
                settings = get_settings()
            cls._instance = cls.create(settings)
        return cls._instance.get_chat_model()

# Convenience function
def get_llm(**kwargs):
    """Get the configured LLM chat model."""
    return LLMFactory.get_llm().get_chat_model(**kwargs)
```

---

### 4. Clarification Flow

**Purpose**: Match incoming questions against FAQ using LLM semantic matching.

**FAQ Matcher**:

```python
import logging
from typing import Dict, Any, List, Optional
import json

logger = logging.getLogger(__name__)

class FAQMatcher:
    """Matches questions against FAQ using LLM."""

    def __init__(self, llm):
        self.llm = llm

    async def find_answer(
        self,
        question: str,
        faq_content: str
    ) -> Dict[str, Any]:
        """Find answer to question in FAQ."""
        logger.info(f"Searching FAQ for answer to: {question[:50]}...")

        prompt = f"""
        A user has asked the following question:
        "{question}"

        Here is the FAQ document:
        ---
        {faq_content}
        ---

        Analyze the FAQ and determine:
        1. Is there a matching question/answer in the FAQ that addresses this question?
        2. If yes, what is the answer?
        3. How confident are you in the match (0.0 to 1.0)?

        Consider semantic similarity, not just exact matches.
        A question about "format" could match FAQ about "file type", etc.

        Respond in JSON format:
        {{
            "found": true/false,
            "confidence": 0.0-1.0,
            "matched_question": "The FAQ question that matches (if found)",
            "answer": "The answer from FAQ (if found)",
            "reasoning": "Brief explanation of why this matches or doesn't match"
        }}
        """

        response = await self.llm.ainvoke(prompt)
        result = self._parse_json_response(response.content)

        logger.info(f"FAQ match result: found={result['found']}, confidence={result.get('confidence', 0)}")

        return result

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response."""
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content.strip())

class ClarificationHandler:
    """Handles clarification questions from target persons."""

    def __init__(self, llm):
        self.faq_matcher = FAQMatcher(llm)
        self.llm = llm

    async def handle_question(
        self,
        question: str,
        faq_content: str,
        workflow_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a clarification question."""
        logger.info("Handling clarification question")

        # Try to find answer in FAQ
        faq_result = await self.faq_matcher.find_answer(question, faq_content)

        # Threshold for accepting FAQ match
        confidence_threshold = 0.7

        if faq_result["found"] and faq_result.get("confidence", 0) >= confidence_threshold:
            # Found in FAQ - compose reply
            reply = await self._compose_faq_reply(
                question=question,
                answer=faq_result["answer"],
                context=workflow_context
            )

            return {
                "action": "reply_from_faq",
                "found_in_faq": True,
                "confidence": faq_result["confidence"],
                "answer": faq_result["answer"],
                "reply": reply
            }
        else:
            # Not in FAQ - needs escalation
            return {
                "action": "escalate_to_user",
                "found_in_faq": False,
                "confidence": faq_result.get("confidence", 0),
                "question": question,
                "reason": faq_result.get("reasoning", "No matching FAQ entry found")
            }

    async def _compose_faq_reply(
        self,
        question: str,
        answer: str,
        context: Dict[str, Any]
    ) -> str:
        """Compose a reply email using FAQ answer."""
        prompt = f"""
        Compose a professional email reply to answer this question:

        Original Question: {question}

        Answer from FAQ: {answer}

        Context:
        - Requester: {context.get('from_name', 'the user')}
        - Original Request: {context.get('requested_info', '')}

        Write a polite, helpful email that:
        1. Acknowledges their question
        2. Provides the answer clearly
        3. Offers to help with any other questions

        Write only the email body (no subject line).
        """

        response = await self.llm.ainvoke(prompt)
        return response.content.strip()
```

---

### 5. Escalation and Timeout Handling

**Purpose**: Handle timeouts and escalations when target doesn't respond or questions can't be answered.

**Escalation Manager**:

```python
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class EscalationType(str, Enum):
    TIMEOUT = "timeout"
    CLARIFICATION = "clarification"
    VALIDATION_FAILED = "validation_failed"
    ERROR = "error"

class EscalationRule(TypedDict):
    """Escalation rule structure."""
    type: EscalationType
    contact_email: str
    contact_name: str
    message_template: str

class EscalationManager:
    """Manages escalation rules and triggers."""

    def __init__(self, llm):
        self.llm = llm

    async def parse_escalation_rules(
        self,
        escalation_content: str
    ) -> List[EscalationRule]:
        """Parse escalation rules from input file."""
        logger.info("Parsing escalation rules")

        prompt = f"""
        Parse the following escalation rules and extract structured data:

        ---
        {escalation_content}
        ---

        Extract each escalation rule with:
        1. type: "timeout", "clarification", "validation_failed", or "error"
        2. contact_email: Email to escalate to
        3. contact_name: Name of the contact (if mentioned)
        4. message_template: Template or description of what to include

        Respond in JSON format:
        {{
            "rules": [
                {{
                    "type": "timeout",
                    "contact_email": "...",
                    "contact_name": "...",
                    "message_template": "..."
                }}
            ]
        }}
        """

        response = await self.llm.ainvoke(prompt)
        result = self._parse_json_response(response.content)

        logger.info(f"Parsed {len(result['rules'])} escalation rules")
        return result["rules"]

    def get_rule_for_type(
        self,
        rules: List[EscalationRule],
        escalation_type: EscalationType
    ) -> Optional[EscalationRule]:
        """Get escalation rule for a specific type."""
        for rule in rules:
            if rule["type"] == escalation_type:
                return rule
        return None

    async def compose_escalation_email(
        self,
        rule: EscalationRule,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Compose escalation email."""
        logger.info(f"Composing {rule['type']} escalation email to {rule['contact_email']}")

        prompt = f"""
        Compose an escalation email based on this rule and context:

        Escalation Type: {rule['type']}
        Contact: {rule['contact_name']} ({rule['contact_email']})
        Template/Instructions: {rule['message_template']}

        Context:
        - Original request: {context.get('requested_info', '')}
        - Target person: {context.get('target_name', '')} ({context.get('target_email', '')})
        - Reason for escalation: {context.get('reason', '')}
        - Additional details: {context.get('details', '')}

        Compose a professional escalation email that:
        1. Clearly explains why the escalation is happening
        2. Provides relevant context
        3. States what action is needed
        4. Includes any relevant history

        Respond in JSON format:
        {{
            "subject": "Email subject line",
            "body": "Email body"
        }}
        """

        response = await self.llm.ainvoke(prompt)
        return self._parse_json_response(response.content)

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response."""
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content.strip())

class TimeoutMonitor:
    """Monitors workflow timeouts."""

    def __init__(self, default_timeout_hours: int = 48, max_retries: int = 3):
        self.default_timeout_hours = default_timeout_hours
        self.max_retries = max_retries

    def check_timeout(
        self,
        sent_at: str,
        timeout_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """Check if a timeout has occurred."""
        timeout_h = timeout_hours or self.default_timeout_hours
        sent_time = datetime.fromisoformat(sent_at)
        deadline = sent_time + timedelta(hours=timeout_h)
        now = datetime.utcnow()

        is_timeout = now >= deadline
        time_remaining = (deadline - now).total_seconds() if not is_timeout else 0

        return {
            "is_timeout": is_timeout,
            "sent_at": sent_at,
            "deadline": deadline.isoformat(),
            "time_remaining_seconds": max(0, time_remaining),
            "timeout_hours": timeout_h
        }

    def should_retry(self, retry_count: int) -> bool:
        """Determine if another retry should be attempted."""
        return retry_count < self.max_retries

    def get_retry_action(
        self,
        retry_count: int
    ) -> Dict[str, Any]:
        """Get the appropriate action based on retry count."""
        if self.should_retry(retry_count):
            return {
                "action": "retry",
                "retry_count": retry_count + 1,
                "max_retries": self.max_retries,
                "message": f"Retry {retry_count + 1} of {self.max_retries}"
            }
        else:
            return {
                "action": "escalate",
                "retry_count": retry_count,
                "max_retries": self.max_retries,
                "message": f"Max retries ({self.max_retries}) reached, escalating"
            }
```

---

### 6. Enhanced LangGraph Workflow

**Complete Workflow Graph**:

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Literal

# Define complete workflow state
class SupervisorState(TypedDict):
    """Complete workflow state for Phase 2."""
    # Workflow identification
    workflow_id: str

    # Input files content
    instructions: str
    faq: str
    escalation_rules: str
    validation_criteria: str

    # Parsed requirements
    target_email: str
    target_name: str
    requested_info: str

    # Escalation configuration
    parsed_escalation_rules: List[dict]
    timeout_hours: int
    retry_count: int
    max_retries: int

    # Execution state
    status: WorkflowStatus
    plan: List[dict]
    current_step: int

    # Communication tracking
    email_thread_id: Optional[str]
    sent_email_id: Optional[str]
    last_sent_at: Optional[str]
    clarification_history: List[dict]

    # Results
    received_response: Optional[str]
    received_attachments: List[dict]
    validation_result: Optional[dict]

    # Flags
    plan_approved: Optional[bool]
    plan_rejected: Optional[bool]
    plan_cancelled: Optional[bool]
    response_received: Optional[bool]
    is_clarification: Optional[bool]
    clarification_question: Optional[str]

    # Audit
    audit_log: List[dict]
    created_at: str
    updated_at: str
    error: Optional[str]

def create_full_workflow() -> StateGraph:
    """Create the complete Phase 2 workflow graph."""

    workflow = StateGraph(SupervisorState)

    # Add all nodes
    workflow.add_node("parse_inputs", parse_input_files)
    workflow.add_node("lookup_agents", query_a2a_registry)
    workflow.add_node("generate_plan", create_execution_plan)
    workflow.add_node("await_approval", wait_for_user_approval)
    workflow.add_node("execute_step", execute_current_step)
    workflow.add_node("send_email", invoke_mail_agent_send)
    workflow.add_node("wait_response", wait_for_email_response)
    workflow.add_node("process_response", handle_email_response)
    workflow.add_node("handle_clarification", process_clarification)
    workflow.add_node("check_timeout", evaluate_timeout)
    workflow.add_node("retry_email", retry_email_send)
    workflow.add_node("escalate", perform_escalation)
    workflow.add_node("validate_document", invoke_validation_agent)
    workflow.add_node("report_results", generate_final_report)

    # Set entry point
    workflow.set_entry_point("parse_inputs")

    # Define edges
    workflow.add_edge("parse_inputs", "lookup_agents")
    workflow.add_edge("lookup_agents", "generate_plan")
    workflow.add_edge("generate_plan", "await_approval")

    # Approval decision
    workflow.add_conditional_edges(
        "await_approval",
        check_approval_status,
        {
            "approved": "execute_step",
            "rejected": "generate_plan",
            "cancelled": END
        }
    )

    # Execute step decision
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

    # Response handling
    workflow.add_conditional_edges(
        "wait_response",
        check_response_type,
        {
            "document_received": "process_response",
            "clarification": "handle_clarification",
            "timeout": "check_timeout",
            "waiting": "wait_response"
        }
    )

    # Process response decision
    workflow.add_conditional_edges(
        "process_response",
        check_has_attachment,
        {
            "has_attachment": "validate_document",
            "no_attachment": "report_results"
        }
    )

    # Clarification handling
    workflow.add_conditional_edges(
        "handle_clarification",
        check_faq_match,
        {
            "found_in_faq": "send_email",
            "not_in_faq": "escalate"
        }
    )

    # Timeout handling
    workflow.add_conditional_edges(
        "check_timeout",
        evaluate_retry_count,
        {
            "retry": "retry_email",
            "escalate": "escalate"
        }
    )

    workflow.add_edge("retry_email", "wait_response")

    # Escalation -> wait for response
    workflow.add_edge("escalate", "wait_response")

    # Validation result
    workflow.add_conditional_edges(
        "validate_document",
        check_validation_result,
        {
            "passed": "report_results",
            "failed": "report_results"
        }
    )

    workflow.add_edge("report_results", END)

    return workflow

# Conditional edge functions
def check_approval_status(state: SupervisorState) -> Literal["approved", "rejected", "cancelled"]:
    """Check plan approval status."""
    if state.get("plan_cancelled"):
        return "cancelled"
    elif state.get("plan_rejected"):
        return "rejected"
    elif state.get("plan_approved"):
        return "approved"
    return "approved"  # Default

def determine_next_action(state: SupervisorState) -> Literal["send_email", "validate", "complete"]:
    """Determine next action based on plan."""
    current_step = state["current_step"]
    plan = state["plan"]

    if current_step >= len(plan):
        return "complete"

    step = plan[current_step]
    action = step.get("action", "")

    if action == "send_email":
        return "send_email"
    elif action == "validate":
        return "validate"
    else:
        return "complete"

def check_response_type(state: SupervisorState) -> Literal["document_received", "clarification", "timeout", "waiting"]:
    """Check the type of response received."""
    if not state.get("response_received"):
        # Check for timeout
        if state.get("last_sent_at"):
            monitor = TimeoutMonitor()
            timeout_check = monitor.check_timeout(state["last_sent_at"], state.get("timeout_hours"))
            if timeout_check["is_timeout"]:
                return "timeout"
        return "waiting"

    if state.get("is_clarification"):
        return "clarification"

    if state.get("received_attachments"):
        return "document_received"

    return "document_received"

def check_has_attachment(state: SupervisorState) -> Literal["has_attachment", "no_attachment"]:
    """Check if response has attachments."""
    if state.get("received_attachments"):
        return "has_attachment"
    return "no_attachment"

def check_faq_match(state: SupervisorState) -> Literal["found_in_faq", "not_in_faq"]:
    """Check if clarification question was found in FAQ."""
    # This is set by handle_clarification node
    if state.get("clarification_found_in_faq"):
        return "found_in_faq"
    return "not_in_faq"

def evaluate_retry_count(state: SupervisorState) -> Literal["retry", "escalate"]:
    """Evaluate whether to retry or escalate."""
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if retry_count < max_retries:
        return "retry"
    return "escalate"

def check_validation_result(state: SupervisorState) -> Literal["passed", "failed"]:
    """Check validation result."""
    result = state.get("validation_result", {})
    if result.get("passed"):
        return "passed"
    return "failed"
```

**Enhanced Node Implementations**:

```python
async def parse_input_files(state: SupervisorState) -> Dict[str, Any]:
    """Parse all input files and extract requirements."""
    workflow_id = state["workflow_id"]
    logger.info(f"Parsing input files for workflow {workflow_id}")

    # Emit AG-UI event
    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.TOOL_CALL_START,
        data={"tool": "parse_inputs", "description": "Parsing input files"}
    )

    llm = get_llm()

    # Parse instructions
    extraction_prompt = f"""
    Extract the following from these instructions:

    Instructions:
    {state['instructions']}

    Extract:
    1. target_email: Email address to send request to
    2. target_name: Name of the person
    3. requested_info: What is being requested

    Respond in JSON:
    {{"target_email": "...", "target_name": "...", "requested_info": "..."}}
    """

    response = await llm.ainvoke(extraction_prompt)
    extracted = parse_json_response(response.content)

    # Parse escalation rules
    escalation_manager = EscalationManager(llm)
    escalation_rules = await escalation_manager.parse_escalation_rules(state["escalation_rules"])

    # Emit completion
    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.TOOL_CALL_END,
        data={"tool": "parse_inputs", "result": "success"}
    )

    return {
        "target_email": extracted["target_email"],
        "target_name": extracted.get("target_name", ""),
        "requested_info": extracted["requested_info"],
        "parsed_escalation_rules": escalation_rules,
        "status": WorkflowStatus.PLANNING,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "parse_inputs",
            "details": f"Extracted: target={extracted['target_email']}"
        }]
    }

async def process_clarification(state: SupervisorState) -> Dict[str, Any]:
    """Process clarification question from target."""
    workflow_id = state["workflow_id"]
    question = state["clarification_question"]

    logger.info(f"Processing clarification: {question[:50]}...")

    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.CLARIFICATION_NEEDED,
        data={"question": question}
    )

    llm = get_llm()
    handler = ClarificationHandler(llm)

    result = await handler.handle_question(
        question=question,
        faq_content=state["faq"],
        workflow_context={
            "from_name": state["target_name"],
            "requested_info": state["requested_info"]
        }
    )

    if result["action"] == "reply_from_faq":
        return {
            "clarification_found_in_faq": True,
            "clarification_reply": result["reply"],
            "clarification_history": state["clarification_history"] + [{
                "question": question,
                "answer": result["answer"],
                "source": "faq",
                "timestamp": datetime.utcnow().isoformat()
            }],
            "audit_log": state["audit_log"] + [{
                "timestamp": datetime.utcnow().isoformat(),
                "action": "clarification_handled",
                "details": f"Found in FAQ with confidence {result['confidence']}"
            }]
        }
    else:
        return {
            "clarification_found_in_faq": False,
            "escalation_question": question,
            "audit_log": state["audit_log"] + [{
                "timestamp": datetime.utcnow().isoformat(),
                "action": "clarification_escalated",
                "details": f"Not in FAQ: {result['reason']}"
            }]
        }

async def evaluate_timeout(state: SupervisorState) -> Dict[str, Any]:
    """Evaluate timeout and determine next action."""
    workflow_id = state["workflow_id"]

    logger.info(f"Evaluating timeout for workflow {workflow_id}")

    monitor = TimeoutMonitor(
        default_timeout_hours=state.get("timeout_hours", 48),
        max_retries=state.get("max_retries", 3)
    )

    timeout_check = monitor.check_timeout(state["last_sent_at"])

    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.TIMEOUT_WARNING,
        data={
            "retry_count": state.get("retry_count", 0),
            "max_retries": state.get("max_retries", 3),
            "timeout_check": timeout_check
        }
    )

    return {
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "timeout_check",
            "details": f"Timeout reached, retry_count={state.get('retry_count', 0)}"
        }]
    }

async def perform_escalation(state: SupervisorState) -> Dict[str, Any]:
    """Perform escalation to alternate contact."""
    workflow_id = state["workflow_id"]

    logger.info(f"Performing escalation for workflow {workflow_id}")

    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.ESCALATION_TRIGGERED,
        data={"reason": "timeout_or_clarification"}
    )

    llm = get_llm()
    manager = EscalationManager(llm)

    # Determine escalation type
    if state.get("escalation_question"):
        escalation_type = EscalationType.CLARIFICATION
        reason = f"Clarification question not in FAQ: {state['escalation_question']}"
    else:
        escalation_type = EscalationType.TIMEOUT
        reason = f"No response after {state.get('retry_count', 0)} retries"

    # Get appropriate rule
    rule = manager.get_rule_for_type(state["parsed_escalation_rules"], escalation_type)

    if not rule:
        logger.error(f"No escalation rule found for type: {escalation_type}")
        return {
            "error": f"No escalation rule configured for {escalation_type}",
            "status": WorkflowStatus.FAILED
        }

    # Compose escalation email
    email_content = await manager.compose_escalation_email(
        rule=rule,
        context={
            "requested_info": state["requested_info"],
            "target_name": state["target_name"],
            "target_email": state["target_email"],
            "reason": reason,
            "details": state.get("escalation_question", "")
        }
    )

    # Send via Mail Agent
    a2a_client = get_a2a_client()
    task_result = await a2a_client.send_task(
        agent_name="mail-agent",
        skill_id="send-email",
        payload={
            "to": rule["contact_email"],
            "subject": email_content["subject"],
            "body": email_content["body"],
            "thread_id": state.get("email_thread_id")
        }
    )

    return {
        "sent_email_id": task_result["message_id"],
        "last_sent_at": datetime.utcnow().isoformat(),
        "status": WorkflowStatus.ESCALATED,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "escalated",
            "details": f"Escalated to {rule['contact_email']}: {reason}"
        }]
    }

async def invoke_validation_agent(state: SupervisorState) -> Dict[str, Any]:
    """Invoke Validation Agent to validate received document."""
    workflow_id = state["workflow_id"]

    logger.info(f"Invoking Validation Agent for workflow {workflow_id}")

    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.VALIDATION_STARTED,
        data={"documents": len(state.get("received_attachments", []))}
    )

    a2a_client = get_a2a_client()

    # Get first attachment
    attachments = state.get("received_attachments", [])
    if not attachments:
        return {
            "validation_result": {
                "passed": False,
                "score": 0,
                "issues": ["No attachments received"],
                "recommendations": ["Please request the document again"]
            },
            "status": WorkflowStatus.COMPLETED
        }

    attachment = attachments[0]

    # Invoke Validation Agent
    task_result = await a2a_client.send_task(
        agent_name="validation-agent",
        skill_id="validate-document",
        payload={
            "document_path": attachment["path"],
            "document_name": attachment["filename"],
            "criteria": state["validation_criteria"],
            "execute_python": True,
            "python_code": None  # Will be generated by Validation Agent if needed
        }
    )

    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.VALIDATION_COMPLETE,
        data={
            "passed": task_result["passed"],
            "score": task_result["score"]
        }
    )

    return {
        "validation_result": task_result,
        "status": WorkflowStatus.VALIDATING if task_result["passed"] else WorkflowStatus.COMPLETED,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "validation_complete",
            "details": f"Validation {'passed' if task_result['passed'] else 'failed'}, score={task_result['score']}"
        }]
    }

async def generate_final_report(state: SupervisorState) -> Dict[str, Any]:
    """Generate final workflow report."""
    workflow_id = state["workflow_id"]

    logger.info(f"Generating final report for workflow {workflow_id}")

    validation_result = state.get("validation_result", {})
    passed = validation_result.get("passed", False)

    await event_streamer.emit(
        workflow_id=workflow_id,
        event_type=AGUIEventType.RUN_FINISHED,
        data={
            "status": "completed",
            "validation_passed": passed,
            "score": validation_result.get("score", 0)
        }
    )

    # If validation failed, send notification email to end user
    if not passed and validation_result:
        # This would trigger an email to the end user
        logger.info("Validation failed, would notify end user")

    return {
        "status": WorkflowStatus.COMPLETED,
        "audit_log": state["audit_log"] + [{
            "timestamp": datetime.utcnow().isoformat(),
            "action": "workflow_complete",
            "details": f"Workflow completed, validation={'passed' if passed else 'failed'}"
        }]
    }
```

---

## Configuration (Phase 2)

### Environment Variables

```bash
# .env file for Phase 2

# ===================
# LLM Configuration (Multi-Provider)
# ===================
LLM_PROVIDER=gemini  # Options: openai, azure_openai, gemini, openrouter

# OpenAI (if LLM_PROVIDER=openai)
OPENAI_API_KEY=sk-...

# Azure OpenAI (if LLM_PROVIDER=azure_openai)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-01

# Google Gemini (if LLM_PROVIDER=gemini)
GOOGLE_API_KEY=...

# OpenRouter (if LLM_PROVIDER=openrouter)
OPENROUTER_API_KEY=sk-or-...

# Model name (varies by provider)
LLM_MODEL=gemini-2.5-flash
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096

# ===================
# Server Configuration
# ===================
HOST=0.0.0.0
GATEWAY_PORT=8000
MAIL_AGENT_PORT=8001
VALIDATION_AGENT_PORT=8002
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
# Timeout Configuration
# ===================
DEFAULT_TIMEOUT_HOURS=48
DEFAULT_RETRY_COUNT=3
VALIDATION_TIMEOUT_SECONDS=30

# ===================
# Logging
# ===================
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Updated Settings

```python
from pydantic_settings import BaseSettings
from typing import Optional, Literal

class Settings(BaseSettings):
    """Phase 2 application settings."""

    # LLM Provider
    llm_provider: Literal["openai", "azure_openai", "gemini", "openrouter"] = "gemini"

    # OpenAI
    openai_api_key: Optional[str] = None

    # Azure OpenAI
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_deployment_name: Optional[str] = None
    azure_openai_api_version: str = "2024-02-01"

    # Gemini
    google_api_key: Optional[str] = None

    # OpenRouter
    openrouter_api_key: Optional[str] = None

    # Model settings
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # Server ports
    host: str = "0.0.0.0"
    gateway_port: int = 8000
    mail_agent_port: int = 8001
    validation_agent_port: int = 8002
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

    # Timeouts
    default_timeout_hours: int = 48
    default_retry_count: int = 3
    validation_timeout_seconds: int = 30

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

---

## Directory Structure (Phase 2 Additions)

```
info-agent/
├── src/
│   └── info_agent/
│       ├── agents/
│       │   ├── supervisor/
│       │   │   ├── clarification.py     # NEW: FAQ matching
│       │   │   └── escalation.py        # NEW: Escalation handling
│       │   ├── mail/
│       │   │   └── ... (from Phase 1)
│       │   └── validation/              # NEW
│       │       ├── __init__.py
│       │       ├── agent.py             # Validation Agent server
│       │       ├── analyzer.py          # Document analysis
│       │       ├── executor.py          # Python sandboxed execution
│       │       └── state.py
│       │
│       ├── workflow/
│       │   ├── graph.py                 # ENHANCED: Full workflow
│       │   ├── nodes.py                 # ENHANCED: All nodes
│       │   ├── conditions.py            # NEW: Conditional edge functions
│       │   └── ... (from Phase 1)
│       │
│       ├── llm/
│       │   ├── factory.py               # ENHANCED: Multi-provider
│       │   ├── base.py                  # NEW: Base interface
│       │   ├── gemini_provider.py       # From Phase 1
│       │   ├── openai_provider.py       # NEW
│       │   ├── azure_provider.py        # NEW
│       │   └── openrouter_provider.py   # NEW
│       │
│       ├── dashboard/                   # NEW
│       │   ├── __init__.py
│       │   ├── stream.py                # AG-UI SSE streaming
│       │   └── events.py                # Event types
│       │
│       └── utils/
│           ├── retry.py                 # NEW: Retry decorator
│           └── security.py              # NEW: Input sanitization
│
├── tests/
│   ├── unit/
│   │   ├── test_validation_agent.py     # NEW
│   │   ├── test_clarification.py        # NEW
│   │   ├── test_escalation.py           # NEW
│   │   ├── test_llm_factory.py          # NEW
│   │   └── ... (from Phase 1)
│   └── integration/
│       ├── test_full_workflow.py        # NEW
│       ├── test_ag_ui_streaming.py      # NEW
│       └── ... (from Phase 1)
│
├── test_data/
│   ├── instructions_example.txt
│   ├── faq_example.txt                  # NEW
│   ├── escalation_example.txt           # NEW
│   ├── validation_example.txt           # NEW
│   └── sample_documents/
│       ├── valid_excel.xlsx             # NEW
│       └── invalid_excel.xlsx           # NEW
│
├── scripts/
│   ├── run_gateway.py
│   ├── run_mail_agent.py
│   ├── run_validation_agent.py          # NEW
│   ├── run_email_server.py
│   └── test_full_workflow.py            # NEW
│
└── ... (rest from Phase 1)
```

---

## New API Endpoints (Phase 2)

```python
# AG-UI Streaming
POST   /api/workflows/{id}/stream        # SSE event stream

# Audit and History
GET    /api/workflows/{id}/audit         # Get audit log
GET    /api/workflows/{id}/emails        # Get email history
GET    /api/workflows/{id}/clarifications # Get clarification history

# Validation Agent (Port 8002)
POST   /a2a/tasks                        # Handle validation task
GET    /.well-known/agent.json           # Agent card
GET    /health                           # Health check
```

---

## Dependencies (Phase 2 Additions)

```toml
[project]
dependencies = [
    # ... (all from Phase 1)

    # Additional LLM Providers
    "langchain-openai>=0.1.0",

    # Document Processing
    "pandas>=2.0.0",
    "openpyxl>=3.1.0",
    "numpy>=1.24.0",

    # Additional utilities
    "tenacity>=8.2.0",  # Retry logic
]
```

---

## Testing Strategy (Phase 2)

### New Unit Tests

```python
# tests/unit/test_validation_agent.py
@pytest.mark.asyncio
async def test_document_analysis():
    """Test document analysis."""
    analyzer = DocumentAnalyzer(mock_llm)
    result = await analyzer.analyze(
        "test_data/sample_documents/valid_excel.xlsx",
        "Excel with 10 rows"
    )
    assert "document_type" in result
    assert result["document_type"] == "excel"

@pytest.mark.asyncio
async def test_python_execution_sandbox():
    """Test sandboxed Python execution."""
    executor = PythonExecutor(timeout_seconds=5)

    # Safe code should work
    result = await executor.execute("print('hello')")
    assert result["success"]

    # Dangerous code should be blocked
    result = await executor.execute("import os; os.system('ls')")
    assert not result["success"]
    assert "Security validation failed" in result["error"]

# tests/unit/test_clarification.py
@pytest.mark.asyncio
async def test_faq_matching():
    """Test FAQ matching."""
    matcher = FAQMatcher(mock_llm)
    result = await matcher.find_answer(
        question="What format should the file be?",
        faq_content="Q: What format?\nA: Excel .xlsx format"
    )
    assert result["found"]
    assert result["confidence"] > 0.5

# tests/unit/test_escalation.py
@pytest.mark.asyncio
async def test_timeout_monitoring():
    """Test timeout monitoring."""
    monitor = TimeoutMonitor(default_timeout_hours=1)

    # Recent email - no timeout
    recent = datetime.utcnow().isoformat()
    result = monitor.check_timeout(recent)
    assert not result["is_timeout"]

    # Old email - timeout
    old = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    result = monitor.check_timeout(old)
    assert result["is_timeout"]
```

### Integration Tests

```python
# tests/integration/test_full_workflow.py
@pytest.mark.asyncio
async def test_complete_workflow_with_validation():
    """Test complete workflow including validation."""
    # Create workflow
    workflow_id = await create_test_workflow()

    # Upload all 4 files
    await upload_file(workflow_id, "instructions", "test_data/instructions_example.txt")
    await upload_file(workflow_id, "faq", "test_data/faq_example.txt")
    await upload_file(workflow_id, "escalation", "test_data/escalation_example.txt")
    await upload_file(workflow_id, "validation", "test_data/validation_example.txt")

    # Start workflow
    await start_workflow(workflow_id)

    # Approve plan
    await approve_plan(workflow_id)

    # Simulate email response with attachment
    await simulate_email_response(
        workflow_id,
        attachment="test_data/sample_documents/valid_excel.xlsx"
    )

    # Wait for completion
    status = await wait_for_completion(workflow_id)

    assert status == "completed"
    assert status["validation_result"]["passed"]

# tests/integration/test_ag_ui_streaming.py
@pytest.mark.asyncio
async def test_ag_ui_event_streaming():
    """Test AG-UI event streaming."""
    workflow_id = await create_test_workflow()

    events = []

    async def collect_events():
        async for event in event_streamer.subscribe(workflow_id):
            events.append(json.loads(event))
            if len(events) >= 5:
                break

    # Start collecting
    task = asyncio.create_task(collect_events())

    # Emit some events
    await event_streamer.emit(workflow_id, AGUIEventType.RUN_STARTED, {})
    await event_streamer.emit(workflow_id, AGUIEventType.TOOL_CALL_START, {"tool": "test"})

    await task

    assert len(events) >= 2
    assert events[0]["type"] == "RUN_STARTED"
```

---

## Phase 2 Completion Criteria

- [ ] Validation Agent running on port 8002 and registered
- [ ] Document analysis working (Excel, CSV, text, JSON)
- [ ] Python execution sandboxed and secure
- [ ] FAQ matching with LLM working
- [ ] Escalation flow triggering correctly
- [ ] Timeout monitoring and retry logic working
- [ ] AG-UI SSE streaming functional
- [ ] Multi-provider LLM support working
- [ ] Complete LangGraph workflow executing all paths
- [ ] All unit and integration tests passing
- [ ] Full workflow test (with validation) completing successfully

---

## Next Phase Preview

**Phase 3: MVP UI** will add:
- Basic frontend templates with Tailwind CSS
- HTMX for dynamic updates
- Workflow creation view (file upload)
- Basic execution status view (polling-based)
- Mock Email Server Web UI

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-13 | Claude | Initial Phase 2 architecture document |
