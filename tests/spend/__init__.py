"""Spend end-to-end tests for synapseForge.

Verifies that a real chat flow records token usage and cost into the ``spend``
table (via the LLM choke points in ``agent.py``) and that the recorded data can
be recovered through the billing REST endpoints.

Follows the same declarative YAML methodology as ``tests.e2e.runner``: no mocks,
real endpoints, asserting on contract structure and recorded values.

Usage::

    python -m tests.spend.runner                       # all scenarios
    python -m tests.spend.runner --only spend          # single scenario by name
    python -m tests.spend.runner --base-url http://127.0.0.1:8000

Prerequisites: the backend must be running and configured with a cloud provider
(LOCAL/Ollama has no cost and records nothing).
"""