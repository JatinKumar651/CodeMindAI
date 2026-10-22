"""
CodeMind AI — Query Rewriter Agent Node.

When the grader finds insufficient relevant chunks, the rewriter
reformulates the query to improve retrieval results.

Limited to max_rewrites attempts to prevent infinite loops.
"""

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from app.agents.state import GraphState
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def rewrite_query(state: GraphState) -> GraphState:
    """
    Rewriter node: reformulates the query for better retrieval.
    
    Strategies:
      - Expand abbreviations
      - Add technical synonyms
      - Focus on specific code constructs
      - Remove ambiguity
    """
    settings = get_settings()
    original_question = state["question"]
    previous_rewrite = state.get("rewritten_question")
    rewrite_count = state.get("rewrite_count", 0)
    
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_fast_model,
        temperature=0.3,  # Slight creativity for diversity
        max_tokens=600,
        reasoning_effort="low",
    )
    
    rewrite_prompt = f"""You are a query optimizer for a code search system.
The original query did not return enough relevant code chunks from the repository.

Original question: {original_question}
{f'Previous rewrite (also failed): {previous_rewrite}' if previous_rewrite else ''}
Rewrite attempt: {rewrite_count + 1}

Rewrite the question to improve code search results. Strategies:
- Use specific programming terms (function names, class names, design patterns)
- Expand abbreviations (e.g., "auth" → "authentication")
- Focus on what the code DOES rather than abstract concepts
- If the question is about a feature, ask about the implementation

Reply with ONLY the rewritten question. Nothing else."""

    response = await llm.ainvoke([HumanMessage(content=rewrite_prompt)])
    rewritten = response.content.strip()
    
    # Remove quotes if the LLM wrapped the response
    if (rewritten.startswith('"') and rewritten.endswith('"')) or (rewritten.startswith("'") and rewritten.endswith("'")):
        rewritten = rewritten[1:-1].strip()
    
    # Robust fallback: ensure query is never empty
    if not rewritten or len(rewritten.strip()) < 3:
        rewritten = f"{original_question} implementation details classes functions"
    
    logger.info(
        "query_rewritten",
        original=original_question[:100],
        rewritten=rewritten[:100],
        attempt=rewrite_count + 1,
    )
    
    # Update trace
    trace = dict(state.get("agent_trace", {}))
    rewrites = trace.get("rewrites", [])
    rewrites.append({
        "attempt": rewrite_count + 1,
        "original": original_question[:200],
        "rewritten": rewritten[:200],
    })
    trace["rewrites"] = rewrites
    
    return {
        **state,
        "rewritten_question": rewritten,
        "rewrite_count": rewrite_count + 1,
        "agent_trace": trace,
    }
