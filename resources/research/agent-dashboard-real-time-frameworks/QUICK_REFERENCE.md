# Quick Reference: Agent Dashboard Frameworks

## One-Minute Summary

| Aspect | AG-UI | Chainlit | FastAPI+HTMX |
|--------|-------|----------|--------------|
| **Setup Time** | 2-3 weeks | 3-5 days | 2-3 weeks |
| **Customization** | Very High | Medium | Very High |
| **Production Ready** | Yes (with support) | Yes | Yes |
| **Standards** | Yes (AG-UI spec) | Proprietary | HTTP standards |
| **Best For** | Long-term infrastructure | Quick MVP chat | Custom dashboards |
| **Code Complexity** | Moderate | Low | Moderate |
| **Dependencies** | Medium | Low | Very Low |

## Choose Your Framework in 30 Seconds

### Chainlit → If:
- [ ] Need working app in <1 week
- [ ] Chat interface is primary UI
- [ ] Don't need heavy customization
- [ ] WebSockets acceptable in your network

### AG-UI → If:
- [ ] Standards/future-proofing important
- [ ] Building multi-agent system
- [ ] Need custom UI alongside chat
- [ ] Want framework-agnostic architecture

### FastAPI+HTMX → If:
- [ ] Zero npm/JavaScript dependencies needed
- [ ] Compliance/HIPAA critical
- [ ] Full UI control essential
- [ ] Server-side rendering preferred

### Streamlit → If:
- [ ] Dashboards/analytics primary
- [ ] NOT real-time agent streaming
- [ ] Data science team building

## Installation Cheat Sheet

### AG-UI + FastAPI
```bash
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn ag-ui-protocol ag-ui-langgraph langgraph pydantic

# Then: Copy code from implementation-guide.md → Option 1
```

### Chainlit
```bash
python -m venv venv && source venv/bin/activate
pip install chainlit langgraph openai

# Then: Copy code from implementation-guide.md → Option 2
# Run: chainlit run app.py
```

### FastAPI + HTMX + Tailwind
```bash
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn jinja2 langgraph pydantic

# Then: Copy code from implementation-guide.md → Option 3
# Run: uvicorn app:app --reload
```

## Architecture in 10 Lines

### AG-UI Pattern
```
Agent → FastAPI (emit AG-UI events) → SSE stream → Browser (EventSource) → HTML update
```

### Chainlit Pattern
```
Agent → Chainlit decorators → WebSocket (Socket.IO) → React UI (bundled)
```

### FastAPI+HTMX Pattern
```
Agent → FastAPI (SSE endpoint) → Browser (HTMX) → HTML template swap → DOM update
```

## Streaming Code Template

### AG-UI
```python
async def event_generator():
    yield encoder.encode(RunStartedEvent())
    async for event in agent.stream(input_data):
        yield encoder.encode(TextMessageContentEvent(content=event.data))
    yield encoder.encode(RunFinishedEvent())

return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Chainlit
```python
@cl.on_message
async def on_message(message: cl.Message):
    msg = cl.Message(content="")
    async for token in agent.stream():
        await msg.stream_token(token)
    await msg.send()
```

### FastAPI+HTMX
```python
async def event_generator():
    async for chunk in agent.stream(input_data):
        data = {"type": "text", "content": chunk}
        yield f"data: {json.dumps(data)}\n\n"

return StreamingResponse(event_generator(), media_type="text/event-stream")
```

## Frontend Connection Code

### AG-UI (JavaScript)
```javascript
const eventSource = new EventSource('/api/run');
eventSource.onmessage = (e) => {
    const event = JSON.parse(e.data);
    handleAgentEvent(event);
};
```

### Chainlit
```python
# Automatic (handled by framework)
```

### FastAPI+HTMX
```html
<div hx-ext="sse" sse-connect="/api/stream" sse-swap="message">
    <!-- Updates appear here -->
</div>
```

## Performance Comparison (Approximate)

| Metric | AG-UI | Chainlit | FastAPI+HTMX |
|--------|-------|----------|--------------|
| Time to first byte | 50-100ms | 100-200ms | 30-80ms |
| Memory per user | 2-5MB | 5-10MB | 1-3MB |
| Max concurrent (1 instance) | 100+ | 50-100 | 200+ |
| Bundle size (frontend) | 0KB | 200KB+ | 0KB |

## When NOT to Use Each

### NOT Chainlit If:
- Need non-chat dashboard UI
- WebSockets blocked in your network
- Don't want React dependency

### NOT AG-UI If:
- Team unfamiliar with protocol concepts
- Don't need standards alignment
- Deadline < 5 days

### NOT FastAPI+HTMX If:
- Team prefers high-level abstractions
- Don't want to write custom UI
- React expertise preferred

## Troubleshooting Quick Fixes

### SSE not streaming?
- Check response headers: `Content-Type: text/event-stream`
- Add: `Cache-Control: no-cache`
- Check browser console for CORS errors

### Events not showing frontend?
- Verify event format: `data: {...}\n\n`
- Check EventSource listener: `onmessage` not `addEventListener`
- Monitor network tab for event stream

### WebSocket won't connect (Chainlit)?
- Check if WebSockets enabled in proxy/firewall
- Verify Socket.IO version compatibility
- Check browser console for connection errors

### HTMX swaps not working?
- Verify CSS selectors in `sse-swap` attribute
- Check that HTML fragments are valid
- Inspect Network tab for HTML content

## Migration Paths

### Streamlit → Chainlit
Time: 1-2 weeks | Effort: Medium | Difficulty: Easy-Medium

### Chainlit → AG-UI
Time: 2-3 weeks | Effort: Medium | Difficulty: Medium

### FastAPI+HTMX → AG-UI
Time: 1-2 weeks | Effort: Low | Difficulty: Easy

## Deployment Checklist (All Frameworks)

- [ ] Error handling implemented (try/except + logging)
- [ ] Input validation (Pydantic or equivalent)
- [ ] Rate limiting configured
- [ ] CORS properly restricted (not ["*"])
- [ ] Timeouts set (5-10 min for agent)
- [ ] Logging structured JSON
- [ ] Health check endpoint
- [ ] Graceful shutdown handling
- [ ] HTTPS/SSL configured
- [ ] Monitoring/alerts in place

## Resources by Framework

### AG-UI
- Docs: https://docs.ag-ui.com
- GitHub: https://github.com/ag-ui-protocol/ag-ui
- LangGraph integration: https://docs.langchain.com/langgraph-platform/generative-ui-react

### Chainlit
- Docs: https://docs.chainlit.io
- GitHub: https://github.com/Chainlit/chainlit

### FastAPI
- Docs: https://fastapi.tiangolo.com
- HTMX: https://htmx.org
- Tailwind: https://tailwindcss.com

## Cost Comparison (Approximate, Per Month)

### Small Deployment (10 users)
- AG-UI/FastAPI: $10-20 (container + monitoring)
- Chainlit SaaS: Free-50 (if using cloud)
- Self-hosted Chainlit: $10-20

### Medium Deployment (100 users)
- AG-UI/FastAPI: $50-100 (load balancer + instances)
- Chainlit: $50-200 (more instances/resources)
- FastAPI+HTMX: $50-100 (lightweight)

### Large Deployment (1000+ users)
- All: $500+ (depends on SLA/region)

## Final Decision Framework

```
START: What's your deadline?
├─ < 1 week → Chainlit
├─ 2-3 weeks → AG-UI or FastAPI+HTMX
└─ > 1 month → Any (optimize for long-term)

Do you need standardization?
├─ Yes → AG-UI
└─ No → Chainlit or FastAPI+HTMX

Is chat primary interface?
├─ Yes → Chainlit or AG-UI
└─ No → FastAPI+HTMX or AG-UI

Need zero npm dependencies?
├─ Yes → FastAPI+HTMX
└─ No → Any

Enterprise compliance critical?
├─ Yes → FastAPI+HTMX
└─ No → Any
```

## Recommended Template to Copy

1. Go to `/resources/research/agent-dashboard-real-time-frameworks/`
2. Open `implementation-guide.md`
3. Copy code from your chosen option (1, 2, or 3)
4. Run the setup commands
5. Customize for your agent

## One Last Thing

**Most organizations should start with Chainlit (fastest) and migrate to AG-UI (most standards-aligned) as system matures.**

This gives you:
- Fast MVP (1 week)
- Production stability (proven framework)
- Future flexibility (AG-UI path forward)
- Standards alignment (after initial success)

---

**Questions?** See the comprehensive analysis document for deep dives into any aspect.
