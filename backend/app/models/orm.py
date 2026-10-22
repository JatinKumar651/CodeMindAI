"""
CodeMind AI — SQLAlchemy ORM Models.

All models map to the Supabase PostgreSQL tables defined in supabase_tables_queries.sql.

Fixes from original orm.py.py:
  • datetime.utcnow → datetime.now(timezone.utc)  (deprecated in Python 3.12+)
  • Added missing Dependency model
  • Added missing relationships for Evaluation and BenchmarkQA
  • Added new AuditLog and PendingReview models
  • Proper column naming for 'metadata' (reserved word)
  • File renamed from orm.py.py → orm.py
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base


def _utcnow() -> datetime:
    """Timezone-aware UTC now. Replaces deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────
# 1. REPOSITORIES
# ─────────────────────────────────────────────────────

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)  # FK to auth.users (managed by Supabase, not SQLAlchemy)
    name = Column(String, nullable=False)
    github_url = Column(String)
    default_branch = Column(String, default="main")
    language = Column(String)
    total_files = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    status = Column(String, default="pending")
    error_message = Column(Text)
    ingested_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    files = relationship("File", back_populates="repository", cascade="all, delete-orphan")
    chunks = relationship("CodeChunk", back_populates="repository", cascade="all, delete-orphan")
    sessions = relationship("ChatSession", back_populates="repository", cascade="all, delete-orphan")
    scans = relationship("Scan", back_populates="repository", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="repository", cascade="all, delete-orphan")
    benchmarks = relationship("BenchmarkQA", back_populates="repository", cascade="all, delete-orphan")
    dependencies = relationship("Dependency", back_populates="repository", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="repository", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────
# 2. FILES
# ─────────────────────────────────────────────────────

class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    path = Column(Text, nullable=False)
    extension = Column(String)
    language = Column(String)
    size_bytes = Column(Integer)
    loc = Column(Integer)
    sha256 = Column(String)
    last_modified = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("repository_id", "path", name="uq_file_repo_path"),
    )

    repository = relationship("Repository", back_populates="files")
    chunks = relationship("CodeChunk", back_populates="file", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────
# 3. CODE CHUNKS
# ─────────────────────────────────────────────────────

class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_type = Column(String, nullable=False)
    chunk_name = Column(String)
    parent_chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("code_chunks.id", ondelete="CASCADE"),
    )
    start_line = Column(Integer)
    end_line = Column(Integer)
    content = Column(Text, nullable=False)
    context_header = Column(Text)
    language = Column(String)
    imports = Column(JSONB, default=list)
    calls = Column(JSONB, default=list)
    called_by = Column(JSONB, default=list)
    metadata_ = Column("metadata", JSONB, default=dict)  # 'metadata' is a reserved name
    token_count = Column(Integer)
    # content_tsv is a GENERATED column in PostgreSQL — not mapped in ORM
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    file = relationship("File", back_populates="chunks")
    repository = relationship("Repository", back_populates="chunks")
    embeddings = relationship("Embedding", back_populates="chunk", cascade="all, delete-orphan")
    parent = relationship("CodeChunk", remote_side=[id], backref="children")


# ─────────────────────────────────────────────────────
# 4. EMBEDDINGS
# ─────────────────────────────────────────────────────

class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("code_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_name = Column(String, nullable=False)
    model_version = Column(String, default="v1")
    embedding = Column(Vector(768), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("chunk_id", "model_name", name="uq_embedding_chunk_model"),
    )

    chunk = relationship("CodeChunk", back_populates="embeddings")
    repository = relationship("Repository", back_populates="embeddings")


# ─────────────────────────────────────────────────────
# 5. DEPENDENCIES
# ─────────────────────────────────────────────────────

class Dependency(Base):
    __tablename__ = "dependencies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type = Column(String, default="import")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint(
            "repository_id", "source_file_id", "target_file_id", "dependency_type",
            name="uq_dep_repo_src_tgt_type",
        ),
    )

    repository = relationship("Repository", back_populates="dependencies")
    source_file = relationship("File", foreign_keys=[source_file_id])
    target_file = relationship("File", foreign_keys=[target_file_id])


# ─────────────────────────────────────────────────────
# 6. CHAT SESSIONS
# ─────────────────────────────────────────────────────

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String, default="New Chat")
    message_count = Column(Integer, default=0)
    user_profile = Column(JSONB, default=dict)   # Profile Scratchpad: {"name": "...", "tech_stack": "...", ...}
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    repository = relationship("Repository", back_populates="sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


# ─────────────────────────────────────────────────────
# 7. CHAT MESSAGES
# ─────────────────────────────────────────────────────

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    agent_trace = Column(JSONB, default=dict)
    tokens_used = Column(Integer, default=0)
    latency_ms = Column(Integer)
    model_used = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    session = relationship("ChatSession", back_populates="messages")
    retrieved = relationship(
        "RetrievedChunk",
        back_populates="message",
        cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────────────────
# 8. RETRIEVED CHUNKS
# ─────────────────────────────────────────────────────

class RetrievedChunk(Base):
    __tablename__ = "retrieved_chunks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("code_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank = Column(Integer)
    similarity_score = Column(Float)
    was_used_in_answer = Column(Boolean, default=False)
    grader_verdict = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    message = relationship("ChatMessage", back_populates="retrieved")
    chunk = relationship("CodeChunk")


# ─────────────────────────────────────────────────────
# 9. SCANS
# ─────────────────────────────────────────────────────

class Scan(Base):
    __tablename__ = "scans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    scan_type = Column(String, nullable=False)
    status = Column(String, default="pending")
    results = Column(JSONB, default=dict)
    summary = Column(Text)
    severity_counts = Column(JSONB, default=lambda: {"high": 0, "medium": 0, "low": 0})
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    repository = relationship("Repository", back_populates="scans")


# ─────────────────────────────────────────────────────
# 10. EVALUATIONS
# ─────────────────────────────────────────────────────

class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    eval_name = Column(String, nullable=False)
    embedding_model = Column(String)
    generation_model = Column(String)
    hit_rate_at_5 = Column(Float)
    hit_rate_at_10 = Column(Float)
    mrr = Column(Float)
    context_precision = Column(Float)
    context_recall = Column(Float)
    faithfulness = Column(Float)
    answer_relevancy = Column(Float)
    avg_latency_ms = Column(Integer)
    avg_token_cost = Column(Float)
    total_questions = Column(Integer)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    repository = relationship("Repository", back_populates="evaluations")


# ─────────────────────────────────────────────────────
# 11. BENCHMARK QA
# ─────────────────────────────────────────────────────

class BenchmarkQA(Base):
    __tablename__ = "benchmark_qa"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    question = Column(Text, nullable=False)
    ground_truth_answer = Column(Text, nullable=False)
    relevant_file_paths = Column(ARRAY(Text), default=list)
    relevant_chunk_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)
    difficulty = Column(String)
    category = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    repository = relationship("Repository", back_populates="benchmarks")


# ─────────────────────────────────────────────────────
# 12. AUDIT LOGS (NEW — security & guardrails tracking)
# ─────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String)
    resource_id = Column(UUID(as_uuid=True))
    metadata_ = Column("metadata", JSONB, default=dict)
    ip_address = Column(INET)
    user_agent = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ─────────────────────────────────────────────────────
# 13. PENDING REVIEWS (NEW — Human-in-the-Loop)
# ─────────────────────────────────────────────────────

class PendingReview(Base):
    __tablename__ = "pending_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), nullable=False)
    original_answer = Column(Text, nullable=False)
    confidence_score = Column(Float)
    validation_reason = Column(Text)
    guardrail_flags = Column(JSONB, default=list)
    status = Column(String, default="pending")
    reviewed_at = Column(DateTime(timezone=True))
    final_answer = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
