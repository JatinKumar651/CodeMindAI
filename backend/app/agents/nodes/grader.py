"""
CodeMind AI — Grader Agent Node.

Scores each retrieved chunk's relevance to the user's question.
Uses LLM-as-a-judge pattern with the fast model.

If fewer than 2 chunks are deemed relevant, triggers query rewriting.
"""

import asyncio
import re
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from app.agents.state import GraphState
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def grade_documents(state: GraphState) -> GraphState:
    """
    Grader node: evaluates relevance of each retrieved chunk.
    
    For each chunk, asks the LLM: "Is this code relevant to the question?"
    Evaluates all chunks in parallel using asyncio.gather for low latency.
    """
    settings = get_settings()
    question = state.get("rewritten_question") or state["question"]
    retrieved_docs = state.get("retrieved_docs", [])
    
    if not retrieved_docs:
        logger.info("grader_no_docs", message="No documents to grade")
        return {
            **state,
            "relevant_docs": [],
            "grader_scores": [],
        }
    
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_fast_model,
        temperature=0,
        max_tokens=600,
        reasoning_effort="low",
    )

    async def _grade_single_doc(doc: dict):
        chunk_content = doc.get("content", "")[:1000]  # Limit context size
        chunk_id = doc.get("chunk_id", "unknown")
        file_path = doc.get("file_path", "unknown")
        
        grading_prompt = f"""You are a relevance grader for a code search system.

Question: {question}

Code chunk from {file_path}:
```
{chunk_content}
```

Is this code chunk relevant to answering the question?
Reply with ONLY "relevant" or "irrelevant" followed by a brief reason.

Format:
verdict: relevant
reason: This function handles the exact functionality asked about."""

        try:
            response = await llm.ainvoke([HumanMessage(content=grading_prompt)])
            raw_text = response.content.strip()
            response_text = raw_text.lower()
            
            # Robust verdict parsing via regex
            match = re.search(r"verdict\s*:\s*(relevant|irrelevant)", response_text, re.I)
            if match:
                verdict = match.group(1).lower()
            elif "relevant" in response_text and "irrelevant" not in response_text:
                verdict = "relevant"
            elif not response_text:
                # If model produced empty output, fail open to avoid losing valid context
                verdict = "relevant"
            else:
                verdict = "irrelevant"
            
            # Extract reason
            reason = ""
            if "reason:" in response_text:
                reason = raw_text.split("reason:")[-1].strip()
            elif raw_text:
                reason = raw_text[:200]
            
            score_entry = {
                "chunk_id": chunk_id,
                "verdict": verdict,
                "reason": reason[:200],
            }
            return doc, score_entry
            
        except Exception as e:
            logger.error("grading_error", chunk_id=chunk_id, error=str(e))
            # On error, fail open
            score_entry = {
                "chunk_id": chunk_id,
                "verdict": "relevant",
                "reason": f"Grading failed open: {str(e)[:100]}",
            }
            return doc, score_entry

    # Execute all evaluations in parallel
    results = await asyncio.gather(*[_grade_single_doc(d) for d in retrieved_docs])
    
    relevant_docs = []
    grader_scores = []
    for doc, score in results:
        grader_scores.append(score)
        if score["verdict"] == "relevant":
            relevant_docs.append(doc)
    
    logger.info(
        "grading_complete",
        total=len(retrieved_docs),
        relevant=len(relevant_docs),
        irrelevant=len(retrieved_docs) - len(relevant_docs),
    )
    
    # Update trace
    trace = dict(state.get("agent_trace", {}))
    trace["grader"] = {
        "total_chunks": len(retrieved_docs),
        "relevant_count": len(relevant_docs),
        "scores": grader_scores[:5],  # Top 5 for trace
    }
    
    return {
        **state,
        "relevant_docs": relevant_docs,
        "grader_scores": grader_scores,
        "agent_trace": trace,
    }
