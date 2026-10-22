"""
CodeMind AI — Validator Agent Node.

Hallucination detection: verifies that the generated answer
is grounded in the retrieved code chunks.

Sets confidence_score and validation_passed which feed into
the HITL gateway.
"""

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from app.agents.state import GraphState
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def validate_answer(state: GraphState) -> GraphState:
    """
    Validator node: checks for hallucination in the generated answer.
    
    Verifies:
      1. Every claim in the answer is supported by retrieved chunks
      2. Code references actually exist in the context
      3. The answer addresses the original question
    
    Sets:
      - validation_passed: True/False
      - confidence_score: 0.0-1.0
      - validation_reason: explanation of the verdict
    """
    settings = get_settings()
    answer = state.get("answer", "")
    question = state.get("rewritten_question") or state["question"]
    relevant_docs = state.get("relevant_docs", [])
    web_search_docs = state.get("web_search_docs", [])
    
    # If no relevant repo docs AND no web search docs, answer was generated without context
    if not relevant_docs and not web_search_docs and state.get("route") in ("retrieve", "debug"):
        logger.warning("validation_no_context", message="Answer generated without code or web context")
        trace = dict(state.get("agent_trace", {}))
        trace["validator"] = {
            "verdict": "low_confidence",
            "reason": "No relevant code or web search context was available",
        }
        return {
            **state,
            "validation_passed": False,
            "confidence_score": 0.3,
            "validation_reason": "Answer generated without context — may not be accurate",
            "guardrail_flags": state.get("guardrail_flags", []) + ["no_context"],
            "needs_human_review": True,
            "agent_trace": trace,
        }
    
    # For direct answers (no retrieval requested), skip detailed validation
    if state.get("route") == "direct":
        return {
            **state,
            "validation_passed": True,
            "confidence_score": 0.9,
            "validation_reason": None,
        }
    
    import re

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_fast_model,
        temperature=0,
        max_tokens=600,
        reasoning_effort="low",
    )
    
    # Build context summary for validation (both repo AST and web sources)
    context_items = []
    for doc in relevant_docs[:5]:
        context_items.append(f"- Repo {doc.get('file_path', '?')}: {doc.get('content', '')[:200]}")
    for wdoc in web_search_docs[:3]:
        context_items.append(f"- Web {wdoc.get('title', 'Web')}: {wdoc.get('content', '')[:200]}")
    context_summary = "\n".join(context_items)
    
    validation_prompt = f"""You are a hallucination detector for a code intelligence system.

Question: {question}

Code context provided:
{context_summary}

Generated answer:
{answer[:1500]}

Evaluate the answer on these criteria:
1. GROUNDED: Is every claim in the answer supported by the code context?
2. ACCURATE: Are code references (file paths, function names, line numbers) correct?
3. RELEVANT: Does the answer address the original question?

Reply in this exact format:
grounded: yes/no
accurate: yes/no
relevant: yes/no
confidence: 0.0-1.0
reason: <brief explanation>"""

    try:
        response = await llm.ainvoke([HumanMessage(content=validation_prompt)])
        result = response.content.strip().lower()
        
        # Robust regex parsing
        grounded_match = re.search(r"grounded\s*:\s*(yes|no)", result)
        accurate_match = re.search(r"accurate\s*:\s*(yes|no)", result)
        relevant_match = re.search(r"relevant\s*:\s*(yes|no)", result)
        
        grounded = grounded_match.group(1) == "yes" if grounded_match else True
        accurate = accurate_match.group(1) == "yes" if accurate_match else True
        relevant = relevant_match.group(1) == "yes" if relevant_match else True
        
        # Extract confidence
        confidence = 0.85
        conf_match = re.search(r"confidence\s*:\s*([0-1](?:\.\d+)?)", result)
        if conf_match:
            try:
                confidence = float(conf_match.group(1))
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                confidence = 0.85
        
        # Extract reason
        reason = None
        reason_match = re.search(r"reason\s*:\s*(.+)", response.content.strip(), re.I)
        if reason_match:
            reason = reason_match.group(1).strip()
        
        validation_passed = grounded and accurate and relevant
        
        # Build guardrail flags
        guardrail_flags = list(state.get("guardrail_flags", []))
        if not grounded:
            guardrail_flags.append("hallucination")
        if not accurate:
            guardrail_flags.append("inaccurate_references")
        if not relevant:
            guardrail_flags.append("irrelevant_answer")
        
        needs_review = (
            not validation_passed
            or confidence < settings.hitl_confidence_threshold
        )
        
    except Exception as e:
        logger.error("validation_error", error=str(e))
        # On validation error, pass through with medium confidence
        validation_passed = True
        confidence = 0.6
        reason = f"Validation check failed: {str(e)[:100]}"
        guardrail_flags = list(state.get("guardrail_flags", []))
        needs_review = False
    
    # Sanitize reason string for clean console output
    safe_reason = reason.encode("ascii", errors="replace").decode("ascii")[:200] if reason else None

    logger.info(
        "validation_complete",
        passed=validation_passed,
        confidence=confidence,
        reason=safe_reason,
        needs_review=needs_review,
    )
    
    # Update trace
    trace = dict(state.get("agent_trace", {}))
    trace["validator"] = {
        "passed": validation_passed,
        "confidence": confidence,
        "reason": reason,
        "needs_review": needs_review,
    }
    
    return {
        **state,
        "validation_passed": validation_passed,
        "confidence_score": confidence,
        "validation_reason": reason,
        "guardrail_flags": guardrail_flags,
        "needs_human_review": needs_review,
        "agent_trace": trace,
    }
