"""Trace identifier helpers."""

from uuid import uuid4


def new_trace_id() -> str:
    """Return a new trace identifier for a cognitive cycle or decision."""
    return f"trace_{uuid4().hex}"
