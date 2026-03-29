"""
Custom log formatters for structured file output and readable console output.
"""

import json
import logging
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    Structured JSON formatter for file-based log handlers.

    Produces one JSON object per line, suitable for log aggregation tools
    (e.g. Datadog, ELK, CloudWatch Logs).
    """

    # Standard LogRecord fields we never want in 'extra'
    _STDLIB_ATTRS = frozenset({
        'name', 'msg', 'args', 'created', 'filename', 'funcName',
        'levelname', 'levelno', 'lineno', 'module', 'msecs',
        'message', 'pathname', 'process', 'processName',
        'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
        'taskName', 'relativeCreated',
    })

    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcfromtimestamp(record.created).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', None),
        }

        # Merge any extra fields set by the middleware (user, direction, etc.)
        for key, value in record.__dict__.items():
            if key not in self._STDLIB_ATTRS and not key.startswith('_'):
                log_entry[key] = value

        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable formatter for console output.

    Displays key fields in a clean, scannable format with ANSI color support.
    """

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',
    }

    def __init__(self, use_colors=True):
        super().__init__()
        self.use_colors = use_colors

    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]
        level = record.levelname
        correlation_id = getattr(record, 'correlation_id', 'N/A')
        # Truncate to first 8 chars for readability; 'N/A' is already short
        cid_display = correlation_id[:8] if correlation_id and correlation_id != 'N/A' else correlation_id

        if self.use_colors and level in self.COLORS:
            level_str = f"{self.COLORS[level]}{level:8s}{self.COLORS['RESET']}"
        else:
            level_str = f"{level:8s}"

        header = f"{timestamp} {level_str} [{record.name[:30]:30s}] {cid_display}"
        output = [header, record.getMessage()]

        # Key fields to surface inline
        important_fields = ['direction', 'method', 'path', 'status_code',
                            'process_time_ms', 'user']
        for field in important_fields:
            value = getattr(record, field, None)
            if value is not None:
                suffix = 'ms' if field == 'process_time_ms' else ''
                output.append(f"  {field}: {value}{suffix}")

        # Headers summary
        if hasattr(record, 'headers'):
            output.append(f"  headers: {len(record.headers)} headers")

        # Body preview (only present in DEBUG mode per middleware config)
        if hasattr(record, 'body'):
            body_str = json.dumps(record.body, ensure_ascii=False)
            if len(body_str) > 200:
                body_str = body_str[:200] + '...'
            output.append(f"  body: {body_str}")

        if record.exc_info:
            output.append(self.formatException(record.exc_info))

        return '\n'.join(output)
