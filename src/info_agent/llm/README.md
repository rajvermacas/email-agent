# LLM Module

This module provides LLM (Large Language Model) integration for the Info-Agent system using Google's Gemini via LangChain.

## Architecture

The module implements a provider pattern with lazy initialization and singleton factory functions for efficient resource usage:

- **GeminiProvider**: Wrapper class for Gemini LLM with lazy initialization
- **Factory Functions**: Singleton pattern for LLM instance management
- **Extensive Logging**: All operations are logged for debugging and monitoring
- **Error Handling**: Custom exceptions with detailed error information

## Components

### 1. GeminiProvider (`gemini_provider.py`)

The `GeminiProvider` class wraps Google's Gemini LLM using LangChain's `ChatGoogleGenerativeAI`.

**Features:**
- Lazy initialization (client only created when first requested)
- Configuration from application settings
- Override support for per-request customization
- Comprehensive logging for all operations
- No fallback defaults - raises exceptions for missing configuration

**Usage:**
```python
from info_agent.config import get_settings
from info_agent.llm.gemini_provider import GeminiProvider

settings = get_settings()
provider = GeminiProvider(settings)
llm = provider.get_chat_model()

# With overrides
llm = provider.get_chat_model(temperature=0.9, max_tokens=2048)
```

### 2. Factory Functions (`factory.py`)

Factory functions implement the singleton pattern to ensure efficient resource usage.

**Functions:**
- `get_gemini_llm(**kwargs)`: Get the configured LLM instance (singleton)
- `reset_llm_instance()`: Clear singleton (for testing)
- `is_llm_initialized()`: Check if singleton exists

**Usage:**
```python
from info_agent.llm import get_gemini_llm

# Get default instance (creates singleton on first call)
llm = get_gemini_llm()

# Get instance with custom parameters (creates new instance)
llm = get_gemini_llm(temperature=0.9)

# Check initialization status
from info_agent.llm import is_llm_initialized
print(f"Initialized: {is_llm_initialized()}")
```

## Configuration

The module uses settings from `info_agent.config.Settings`:

```python
# Required
google_api_key: str          # Google API key for Gemini

# Optional (with defaults)
llm_model: str = "gemini-2.5-flash"
llm_temperature: float = 0.7
llm_max_tokens: int = 4096
```

### Environment Variables

Set these in your `.env` file:

```bash
GOOGLE_API_KEY=your-google-api-key-here
LLM_MODEL=gemini-2.5-flash
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
```

## Usage Examples

### Basic Usage

```python
from info_agent.llm import get_gemini_llm

# Get the LLM instance
llm = get_gemini_llm()

# Use with async invoke
response = await llm.ainvoke("Hello, how are you?")
print(response.content)
```

### Using with LangChain Chains

```python
from info_agent.llm import get_gemini_llm
from langchain.prompts import ChatPromptTemplate

llm = get_gemini_llm()

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("user", "{input}")
])

chain = prompt | llm
response = await chain.ainvoke({"input": "What is AI?"})
```

### Custom Parameters

```python
from info_agent.llm import get_gemini_llm

# Creative task - high temperature
creative_llm = get_gemini_llm(temperature=0.9)
response = await creative_llm.ainvoke("Write a poem about coding")

# Analytical task - low temperature
analytical_llm = get_gemini_llm(temperature=0.1)
response = await analytical_llm.ainvoke("List the steps to deploy an app")
```

### Testing and Cleanup

```python
from info_agent.llm import get_gemini_llm, reset_llm_instance

# Use LLM
llm = get_gemini_llm()
# ... do work ...

# Reset singleton (e.g., in test teardown)
reset_llm_instance()
```

## Error Handling

The module raises `LLMError` exceptions with detailed error information:

```python
from info_agent.llm import get_gemini_llm
from info_agent.utils.exceptions import LLMError

try:
    llm = get_gemini_llm()
    response = await llm.ainvoke("Test prompt")
except LLMError as e:
    print(f"Error: {e.message}")
    print(f"Code: {e.code}")
    print(f"Model: {e.model}")
    print(f"Details: {e.details}")
```

## Logging

All operations are extensively logged using structured logging:

```python
# Logs include:
# - Provider initialization
# - Client creation (lazy initialization)
# - Parameter overrides
# - Errors and exceptions
# - Singleton lifecycle events
```

Log output example:
```
[info] Initializing GeminiProvider [model=gemini-2.5-flash temperature=0.7]
[info] GeminiProvider initialized successfully [lazy_initialization=True]
[info] Creating LLM client (lazy initialization) [model=gemini-2.5-flash]
[debug] ChatGoogleGenerativeAI client created [model=gemini-2.5-flash]
```

## Design Decisions

### Lazy Initialization

The provider uses lazy initialization to:
- Avoid API calls during application startup
- Allow configuration to be finalized before LLM creation
- Support testing without actual API credentials

### Singleton Pattern

The factory functions use the singleton pattern to:
- Avoid creating multiple LLM instances unnecessarily
- Reduce memory usage
- Simplify application code

### No Fallback Defaults

The module requires all essential configuration to be explicitly provided:
- Prevents silent failures from misconfiguration
- Makes configuration issues immediately visible
- Follows the "fail fast" principle

## Testing

Run the unit tests:

```bash
pytest tests/unit/test_llm.py -v
```

Test with a real API (requires valid `GOOGLE_API_KEY`):

```bash
python scripts/test_llm_module.py
```

## File Structure

```
llm/
├── __init__.py           # Module exports
├── gemini_provider.py    # GeminiProvider class (199 lines)
├── factory.py            # Factory functions (161 lines)
└── README.md             # This file
```

All files are under 200 lines as per project guidelines.

## Integration with Info-Agent

The LLM module is used throughout Info-Agent for:

1. **Supervisor Agent** (`agents/supervisor/`):
   - Parsing input instructions
   - Generating execution plans
   - Composing emails

2. **Workflow Orchestration** (`workflow/`):
   - Plan generation nodes
   - Content composition nodes
   - Response analysis nodes

Example from Supervisor Agent:
```python
from info_agent.llm import get_gemini_llm

async def generate_plan(state: SupervisorState) -> dict:
    """Generate execution plan using LLM."""
    llm = get_gemini_llm()

    prompt = f"""
    Create an execution plan to collect: {state['requested_info']}
    From: {state['target_email']}
    """

    response = await llm.ainvoke(prompt)
    plan = parse_json_response(response.content)

    return {"plan": plan}
```

## Troubleshooting

### Missing API Key

**Error:**
```
LLMError: GOOGLE_API_KEY is required but not provided
```

**Solution:**
Set `GOOGLE_API_KEY` in your `.env` file or environment variables.

### Invalid API Key

**Error:**
```
LLMError: Failed to create Gemini client: Invalid API key
```

**Solution:**
Get a valid API key from https://aistudio.google.com/apikey

### Client Creation Fails

**Error:**
```
LLMError: Failed to create Gemini client: [original error]
```

**Solution:**
Check the original error in `details.original_error`. Common causes:
- Network issues
- API quota exceeded
- Invalid model name

## Best Practices

1. **Use the factory function**: Always use `get_gemini_llm()` instead of creating `GeminiProvider` directly
2. **Reset in tests**: Always call `reset_llm_instance()` in test teardown
3. **Use overrides sparingly**: Only override parameters when necessary
4. **Handle errors**: Always wrap LLM calls in try-except blocks
5. **Log context**: Use structured logging to track LLM operations

## Future Enhancements

Planned for Phase 2:

- Multi-provider support (OpenAI, Anthropic, etc.)
- Response caching
- Rate limiting
- Token usage tracking
- Retry logic with exponential backoff
- Streaming responses
