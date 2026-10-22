"""
CodeMind AI — Chat Routes.

Handles chat sessions, messages, and the agentic RAG pipeline.
Integrates all security guardrails:
  Rate Limiter → Auth → PII Filter → Prompt Guard → Agent → HITL → PII Filter (output)
"""

import time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.core.logging import get_logger
from app.guardrails.human_in_the_loop import HITLGateway
from app.middleware.pii_filter import get_pii_filter
from app.middleware.prompt_guard import get_prompt_guard, ThreatLevel
from app.middleware.rate_limiter import limiter
from app.models.orm import ChatMessage, ChatSession, PendingReview, Repository, AuditLog, RetrievedChunk
from app.models.schemas import (
    ChatHistoryResponse,
    MessageCreate,
    MessageResponse,
    PendingReviewResponse,
    ReviewAction,
    SessionCreate,
    SessionResponse,
)

router = APIRouter(tags=["Chat"])
logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════
# SESSIONS
# ═══════════════════════════════════════════════════════

@router.post("/repos/{repo_id}/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    repo_id: UUID,
    body: SessionCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session for a repository."""
    # Verify repo ownership
    await _verify_repo_access(db, repo_id, user.id)
    
    session = ChatSession(
        user_id=user.id,
        repository_id=repo_id,
        title=body.title or "New Chat",
    )
    db.add(session)
    await db.flush()
    
    logger.info("session_created", session_id=str(session.id), repo_id=str(repo_id))
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/repos/{repo_id}/sessions", response_model=List[SessionResponse])
async def list_sessions(
    repo_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all chat sessions for a repository."""
    await _verify_repo_access(db, repo_id, user.id)
    
    result = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.repository_id == repo_id,
            ChatSession.user_id == user.id,
        )
        .order_by(ChatSession.updated_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a chat session and all its messages."""
    session = await _get_user_session(db, session_id, user.id)
    await db.delete(session)
    logger.info("session_deleted", session_id=str(session_id))


# ═══════════════════════════════════════════════════════
# MESSAGES (The main chat endpoint)
# ═══════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
@limiter.limit("60/minute")
async def send_message(
    request: Request,
    session_id: UUID,
    body: MessageCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and get an AI response.
    
    Security pipeline:
    1. Rate limiting (decorator)
    2. Auth (dependency)
    3. PII detection on input
    4. Prompt injection detection
    5. Agent pipeline (LangGraph)
    6. Hallucination validation + HITL
    7. PII detection on output
    """
    start_time = time.perf_counter()
    
    # ── Step 1: Verify session ownership ──────────
    session = await _get_user_session(db, session_id, user.id)
    
    # ── Step 2: PII Filter (input) ────────────────
    pii_filter = get_pii_filter()
    pii_result = pii_filter.scan(body.content)
    
    if pii_result.pii_detected:
        # Log PII detection
        db.add(AuditLog(
            user_id=user.id,
            action="pii_detected",
            resource_type="message",
            metadata_={
                "types": [d.entity_type for d in pii_result.detections],
                "count": pii_result.detection_count,
                "mode": "redact",
            },
        ))
    
    # Use redacted text for the LLM
    clean_input = pii_result.filtered_text
    
    # ── Step 3: Prompt Injection Guard ────────────
    prompt_guard = get_prompt_guard()
    guard_result = prompt_guard.analyze(clean_input)
    
    if guard_result.should_block:
        # Log blocked attempt
        db.add(AuditLog(
            user_id=user.id,
            action="injection_blocked",
            resource_type="message",
            metadata_={
                "patterns": guard_result.matched_patterns,
                "threat_level": guard_result.threat_level.value,
            },
        ))
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your message was blocked by our security system. Please rephrase your question about the code.",
        )
    
    # Use sanitized input
    sanitized_input = guard_result.sanitized_input
    
    # ── Step 4: Store user message ────────────────
    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=body.content,  # Store original (for user's view)
    )
    db.add(user_message)
    await db.flush()
    
    # ── Step 4b: Load memory context for agent ───
    # Fetch the last assistant answer for follow-up resolution (cheap: indexed query)
    last_answer_result = await db.execute(
        select(ChatMessage.content)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "assistant",
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    last_assistant_row = last_answer_result.scalar_one_or_none()
    last_assistant_answer = last_assistant_row[:500] if last_assistant_row else None

    # Load existing profile scratchpad from session
    existing_profile = session.user_profile or {}

    # ── Step 5: Run Agent Pipeline ────────────────
    try:
        agent_response = await _run_agent_pipeline(
            db=db,
            session=session,
            user=user,
            question=sanitized_input,
            user_profile=existing_profile,
            last_assistant_answer=last_assistant_answer,
        )
    except Exception as e:
        logger.error("agent_pipeline_error", error=str(e), session_id=str(session_id))
        agent_response = {
            "answer": "I encountered an error processing your request. Please try again.",
            "citations": [],
            "tokens_used": 0,
            "model_used": "error",
            "validation_passed": True,
            "confidence_score": 0.0,
            "agent_trace": {"error": str(e)},
        }
    
    # ── Step 6: PII Filter (output) ───────────────
    output_pii = pii_filter.scan_output(agent_response["answer"])
    final_answer = output_pii.filtered_text
    
    if output_pii.pii_detected:
        db.add(AuditLog(
            user_id=user.id,
            action="pii_redacted",
            resource_type="message",
            metadata_={
                "direction": "output",
                "types": [d.entity_type for d in output_pii.detections],
            },
        ))
    
    # ── Step 7: Store assistant message ───────────
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    
    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=final_answer,
        agent_trace=agent_response.get("agent_trace", {}),
        tokens_used=agent_response.get("tokens_used", 0),
        latency_ms=latency_ms,
        model_used=agent_response.get("model_used"),
    )
    db.add(assistant_message)
    await db.flush()
    
    # ── Step 7b: Persist retrieved chunks for observability ──
    retrieved_docs = agent_response.get("retrieved_docs", [])
    grader_scores = agent_response.get("grader_scores", [])
    
    if retrieved_docs:
        # Build a lookup for grader verdicts by chunk_id
        verdict_map = {}
        for score in grader_scores:
            cid = score.get("chunk_id")
            if cid:
                verdict_map[cid] = score.get("verdict", "unknown")
        
        # Determine which chunk_ids were used in the final answer (relevant_docs)
        relevant_chunk_ids = set()
        for rdoc in agent_response.get("relevant_docs", []):
            cid = rdoc.get("chunk_id")
            if cid:
                relevant_chunk_ids.add(cid)
        
        for rank, doc in enumerate(retrieved_docs, start=1):
            chunk_id = doc.get("chunk_id")
            if not chunk_id:
                continue
            
            try:
                from uuid import UUID as _UUID
                chunk_uuid = _UUID(chunk_id) if isinstance(chunk_id, str) else chunk_id
                
                rc = RetrievedChunk(
                    message_id=assistant_message.id,
                    chunk_id=chunk_uuid,
                    rank=rank,
                    similarity_score=doc.get("combined_score") or doc.get("similarity"),
                    was_used_in_answer=chunk_id in relevant_chunk_ids or str(chunk_id) in relevant_chunk_ids,
                    grader_verdict=verdict_map.get(chunk_id, verdict_map.get(str(chunk_id), "unknown")),
                )
                db.add(rc)
            except (ValueError, TypeError) as e:
                logger.warning("retrieved_chunk_save_error", chunk_id=str(chunk_id), error=str(e))
        
        await db.flush()
        logger.info(
            "retrieved_chunks_saved",
            message_id=str(assistant_message.id),
            count=len(retrieved_docs),
        )
    
    # ── Step 8: HITL Check ────────────────────────
    needs_review = False
    hitl = HITLGateway(db)
    
    if hitl.should_flag(
        validation_passed=agent_response.get("validation_passed", True),
        confidence_score=agent_response.get("confidence_score", 1.0),
        guardrail_flags=agent_response.get("guardrail_flags", []),
    ):
        await hitl.flag_for_review(
            message_id=assistant_message.id,
            session_id=session_id,
            user_id=user.id,
            answer=final_answer,
            confidence_score=agent_response.get("confidence_score", 0.0),
            reason=agent_response.get("validation_reason"),
            flags=agent_response.get("guardrail_flags", []),
        )
        needs_review = True
    
    # Update session message count and auto-title on first message
    new_title = session.title
    if (not session.title or session.title in ("New Chat", "Main")) and body.content:
        clean_title = body.content.strip().split("\n")[0][:45]
        if clean_title:
            new_title = clean_title

    # ── Step 8b: Persist updated profile scratchpad ──
    updated_profile = agent_response.get("user_profile") or {}
    profile_changed = updated_profile != existing_profile

    await db.execute(
        update(ChatSession)
        .where(ChatSession.id == session_id)
        .values(
            message_count=ChatSession.message_count + 2,
            title=new_title,
            updated_at=func.now(),
            **({
                "user_profile": updated_profile,
            } if profile_changed else {}),
        )
    )
    
    await db.commit()
    await db.refresh(assistant_message)
    
    return MessageResponse(
        id=assistant_message.id,
        session_id=session_id,
        role="assistant",
        content=final_answer,
        citations=agent_response.get("citations", []),
        agent_trace=assistant_message.agent_trace,
        tokens_used=agent_response.get("tokens_used", 0),
        latency_ms=latency_ms,
        model_used=agent_response.get("model_used"),
        needs_review=needs_review,
        created_at=assistant_message.created_at,
    )


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """Get message history for a session."""
    await _get_user_session(db, session_id, user.id)
    
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(min(limit, 200))
    )
    return list(result.scalars().all())


# ═══════════════════════════════════════════════════════
# HUMAN-IN-THE-LOOP REVIEWS
# ═══════════════════════════════════════════════════════

@router.get("/reviews", response_model=List[PendingReviewResponse])
async def list_pending_reviews(
    session_id: Optional[UUID] = None,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all pending reviews for the authenticated user."""
    hitl = HITLGateway(db)
    reviews = await hitl.get_pending_reviews(user.id, session_id)
    return reviews


@router.post("/reviews/{review_id}", response_model=PendingReviewResponse)
async def act_on_review(
    review_id: UUID,
    body: ReviewAction,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve, reject, or edit a pending review."""
    hitl = HITLGateway(db)
    
    if body.action == "approve":
        review = await hitl.approve(review_id, user.id)
    elif body.action == "reject":
        review = await hitl.reject(review_id, user.id)
    elif body.action == "edit":
        review = await hitl.edit(review_id, user.id, body.edited_answer)
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    await db.commit()
    return review


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

async def _verify_repo_access(db: AsyncSession, repo_id: UUID, user_id: UUID):
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


async def _get_user_session(db: AsyncSession, session_id: UUID, user_id: UUID) -> ChatSession:
    """Fetch a session and verify ownership."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return session


async def _run_agent_pipeline(
    db: AsyncSession,
    session: ChatSession,
    user: AuthenticatedUser,
    question: str,
    user_profile: dict | None = None,
    last_assistant_answer: str | None = None,
) -> dict:
    """
    Execute the LangGraph agentic RAG pipeline.
    
    Returns a dict with:
      - answer: str
      - citations: List[dict]
      - tokens_used: int
      - model_used: str
      - validation_passed: bool
      - confidence_score: float
      - validation_reason: str | None
      - guardrail_flags: List[str]
      - agent_trace: dict
    """
    try:
        from app.agents.graph import get_agent_graph
        from app.core.config import get_settings
        
        settings = get_settings()
        graph = get_agent_graph()
        
        # Build initial state
        initial_state = {
            "messages": [],
            "repository_id": str(session.repository_id),
            "session_id": str(session.id),
            "user_id": str(user.id),
            "question": question,
            "rewritten_question": None,
            "retrieved_docs": [],
            "relevant_docs": [],
            "grader_scores": [],
            "rewrite_count": 0,
            "max_rewrites": settings.max_rewrites,
            "route": "",
            "web_search_docs": [],
            "used_web_search": False,
            "is_error_query": False,
            "error_metadata": None,
            "answer": None,
            "citations": [],
            "validation_passed": True,
            "validation_reason": None,
            "confidence_score": 1.0,
            "needs_human_review": False,
            "guardrail_flags": [],
            "agent_trace": {},
            "tokens_used": 0,
            "latency_ms": 0,
            "model_used": "",
            "max_tokens_budget": settings.max_tokens_budget,
            "pii_detected": False,
            "user_profile": user_profile or {},
            "last_assistant_answer": last_assistant_answer,
        }
        
        # Run the graph
        config = {
            "configurable": {
                "thread_id": str(session.id),
            }
        }
        
        result = await graph.ainvoke(initial_state, config=config)
        
        return {
            "answer": result.get("answer", "I could not generate a response."),
            "citations": result.get("citations", []),
            "tokens_used": result.get("tokens_used", 0),
            "model_used": result.get("model_used", ""),
            "validation_passed": result.get("validation_passed", True),
            "confidence_score": result.get("confidence_score", 1.0),
            "validation_reason": result.get("validation_reason"),
            "guardrail_flags": result.get("guardrail_flags", []),
            "agent_trace": result.get("agent_trace", {}),
            "retrieved_docs": result.get("retrieved_docs", []),
            "grader_scores": result.get("grader_scores", []),
            "relevant_docs": result.get("relevant_docs", []),
            "user_profile": result.get("user_profile", {}),
        }
    except ImportError:
        logger.warning("agent_graph_not_available", message="Using placeholder response")
        return {
            "answer": f"[Agent pipeline not yet initialized] Your question: {question}",
            "citations": [],
            "tokens_used": 0,
            "model_used": "placeholder",
            "validation_passed": True,
            "confidence_score": 1.0,
            "validation_reason": None,
            "guardrail_flags": [],
            "agent_trace": {"status": "placeholder"},
        }
