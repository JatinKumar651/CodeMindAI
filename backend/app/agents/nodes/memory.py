"""
CodeMind AI — Memory Extractor Agent Node (Profile Scratchpad).

Runs BEFORE the router on every turn. Two responsibilities:

1. **Profile Extraction (regex-first):**
   Detects user facts like name, tech stack, role, and current goal.
   Updates the persistent user_profile dict (~0ms for regex path).

2. **Follow-up Resolution:**
   If the user references the previous turn ("explain step 2",
   "write tests for that"), rewrites the question to be self-contained
   using a truncated snippet of the last assistant answer.
"""

import re
from typing import Dict, Optional

from app.agents.state import GraphState
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Regex Patterns for Profile Extraction ──────────────

# Name patterns: "I'm Jatin", "my name is Jatin", "I am Jatin", "call me Jatin"
_NAME_PATTERNS = [
    re.compile(r"\b(?:I'?m|I am|my name is|call me|this is)\s+([A-Z][a-z]{1,20})\b", re.IGNORECASE),
    re.compile(r"\b(?:hey|hi|hello),?\s*I'?m\s+([A-Z][a-z]{1,20})\b", re.IGNORECASE),
]

# Tech stack patterns: "I use React", "I work with Python and FastAPI", "my stack is ..."
_STACK_PATTERNS = [
    re.compile(
        r"\b(?:I (?:use|work with|code in|develop (?:in|with)|prefer)|my (?:stack|tech|framework) is)\s+(.+?)(?:\.|$)",
        re.IGNORECASE,
    ),
]

# Role patterns: "I'm a frontend developer", "I am a senior engineer", "looking for junior ai engineer roles"
_ROLE_PATTERNS = [
    re.compile(
        r"\b(?:I'?m|I am|working as|looking for)\s+(?:an?\s+)?((?:senior|junior|lead|staff|principal|full[- ]?stack|front[- ]?end|back[- ]?end|ai|ml|data|software|cloud|devops)?\s*(?:ai|ml)?\s*(?:developer|engineer|dev|programmer|architect|student|intern))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bmy (?:role|title|position|job)\s+is\s+(?:an?\s+)?([A-Za-z\s-]+?)(?:\.|\band\b|$)",
        re.IGNORECASE,
    ),
]

# Goal / working-on patterns: "I'm working on auth module", "I am currently working on agentic ai"
_GOAL_PATTERNS = [
    re.compile(
        r"\b(?:I'?m|I am)\s+(?:currently\s+)?(?:working on|building|developing|fixing|refactoring|debugging|focused on)\s+(.+?)(?:\.|\band\s+(?:looking|working|aiming|hoping)\b|$)",
        re.IGNORECASE,
    ),
]

# ── Follow-up Detection ───────────────────────────────

# Patterns indicating the user is referencing the previous response
_FOLLOWUP_PATTERNS = [
    re.compile(r"\b(?:explain|elaborate|expand on)\s+(?:step|point|that|this|it|the above)", re.IGNORECASE),
    re.compile(r"\b(?:what (?:did you|do you) mean|can you clarify)", re.IGNORECASE),
    re.compile(r"\b(?:write|add|create|generate)\s+(?:tests?|unit tests?|docs?|documentation)\s+for\s+(?:that|this|it)\b", re.IGNORECASE),
    re.compile(r"\b(?:more details?|more info|tell me more)\b", re.IGNORECASE),
    re.compile(r"\b(?:how|why)\s+(?:does|did)\s+(?:that|this|it)\b", re.IGNORECASE),
]


def _extract_profile_facts(question: str, existing_profile: Dict[str, str]) -> Dict[str, str]:
    """
    Extract user facts from the question using regex patterns.
    Merges with existing profile (new facts overwrite old ones).
    Returns the updated profile dict.
    """
    profile = dict(existing_profile)

    # Extract name
    for pattern in _NAME_PATTERNS:
        match = pattern.search(question)
        if match:
            name = match.group(1).strip()
            # Filter out common false positives (code keywords and verbs following "I'm")
            if name.lower() not in {
                "none", "null", "true", "false", "error", "class", "function", "import", "return",
                "working", "building", "developing", "fixing", "refactoring", "debugging",
                "looking", "trying", "getting", "having", "using", "running", "testing",
                "learning", "making", "creating", "writing", "reading", "doing", "going",
                "wondering", "thinking", "asking", "stuck", "confused", "new", "not", "also",
            }:
                profile["name"] = name.title()
                logger.info("profile_name_extracted", name=profile["name"])
                break

    # Extract tech stack
    for pattern in _STACK_PATTERNS:
        match = pattern.search(question)
        if match:
            stack = match.group(1).strip().rstrip(".,!?")
            if len(stack) > 2 and len(stack) < 200:
                profile["tech_stack"] = stack
                logger.info("profile_stack_extracted", stack=stack)
                break

    # Extract role
    for pattern in _ROLE_PATTERNS:
        match = pattern.search(question)
        if match:
            role = match.group(1).strip()
            profile["role"] = role
            logger.info("profile_role_extracted", role=role)
            break

    # Extract goal / working on
    for pattern in _GOAL_PATTERNS:
        match = pattern.search(question)
        if match:
            goal = match.group(1).strip().rstrip(".,!?")
            if len(goal) > 2 and len(goal) < 200:
                profile["current_goal"] = goal
                logger.info("profile_goal_extracted", goal=goal)
                break

    return profile


def _detect_followup(question: str) -> bool:
    """Check if the question references the previous turn."""
    for pattern in _FOLLOWUP_PATTERNS:
        if pattern.search(question):
            return True
    return False


def _resolve_followup(question: str, last_answer: str) -> str:
    """
    Prepend a truncated context snippet from the last assistant answer
    so the question becomes self-contained for downstream nodes.
    """
    # Truncate last answer to first ~300 chars for context
    truncated = last_answer[:300].strip()
    if len(last_answer) > 300:
        truncated += "..."

    resolved = (
        f"[Follow-up context from previous response: {truncated}]\n\n"
        f"User follow-up question: {question}"
    )
    return resolved


async def extract_memory(state: GraphState) -> GraphState:
    """
    Memory Extractor node: runs before the router on every turn.

    1. Extracts profile facts (name, stack, role, goal) via regex.
    2. Resolves follow-up references using the last assistant answer.

    Cost: ~0ms for regex path (no LLM call, no network).
    """
    question = state["question"]
    existing_profile = state.get("user_profile", {}) or {}
    last_answer = state.get("last_assistant_answer") or ""

    # ── 1. Profile Extraction ──
    updated_profile = _extract_profile_facts(question, existing_profile)
    profile_changed = updated_profile != existing_profile

    if profile_changed:
        logger.info(
            "profile_updated",
            old_keys=list(existing_profile.keys()),
            new_keys=list(updated_profile.keys()),
        )

    # ── 2. Follow-up Resolution ──
    resolved_question = None
    if last_answer and _detect_followup(question):
        resolved_question = _resolve_followup(question, last_answer)
        logger.info(
            "followup_resolved",
            original=question[:80],
            resolved=resolved_question[:120],
        )

    # ── Update trace ──
    trace = dict(state.get("agent_trace", {}))
    trace["memory"] = {
        "profile_changed": profile_changed,
        "profile": updated_profile,
        "followup_detected": resolved_question is not None,
    }

    result = {
        **state,
        "user_profile": updated_profile,
        "agent_trace": trace,
    }

    # Only overwrite rewritten_question if follow-up was detected
    if resolved_question:
        result["rewritten_question"] = resolved_question

    return result
