"""
CodeMind AI — Human-in-the-Loop (HITL) Gateway.

Manages the workflow when the AI's answer needs human review:
  1. Validator Agent detects low confidence or hallucination
  2. Answer is stored in pending_reviews table with status='pending'
  3. User is notified and can approve, reject, or edit the answer
  4. Only approved/edited answers become the final response

Triggers:
  • validation_passed == False (hallucination detected)
  • confidence_score < threshold (configurable, default 0.7)
  • High-severity scan results (require human confirmation)
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.orm import AuditLog, ChatMessage, PendingReview

logger = get_logger(__name__)


class HITLGateway:
    """
    Human-in-the-Loop gateway for managing answer reviews.
    
    Usage in the agent pipeline:
        hitl = HITLGateway(db_session)
        
        if not state["validation_passed"] or state["confidence_score"] < threshold:
            review = await hitl.flag_for_review(
                message_id=msg.id,
                session_id=state["session_id"],
                user_id=state["user_id"],
                answer=state["answer"],
                confidence_score=state["confidence_score"],
                reason=state["validation_reason"],
                flags=["hallucination"],
            )
            # Return a placeholder response to the user
            return {"needs_review": True, "review_id": review.id}
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    def should_flag(
        self,
        validation_passed: bool,
        confidence_score: float,
        guardrail_flags: List[str] = None,
    ) -> bool:
        """
        Determine if an answer should be flagged for human review.
        
        Returns True if:
          - Validation failed (hallucination detected)
          - Confidence score is below threshold
          - Critical guardrail flags are present
        """
        if not validation_passed:
            return True
        
        if confidence_score < self.settings.hitl_confidence_threshold:
            return True
        
        if guardrail_flags:
            critical_flags = {"hallucination", "pii_in_output", "injection_in_output"}
            if critical_flags.intersection(set(guardrail_flags)):
                return True
        
        return False

    async def flag_for_review(
        self,
        message_id: UUID,
        session_id: UUID,
        user_id: UUID,
        answer: str,
        confidence_score: float = 0.0,
        reason: Optional[str] = None,
        flags: List[str] = None,
    ) -> PendingReview:
        """
        Create a pending review record for an answer that needs human verification.
        """
        review = PendingReview(
            message_id=message_id,
            session_id=session_id,
            user_id=user_id,
            original_answer=answer,
            confidence_score=confidence_score,
            validation_reason=reason,
            guardrail_flags=flags or [],
            status="pending",
        )
        
        self.db.add(review)
        
        # Log to audit trail
        audit = AuditLog(
            user_id=user_id,
            action="hitl_flagged",
            resource_type="message",
            resource_id=message_id,
            metadata_={
                "confidence_score": confidence_score,
                "reason": reason,
                "flags": flags or [],
            },
        )
        self.db.add(audit)
        
        await self.db.flush()  # Get the review ID without committing
        
        logger.info(
            "hitl_flagged",
            review_id=str(review.id),
            message_id=str(message_id),
            confidence=confidence_score,
            reason=reason,
        )
        
        return review

    async def approve(self, review_id: UUID, user_id: UUID) -> PendingReview:
        """
        Approve a pending review — the original answer becomes the final answer.
        """
        review = await self._get_review(review_id, user_id)
        
        review.status = "approved"
        review.reviewed_at = datetime.now(timezone.utc)
        review.final_answer = review.original_answer
        
        # Update the original chat message to mark it as reviewed
        await self.db.execute(
            update(ChatMessage)
            .where(ChatMessage.id == review.message_id)
            .values(agent_trace={
                **(await self._get_message_trace(review.message_id)),
                "hitl_status": "approved",
                "reviewed_at": review.reviewed_at.isoformat(),
            })
        )
        
        # Audit log
        self.db.add(AuditLog(
            user_id=user_id,
            action="hitl_approved",
            resource_type="review",
            resource_id=review_id,
        ))
        
        logger.info("hitl_approved", review_id=str(review_id))
        return review

    async def reject(self, review_id: UUID, user_id: UUID) -> PendingReview:
        """
        Reject a pending review — the answer is discarded.
        """
        review = await self._get_review(review_id, user_id)
        
        review.status = "rejected"
        review.reviewed_at = datetime.now(timezone.utc)
        
        # Update chat message
        await self.db.execute(
            update(ChatMessage)
            .where(ChatMessage.id == review.message_id)
            .values(
                content="[This answer was rejected during review. Please rephrase your question.]",
                agent_trace={
                    **(await self._get_message_trace(review.message_id)),
                    "hitl_status": "rejected",
                    "reviewed_at": review.reviewed_at.isoformat(),
                },
            )
        )
        
        # Audit log
        self.db.add(AuditLog(
            user_id=user_id,
            action="hitl_rejected",
            resource_type="review",
            resource_id=review_id,
        ))
        
        logger.info("hitl_rejected", review_id=str(review_id))
        return review

    async def edit(self, review_id: UUID, user_id: UUID, edited_answer: str) -> PendingReview:
        """
        Edit and approve a pending review — the user provides a corrected answer.
        """
        review = await self._get_review(review_id, user_id)
        
        review.status = "edited"
        review.reviewed_at = datetime.now(timezone.utc)
        review.final_answer = edited_answer
        
        # Update chat message with the edited answer
        await self.db.execute(
            update(ChatMessage)
            .where(ChatMessage.id == review.message_id)
            .values(
                content=edited_answer,
                agent_trace={
                    **(await self._get_message_trace(review.message_id)),
                    "hitl_status": "edited",
                    "reviewed_at": review.reviewed_at,
                },
            )
        )
        
        # Audit log
        self.db.add(AuditLog(
            user_id=user_id,
            action="hitl_edited",
            resource_type="review",
            resource_id=review_id,
        ))
        
        logger.info("hitl_edited", review_id=str(review_id))
        return review

    async def get_pending_reviews(
        self, user_id: UUID, session_id: Optional[UUID] = None
    ) -> List[PendingReview]:
        """Get all pending reviews for a user, optionally filtered by session."""
        query = (
            select(PendingReview)
            .where(
                PendingReview.user_id == user_id,
                PendingReview.status == "pending",
            )
            .order_by(PendingReview.created_at.desc())
        )
        
        if session_id:
            query = query.where(PendingReview.session_id == session_id)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ── Private helpers ──────────────────────────────

    async def _get_review(self, review_id: UUID, user_id: UUID) -> PendingReview:
        """Fetch a review and verify ownership."""
        result = await self.db.execute(
            select(PendingReview).where(PendingReview.id == review_id)
        )
        review = result.scalar_one_or_none()
        
        if not review:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found",
            )
        
        if review.user_id != user_id:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this review",
            )
        
        if review.status != "pending":
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Review already {review.status}",
            )
        
        return review

    async def _get_message_trace(self, message_id: UUID) -> dict:
        """Get the current agent_trace from a chat message."""
        result = await self.db.execute(
            select(ChatMessage.agent_trace).where(ChatMessage.id == message_id)
        )
        trace = result.scalar_one_or_none()
        return trace if isinstance(trace, dict) else {}
