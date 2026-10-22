"""
CodeMind AI — Database & Supabase Client Setup.

Provides:
  • Async SQLAlchemy engine + session factory (for direct DB access)
  • Supabase client (for auth, RPC, storage)
  • Service-role Supabase client (bypasses RLS for backend operations)
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from supabase import create_client, Client

from app.core.config import get_settings


# ── SQLAlchemy Base ──────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ── Engine & Session Factory ─────────────────────────
_settings = get_settings()

_db_url = _settings.database_url
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _db_url,
    echo=_settings.debug,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=False,         # Disable per-request 500ms pre-ping roundtrip
    pool_recycle=1800,           # Recycle every 30 mins
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async DB session.
    Usage: `db: AsyncSession = Depends(get_db)`
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Supabase Clients ─────────────────────────────────

def get_supabase_client() -> Client:
    """
    Supabase client using the ANON key.
    Respects RLS — used for client-facing operations.
    """
    return create_client(_settings.supabase_url, _settings.supabase_anon_key)


def get_supabase_admin() -> Client:
    """
    Supabase client using the SERVICE_ROLE key.
    Bypasses RLS — used for backend ingestion, agent operations, and audit logging.
    
    ⚠️ NEVER expose this client to user-facing endpoints.
    """
    return create_client(_settings.supabase_url, _settings.supabase_service_role_key)


# ── Lifecycle ────────────────────────────────────────

async def init_db():
    """Initialize database connection pool on app startup."""
    # Verify connectivity
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text("SELECT 1")
        )


async def close_db():
    """Cleanup database connections on app shutdown."""
    await engine.dispose()
