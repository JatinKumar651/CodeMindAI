"""
CodeMind AI — LangGraph State Definition.

Enhanced from the original GraphState.py with:
  • max_tokens_budget for cost control
  • pii_detected flag
  • confidence_score for HITL gating
  • needs_human_review flag
  • guardrail_flags for tracking security events
"""

from typing import Annotated, Any, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    """
    LangGraph state for CodeMind AI.
    Must be serializable — no ORM objects, only primitives/dicts.
    """

    # ── Conversation (persisted by checkpointer) ──
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # ── Session context ──
    repository_id: str       # UUID as string
    session_id: str          # UUID as string
    user_id: Optional[str]

    # ── Current turn ──
    question: str
    rewritten_question: Optional[str]

    # ── Retrieval & Web Search ──
    retrieved_docs: List[Dict[str, Any]]   # [{chunk_id, file_path, content, similarity, ...}]
    relevant_docs: List[Dict[str, Any]]    # after grading
    grader_scores: List[Dict[str, Any]]    # [{chunk_id, verdict, reason}]
    web_search_docs: List[Dict[str, Any]]  # [{title, url, content, score}]
    used_web_search: bool

    # ── Error Debugging Context ──
    is_error_query: bool
    error_metadata: Optional[Dict[str, Any]]  # {error_type, error_message, file_hint, line_hint}

    # ── Control flow ──
    rewrite_count: int
    max_rewrites: int
    route: str               # 'retrieve' | 'direct' | 'debug' | 'scan' | 'doc'

    # ── Output ──
    answer: Optional[str]
    citations: List[Dict[str, Any]]
    validation_passed: bool
    validation_reason: Optional[str]

    # ── Security & Guardrails (NEW) ──
    confidence_score: float           # 0.0 - 1.0, used for HITL gating
    needs_human_review: bool          # set by validator if confidence < threshold
    guardrail_flags: List[str]        # e.g. ["hallucination", "pii_in_output"]
    pii_detected: bool                # whether PII was found in input
    max_tokens_budget: int            # ceiling for token usage in this turn

    # ── Memory (Profile Scratchpad) ──
    user_profile: Dict[str, str]          # {"name": "Jatin", "tech_stack": "Python, React", ...}
    last_assistant_answer: Optional[str]  # Previous turn's answer (truncated) for follow-up resolution

    # ── Observability ──
    agent_trace: Dict[str, Any]       # step-by-step log
    tokens_used: int
    latency_ms: int
    model_used: str

