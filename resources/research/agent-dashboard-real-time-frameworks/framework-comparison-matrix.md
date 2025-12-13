# Agent Dashboard Frameworks: Quick Comparison Matrix

## Feature Comparison Table

| Feature | AG-UI | Chainlit | FastAPI + HTMX | Streamlit |
|---------|-------|----------|-----------------|-----------|
| **Maturity** | Emerging (2024) | Proven | Proven | Proven |
| **Learning Curve** | Moderate | Low | Moderate | Very Low |
| **Production Ready** | Yes (with support) | Yes | Yes | Partial |
| **Time to Deploy** | 2-3 weeks | 3-5 days | 2-3 weeks | 1-2 days |
| **Customization** | High (protocol) | Medium | Very High | Low |
| **Performance** | High (SSE native) | High (WebSocket) | Very High | Medium |
| **Streaming Support** | Native (event-based) | Native (async) | Native (SSE) | Limited |
| **Chat UI** | Custom required | Built-in | Custom required | Built-in |
| **Dashboard UI** | Custom required | Limited | Native (HTML) | Built-in |
| **Framework Agnostic** | Yes | Partial | Yes | No |
| **Standards-Based** | Yes (AG-UI spec) | No (proprietary) | No (HTTP standard) | No |
| **DevOps Friendly** | Yes | Yes | Yes | Medium |
| **TypeScript Support** | Yes (@ag-ui/langgraph) | Yes | Requires npm | No |
| **Python SDK Quality** | Good | Excellent | N/A | Excellent |
| **Community Size** | Growing | Large | Large | Very Large |
| **Documentation** | Good (improving) | Excellent | Excellent | Excellent |
| **Real-time Updates** | SSE (unidirectional) | WebSocket (bidirectional) | SSE (unidirectional) | Polling (limited) |
| **Build/Bundle Size** | None | Small | None | Large |
| **npm Dependencies** | No | No (bundled React) | Minimal (HTMX) | Included |

---

## Use Case Recommendations

### When to Use AG-UI

**Perfect For:**
- Integrating with Microsoft Agent Framework, Google ADK, AWS Strands
- Multi-agent systems requiring standardized protocols
- Custom UI requirements with full control
- Organizations investing in agent infrastructure long-term
- Need for framework switching without frontend rewrite

**Example Stack:**
```
LangGraph/CrewAI → FastAPI → AG-UI Events → HTML/Tailwind/HTMX Frontend
```

**Current Limitations:**
- Smaller ecosystem of pre-built components
- Limited documentation compared to Chainlit
- Community still building best practices
- Less proven in large-scale production deployments

---

### When to Use Chainlit

**Perfect For:**
- Chat-first conversational AI applications
- Rapid prototyping and MVP development
- Teams wanting built-in observability and debugging
- Organizations using LangChain/LlamaIndex ecosystem
- Need for step-by-step execution visualization

**Example Stack:**
```
Any Agent Framework → Chainlit Decorators → Chainlit UI (React)
```

**Ideal Scenarios:**
- Customer support chat bots
- Internal copilots
- Research assistant interfaces
- Financial analysis assistants

**Trade-offs:**
- Not suitable for non-chat dashboards
- Limited UI customization
- Requires understanding Chainlit's async patterns
- Community-maintained (as of May 2025)

---

### When to Use FastAPI + HTMX + Tailwind

**Perfect For:**
- Organizations with strong HTML/CSS expertise
- Custom dashboard and chat UI combinations
- Zero npm/build process requirement
- Full control over every pixel
- Privacy/compliance concerns (all open source)

**Example Stack:**
```
LangGraph → FastAPI (Python) → Jinja2 Templates → HTMX + Tailwind
```

**Ideal Scenarios:**
- Enterprise internal tools with custom branding
- HIPAA/FedRAMP compliant applications
- Lightweight dashboards with streaming data
- Teams preferring server-side rendering

**Advantages:**
- Minimal dependencies (single Python process)
- Maximum debugging control
- SEO-friendly (server-rendered HTML)
- Great for traditional web developers

---

### When to Use Streamlit

**Perfect For:**
- Data science/analysis dashboards
- Quick prototypes and demos
- Non-interactive agent visualizations
- Data scientists (not software engineers)
- Visualization-heavy applications

**Example Stack:**
```
Agent → FastAPI (Backend) ⟷ Streamlit (Frontend via API calls)
```

**NOT Good For:**
- Real-time chat interactions
- Custom UI requirements
- Production applications needing fine-grained control
- Agents with continuous streaming

---

## Decision Matrix: Which Framework to Choose?

```
START: Do you need real-time agent dashboard?
├─ NO → Skip, use simple REST API
└─ YES ↓

Is chat the PRIMARY interface?
├─ YES ↓
│  └─ Want rapid MVP or production?
│     ├─ MVP (< 1 week) → CHAINLIT
│     └─ Production with control → AG-UI + Custom Frontend or Chainlit
│
└─ NO (Dashboard/mixed interface) ↓

Do you need maximum customization?
├─ YES → FastAPI + HTMX + Tailwind
└─ NO ↓

Do you want future standardization?
├─ YES → AG-UI Protocol (custom frontend)
└─ NO → Chainlit or FastAPI + HTMX

Is this for data science team?
├─ YES → Streamlit (if not real-time)
└─ NO → Chainlit or custom stack
```

---

## Technology Stack Detail Comparison

### AG-UI + Custom HTML/Tailwind

**Architecture:**
```
┌─────────────────────────────────────┐
│ Agent Execution                     │
│ (LangGraph, CrewAI, etc)           │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│ FastAPI + ag-ui-protocol SDK        │
│ - Event translation layer           │
│ - SSE streaming endpoint            │
│ - Input validation (Pydantic)       │
└────────────────┬────────────────────┘
                 │ (SSE stream)
                 ▼
┌─────────────────────────────────────┐
│ HTML5 + Tailwind CSS + HTMX         │
│ - Custom component library          │
│ - Full DOM control                  │
│ - Server-sent Events subscription   │
└─────────────────────────────────────┘
```

**Pros:**
- Event-driven, protocol-standardized
- No build step, pure HTML/CSS
- Lightweight and fast
- Framework-agnostic backend
- SSE simple and HTTP standard
- Full customization

**Cons:**
- More development effort
- Manual UI component building
- Event format translation needed
- No built-in debugging tools
- Smaller community

**Deployment:**
```bash
# Single container, single process
docker run -p 8000:8000 my-agent-app
```

---

### Chainlit

**Architecture:**
```
┌─────────────────────────────────────┐
│ Python Agent Code                   │
│ (decorated with @cl decorators)     │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│ Chainlit Framework                  │
│ - WebSocket connection mgmt         │
│ - Chat state management             │
│ - Observability layer               │
│ - Built-in UI components            │
└────────────────┬────────────────────┘
                 │ (WebSocket/Socket.IO)
                 ▼
┌─────────────────────────────────────┐
│ Chainlit React Frontend (bundled)   │
│ - Chat interface                    │
│ - Message history                   │
│ - Step visualization                │
│ - File upload support               │
└─────────────────────────────────────┘
```

**Pros:**
- Instant UI with zero frontend code
- Built-in async pattern support
- Integrated observability
- Production-ready deployment
- Strong community and docs
- Fast development

**Cons:**
- Chat-only paradigm
- Limited customization
- Proprietary (not standards-based)
- Bundled React even if not needed
- WebSocket required (not all networks support)

**Deployment:**
```bash
# Single command deployment
chainlit run app.py

# Or containerized
docker run -p 8000:8000 chainlit-app
```

---

### FastAPI + HTMX + Tailwind

**Architecture:**
```
┌─────────────────────────────────────┐
│ LangGraph Agent                     │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│ FastAPI Server                      │
│ - SSE endpoint for streams          │
│ - HTML template rendering           │
│ - Form handling                     │
│ - JSON API endpoints                │
└────────────────┬────────────────────┘
                 │
         ┌───────┴────────┐
         │ (HTTP/SSE)     │ (HTTP)
         ▼                ▼
┌──────────────────┐ ┌──────────────────┐
│ HTMX Client      │ │ REST API Calls   │
│ DOM Swapping     │ │ Form Submission  │
└──────────────────┘ └──────────────────┘
         │                │
         └────────┬───────┘
                  ▼
         ┌──────────────────┐
         │ HTML (Tailwind)  │
         │ Fully Styled     │
         └──────────────────┘
```

**Pros:**
- Full control over every detail
- No JavaScript framework overhead
- Server-side rendering benefits
- Minimal dependencies
- Perfect for traditional HTML developers
- Great for custom admin dashboards

**Cons:**
- More code to write
- Manual state management
- No pre-built components
- Less abstraction means more responsibility
- HTMX learning curve

**Deployment:**
```bash
# Standard ASGI deployment
uvicorn app:app --host 0.0.0.0 --port 8000

# Or containerized
docker run -p 8000:8000 my-fastapi-app
```

---

## Performance Characteristics

### Latency (Time from Agent Event to UI Update)

| Framework | Best Case | Typical Case | Worst Case | Notes |
|-----------|-----------|--------------|-----------|-------|
| **AG-UI + Custom** | 50ms | 100-200ms | 500ms | SSE has lower overhead |
| **Chainlit** | 100ms | 150-300ms | 1s | WebSocket connection overhead |
| **FastAPI + HTMX** | 30ms | 80-150ms | 300ms | Server-rendered HTML fastest |
| **Streamlit** | 500ms | 1-2s | 5s+ | Full page rerun model |

### Memory Usage (Per Connection)

| Framework | Idle | Active Stream | Notes |
|-----------|------|---------------|-------|
| **AG-UI** | 2-5 MB | 5-10 MB | Minimal, pure event stream |
| **Chainlit** | 5-10 MB | 15-30 MB | Maintains chat state |
| **FastAPI + HTMX** | 1-3 MB | 3-5 MB | Minimal templating overhead |
| **Streamlit** | 50-100 MB | 100-200 MB | Large base memory footprint |

### Scalability

| Framework | Concurrent Users | Recommended Setup |
|-----------|-----------------|-----------------|
| **AG-UI** | 100+ | Load balancer + multiple instances |
| **Chainlit** | 50-100 | Horizontal scaling with Redis |
| **FastAPI + HTMX** | 200+ | Load balancer + connection pooling |
| **Streamlit** | 5-20 | Not optimized for many concurrent users |

---

## Integration Paths

### Path 1: Future-Proof (Recommended for Long-term)

```
Start with: Chainlit (fastest MVP)
              ↓
         Get feedback, iterate
              ↓
        Migrate to: AG-UI + Custom Frontend
              ↓
      Future-proof for framework changes
```

**Timeline:** 3-6 months migration window

---

### Path 2: All-In AG-UI (Recommended for Teams Adopting Multiple Agents)

```
Start with: AG-UI + Custom Frontend
            ↓
     Build reusable event handlers
            ↓
    Scale across multiple agent deployments
            ↓
   Standardize infrastructure
```

**Timeline:** 4-8 weeks full implementation

---

### Path 3: Rapid MVP → Production Hardening

```
Week 1-2:  Streamlit prototype
           ↓
Week 3-4:  Migrate to Chainlit
           ↓
Week 5-8:  Optimize and harden
           ↓
Production: Chainlit stable
```

**Timeline:** 2 months to production

---

## Migration Paths Between Frameworks

### From Chainlit to AG-UI + Custom Frontend

**Effort:** Medium (2-3 weeks)

**Steps:**
1. Extract agent logic from Chainlit decorators
2. Implement FastAPI endpoint with AG-UI protocol
3. Rebuild frontend with HTML/Tailwind
4. Migrate message handling to event-based

**Benefits:**
- Gain customization
- Standardize on protocol
- Reduce Chainlit dependencies

---

### From Streamlit to FastAPI + HTMX

**Effort:** High (4-6 weeks)

**Steps:**
1. Refactor Streamlit app into modular functions
2. Implement FastAPI endpoints
3. Create Jinja2 templates
4. Wire HTMX for interactivity

**Benefits:**
- Proper async support
- Real-time streaming
- Better performance
- Custom UI

---

### From FastAPI + HTMX to AG-UI

**Effort:** Low (1-2 weeks)

**Steps:**
1. Add ag-ui-protocol SDK
2. Wrap FastAPI endpoints with AG-UI event emission
3. Update frontend to consume AG-UI events (mostly transparent)
4. Implement state synchronization

**Benefits:**
- Standardized protocol
- Better tooling and ecosystem
- Framework switching easier

---

## Quick Start Commands

### AG-UI + FastAPI

```bash
# Create project
mkdir my-agent-dashboard
cd my-agent-dashboard

# Setup Python
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn ag-ui-protocol langgraph pydantic

# Create main.py with AG-UI endpoint
# Create templates/ directory with HTML
# Create static/ directory with Tailwind CSS

# Run
uvicorn main:app --reload
```

### Chainlit

```bash
# Create and enter directory
mkdir my-agent-dashboard
cd my-agent-dashboard

# Install Chainlit
pip install chainlit

# Create app.py with agent logic
# Decorate with @cl decorators

# Run
chainlit run app.py
```

### FastAPI + HTMX + Tailwind

```bash
# Create project
mkdir my-agent-dashboard
cd my-agent-dashboard

# Setup Python
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn jinja2 langgraph pydantic

# Create directory structure
mkdir templates static

# Add Tailwind CSS CDN or local build
# Create templates/base.html
# Create main.py with FastAPI app

# Run
uvicorn main:app --reload
```

---

## Enterprise Readiness Checklist

### AG-UI Protocol

- [x] Official specification (GitHub open source)
- [x] Multiple SDK languages (Python, TypeScript, Java, Go, Rust)
- [x] Backed by major companies (Microsoft, Google, AWS)
- [x] Active development (bi-weekly working group)
- [x] MIT licensing
- [ ] Large-scale production deployments (limited public case studies)
- [ ] Enterprise support contracts (not yet available)
- [x] Clear migration paths
- [x] Community growing

**Readiness Score: 8/10** (Good for new projects, consider hybrid approach for existing)

---

### Chainlit

- [x] Official specification (proprietary)
- [x] Multiple SDKs (Python, TypeScript)
- [x] Established ecosystem (integrations with many frameworks)
- [ ] Active commercial support (not available, community-maintained)
- [x] Clear licensing (Apache 2.0)
- [x] Large-scale production deployments (publicly documented)
- [x] Extensive documentation
- [x] Active community
- [ ] SLA/Support (not enterprise-level yet)

**Readiness Score: 9/10** (Production-ready, best for chat applications)

---

### FastAPI + HTMX + Tailwind

- [x] Official specifications (HTTP, SSE, HTML standards)
- [x] Multiple implementations (all open source)
- [x] Wide adoption (FastAPI by Microsoft, Netflix, Uber)
- [x] Enterprise support available (each component independently)
- [x] Clear licensing (all open source)
- [x] Large-scale production deployments (well-documented)
- [x] Excellent documentation (each component strong)
- [x] Very active communities
- [x] Enterprise SLA support available

**Readiness Score: 10/10** (Best for traditional enterprises, maximum control)

---

### Streamlit

- [x] Official product (Streamlit Inc.)
- [x] Enterprise version available
- [x] Commercial support
- [x] Large company adoption
- [x] Well-funded and active development
- [x] Large-scale deployments (analytics/dashboards)
- [ ] Real-time agent streaming (not optimized for)
- [ ] Chat interface (not designed for)

**Readiness Score: 6/10 for agent dashboards** (Better for analytics/reports)

---

## Conclusion and Recommendation

**For FastAPI + HTML/Tailwind Stack:**

1. **Best Overall Choice**: AG-UI + Custom HTML/Tailwind Frontend
   - Most future-proof
   - Standards-based
   - Maximum customization
   - Aligns with industry direction

2. **Fastest to Market**: Chainlit
   - Production-ready immediately
   - But limited customization

3. **Best Control**: FastAPI + HTMX + Tailwind
   - All open source
   - Maximum flexibility
   - Steepest learning curve

**Recommended Path:**
- **Start with**: AG-UI + custom frontend (or Chainlit if time-constrained)
- **Stabilize with**: Add monitoring, testing, error handling
- **Scale with**: Containerization, load balancing, multi-instance deployment

**Don't use** pure Streamlit for real-time agent applications (architectural mismatch).
