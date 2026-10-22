"""
CodeMind AI — Router Agent Node.

Classifies user queries into one of:
  • retrieve — needs code search from the repository
  • direct — can be answered directly without retrieval (general coding questions)
  • scan — user wants a code scan/analysis
  • doc — user wants documentation generation

Uses the fast model (gpt-oss-20b) for cost efficiency.
"""

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from app.agents.state import GraphState
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


OUT_OF_SCOPE_RESPONSE = (
    "I appreciate the question, but it's outside my scope: "
    "I'm specifically designed to help with codebase comprehension, software development, debugging, and code architecture."
)


async def route_query(state: GraphState) -> GraphState:
    """
    Router node: classifies the user's question intent.
    
    Determines whether the question requires:
      - Out-of-scope rejection (out_of_scope)
      - Code retrieval from the repo (retrieve)
      - Direct LLM answer (direct)
      - A code scan (scan)
      - Documentation generation (doc)
      - Debugging assistance (debug)
    """
    settings = get_settings()
    question = state.get("rewritten_question") or state["question"]
    
    import re

    # Fast heuristic override for obvious greetings, user introductions, and profile/identity questions
    direct_patterns = [
        r"^(?:hi|hello|hey|greetings|howdy|good\s+(?:morning|afternoon|evening))\b",
        r"\b(?:what(?:'s|\s+is)\s+my\s+name|who\s+am\s+i|can\s+you\s+tell\s+my\s+name|do\s+you\s+remember\s+(?:me|my\s+name))\b",
        r"\b(?:what(?:\s+do\s+you\s+know|\s+information\s+do\s+you\s+have)\s+about\s+me)\b",
        r"\b(?:what(?:'s|\s+is)\s+my\s+(?:tech\s+)?stack|what\s+am\s+i\s+working\s+on|what\s+is\s+my\s+role)\b",
        r"\b(?:who\s+are\s+you|what\s+can\s+you\s+do|how\s+can\s+you\s+help\s+me)\b",
        r"^(?:i\s*am|i'?m|my\s+name\s+is)\s+[A-Za-z]+",
    ]
    for pat in direct_patterns:
        if re.search(pat, question.strip(), re.IGNORECASE):
            route = "direct"
            break
    else:
        llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_fast_model,
            temperature=0,
            max_tokens=300,
            reasoning_effort="low",
        )
        
        routing_prompt = f"""You are a query router for a code intelligence and developer assistant system.
Classify the user question into exactly ONE category:

- "debug" — User reports a code error, bug, exception, stack trace, failing test, or asks for code troubleshooting (e.g., "I am getting error...", "Why is this failing?", "Fix TypeError in auth")
- "retrieve" — Question about understanding or finding specific code in the repository (e.g., "How does the auth module work?", "Where is the database connection?", "What APIs are defined?")
- "direct" — General programming questions, syntax, algorithms, software engineering concepts, greetings, assistant capabilities, user self-introductions, developer background/goals, or questions about the user's profile/identity (e.g., "What is a decorator in Python?", "Explain async/await", "Hello", "I am Jatin, working on AI", "Can you tell my name?", "What stack do I use?")
- "scan" — User wants to analyze/scan code for security, dead code, or complexity (e.g., "Find security vulnerabilities", "Run complexity analysis")
- "doc" — User wants documentation generated (e.g., "Generate README", "Document this module")
- "out_of_scope" — Any question completely unrelated to programming, software development, computer science, or the assistant itself (e.g., general trivia like "who's the first man to land on moon?", history, space, sports, cooking, politics, pop culture, entertainment)

Question: {question}

Reply with ONLY the category word (debug, retrieve, direct, scan, doc, or out_of_scope). Nothing else."""

        try:
            response = await llm.ainvoke([HumanMessage(content=routing_prompt)])
            raw_text = response.content.strip().lower()
            match = re.search(r"\b(debug|retrieve|direct|scan|doc|out_of_scope)\b", raw_text)
            route = match.group(1) if match else "retrieve"
        except Exception as e:
            logger.error("routing_error", error=str(e))
            route = "retrieve"
    
    # Handle out-of-scope questions immediately without unnecessary retrieval or LLM tokens
    if route == "out_of_scope":
        logger.info(
            "query_routed_out_of_scope",
            question=question[:100],
            route="out_of_scope",
        )
        trace = dict(state.get("agent_trace", {}))
        trace["router"] = {
            "route": "out_of_scope",
            "is_error_query": False,
            "error_metadata": None,
            "question": question[:200],
        }
        return {
            **state,
            "route": "out_of_scope",
            "answer": OUT_OF_SCOPE_RESPONSE,
            "citations": [],
            "validation_passed": True,
            "confidence_score": 1.0,
            "is_error_query": False,
            "error_metadata": None,
            "agent_trace": trace,
            "model_used": settings.groq_fast_model,
        }
    
    # Fast heuristic override for obvious error queries
    error_patterns = [
        r"\b(?:getting|got|have|having|throws?|throwing)\s+(?:an?\s+)?error\b",
        r"\btraceback\s+\(most recent call last\)\b",
        r"\b(?:[A-Z][a-zA-Z0-9_]*(?:Error|Exception))\b",
        r"\b(?:4\d\d|5\d\d)\s+[A-Za-z]+\b",
        r"\b(?:syntax error|segfault|nullpointer|undefined is not a function)\b",
        r"\bwhy is (?:this|my code) (?:failing|crashing|not working)\b",
    ]
    is_error = (route == "debug")
    if not is_error:
        for pat in error_patterns:
            if re.search(pat, question, re.I):
                route = "debug"
                is_error = True
                break
                
    # Extract error metadata if present
    error_metadata = None
    if is_error:
        exc_match = re.search(r"\b([A-Z][a-zA-Z0-9_]*(?:Error|Exception))\b", question)
        http_match = re.search(r"\b(4\d\d|5\d\d)\s+([A-Za-z]+)\b", question)
        file_match = re.search(r"([a-zA-Z0-9_/-]+\.(?:py|ts|js|go|java|rs|cpp))(?::(\d+))?", question)
        
        error_metadata = {
            "error_type": exc_match.group(1) if exc_match else (http_match.group(0) if http_match else "RuntimeError"),
            "file_hint": file_match.group(1) if file_match else None,
            "line_hint": int(file_match.group(2)) if file_match and file_match.group(2) else None,
        }

    logger.info(
        "query_routed",
        question=question[:100],
        route=route,
        is_error=is_error,
    )
    
    # Update trace
    trace = dict(state.get("agent_trace", {}))
    trace["router"] = {
        "route": route,
        "is_error_query": is_error,
        "error_metadata": error_metadata,
        "question": question[:200],
    }
    
    return {
        **state,
        "route": route,
        "is_error_query": is_error,
        "error_metadata": error_metadata,
        "agent_trace": trace,
        "model_used": settings.groq_fast_model,
    }
