"""
CodeMind AI — FastAPI Application Entry Point.

Central orchestrator for the backend:
  • Lifespan events (DB pool warmup, logging init, shutdown cleanup)
  • Security middleware pipeline (CORS, Rate Limiter, Request Tracking)
  • Router aggregation (Auth, Repos, Chat/Agentic RAG, Scans, Health)
  • Global error handlers with structured logging
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import RequestLoggingMiddleware, get_logger, setup_logging
from app.middleware.rate_limiter import setup_rate_limiter
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.health import router as health_router
from app.routers.repos import router as repos_router
from app.routers.scans import router as scans_router

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.
    Handles startup configuration and graceful shutdown.
    """
    settings = get_settings()

    # 1. Initialize structured logging
    setup_logging(debug=settings.debug)
    logger.info(
        "app_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    # 2. Pre-warm database pool with persistent connections & background keep-alive
    import asyncio
    keep_alive_task = None
    try:
        async def _warm():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        
        # Pre-warm 3 parallel database connections to eliminate 4s cold-connect lag
        await asyncio.gather(_warm(), _warm(), _warm())
        logger.info("database_pool_warmed", connections=3)

        async def _keep_alive():
            while True:
                await asyncio.sleep(45)
                try:
                    async with engine.connect() as conn:
                        await conn.execute(text("SELECT 1"))
                except Exception:
                    pass

        keep_alive_task = asyncio.create_task(_keep_alive())
    except Exception as e:
        logger.warning(
            "database_connection_warning",
            error=str(e),
            message="Database connection test failed. Verify DATABASE_URL in .env if running queries.",
        )

    yield

    # 3. Graceful shutdown
    if keep_alive_task:
        keep_alive_task.cancel()
    logger.info("app_shutting_down")
    await engine.dispose()
    logger.info("database_pool_disposed")


# ── Create FastAPI Application ──────────────────────────

settings = get_settings()

is_dev = settings.debug or settings.environment == "development"

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="CodeMind AI — Agentic RAG Code Intelligence Platform",
    docs_url="/docs" if is_dev else None,
    redoc_url="/redoc" if is_dev else None,
    openapi_url="/openapi.json" if is_dev else None,
    lifespan=lifespan,
)


# ── Register Middleware (Order Matters) ──────────────────

# 1. Rate Limiter (SlowAPI)
setup_rate_limiter(app)

# 2. Request Correlation & Structured Logging
app.add_middleware(RequestLoggingMiddleware)

# 3. Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# ── Global Exception Handlers ───────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Clean JSON response for validation errors."""
    logger.warning(
        "request_validation_error",
        path=request.url.path,
        errors=exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions, preventing raw trace leaks."""
    logger.error(
        "unhandled_server_error",
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. Please check server logs.",
        },
    )


# ── Root Welcome Endpoint ────────────────────────────────

@app.get("/", tags=["General"])
async def root():
    """Welcome / discovery endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }


# ── Register Routers ────────────────────────────────────

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(repos_router)
app.include_router(chat_router)
app.include_router(scans_router)
