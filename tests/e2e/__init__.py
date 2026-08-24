"""End-to-end tests for synapseForge (declarative YAML scenarios).

Methodology ported from ProspectingAgent's E2E suite: a bot that writes
messages into the real chat flow (SSE) plus declarative scenario files,
asserting on contract structure and event sequences rather than exact
model text.

Usage::

    python -m tests.e2e.runner                       # all scenarios
    python -m tests.e2e.runner --only rag            # single scenario by name
    python -m tests.e2e.runner --base-url http://127.0.0.1:8000

Prerequisites: the backend must be running (``python -m uvicorn backend.main:app``
or the packaged app). Scenarios that need an LLM or provider keys require a
configured environment; otherwise they fail with a clear connection/contract
error.
"""
