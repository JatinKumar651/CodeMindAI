"""
CodeMind AI — Application Configuration.

Uses Pydantic Settings to load all configuration from environment variables.
All secrets and tunables are centralized here.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Explicitly load project .env with override=True so stale OS environment variables don't hijack settings
_backend_dir = Path(__file__).resolve().parent.parent.parent
_env_path = _backend_dir / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)


class Settings(BaseSettings):
    """
    Central configuration loaded from .env file.
    All values can be overridden via environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=str(_env_path) if _env_path.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────
    app_name: str = "CodeMind AI"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"  # development | staging | production

    # ── Server ───────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Supabase ─────────────────────────────────────
    supabase_url: str = "https://your-project.supabase.co"
    supabase_anon_key: str = "your-anon-key"
    supabase_service_role_key: str = "your-service-role-key"
    # Direct DB connection string for SQLAlchemy (bypasses PostgREST)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    @field_validator("database_url", mode="after")
    @classmethod
    def ensure_asyncpg_driver(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    # ── Groq LLM ─────────────────────────────────────
    groq_api_key: str = "gsk_your_groq_api_key"
    # Models (from user's updated spec)
    groq_generation_model: str = "openai/gpt-oss-120b"   # primary generation
    groq_fast_model: str = "openai/gpt-oss-20b"          # routing, grading, validation
    groq_compound_model: str = "groq/compound"            # compound tasks
    groq_whisper_model: str = "whisper-large-v3-turbo"    # voice (future)

    # ── Embeddings ───────────────────────────────────
    embedding_model_name: str = "nightowl-code-embedding"
    embedding_dimension: int = 768
    # URL for the embedding inference endpoint (HuggingFace / self-hosted)
    embedding_api_url: Optional[str] = None
    embedding_api_key: Optional[str] = None

    # ── Retrieval ────────────────────────────────────
    retrieval_top_k: int = 10
    retrieval_threshold: float = 0.3
    retrieval_vector_weight: float = 0.7
    retrieval_keyword_weight: float = 0.3
    rerank_top_k: int = 5

    # ── Agent Pipeline ───────────────────────────────
    max_rewrites: int = 2
    max_tokens_budget: int = 4000
    hitl_confidence_threshold: float = 0.7  # flag for HITL below this
    tavily_api_key: Optional[str] = None
    web_search_max_results: int = 5
    
    # ── Rate Limiting ────────────────────────────────
    rate_limit_chat: str = "60/minute"       # per user
    rate_limit_ingestion: str = "10/minute"  # per user
    rate_limit_global: str = "200/minute"    # per IP (unauthenticated)

    # ── Security ─────────────────────────────────────
    max_input_length: int = 4000             # max chars per user query
    max_upload_size_mb: int = 100            # max repo upload size
    pii_filter_mode: str = "redact"          # 'redact' | 'block'

    # ── GitHub & HuggingFace ─────────────────────────
    github_token: Optional[str] = None       # for cloning private repos
    hf_token: Optional[str] = None           # HuggingFace Hub token for higher rate limits

    # ── Ingestion ────────────────────────────────────
    max_chunk_tokens: int = 512
    max_chunks_per_file: int = 100
    supported_languages: List[str] = [
        "python", "javascript", "typescript", "java", "go", "cpp", "c", "rust"
    ]


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance — loaded once, reused everywhere.
    Use dependency injection: `settings = Depends(get_settings)`
    """
    return Settings()
