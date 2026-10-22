"""
CodeMind AI — Security & Authentication.

Provides:
  • JWT validation for Supabase Auth tokens
  • get_current_user() dependency for protected routes
  • Utility functions for token extraction and validation
"""

import time
from typing import Optional
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import Settings, get_settings


# ── Models ───────────────────────────────────────────

class AuthenticatedUser(BaseModel):
    """Represents a validated, authenticated user from Supabase JWT."""
    id: UUID
    email: Optional[str] = None
    role: str = "authenticated"
    
    class Config:
        frozen = True


# ── Bearer Token Scheme ──────────────────────────────

_bearer_scheme = HTTPBearer(
    scheme_name="Supabase JWT",
    description="Pass the Supabase access_token as a Bearer token",
    auto_error=True,
)


# ── In-Memory Token Cache & Shared Client ───────────
# Caches validated Supabase auth user payloads for 120s to eliminate
# 1000ms+ roundtrip TLS handshakes on every single API request.
_token_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL_SECONDS = 120.0
_shared_client: Optional[httpx.AsyncClient] = None


def _get_auth_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
    return _shared_client


# ── JWT Validation ───────────────────────────────────

async def _verify_supabase_token(
    token: str, settings: Settings
) -> dict:
    """
    Verify a Supabase JWT by calling Supabase's auth API with caching.
    Cached for 120s to provide sub-millisecond route transitions.
    """
    now = time.time()
    
    # 1. Fast path: check in-memory cache
    if token in _token_cache:
        cached_data, cached_at = _token_cache[token]
        if (now - cached_at) < _CACHE_TTL_SECONDS:
            return cached_data
        else:
            _token_cache.pop(token, None)

    # 2. Remote validation over persistent HTTP pool
    client = _get_auth_client()
    try:
        response = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_anon_key,
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to contact authentication provider",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_data = response.json()
    
    # Store in cache
    _token_cache[token] = (user_data, now)
    
    # Periodic sweep if cache grows large
    if len(_token_cache) > 500:
        expired = [t for t, (_, ts) in _token_cache.items() if (now - ts) >= _CACHE_TTL_SECONDS]
        for t in expired:
            _token_cache.pop(t, None)
            
    return user_data


# ── Dependencies ─────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    FastAPI dependency that validates the Bearer token and returns the user.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
            return {"user_id": str(user.id)}
    """
    token = credentials.credentials
    
    try:
        user_data = await _verify_supabase_token(token, settings)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    
    return AuthenticatedUser(
        id=UUID(user_data["id"]),
        email=user_data.get("email"),
        role=user_data.get("role", "authenticated"),
    )


async def get_optional_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Optional[AuthenticatedUser]:
    """
    Optional auth — returns None if no token provided.
    Useful for endpoints that work both authenticated and anonymously.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ", 1)[1]
    try:
        user_data = await _verify_supabase_token(token, settings)
        return AuthenticatedUser(
            id=UUID(user_data["id"]),
            email=user_data.get("email"),
            role=user_data.get("role", "authenticated"),
        )
    except Exception:
        return None


def require_repo_ownership(user_id: UUID, repo_user_id: UUID) -> None:
    """
    Verify that the authenticated user owns the repository.
    Raises 403 if not.
    
    This is an app-layer check in addition to RLS (defense in depth).
    """
    if user_id != repo_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this repository",
        )
