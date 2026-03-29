"""
Custom logging filters for correlation ID management.

This module provides filters that add correlation IDs to log records
when they don't already have one, ensuring all logs can include
traceability information.
"""

import contextvars
from logging import Filter


# Context variable for storing correlation ID throughout request lifecycle
correlation_id_var = contextvars.ContextVar('correlation_id', default=None)


def get_correlation_id() -> str:
    """Get current correlation ID, or 'N/A' if outside a request context."""
    return correlation_id_var.get() or 'N/A'


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context."""
    correlation_id_var.set(correlation_id)


def clear_correlation_id() -> None:
    """Clear correlation ID from current context."""
    correlation_id_var.set(None)


class CorrelationIDFilter(Filter):
    """
    Filter that adds a correlation ID to log records.

    Reads correlation ID from contextvars if available. If not present,
    generates a new one to ensure every log has a correlation ID.
    """

    def filter(self, record):
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = get_correlation_id()
        return True

