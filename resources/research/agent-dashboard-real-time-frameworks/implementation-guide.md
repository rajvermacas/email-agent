# Real-Time Agent Dashboard: Implementation Guide

## Quick Start: Choose Your Path

This guide provides step-by-step instructions for implementing each approach.

---

## Option 1: AG-UI + Custom HTML/Tailwind (Recommended for Production)

### Step 1: Project Setup

```bash
# Create project directory
mkdir agent-dashboard
cd agent-dashboard

# Initialize Python virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Create project structure
mkdir -p app/templates app/static/{css,js} tests

# Initialize pyproject.toml
cat > pyproject.toml << 'EOF'
[project]
name = "agent-dashboard"
version = "0.1.0"
description = "Real-time agent dashboard using AG-UI and FastAPI"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "ag-ui-protocol>=0.4.0",
    "ag-ui-langgraph>=0.4.0",
    "langgraph>=0.1.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.24.0",
]
EOF

# Install dependencies
pip install -e ".[dev]"
```

### Step 2: Implement FastAPI Backend with AG-UI

```python
# app/main.py
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ag_ui_protocol import (
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    ToolCallStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    RunFinishedEvent,
    RunErrorEvent,
    EventEncoder,
)

from app.agent import create_agent
from app.config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load settings
settings = Settings()

# Initialize agent
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing agent on startup")
    app.state.agent = create_agent()
    yield
    logger.info("Shutting down agent")

app = FastAPI(
    title="Agent Dashboard API",
    description="Real-time agent dashboard using AG-UI protocol",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration (restrict to your domain in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Models
class AgentInput(BaseModel):
    """Input to agent execution"""
    message: str = Field(..., min_length=1, max_length=10000)
    user_id: str = Field(..., pattern="^[a-zA-Z0-9_-]+$")

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agent_ready": app.state.agent is not None,
    }

# Root endpoint
@app.get("/")
async def root():
    """Serve dashboard HTML"""
    from fastapi.responses import FileResponse
    return FileResponse("app/templates/index.html")

# Main agent endpoint with AG-UI streaming
@app.post("/api/run")
async def run_agent(input_data: AgentInput):
    """
    Execute agent and stream AG-UI protocol events.

    This endpoint implements the AG-UI protocol, streaming a sequence
    of typed events that describe the agent's execution lifecycle and
    message content to the client.
    """

    logger.info(
        "Agent execution started",
        extra={
            "user_id": input_data.user_id,
            "message_length": len(input_data.message),
        }
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        """Generate AG-UI protocol events from agent execution"""

        encoder = EventEncoder()

        # Emit lifecycle event
        run_started = RunStartedEvent()
        yield encoder.encode(run_started)

        try:
            # Execute agent with streaming
            message_buffer = ""

            async for event in app.state.agent.stream(
                {"message": input_data.message},
                config={"user_id": input_data.user_id}
            ):
                logger.debug(f"Agent event: {event}")

                # Route events based on type
                if event["type"] == "message":
                    # Stream text message content
                    content = event["data"].get("content", "")

                    # Emit message start event
                    if not message_buffer:
                        msg_start = TextMessageContentEvent(
                            content=content[:1],
                            is_first=True
                        )
                        yield encoder.encode(msg_start)
                        message_buffer = content[1:]
                    else:
                        message_buffer += content

                    # Emit message content events
                    for chunk in [message_buffer[i:i+50]
                                  for i in range(0, len(message_buffer), 50)]:
                        if chunk:
                            msg_event = TextMessageContentEvent(
                                content=chunk
                            )
                            yield encoder.encode(msg_event)

                elif event["type"] == "tool_call":
                    # Stream tool execution
                    tool_call = event["data"]

                    tool_start = ToolCallStartEvent(
                        tool_name=tool_call["name"]
                    )
                    yield encoder.encode(tool_start)

                    # Emit args
                    tool_args = ToolCallArgsEvent(
                        args=json.dumps(tool_call.get("args", {}))
                    )
                    yield encoder.encode(tool_args)

                    # TODO: Emit tool result when available
                    tool_end = ToolCallEndEvent(
                        output=json.dumps({"status": "completed"})
                    )
                    yield encoder.encode(tool_end)

                elif event["type"] == "state_snapshot":
                    # State synchronization
                    logger.debug("State snapshot received")

            # Emit message end
            if message_buffer:
                msg_end = TextMessageEndEvent()
                yield encoder.encode(msg_end)

            # Emit completion event
            run_finished = RunFinishedEvent()
            yield encoder.encode(run_finished)

            logger.info(
                "Agent execution completed",
                extra={"user_id": input_data.user_id}
            )

        except Exception as e:
            logger.error(
                "Agent execution failed",
                extra={
                    "user_id": input_data.user_id,
                    "error": str(e),
                },
                exc_info=True
            )

            # Emit error event
            run_error = RunErrorEvent(error=str(e))
            yield encoder.encode(run_error)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable proxy buffering
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Step 3: Create Agent Configuration

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    openai_api_key: str
    model: str = "gpt-4-turbo"
    max_iterations: int = 10
    timeout_seconds: int = 300

    class Config:
        env_file = ".env"

# app/agent.py
from typing import Any
from langgraph.graph import StateGraph
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from app.config import Settings

settings = Settings()

def create_agent():
    """Create and return LangGraph agent"""

    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.model,
        temperature=0,
        streaming=True,
    )

    # Define tools (example)
    tools = [
        # Add your tools here
    ]

    # Create agent
    agent = create_react_agent(
        llm,
        tools=tools,
        max_iterations=settings.max_iterations,
    )

    return agent
```

### Step 4: Create Frontend HTML

```html
<!-- app/templates/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org"></script>
</head>
<body class="bg-gray-50">
    <div class="max-w-4xl mx-auto p-4">
        <!-- Header -->
        <div class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">Agent Dashboard</h1>
            <p class="text-gray-600 mt-2">Real-time agent execution with streaming events</p>
        </div>

        <!-- Main container -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <!-- Chat panel -->
            <div class="md:col-span-2">
                <div class="bg-white rounded-lg shadow h-[600px] flex flex-col">
                    <!-- Messages -->
                    <div id="messages" class="flex-1 overflow-y-auto p-4 space-y-4">
                        <div class="text-gray-500 text-sm">
                            Messages will appear here...
                        </div>
                    </div>

                    <!-- Input form -->
                    <div class="border-t p-4">
                        <form id="message-form" class="flex gap-2">
                            <input
                                type="text"
                                id="message-input"
                                placeholder="Type your message..."
                                class="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                required
                            />
                            <button
                                type="submit"
                                class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                            >
                                Send
                            </button>
                        </form>
                    </div>
                </div>
            </div>

            <!-- Sidebar: Status and Events -->
            <div class="bg-white rounded-lg shadow p-4 h-fit">
                <h2 class="text-lg font-semibold mb-4">Status</h2>

                <!-- Connection status -->
                <div class="mb-4">
                    <p class="text-sm text-gray-600">Connection</p>
                    <p id="status" class="text-green-600 font-semibold">Ready</p>
                </div>

                <!-- Recent events -->
                <h3 class="text-sm font-semibold mb-2 text-gray-700">Recent Events</h3>
                <div id="events" class="space-y-2 max-h-64 overflow-y-auto text-xs text-gray-600">
                    <div>Ready to start...</div>
                </div>
            </div>
        </div>
    </div>

    <script src="/static/js/app.js"></script>
</body>
</html>
```

### Step 5: Implement Frontend JavaScript

```javascript
// app/static/js/app.js
class AgentDashboard {
    constructor() {
        this.messageForm = document.getElementById('message-form');
        this.messageInput = document.getElementById('message-input');
        this.messagesDiv = document.getElementById('messages');
        this.eventsDiv = document.getElementById('events');
        this.statusDiv = document.getElementById('status');
        this.isStreaming = false;

        this.setupEventListeners();
    }

    setupEventListeners() {
        this.messageForm.addEventListener('submit', (e) => this.handleSubmit(e));
    }

    async handleSubmit(e) {
        e.preventDefault();

        const message = this.messageInput.value.trim();
        if (!message) return;

        const userId = this.getUserId();

        // Add user message to UI
        this.addMessage(message, 'user');

        // Clear input
        this.messageInput.value = '';
        this.messageInput.disabled = true;

        // Stream agent response
        await this.streamAgentResponse(message, userId);

        this.messageInput.disabled = false;
        this.messageInput.focus();
    }

    async streamAgentResponse(message, userId) {
        this.isStreaming = true;
        this.updateStatus('Streaming...', 'blue');

        let currentMessage = '';
        let messageElement = null;

        try {
            const response = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    user_id: userId,
                }),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();

                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;

                    try {
                        const event = JSON.parse(line.slice(6));
                        this.handleAgentEvent(event, (msg) => {
                            currentMessage = msg;
                            if (!messageElement) {
                                messageElement = this.addMessage('', 'agent');
                            }
                            messageElement.textContent = msg;
                        });
                    } catch (e) {
                        console.error('Invalid event:', e);
                    }
                }
            }

            this.updateStatus('Ready', 'green');

        } catch (error) {
            console.error('Stream error:', error);
            this.addMessage(`Error: ${error.message}`, 'error');
            this.updateStatus('Error', 'red');
        } finally {
            this.isStreaming = false;
        }
    }

    handleAgentEvent(event, updateMessage) {
        const eventName = event.type || 'UNKNOWN';
        this.logEvent(eventName);

        switch (event.type) {
            case 'RUN_STARTED':
                this.updateStatus('Executing...', 'yellow');
                break;

            case 'TEXT_MESSAGE_CONTENT':
                if (event.content) {
                    updateMessage((event.content || ''));
                }
                break;

            case 'TOOL_CALL_START':
                this.logEvent(`Tool: ${event.tool_name}`);
                break;

            case 'RUN_FINISHED':
                this.updateStatus('Complete', 'green');
                break;

            case 'RUN_ERROR':
                this.addMessage(`Error: ${event.error}`, 'error');
                this.updateStatus('Error', 'red');
                break;
        }
    }

    addMessage(content, role) {
        // Remove placeholder
        const placeholder = this.messagesDiv.querySelector('.text-gray-500');
        if (placeholder) placeholder.remove();

        // Create message element
        const element = document.createElement('div');
        element.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'}`;

        const contentElement = document.createElement('div');
        contentElement.className = `
            max-w-xs px-4 py-2 rounded-lg
            ${role === 'user'
                ? 'bg-blue-600 text-white'
                : role === 'error'
                    ? 'bg-red-100 text-red-900'
                    : 'bg-gray-100 text-gray-900'
            }
        `;
        contentElement.textContent = content;

        element.appendChild(contentElement);
        this.messagesDiv.appendChild(element);

        // Auto-scroll to bottom
        this.messagesDiv.scrollTop = this.messagesDiv.scrollHeight;

        return contentElement;
    }

    logEvent(eventName) {
        // Remove placeholder
        const placeholder = this.eventsDiv.querySelector(':first-child');
        if (placeholder?.textContent === 'Ready to start...') {
            placeholder.remove();
        }

        // Add event
        const eventElement = document.createElement('div');
        eventElement.className = 'text-xs text-gray-500 py-1';
        eventElement.textContent = `${new Date().toLocaleTimeString()}: ${eventName}`;

        this.eventsDiv.insertBefore(eventElement, this.eventsDiv.firstChild);

        // Keep only last 20 events
        while (this.eventsDiv.children.length > 20) {
            this.eventsDiv.removeChild(this.eventsDiv.lastChild);
        }
    }

    updateStatus(text, color = 'gray') {
        this.statusDiv.textContent = text;
        this.statusDiv.className = `font-semibold text-${color}-600`;
    }

    getUserId() {
        let userId = localStorage.getItem('userId');
        if (!userId) {
            userId = 'user_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('userId', userId);
        }
        return userId;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new AgentDashboard();
});
```

### Step 6: Create .env File

```bash
# .env
OPENAI_API_KEY=sk-your-key-here
MODEL=gpt-4-turbo
MAX_ITERATIONS=10
TIMEOUT_SECONDS=300
```

### Step 7: Run the Application

```bash
# Terminal 1: Start the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Visit in browser
# http://localhost:8000
```

---

## Option 2: Chainlit (Fastest to Market)

### Step 1: Setup

```bash
mkdir agent-dashboard
cd agent-dashboard

python3 -m venv venv
source venv/bin/activate

pip install chainlit langgraph pydantic python-dotenv openai
```

### Step 2: Create Agent App

```python
# app.py
import chainlit as cl
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import os

# Get LLM
llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4-turbo",
    temperature=0,
    streaming=True,
)

# Create agent
agent = create_react_agent(llm, tools=[])  # Add tools here

@cl.on_chat_start
async def on_chat_start():
    """Initialize session"""
    cl.user_session.set("agent", agent)
    await cl.Message(content="Hello! I'm your AI agent. How can I help?").send()

@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages"""
    agent = cl.user_session.get("agent")

    # Stream response
    response_msg = cl.Message(content="")

    async for chunk in agent.astream({"messages": [{"role": "user", "content": message.content}]}):
        if "text" in chunk:
            await response_msg.stream_token(chunk["text"])

    await response_msg.send()

if __name__ == "__main__":
    cl.run()
```

### Step 3: Run

```bash
chainlit run app.py
```

---

## Option 3: FastAPI + HTMX + Tailwind

### Step 1: Setup

```bash
mkdir agent-dashboard
cd agent-dashboard

python3 -m venv venv
source venv/bin/activate

pip install fastapi uvicorn jinja2 langgraph pydantic python-dotenv openai
```

### Step 2: Create Project Structure

```bash
mkdir -p templates static/css static/js
touch app.py
touch .env
```

### Step 3: Implement FastAPI Server

```python
# app.py
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

class MessageInput(BaseModel):
    message: str

@app.get("/")
async def index():
    return FileResponse("templates/index.html")

@app.post("/api/stream")
async def stream_message(input_data: MessageInput):
    """Stream agent response via SSE"""

    async def event_generator():
        # Simulate agent processing
        yield "data: {\"type\": \"start\"}\n\n"

        words = input_data.message.split()
        response = f"You said: {input_data.message}"

        for i, char in enumerate(response):
            # Simulate streaming
            await asyncio.sleep(0.01)

            data = {
                "type": "text",
                "content": char,
                "progress": int((i / len(response)) * 100),
            }
            yield f"data: {json.dumps(data)}\n\n"

        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Step 4: Create HTML Template

```html
<!-- templates/index.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Agent Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org"></script>
</head>
<body class="bg-gray-50">
    <div class="max-w-2xl mx-auto p-4">
        <h1 class="text-2xl font-bold mb-4">Agent Dashboard</h1>

        <div class="bg-white rounded shadow p-4">
            <!-- Chat display -->
            <div id="messages" class="h-96 overflow-y-auto mb-4 p-4 border rounded bg-gray-50">
                <p class="text-gray-400">Messages will appear here...</p>
            </div>

            <!-- Input form -->
            <form id="message-form" class="flex gap-2">
                <input
                    type="text"
                    name="message"
                    placeholder="Type message..."
                    class="flex-1 px-4 py-2 border rounded"
                    required
                />
                <button
                    type="submit"
                    class="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                    Send
                </button>
            </form>
        </div>
    </div>

    <script>
        const form = document.getElementById('message-form');
        const messagesDiv = document.getElementById('messages');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const input = form.querySelector('input[name="message"]');
            const message = input.value;
            input.value = '';

            // Add user message
            const userMsg = document.createElement('div');
            userMsg.className = 'text-right mb-2';
            userMsg.innerHTML = `<div class="inline-block bg-blue-600 text-white px-4 py-2 rounded">${message}</div>`;
            messagesDiv.appendChild(userMsg);

            // Create agent message element
            const agentMsg = document.createElement('div');
            agentMsg.className = 'mb-2';
            agentMsg.innerHTML = '<div class="inline-block bg-gray-200 px-4 py-2 rounded"><span id="response"></span></div>';
            messagesDiv.appendChild(agentMsg);

            // Stream response
            const response = await fetch('/api/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let content = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;

                    const data = JSON.parse(line.slice(6));

                    if (data.type === 'text') {
                        content += data.content;
                        document.getElementById('response').textContent = content;
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    }
                }
            }
        });
    </script>
</body>
</html>
```

### Step 5: Run

```bash
python app.py
# Visit http://localhost:8000
```

---

## Testing and Debugging

### Test AG-UI Event Stream

```bash
# Using curl to test SSE endpoint
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "user_id": "test_user"}'

# You should see:
# data: {"type":"RUN_STARTED",...}
# data: {"type":"TEXT_MESSAGE_CONTENT",...}
# data: {"type":"RUN_FINISHED",...}
```

### Debug EventSource Connection

```javascript
const eventSource = new EventSource('/api/stream');

eventSource.addEventListener('open', () => {
    console.log('Connection opened');
});

eventSource.addEventListener('message', (e) => {
    console.log('Event:', e.data);
});

eventSource.addEventListener('error', (e) => {
    console.error('Error:', e);
    if (eventSource.readyState === EventSource.CLOSED) {
        console.log('Connection closed');
    }
});
```

### Load Testing

```bash
# Install Apache Bench
apt-get install apache2-utils

# Test concurrent requests
ab -n 100 -c 10 -p payload.json -T application/json http://localhost:8000/api/run
```

---

## Production Checklist

- [ ] Implement proper error handling and logging
- [ ] Add input validation and sanitization
- [ ] Configure CORS properly (not `["*"]`)
- [ ] Add rate limiting
- [ ] Implement authentication/authorization
- [ ] Set appropriate timeouts
- [ ] Add monitoring and alerting
- [ ] Test with production load
- [ ] Document API and deployment
- [ ] Configure SSL/TLS
- [ ] Set up health checks
- [ ] Implement graceful shutdown
