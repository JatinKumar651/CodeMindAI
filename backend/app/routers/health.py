"""
CodeMind AI — Health Check Routes.

Provides health/readiness endpoints for monitoring.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])
logger = get_logger(__name__)


@router.get("", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(get_settings)):
    """Basic health check — confirms the API is running."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
    )


@router.get("/db", response_model=HealthResponse)
async def db_health(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    """Database connectivity check."""
    db_status = "unknown"
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_status = "connected"
        else:
            db_status = "error"
    except Exception as e:
        db_status = f"error: {str(e)[:100]}"
        logger.error("db_health_check_failed", error=str(e))
    
    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        version=settings.app_version,
        database=db_status,
    )


@router.get("/groq", response_model=HealthResponse)
async def groq_health(settings: Settings = Depends(get_settings)):
    """Groq API reachability check."""
    groq_status = "unknown"
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                timeout=5.0,
            )
            if response.status_code == 200:
                groq_status = "connected"
            else:
                groq_status = f"error: HTTP {response.status_code}"
    except Exception as e:
        groq_status = f"error: {str(e)[:100]}"
        logger.error("groq_health_check_failed", error=str(e))
    
    return HealthResponse(
        status="ok" if groq_status == "connected" else "degraded",
        version=settings.app_version,
        groq=groq_status,
    )
