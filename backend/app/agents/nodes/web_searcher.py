"""
CodeMind AI — Web Search Agent Node.

Fallback node when local repository search yields insufficient relevant chunks,
or when the user reports a runtime error/stack trace requiring external documentation.

Uses Tavily Search API (via AsyncTavilyClient) to fetch official documentation,
GitHub issues, and developer community solutions.
"""

import re
from typing import Any, Dict, List

from tavily import AsyncTavilyClient

from app.agents.state import GraphState
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _sanitize_search_query(raw_query: str, is_error: bool = False) -> str:
    """
    Cleans local file paths and noise from search query for high-relevance web results.
    E.g., transforms 'C:\\Users\\Jatin\\Desktop\\CMAI\\backend\\app\\routers\\auth.py: line 45 TypeError'
    into 'FastAPI auth TypeError'
    """
    # Remove Windows/Unix absolute paths
    clean = re.sub(r"[a-zA-Z]:\\[^\s:]+", "", raw_query)
    clean = re.sub(r"/(?:[a-zA-Z0-9_-]+/)+[a-zA-Z0-9_.-]+", "", clean)
    
    # If error, keep error type and core message
    if is_error:
        # Extract exception or HTTP error
        match = re.search(r"((?:[A-Z][a-zA-Z0-9_]*Error|[A-Z][a-zA-Z0-9_]*Exception|\b\d{3}\s+[A-Za-z]+)\b.*)", clean)
        if match:
            clean = match.group(1)
    
    # Remove redundant whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:200] if clean else raw_query[:200]


async def search_web(state: GraphState) -> GraphState:
    """
    Web Search node: queries Tavily for external documentation, error solutions,
    and library APIs when local repo chunks are absent.
    """
    settings = get_settings()
    api_key = settings.tavily_api_key
    
    question = state.get("rewritten_question") or state["question"]
    is_error = state.get("is_error_query", False)
    search_query = _sanitize_search_query(question, is_error=is_error)
    
    trace = dict(state.get("agent_trace", {}))
    
    if not api_key:
        logger.warning(
            "tavily_api_key_missing",
            message="TAVILY_API_KEY is not configured in settings. Skipping web search fallback."
        )
        trace["web_search"] = {
            "status": "skipped",
            "reason": "TAVILY_API_KEY not configured",
            "query": search_query,
            "results_count": 0,
        }
        return {
            **state,
            "web_search_docs": [],
            "used_web_search": False,
            "agent_trace": trace,
        }
    
    logger.info("web_search_invoked", query=search_query, is_error=is_error)
    
    try:
        client = AsyncTavilyClient(api_key=api_key)
        response = await client.search(
            query=search_query,
            max_results=settings.web_search_max_results,
            search_depth="advanced" if is_error else "basic",
            include_answer=True,
        )
        
        raw_results = response.get("results", [])
        web_docs: List[Dict[str, Any]] = []
        
        for item in raw_results:
            web_docs.append({
                "title": item.get("title", "Web Source"),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.8),
            })
            
        direct_answer = response.get("answer")
        
        logger.info(
            "web_search_success",
            query=search_query,
            results_found=len(web_docs),
            has_tavily_answer=bool(direct_answer),
        )
        
        trace["web_search"] = {
            "status": "success",
            "query": search_query,
            "results_count": len(web_docs),
            "sources": [{"title": d["title"], "url": d["url"]} for d in web_docs[:3]],
            "tavily_answer": direct_answer[:200] if direct_answer else None,
        }
        
        return {
            **state,
            "web_search_docs": web_docs,
            "used_web_search": len(web_docs) > 0,
            "agent_trace": trace,
        }
        
    except Exception as e:
        logger.error("web_search_failed", query=search_query, error=str(e))
        trace["web_search"] = {
            "status": "error",
            "error": str(e)[:200],
            "query": search_query,
            "results_count": 0,
        }
        return {
            **state,
            "web_search_docs": [],
            "used_web_search": False,
            "agent_trace": trace,
        }
