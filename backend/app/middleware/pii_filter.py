"""
CodeMind AI — PII Detection & Redaction Middleware.

Uses Microsoft Presidio to detect and redact Personally Identifiable Information.
Applied in TWO places:
  1. INPUT: Before user message reaches the LLM (prevents sending PII to Groq)
  2. OUTPUT: Before LLM response reaches the user (catches leaked PII from training data)

Detects: emails, phone numbers, credit cards, SSNs, IP addresses, API keys, passwords.
Modes:
  • REDACT: replaces PII with <PII_TYPE> tokens (default)
  • BLOCK: rejects the entire request if PII is found
"""

import re
from typing import List, Optional, Tuple

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PIIDetection(BaseModel):
    """A single PII detection result."""
    entity_type: str        # e.g. "EMAIL_ADDRESS", "API_KEY"
    text: str               # the matched text
    start: int
    end: int
    score: float


class PIIFilterResult(BaseModel):
    """Result of PII filtering."""
    original_text: str
    filtered_text: str
    pii_detected: bool
    detections: List[PIIDetection] = []
    detection_count: int = 0


# ── Regex-based PII patterns (fast, no ML model needed) ──

_PII_PATTERNS = {
    "EMAIL_ADDRESS": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    ),
    "PHONE_NUMBER": re.compile(
        r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    ),
    "CREDIT_CARD": re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
    ),
    "SSN": re.compile(
        r"\b\d{3}-\d{2}-\d{4}\b"
    ),
    "API_KEY": re.compile(
        # Common API key patterns: sk-..., ghp_..., xoxb-..., etc.
        r"\b(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xox[bpas]-[A-Za-z0-9-]{10,}|AIza[A-Za-z0-9_-]{35}|AKIA[A-Z0-9]{16})\b"
    ),
    "PASSWORD_IN_URL": re.compile(
        r"://[^:]+:([^@]+)@"  # matches passwords in URLs like postgresql://user:PASSWORD@host
    ),
    "PRIVATE_KEY": re.compile(
        r"-----BEGIN (?:RSA |DSA |EC )?PRIVATE KEY-----"
    ),
    "AWS_SECRET": re.compile(
        r"\b(?:aws_secret_access_key|aws_secret)\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"
    ),
}

# Patterns that are OK in code context (avoid false positives)
_CODE_ALLOWLIST = {
    "IP_ADDRESS": re.compile(
        r"(?:0\.0\.0\.0|127\.0\.0\.1|localhost|255\.255\.255\.\d+)"
    ),
}


class PIIFilter:
    """
    PII detection and redaction engine.
    
    Usage:
        pii_filter = PIIFilter(mode="redact")
        result = pii_filter.scan("My email is john@example.com")
        print(result.filtered_text)  # "My email is <EMAIL_ADDRESS>"
    """

    def __init__(self, mode: str = "redact"):
        """
        Args:
            mode: 'redact' to replace PII with tokens, 'block' to flag for rejection
        """
        self.mode = mode
        self._presidio_available = False
        self._analyzer = None
        self._anonymizer = None
        self._init_presidio()

    def _init_presidio(self):
        """Try to initialize Presidio. Falls back to regex-only if not installed or model unavailable."""
        try:
            import spacy
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            from presidio_anonymizer import AnonymizerEngine

            # Check if an English model is already installed locally without triggering download
            model_name = None
            for name in ["en_core_web_sm", "en_core_web_md", "en_core_web_lg"]:
                if spacy.util.is_package(name):
                    model_name = name
                    break

            if model_name:
                configuration = {
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": model_name}],
                }
                provider = NlpEngineProvider(nlp_configuration=configuration)
                nlp_engine = provider.create_engine()
                self._analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
                self._anonymizer = AnonymizerEngine()
                self._presidio_available = True
                logger.info("pii_filter_initialized", engine="presidio", model=model_name)
            else:
                # No spaCy package installed locally; use fast built-in regex filter
                self._analyzer = None
                self._anonymizer = None
                self._presidio_available = False
                logger.info("pii_filter_initialized", engine="regex")
        except Exception as e:
            self._presidio_available = False
            logger.warning(
                "pii_filter_fallback",
                error=str(e),
                message="Using regex-only PII detection.",
            )

    def scan(self, text: str) -> PIIFilterResult:
        """
        Scan text for PII and optionally redact it.
        
        Returns a PIIFilterResult with:
          - filtered_text: the redacted text (if mode='redact')
          - pii_detected: whether any PII was found
          - detections: list of individual PII matches
        """
        detections: List[PIIDetection] = []
        
        # Phase 1: Regex-based detection (fast, always available)
        for entity_type, pattern in _PII_PATTERNS.items():
            for match in pattern.finditer(text):
                # Skip allowlisted patterns
                if entity_type in _CODE_ALLOWLIST:
                    if _CODE_ALLOWLIST[entity_type].search(match.group()):
                        continue
                
                detections.append(PIIDetection(
                    entity_type=entity_type,
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    score=0.9,
                ))
        
        # Phase 2: Presidio-based detection (if available, catches more)
        if self._presidio_available and self._analyzer:
            try:
                presidio_results = self._analyzer.analyze(
                    text=text,
                    language="en",
                    entities=[
                        "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                        "CREDIT_CARD", "IBAN_CODE", "IP_ADDRESS",
                        "US_SSN", "US_PASSPORT",
                    ],
                    score_threshold=0.7,
                )
                for result in presidio_results:
                    # Avoid duplicates with regex results
                    is_duplicate = any(
                        d.start == result.start and d.end == result.end
                        for d in detections
                    )
                    if not is_duplicate:
                        detections.append(PIIDetection(
                            entity_type=result.entity_type,
                            text=text[result.start:result.end],
                            start=result.start,
                            end=result.end,
                            score=result.score,
                        ))
            except Exception as e:
                logger.error("presidio_scan_error", error=str(e))
        
        # Sort detections by position (descending) for safe replacement
        detections.sort(key=lambda d: d.start, reverse=True)
        
        # Apply redaction
        filtered_text = text
        if self.mode == "redact" and detections:
            for det in detections:
                replacement = f"<{det.entity_type}>"
                filtered_text = (
                    filtered_text[:det.start] + replacement + filtered_text[det.end:]
                )
        
        pii_detected = len(detections) > 0
        
        if pii_detected:
            logger.warning(
                "pii_detected",
                count=len(detections),
                types=[d.entity_type for d in detections],
                mode=self.mode,
            )
        
        return PIIFilterResult(
            original_text=text,
            filtered_text=filtered_text,
            pii_detected=pii_detected,
            detections=detections,
            detection_count=len(detections),
        )

    def scan_output(self, text: str) -> PIIFilterResult:
        """
        Scan LLM output for PII leakage.
        Same as scan() but with additional logging context.
        """
        result = self.scan(text)
        if result.pii_detected:
            logger.warning(
                "pii_in_llm_output",
                count=result.detection_count,
                types=[d.entity_type for d in result.detections],
            )
        return result


# ── Module-level singleton ───────────────────────────

_pii_filter: Optional[PIIFilter] = None


def get_pii_filter() -> PIIFilter:
    """Get or create the PII filter singleton."""
    global _pii_filter
    if _pii_filter is None:
        settings = get_settings()
        _pii_filter = PIIFilter(mode=settings.pii_filter_mode)
    return _pii_filter
