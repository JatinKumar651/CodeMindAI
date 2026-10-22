"""
CodeMind AI — Pydantic Request/Response Schemas.

All API request bodies and response models are defined here.
Uses Pydantic v2 with strict validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ═══════════════════════════════════════════════════════
# REPOSITORIES
# ═══════════════════════════════════════════════════════

class RepoCreate(BaseModel):
    """Request body for creating a new repository."""
    name: str = Field(..., min_length=1, max_length=200, examples=["my-project"])
    github_url: Optional[str] = Field(None, examples=["https://github.com/user/repo"])
    default_branch: str = Field("main", examples=["main", "master"])
    language: Optional[str] = Field(None, examples=["python", "javascript"])

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v.startswith("https://github.com/"):
                raise ValueError("Only public GitHub URLs (https://github.com/...) are accepted")
            # Block common SSRF patterns
            if any(bad in v.lower() for bad in ["localhost", "127.0.0.1", "0.0.0.0", "169.254", "10.", "172.16", "192.168"]):
                raise ValueError("Internal/private URLs are not allowed")
        return v


class RepoResponse(BaseModel):
    """Response for a repository."""
    id: UUID
    user_id: UUID
    name: str
    github_url: Optional[str] = None
    default_branch: str
    language: Optional[str] = None
    total_files: int
    total_chunks: int
    status: str
    error_message: Optional[str] = None
    ingested_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RepoListResponse(BaseModel):
    """Paginated list of repositories."""
    repositories: List[RepoResponse]
    total: int


# ═══════════════════════════════════════════════════════
# CHAT
# ═══════════════════════════════════════════════════════

class SessionCreate(BaseModel):
    """Request body for creating a chat session."""
    title: Optional[str] = Field("New Chat", max_length=200)


class SessionResponse(BaseModel):
    """Response for a chat session."""
    id: UUID
    repository_id: UUID
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    """Request body for sending a chat message."""
    content: str = Field(..., min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        # Strip null bytes and control characters (except newlines/tabs)
        cleaned = "".join(
            c for c in v
            if c in ("\n", "\t", "\r") or (ord(c) >= 32)
        )
        return cleaned.strip()


class CitationSchema(BaseModel):
    """A citation linking an answer to a code chunk or external documentation."""
    file_path: Optional[str] = "source"
    chunk_name: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    similarity_score: Optional[float] = None
    type: Optional[str] = "repo"
    url: Optional[str] = None
    title: Optional[str] = None


class MessageResponse(BaseModel):
    """Response for a chat message."""
    id: UUID
    session_id: UUID
    role: str
    content: str
    citations: List[CitationSchema] = []
    agent_trace: Optional[Dict[str, Any]] = None
    tokens_used: int = 0
    latency_ms: Optional[int] = None
    model_used: Optional[str] = None
    needs_review: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """Full chat history for a session."""
    session: SessionResponse
    messages: List[MessageResponse]


# ═══════════════════════════════════════════════════════
# SCANS
# ═══════════════════════════════════════════════════════

class ScanCreate(BaseModel):
    """Request body for triggering a scan."""
    scan_type: str = Field(
        ...,
        pattern="^(security|dead_code|complexity|tests|deps|documentation)$",
        examples=["security"],
    )


class ScanResponse(BaseModel):
    """Response for a scan."""
    id: UUID
    repository_id: UUID
    scan_type: str
    status: str
    results: Dict[str, Any] = {}
    summary: Optional[str] = None
    severity_counts: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════
# CODE CHUNKS & FILES
# ═══════════════════════════════════════════════════════

class FileResponse(BaseModel):
    """Response for a file."""
    id: UUID
    repository_id: UUID
    path: str
    extension: Optional[str] = None
    language: Optional[str] = None
    size_bytes: Optional[int] = None
    loc: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkResponse(BaseModel):
    """Response for a code chunk."""
    id: UUID
    file_id: UUID
    chunk_type: str
    chunk_name: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    content: str
    context_header: Optional[str] = None
    language: Optional[str] = None
    token_count: Optional[int] = None

    class Config:
        from_attributes = True


class RetrievalResult(BaseModel):
    """A single retrieval result from hybrid search."""
    chunk_id: UUID
    file_path: str
    chunk_type: str
    chunk_name: Optional[str] = None
    content: str
    context_header: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    combined_score: Optional[float] = None
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None


# ═══════════════════════════════════════════════════════
# HUMAN-IN-THE-LOOP
# ═══════════════════════════════════════════════════════

class ReviewAction(BaseModel):
    """User action on a pending review."""
    action: str = Field(..., pattern="^(approve|reject|edit)$")
    edited_answer: Optional[str] = Field(None, max_length=10000)

    @field_validator("edited_answer")
    @classmethod
    def require_answer_for_edit(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get("action") == "edit" and not v:
            raise ValueError("edited_answer is required when action is 'edit'")
        return v


class PendingReviewResponse(BaseModel):
    """Response for a pending review item."""
    id: UUID
    message_id: UUID
    session_id: UUID
    original_answer: str
    confidence_score: Optional[float] = None
    validation_reason: Optional[str] = None
    guardrail_flags: List[str] = []
    status: str
    final_answer: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════
# HEALTH & MISC
# ═══════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str
    database: str = "unknown"
    groq: str = "unknown"


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None
