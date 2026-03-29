"""
Request/Response logging middleware with correlation ID tracking.

This middleware logs:
- Request: method, path, headers (sanitized), body (if present)
- Response: status code, headers, body (if present), processing time
- Correlation ID for tracing requests through the system
"""

import json
import logging
import time
import uuid
from typing import Any, Dict

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from apps.common.logging_filters import set_correlation_id, clear_correlation_id

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log HTTP requests and responses with correlation IDs.

    Features:
    - Generates unique correlation ID for each request
    - Adds correlation ID to response headers for client tracking
    - Sanitizes sensitive data (passwords, tokens, authorization headers)
    - Logs request/response details in structured JSON format
    - Measures request processing time
    """

    # Sensitive headers to redact
    SENSITIVE_HEADERS = {
        'authorization',
        'cookie',
        'x-csrf-token',
        'set-cookie',
    }

    # Sensitive JSON keys to redact (case-insensitive)
    SENSITIVE_KEYS = {
        'password',
        'token',
        'access_token',
        'refresh_token',
        'api_key',
        'secret',
        'authorization',
        'cookie',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Process the request and log details.
        """
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        request.correlation_id = correlation_id

        # Set correlation ID in context for all logs during this request
        set_correlation_id(correlation_id)

        start_time = time.time()

        try:
            # Log the request
            self._log_request(request, correlation_id)

            # Get response
            response = self.get_response(request)

            # Calculate processing time
            process_time = (time.time() - start_time) * 1000  # Convert to ms

            # Log the response
            self._log_response(request, response, correlation_id, process_time)

            # Add correlation ID to response headers
            response['X-Correlation-ID'] = correlation_id

            return response
        finally:
            # Clear correlation ID from context
            clear_correlation_id()

    def _log_request(self, request, correlation_id: str):
        """
        Log request details.
        """
        try:
            log_data = {
                'correlation_id': correlation_id,
                'direction': 'request',
                'method': request.method,
                'path': request.get_full_path(),
                'scheme': request.scheme,
                'content_type': request.content_type or '',
                'headers': self._sanitize_headers(dict(request.headers)),
                # JWT is parsed inside the Ninja view — user is not yet known at request time
                'user': 'pending',
            }

            # Log request body only in DEBUG mode
            if settings.DEBUG and request.body and request.content_type and 'application/json' in request.content_type:
                try:
                    body = json.loads(request.body.decode('utf-8'))
                    log_data['body'] = self._sanitize_body(body)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    log_data['body'] = request.body.decode('utf-8', errors='replace')

            logger.info(f"Request: {request.method} {request.get_full_path()}", extra=log_data)
        except Exception as e:
            logger.error(f"Failed to log request: {e}", extra={'correlation_id': correlation_id})

    def _log_response(self, request, response, correlation_id: str, process_time: float):
        """
        Log response details.
        """
        try:
            log_data = {
                'correlation_id': correlation_id,
                'direction': 'response',
                'method': request.method,
                'path': request.get_full_path(),
                'status_code': response.status_code,
                'process_time_ms': round(process_time, 2),
                'headers': self._sanitize_headers(dict(response.items())),
                # By response time, Ninja has set request.auth if JWT was valid
                'user': self._resolve_user(request),
            }

            # Log response body only in DEBUG mode
            if settings.DEBUG:
                content_type = response.get('Content-Type', '')
                if 'application/json' in content_type:
                    try:
                        body = json.loads(response.content.decode('utf-8'))
                        log_data['body'] = self._sanitize_body(body)
                    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
                        log_data['body'] = response.content.decode('utf-8', errors='replace') if hasattr(response, 'content') else str(response)

            # Log at appropriate level based on status code
            if response.status_code >= 400:
                logger.warning(f"Response: {response.status_code} {request.get_full_path()}", extra=log_data)
            else:
                logger.info(f"Response: {response.status_code} {request.get_full_path()}", extra=log_data)
        except Exception as e:
            logger.error(f"Failed to log response: {e}", extra={'correlation_id': correlation_id})

    def _resolve_user(self, request) -> str:
        """
        Resolve the authenticated user from the request.

        Django Ninja sets request.auth (a domain User) after JWT validation inside
        the view. Django's session-based request.user is always AnonymousUser for
        JWT-only APIs, so we prefer request.auth when available.
        """
        # Django Ninja JWT auth sets request.auth after view authentication
        if hasattr(request, 'auth') and request.auth:
            return str(request.auth)
        # Fallback: Django session auth (e.g. admin panel)
        if hasattr(request, 'user') and request.user.is_authenticated:
            return str(request.user)
        return 'anonymous'

    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Sanitize headers by removing or masking sensitive values.
        """
        sanitized = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in self.SENSITIVE_HEADERS:
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = value
        return sanitized

    def _sanitize_body(self, body: Any) -> Any:
        """
        Recursively sanitize body data, masking sensitive fields.
        """
        if isinstance(body, dict):
            sanitized = {}
            for key, value in body.items():
                key_lower = str(key).lower()
                if any(sensitive in key_lower for sensitive in self.SENSITIVE_KEYS):
                    sanitized[key] = '***REDACTED***'
                else:
                    sanitized[key] = self._sanitize_body(value)
            return sanitized
        elif isinstance(body, list):
            return [self._sanitize_body(item) for item in body]
        else:
            return body
