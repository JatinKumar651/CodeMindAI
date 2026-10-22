"""
CodeMind AI — Repository Routes.

CRUD operations for repositories + ingestion trigger.
All routes require authentication and enforce ownership.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.core.logging import get_logger
from app.middleware.rate_limiter import limiter
from app.models.orm import Repository
from app.models.schemas import RepoCreate, RepoListResponse, RepoResponse

router = APIRouter(prefix="/repos", tags=["Repositories"])
logger = get_logger(__name__)


@router.post("", response_model=RepoResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_repository(
    request: Request,
    body: RepoCreate,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new repository and optionally trigger ingestion.
    If github_url is provided, ingestion starts automatically in the background.
    """
    repo = Repository(
        user_id=user.id,
        name=body.name,
        github_url=body.github_url,
        default_branch=body.default_branch,
        language=body.language,
        status="pending" if body.github_url else "ready",
    )
    db.add(repo)
    await db.flush()
    
    logger.info("repo_created", repo_id=str(repo.id), name=body.name)
    
    # Trigger async ingestion if GitHub URL provided
    if body.github_url:
        background_tasks.add_task(
            _run_ingestion, str(repo.id), str(user.id), body.github_url, body.default_branch
        )
    
    await db.commit()
    await db.refresh(repo)
    return repo


@router.get("", response_model=RepoListResponse)
async def list_repositories(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 20,
):
    """List all repositories for the authenticated user."""
    # Count total
    count_query = select(func.count(Repository.id)).where(Repository.user_id == user.id)
    total = (await db.execute(count_query)).scalar() or 0
    
    # Fetch page
    query = (
        select(Repository)
        .where(Repository.user_id == user.id)
        .order_by(Repository.created_at.desc())
        .offset(skip)
        .limit(min(limit, 100))
    )
    result = await db.execute(query)
    repos = list(result.scalars().all())
    
    return RepoListResponse(repositories=repos, total=total)


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repository(
    repo_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single repository by ID."""
    repo = await _get_user_repo(db, repo_id, user.id)
    return repo


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a repository and all its data (cascades)."""
    repo = await _get_user_repo(db, repo_id, user.id)
    await db.delete(repo)
    logger.info("repo_deleted", repo_id=str(repo_id))


@router.post("/{repo_id}/ingest", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def trigger_ingestion(
    request: Request,
    repo_id: UUID,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-trigger ingestion for an existing repository."""
    repo = await _get_user_repo(db, repo_id, user.id)
    
    if not repo.github_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository has no GitHub URL. Upload a ZIP instead.",
        )
    
    if repo.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ingestion is already in progress",
        )
    
    repo.status = "processing"
    repo.error_message = None
    await db.commit()
    
    background_tasks.add_task(
        _run_ingestion, str(repo.id), str(user.id), repo.github_url, repo.default_branch
    )
    
    return {"message": "Ingestion started", "repo_id": str(repo_id)}


# ── Helpers ──────────────────────────────────────────

async def _get_user_repo(db: AsyncSession, repo_id: UUID, user_id: UUID) -> Repository:
    """Fetch a repo and verify ownership (defense in depth alongside RLS)."""
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    
    if repo.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return repo


async def _run_ingestion(repo_id: str, user_id: str, github_url: str, branch: str):
    """
    Run the ingestion pipeline in the background.
    This is a wrapper that imports and calls the ingestion pipeline service.
    """
    repo_uuid = UUID(repo_id) if isinstance(repo_id, str) else repo_id
    try:
        from app.services.ingestion.pipeline import IngestionPipeline
        from app.core.database import async_session_factory
        
        async with async_session_factory() as db:
            pipeline = IngestionPipeline(db)
            await pipeline.run(
                repo_id=str(repo_uuid),
                user_id=user_id,
                github_url=github_url,
                branch=branch,
            )
            await db.commit()
    except Exception as e:
        err_text = str(e) or repr(e)
        logger.exception("ingestion_failed", repo_id=str(repo_uuid), error=err_text)
        # Update repo status to failed
        try:
            from sqlalchemy import update
            async with async_session_factory() as db:
                await db.execute(
                    update(Repository)
                    .where(Repository.id == repo_uuid)
                    .values(status="failed", error_message=err_text[:1000])
                )
                await db.commit()
        except Exception:
            pass
