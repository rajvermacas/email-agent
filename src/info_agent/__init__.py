"""
Info-Agent: Multi-agent information retrieval and validation system.

This package provides a complete multi-agent system for:
- Automated email communication with external parties
- Intelligent clarification handling using FAQ or escalation
- Document validation using LLM and Python execution
- Real-time dashboard visibility via AG-UI protocol

Components:
- Supervisor Agent: Central orchestrator (embedded in FastAPI Gateway)
- Mail Agent: Email sending, receiving, and parsing (A2A worker)
- Validation Agent: Document validation with LLM + Python (A2A worker)
- A2A Registry: Agent registration and discovery (embedded in Gateway)
- Mock Email Server: SMTP + REST API for development/demo
"""

__version__ = "0.1.0"
__author__ = "Info-Agent Team"
