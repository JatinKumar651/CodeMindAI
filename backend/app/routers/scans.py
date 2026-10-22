"""
CodeMind AI — Scan Routes.

Trigger and manage code analysis scans (security, dead code, complexity, etc.).
High-severity findings are flagged for HITL review.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.core.logging import get_logger
from app.middleware.rate_limiter import limiter
from app.models.orm import Repository, Scan
from app.models.schemas import ScanCreate, ScanResponse

router = APIRouter(tags=["Scans"])
logger = get_logger(__name__)


@router.post("/repos/{repo_id}/scans", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def trigger_scan(
    request: Request,
    repo_id: UUID,
    body: ScanCreate,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a code analysis scan."""
    # Verify ownership
    repo = await _verify_repo_access(db, repo_id, user.id)
    
    if repo.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository is not ready (status: {repo.status}). Ingest the repo first.",
        )
    
    scan = Scan(
        repository_id=repo_id,
        scan_type=body.scan_type,
        status="pending",
    )
    db.add(scan)
    await db.flush()
    
    logger.info("scan_triggered", scan_id=str(scan.id), type=body.scan_type)
    
    # Run scan in background
    background_tasks.add_task(_run_scan, str(scan.id), str(repo_id), body.scan_type)
    
    await db.commit()
    await db.refresh(scan)
    return scan


@router.get("/repos/{repo_id}/scans", response_model=List[ScanResponse])
async def list_scans(
    repo_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all scans for a repository."""
    await _verify_repo_access(db, repo_id, user.id)
    
    result = await db.execute(
        select(Scan)
        .where(Scan.repository_id == repo_id)
        .order_by(Scan.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get scan details and results."""
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Verify repo ownership
    await _verify_repo_access(db, scan.repository_id, user.id)
    
    return scan


# ── Helpers ──────────────────────────────────────────

async def _verify_repo_access(db: AsyncSession, repo_id: UUID, user_id: UUID) -> Repository:
    """Verify user owns the repository."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return repo


async def _run_scan(scan_id: str, repo_id: str, scan_type: str):
    """Run a scan in the background. Placeholder for now."""
    try:
        from app.core.database import async_session_factory
        from sqlalchemy import update
        from datetime import datetime, timezone
        
        async with async_session_factory() as db:
            # Mark as running
            await db.execute(
                update(Scan)
                .where(Scan.id == scan_id)
                .values(
                    status="running",
                    started_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            
            # TODO: Implement actual scan logic per scan_type
            # For now, mark as completed with empty results
            await db.execute(
                update(Scan)
                .where(Scan.id == scan_id)
                .values(
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                    results={"message": f"{scan_type} scan completed (placeholder)"},
                    summary=f"{scan_type} scan completed successfully",
                )
            )
            await db.commit()
            
        logger.info("scan_completed", scan_id=scan_id, type=scan_type)
        
    except Exception as e:
        logger.error("scan_failed", scan_id=scan_id, error=str(e))
        try:
            from app.core.database import async_session_factory
            from sqlalchemy import update
            
            async with async_session_factory() as db:
                await db.execute(
                    update(Scan)
                    .where(Scan.id == scan_id)
                    .values(status="failed", error_message=str(e)[:1000])
                )
                await db.commit()
        except Exception:
            pass
