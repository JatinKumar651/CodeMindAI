"""
CodeMind AI — Structured Logging.

Uses structlog for JSON-formatted, context-rich logging.
Every log entry includes:
  • request_id (correlation ID)
  • user_id (if authenticated)
  • timestamp
  • module/function info
"""

import sys
import uuid
from typing import Optional

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


def setup_logging(debug: bool = False) -> None:
    """
    Configure structlog for the application.
    Call once at startup in main.py.
    """
    import logging

    # Ensure UTF-8 encoding for stdout and stderr on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    min_level = logging.DEBUG if debug else logging.INFO
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            # In production, use JSONRenderer; in dev, use ConsoleRenderer
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a bound logger with optional module name.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("something happened", user_id="abc", action="query")
    """
    log = structlog.get_logger()
    if name:
        log = log.bind(module=name)
    return log


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
      1. Generates a unique request_id for each request
      2. Binds it to structlog context (available in all downstream logs)
      3. Logs request start/end with latency
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        
        # Bind request context to structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )
        
        logger = get_logger("http")
        logger.info("request_started")
        
        import time
        start = time.perf_counter()
        
        try:
            response = await call_next(request)
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            
            logger.info(
                "request_completed",
                status_code=response.status_code,
                latency_ms=latency_ms,
            )
            
            # Add request_id to response headers for tracing
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as e:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
                latency_ms=latency_ms,
            )
            raise
