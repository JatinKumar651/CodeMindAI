"""
CodeMind AI — Retriever Agent Node.

Performs hybrid search (vector + keyword) against Supabase pgvector
to find relevant code chunks for the user's question.
"""

from typing import Any, Dict, List

from app.agents.state import GraphState
from app.core.config import get_settings
from app.core.database import get_supabase_admin
from app.core.logging import get_logger

logger = get_logger(__name__)


async def retrieve_chunks(state: GraphState) -> GraphState:
    """
    Retriever node: fetches relevant code chunks using hybrid search.
    
    Uses the Supabase RPC function `hybrid_search_code` which combines:
      - pgvector cosine similarity (semantic match)
      - tsvector BM25 keyword matching (exact term match)
    """
    settings = get_settings()
    question = state.get("rewritten_question") or state["question"]
    repo_id = state["repository_id"]
    user_id = state.get("user_id")
    
    # Generate query embedding
    from app.services.ingestion.embedder import EmbeddingGenerator
    embedder = EmbeddingGenerator()
    query_embedding = await embedder.embed_text(question)
    
    # Call Supabase RPC for hybrid search
    supabase = get_supabase_admin()
    
    try:
        response = supabase.rpc(
            "hybrid_search_code",
            {
                "query_embedding": query_embedding,
                "query_text": question,
                "match_threshold": settings.retrieval_threshold,
                "match_count": settings.retrieval_top_k,
                "filter_repo": repo_id,
                "filter_model": settings.embedding_model_name,
                "requesting_user_id": user_id,  # ownership enforcement
                "vector_weight": settings.retrieval_vector_weight,
                "keyword_weight": settings.retrieval_keyword_weight,
            }
        ).execute()
        
        retrieved_docs = response.data if response.data else []
        
    except Exception as e:
        logger.error("retrieval_failed", error=str(e), repo_id=repo_id)
        # Fallback to vector-only search
        try:
            response = supabase.rpc(
                "match_code_docs",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": settings.retrieval_threshold,
                    "match_count": settings.retrieval_top_k,
                    "filter_repo": repo_id,
                    "filter_model": settings.embedding_model_name,
                    "requesting_user_id": user_id,
                }
            ).execute()
            retrieved_docs = response.data if response.data else []
        except Exception as e2:
            logger.error("retrieval_fallback_failed", error=str(e2))
            retrieved_docs = []
    
    logger.info(
        "chunks_retrieved",
        count=len(retrieved_docs),
        repo_id=repo_id,
        question=question[:100],
    )
    
    # Update trace
    trace = dict(state.get("agent_trace", {}))
    trace["retriever"] = {
        "chunks_found": len(retrieved_docs),
        "top_scores": [
            {"chunk_id": d.get("chunk_id"), "score": d.get("combined_score") or d.get("similarity")}
            for d in retrieved_docs[:3]
        ],
    }
    
    return {
        **state,
        "retrieved_docs": retrieved_docs,
        "agent_trace": trace,
    }
