"""
CodeMind AI — LangGraph Agentic RAG Workflow.

Builds the cyclic multi-agent graph:
  1. Router classifies intent (retrieve vs direct)
  2. If direct -> Direct Generator -> Validator -> END
  3. If retrieve -> Retriever -> Grader
  4. Grader evaluates relevance:
       - If enough relevant docs OR max rewrites reached -> Generator -> Validator -> END
       - If insufficient relevant docs -> Rewriter -> loops back to Retriever
  5. Validator performs hallucination check & confidence scoring -> END (flags for HITL if needed)
"""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes.generator import generate_answer, generate_direct_answer
from app.agents.nodes.grader import grade_documents
from app.agents.nodes.memory import extract_memory
from app.agents.nodes.retriever import retrieve_chunks
from app.agents.nodes.rewriter import rewrite_query
from app.agents.nodes.router import route_query
from app.agents.nodes.validator import validate_answer
from app.agents.nodes.web_searcher import search_web
from app.agents.state import GraphState
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Conditional Edge Deciders ──────────────────────────

def decide_route(state: GraphState) -> Literal["direct_generator", "retriever", "__end__"]:
    """
    Route after intent classification:
      - 'out_of_scope' -> immediately end with out-of-scope response
      - 'direct' -> direct answer without retrieval
      - 'debug', 'retrieve' (or scan/doc/other) -> hybrid retrieval pipeline
    """
    route = state.get("route", "retrieve")
    if route == "out_of_scope":
        return "__end__"
    if route == "direct":
        return "direct_generator"
    return "retriever"


def decide_to_generate(state: GraphState) -> Literal["generator", "rewriter", "web_searcher"]:
    """
    Decide next step after document grading:
      - If relevant documents >= 1 -> proceed to generator
      - If 0 relevant docs and rewrites remaining -> rewriter
      - If 0 relevant docs and max rewrites exhausted (or debug query without repo matches) -> web_searcher
    """
    relevant_docs = state.get("relevant_docs", [])
    rewrite_count = state.get("rewrite_count", 0)
    max_rewrites = state.get("max_rewrites", 2)
    route = state.get("route", "retrieve")

    logger.info(
        "grading_decision",
        relevant_docs_count=len(relevant_docs),
        rewrite_count=rewrite_count,
        max_rewrites=max_rewrites,
        route=route,
    )

    # If we have at least 1 relevant doc, generate answer directly
    if len(relevant_docs) >= 1:
        return "generator"

    # For debug queries without local repo matches, fallback immediately to web search
    if route == "debug":
        logger.info("debug_web_search_fallback", message="No local code matches for error; querying web search")
        return "web_searcher"

    # If rewrites remaining, rewrite query to improve search
    if rewrite_count < max_rewrites:
        return "rewriter"

    # If max rewrites exhausted and still 0 relevant docs, fallback to web search!
    logger.info("web_search_fallback", message="Max rewrites reached with 0 local docs; invoking web search")
    return "web_searcher"


# ── Build StateGraph ───────────────────────────────────

def build_graph() -> StateGraph:
    """
    Constructs the uncompiled LangGraph StateGraph.
    """
    workflow = StateGraph(GraphState)

    # Register all nodes
    workflow.add_node("memory_extractor", extract_memory)
    workflow.add_node("router", route_query)
    workflow.add_node("retriever", retrieve_chunks)
    workflow.add_node("grader", grade_documents)
    workflow.add_node("rewriter", rewrite_query)
    workflow.add_node("web_searcher", search_web)
    workflow.add_node("generator", generate_answer)
    workflow.add_node("direct_generator", generate_direct_answer)
    workflow.add_node("validator", validate_answer)

    # Define edges
    # START -> memory_extractor -> router
    workflow.add_edge(START, "memory_extractor")
    workflow.add_edge("memory_extractor", "router")

    # router -> direct_generator OR retriever OR __end__
    workflow.add_conditional_edges(
        "router",
        decide_route,
        {
            "direct_generator": "direct_generator",
            "retriever": "retriever",
            "__end__": END,
        },
    )

    # retriever -> grader
    workflow.add_edge("retriever", "grader")

    # grader -> generator OR rewriter OR web_searcher
    workflow.add_conditional_edges(
        "grader",
        decide_to_generate,
        {
            "generator": "generator",
            "rewriter": "rewriter",
            "web_searcher": "web_searcher",
        },
    )

    # rewriter loops back to retriever
    workflow.add_edge("rewriter", "retriever")

    # web_searcher -> generator
    workflow.add_edge("web_searcher", "generator")

    # generator / direct_generator -> validator
    workflow.add_edge("generator", "validator")
    workflow.add_edge("direct_generator", "validator")

    # validator -> END
    workflow.add_edge("validator", END)

    return workflow


# ── Compiled Graph Singleton ───────────────────────────

_compiled_graph = None


def get_agent_graph():
    """
    Returns the compiled LangGraph workflow with conversation checkpointer.
    Thread persistence is handled via session_id passed as configurable thread_id.
    """
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_graph()
        checkpointer = MemorySaver()
        _compiled_graph = workflow.compile(checkpointer=checkpointer)
        logger.info("agent_graph_compiled", message="LangGraph StateGraph initialized with MemorySaver")
    return _compiled_graph
