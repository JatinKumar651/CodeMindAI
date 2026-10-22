"""
CodeMind AI — Rate Limiting Middleware.

Implements per-user and per-IP rate limiting using SlowAPI.
Protects against:
  • API abuse / denial of service
  • Groq API quota exhaustion (free tier: 30 req/min)
  • Cost explosion from excessive LLM calls
"""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import FastAPI, Request

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_user_identifier(request: Request) -> str:
    """
    Extract rate-limit key from request.
    Uses user_id from JWT if authenticated, falls back to IP address.
    """
    # Check if user was already extracted by auth middleware
    if hasattr(request.state, "user_id") and request.state.user_id:
        return f"user:{request.state.user_id}"
    
    # Check Authorization header for a quick user extraction
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # Use a hash of the token as identifier (avoid storing tokens)
        import hashlib
        token_hash = hashlib.sha256(auth_header.encode()).hexdigest()[:16]
        return f"token:{token_hash}"
    
    # Fall back to IP
    return f"ip:{get_remote_address(request)}"


# Create the limiter instance
limiter = Limiter(
    key_func=_get_user_identifier,
    default_limits=["200/minute"],
    storage_uri="memory://",  # Use Redis in production: "redis://localhost:6379"
)


def setup_rate_limiter(app: FastAPI) -> None:
    """
    Attach rate limiter to the FastAPI app.
    Call this in main.py during app setup.
    
    Route-specific limits are applied via decorators:
        @router.post("/chat")
        @limiter.limit("60/minute")
        async def send_message(request: Request, ...):
            ...
    """
    settings = get_settings()
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _custom_rate_limit_handler)
    
    logger.info(
        "rate_limiter_configured",
        chat_limit=settings.rate_limit_chat,
        ingestion_limit=settings.rate_limit_ingestion,
    )


async def _custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom handler that logs rate limit events to audit trail.
    """
    logger.warning(
        "rate_limit_exceeded",
        client=_get_user_identifier(request),
        path=request.url.path,
        limit=str(exc.detail),
    )
    
    # Use the default handler to return 429
    return await _rate_limit_exceeded_handler(request, exc)
