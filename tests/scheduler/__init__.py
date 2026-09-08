"""Scheduler end-to-end tests for synapseForge.

Verifies the scheduled-task CRUD lifecycle against a live backend: creation,
listing, update, the permissions catalog and deletion. Follows the same
declarative YAML methodology as ``tests.e2e.runner``: no mocks, real endpoints,
asserting on contract structure and persisted values.

Usage::

    python -m tests.scheduler.runner                       # all scenarios
    python -m tests.scheduler.runner --only scheduler      # single scenario
    python -m tests.scheduler.runner --base-url http://127.0.0.1:8000

Prerequisites: the backend must be running.
"""