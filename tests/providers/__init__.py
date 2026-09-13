"""Providers end-to-end tests for synapseForge.

Verifies the provider configuration endpoints: provider listing, API key
status, key validation (live check against the provider API, rejection of
unknown providers and empty keys) and model listing/capabilities served
from the startup cache and the synced model catalog.

Follows the same declarative YAML methodology as ``tests.e2e.runner``: no mocks,
real endpoints, asserting on contract structure. Scenarios never store a real
key and never delete a configured one.

Usage::

    python -m tests.providers.runner                       # all scenarios
    python -m tests.providers.runner --only providers-list  # single scenario by name
    python -m tests.providers.runner --base-url http://127.0.0.1:8000

Prerequisites: the backend must be running.
"""
