"""
CodeMind AI — Generator Agent Node.

Generates the final answer using the primary Groq model with
relevant code chunks as context.

Enforces citation format: [file_path:L{start}-L{end}]
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.agents.state import GraphState
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_profile_context(state) -> str:
    """Build a tiny user context header from the profile scratchpad (~20-30 tokens)."""
    profile = state.get("user_profile") or {}
    if not profile:
        return ""
    parts = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("role"):
        parts.append(f"Role: {profile['role']}")
    if profile.get("tech_stack"):
        parts.append(f"Stack: {profile['tech_stack']}")
    if profile.get("current_goal"):
        parts.append(f"Working on: {profile['current_goal']}")
    if not parts:
        return ""
    return f"User Context: {' | '.join(parts)}\n\n"

_SYSTEM_PROMPT = """You are CodeMind AI, an expert code intelligence and debugging assistant.
You help developers understand, navigate, debug, and improve their codebases.

FORMATTING & READABILITY RULES (MANDATORY):
1. **Structure for High Scanability**:
   - Begin with a crisp **1–2 sentence Executive Summary** paragraph answering the core question upfront.
   - Use clear Markdown headings (`### Section Title`) to segment the response.
   - Present details, architecture, components, and concepts as **bullet points with bold lead-ins** (e.g. `- **Key Component:** Explanation...`).
   - Keep any supporting paragraphs concise (2–3 sentences max). NEVER write dense, uninterrupted walls of text.
   - Use concise, well-annotated code blocks with language identifiers (e.g. ```python, ```typescript) and inline comments.
   - Conclude with a brief bulleted list of **Key Takeaways** or **Best Practices**.

2. **Error & Debugging Questions Structure**:
   - 🔴 **Root Cause**: 1–2 sentence summary paragraph explaining why the issue occurs.
   - 🔍 **Implicated Code & Context**: Bullet points highlighting affected files, line numbers, and variables.
   - 💡 **Step-by-Step Fix**: Scannable bullet steps + exact, copy-pasteable code block with language specifier.
   - 🛡️ **Prevention & Best Practices**: Bullet points for edge cases, type hints, or defensive validation.

3. **Grounding & Sources**:
   - Answer based strictly on the provided Code Context and/or Web Search Context. If information is missing, state so clearly.
   - ALWAYS cite repository sources using format: `[file_path:L{start_line}-L{end_line}]`.
   - Cite web documentation or community fixes using markdown links: `[Source Title](URL)`.

4. **Domain Scope Rule**:
   - If the user asks a question completely outside programming, software development, codebases, or computer science (e.g., general trivia, history, celebrities, sports, cooking, politics):
     Do NOT answer the unrelated question. Do NOT provide code snippets that merely print the answer.
     Reply EXACTLY with:
     "I appreciate the question, but it's outside my scope: I'm specifically designed to help with codebase comprehension, software development, debugging, and code architecture." """


async def generate_answer(state: GraphState) -> GraphState:
    """
    Generator node: produces the final answer using retrieved context and/or web search.
    
    Uses the primary generation model (gpt-oss-120b) for quality.
    Supports both local AST chunks and Tavily web results.
    """
    settings = get_settings()
    question = state.get("rewritten_question") or state["question"]
    relevant_docs = state.get("relevant_docs", [])
    web_search_docs = state.get("web_search_docs", [])
    is_error = state.get("is_error_query", False)
    
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_generation_model,
        temperature=0.1,
        max_tokens=settings.max_tokens_budget,
    )
    
    # Build context from relevant chunks
    context_parts = []
    citations_data = []
    
    for i, doc in enumerate(relevant_docs[:5]):  # Limit to top 5 for context window
        file_path = doc.get("file_path", "unknown")
        chunk_name = doc.get("chunk_name", "")
        start_line = doc.get("start_line", 0)
        end_line = doc.get("end_line", 0)
        content = doc.get("content", "")
        chunk_type = doc.get("chunk_type", "code")
        score = doc.get("combined_score") or doc.get("similarity", 0)
        
        context_parts.append(
            f"--- Repo Chunk {i+1}: {file_path} (L{start_line}-L{end_line}) [{chunk_type}: {chunk_name}] ---\n"
            f"```\n{content}\n```\n"
        )
        
        citations_data.append({
            "file_path": file_path,
            "chunk_name": chunk_name,
            "start_line": start_line,
            "end_line": end_line,
            "similarity_score": score,
            "type": "repo",
        })
        
    # Append web search context if available
    web_context_parts = []
    if web_search_docs:
        for j, wdoc in enumerate(web_search_docs[:4]):
            title = wdoc.get("title", "Web Source")
            url = wdoc.get("url", "")
            wcontent = wdoc.get("content", "")
            web_context_parts.append(
                f"--- Web Source {j+1}: {title} ({url}) ---\n{wcontent}\n"
            )
            citations_data.append({
                "file_path": url or title or "Web Source",
                "chunk_name": title,
                "title": title,
                "url": url,
                "type": "web",
            })
    
    repo_context = "\n".join(context_parts) if context_parts else "No relevant repository code chunks found."
    web_context = "\n".join(web_context_parts) if web_context_parts else ""
    
    user_prompt = f"""{_build_profile_context(state)}User Question / Error:
{question}

Repository Code Context:
{repo_context}
"""
    if web_context:
        user_prompt += f"""
Web Search & Documentation Context (from Tavily):
{web_context}
"""

    if is_error:
        user_prompt += """
Please analyze this error using high-clarity scannable formatting:
1. 🔴 **Root Cause**: 1–2 sentence summary explaining the defect.
2. 🔍 **Implicated Code**: Bullet points highlighting affected files, line numbers, and variables.
3. 💡 **Step-by-Step Fix**: Clean code snippet with language tag, followed by bulleted steps of changes.
4. 🛡️ **Prevention**: Bullet points for edge cases, defensive checks, and best practices.
"""
    else:
        user_prompt += """
Please answer using high-clarity scannable formatting:
1. **Executive Summary**: 1–2 sentence direct answer upfront.
2. **Key Concepts / Architecture Breakdown**: Bullet points with bold lead-ins (`- **Component:** Explanation`).
3. **Implementation / Code Walkthrough**: Short, annotated code blocks with language specifiers where relevant.
4. **Key Takeaways & Best Practices**: Bullet points summarizing actionable recommendations.
Remember to cite repository sources as [file_path:L{start}-L{end}] and web sources as [Title](URL).
"""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        
        answer = response.content
        tokens_used = response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
        
    except Exception as e:
        logger.error("generation_error", error=str(e))
        answer = (
            "I encountered an error generating the response. "
            f"Error: {str(e)[:200]}. Please try again."
        )
        tokens_used = 0
    
    logger.info(
        "answer_generated",
        question=question[:100],
        answer_length=len(answer),
        tokens=tokens_used,
        context_chunks=len(relevant_docs),
    )
    
    # Update trace
    trace = dict(state.get("agent_trace", {}))
    trace["generator"] = {
        "context_chunks": len(relevant_docs),
        "answer_length": len(answer),
        "tokens_used": tokens_used,
        "model": settings.groq_generation_model,
    }
    
    return {
        **state,
        "answer": answer,
        "citations": citations_data,
        "tokens_used": state.get("tokens_used", 0) + tokens_used,
        "model_used": settings.groq_generation_model,
        "agent_trace": trace,
    }


async def generate_direct_answer(state: GraphState) -> GraphState:
    """
    Direct answer node: answers general programming questions
    without retrieval (used when router selects 'direct').
    """
    settings = get_settings()
    question = state["question"]
    
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_generation_model,
        temperature=0.2,
        max_tokens=settings.max_tokens_budget,
    )
    
    profile_header = _build_profile_context(state)

    direct_prompt = f"""You are CodeMind AI, an expert code intelligence and software development assistant.

{profile_header}CONVERSATIONAL CONTEXT & USER PROFILE RULES:
- If the user is introducing themselves, sharing their background, role, tech stack, or career/learning goals (e.g., "I am Jatin and I am working on AI..."):
  Warmly welcome them, address them by their name, acknowledge their background/goals, and let them know how CodeMind AI can help them build, comprehend, and debug their software systems.
- If the user asks about their identity, name, or profile (e.g., "What is my name?", "Can you tell my name?", "Who am I?", "What stack am I using?"):
  Answer directly and helpfully using the User Context provided above (e.g., "You are Jatin!"). If a detail isn't in User Context, politely mention that they haven't shared it yet.
- If the user is saying a polite greeting (like "hi", "hello", "who are you"):
  Politely introduce yourself as CodeMind AI and state that you are here to help them understand, debug, and navigate their code repositories.{' Address them by their name if you know it.' if (state.get('user_profile') or {}).get('name') else ''}
- These user profile interactions and developer greetings are fully IN-SCOPE. Do NOT trigger the out-of-scope rejection for them.

CRITICAL SCOPE RULE:
You ONLY assist with programming, software engineering, codebases, computer science, and technical development.
If the question is completely unrelated to programming, software development, code, technical architecture, or the assistant itself (for example: questions about history, space exploration, celebrities, sports, cooking, politics, or general trivia like "who landed on the moon"):
You MUST NOT answer the trivia or unrelated question. Do NOT provide code examples that merely print the trivia answer.
Instead, reply EXACTLY with:
"I appreciate the question, but it's outside my scope: I'm specifically designed to help with codebase comprehension, software development, debugging, and code architecture."

FORMATTING REQUIREMENTS (FOR HIGH SCANABILITY & READABILITY):
- **Executive Summary**: Start with a crisp 1–2 sentence paragraph providing the direct answer upfront.
- **Scannable Bullets**: Present key concepts, reasons, mechanisms, or steps as bullet points with **bold lead-ins** (e.g. `- **Key Concept:** Direct explanation.`).
- **Concise Explanatory Paragraphs**: Keep supporting paragraphs concise (2–3 sentences max). Never output giant walls of text.
- **Annotated Code Snippets**: Provide minimal, focused code blocks with language specifiers (e.g. ```python) and inline comments where relevant.
- **Key Takeaways**: End with 2–3 actionable bullet points summarizing best practices or practical tips when answering technical concepts.

Question: {question}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=direct_prompt)])
        answer = response.content
        tokens_used = response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
    except Exception as e:
        answer = f"Error generating answer: {str(e)[:200]}"
        tokens_used = 0
    
    trace = dict(state.get("agent_trace", {}))
    trace["generator"] = {
        "mode": "direct",
        "tokens_used": tokens_used,
    }
    
    return {
        **state,
        "answer": answer,
        "citations": [],
        "tokens_used": tokens_used,
        "model_used": settings.groq_generation_model,
        "validation_passed": True,
        "confidence_score": 0.9,  # Direct answers are generally reliable
        "agent_trace": trace,
    }
