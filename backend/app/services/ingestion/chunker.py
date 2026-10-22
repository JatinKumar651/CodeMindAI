"""
CodeMind AI — Code Chunker.

Takes parsed AST units and creates properly sized chunks for embedding.
Handles:
  • Token counting and splitting oversized chunks
  • Context-aware sliding window for large files
  • Parent-child chunk relationships
"""

from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _count_tokens(text: str) -> int:
    """
    Estimate token count. Uses a simple heuristic (4 chars ≈ 1 token).
    For precise counting, install tiktoken and use it here.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Rough estimate: ~4 characters per token
        return len(text) // 4


class CodeChunker:
    """
    Takes AST-parsed semantic units and ensures they're within
    the token budget for embedding.
    
    Strategy:
      1. If a chunk is within max_tokens → keep as-is
      2. If a chunk is too large → split with sliding window, preserving context_header
      3. For files with no AST parse → use line-based sliding window
    """

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        max_chunks_per_file: Optional[int] = None,
    ):
        settings = get_settings()
        self.max_tokens = max_tokens or settings.max_chunk_tokens
        self.max_chunks_per_file = max_chunks_per_file or getattr(settings, "max_chunks_per_file", 100)

    def chunk_parsed_units(
        self,
        parsed_units: List[Dict[str, Any]],
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Take AST-parsed units and return embedding-ready chunks.
        
        Each returned chunk has:
          - chunk_type, chunk_name, content, context_header
          - start_line, end_line, language
          - token_count
          - parent_chunk_name (if split from a larger chunk)
        """
        chunks = []
        
        for unit in parsed_units:
            token_count = _count_tokens(unit["content"])
            
            if token_count <= self.max_tokens:
                # Fits within budget — keep as-is
                unit["token_count"] = token_count
                chunks.append(unit)
            else:
                # Too large — split it
                sub_chunks = self._split_chunk(unit, file_path)
                chunks.extend(sub_chunks)
        
        # Safety cap: prevent any single anomalous file from blowing up embedding costs
        if len(chunks) > self.max_chunks_per_file:
            logger.warning(
                "oversized_file_chunks_capped",
                file=file_path,
                total_generated=len(chunks),
                capped_at=self.max_chunks_per_file,
            )
            chunks = chunks[:self.max_chunks_per_file]

        logger.info(
            "chunking_complete",
            file=file_path,
            input_units=len(parsed_units),
            output_chunks=len(chunks),
        )
        
        return chunks

    def _split_chunk(
        self,
        unit: Dict[str, Any],
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Split an oversized chunk using a line-based sliding window.
        Preserves the context_header in each sub-chunk.
        """
        lines = unit["content"].splitlines(keepends=True)
        original_start = unit.get("start_line", 1)
        
        sub_chunks = []
        current_lines = []
        current_tokens = 0
        chunk_idx = 0
        
        # Reserve tokens for context header
        header = unit.get("context_header", file_path)
        header_tokens = _count_tokens(header) + 5  # +5 for separator
        effective_max = self.max_tokens - header_tokens
        
        for i, line in enumerate(lines):
            line_tokens = _count_tokens(line)
            
            if current_tokens + line_tokens > effective_max and current_lines:
                # Emit current chunk
                content = "".join(current_lines)
                sub_chunks.append({
                    "chunk_type": unit["chunk_type"],
                    "chunk_name": f"{unit.get('chunk_name', 'chunk')}_{chunk_idx}",
                    "content": f"# {header}\n\n{content}",
                    "context_header": header,
                    "start_line": original_start + (i - len(current_lines)),
                    "end_line": original_start + i - 1,
                    "language": unit["language"],
                    "imports": unit.get("imports", []) if chunk_idx == 0 else [],
                    "calls": [],  # Can't attribute calls to sub-chunks reliably
                    "parent_name": unit.get("chunk_name"),
                    "token_count": current_tokens + header_tokens,
                })
                
                # Overlap: keep last 3 lines for context continuity
                overlap = current_lines[-3:] if len(current_lines) > 3 else []
                current_lines = list(overlap)
                current_tokens = sum(_count_tokens(l) for l in current_lines)
                chunk_idx += 1
            
            current_lines.append(line)
            current_tokens += line_tokens
        
        # Emit final chunk
        if current_lines:
            content = "".join(current_lines)
            sub_chunks.append({
                "chunk_type": unit["chunk_type"],
                "chunk_name": f"{unit.get('chunk_name', 'chunk')}_{chunk_idx}",
                "content": f"# {header}\n\n{content}",
                "context_header": header,
                "start_line": original_start + (len(lines) - len(current_lines)),
                "end_line": original_start + len(lines) - 1,
                "language": unit["language"],
                "imports": [],
                "calls": unit.get("calls", []),
                "parent_name": unit.get("chunk_name"),
                "token_count": current_tokens + header_tokens,
            })
        
        return sub_chunks

    def chunk_raw_text(
        self,
        content: str,
        file_path: str,
        language: str = "text",
    ) -> List[Dict[str, Any]]:
        """
        Chunk raw text (no AST) using a sliding window approach.
        Used for README, config files, etc.
        """
        lines = content.splitlines(keepends=True)
        chunks = []
        current_lines = []
        current_tokens = 0
        chunk_idx = 0
        
        for i, line in enumerate(lines):
            line_tokens = _count_tokens(line)
            
            if current_tokens + line_tokens > self.max_tokens and current_lines:
                text = "".join(current_lines)
                chunks.append({
                    "chunk_type": "text",
                    "chunk_name": f"{file_path}_part{chunk_idx}",
                    "content": text,
                    "context_header": file_path,
                    "start_line": i - len(current_lines) + 1,
                    "end_line": i,
                    "language": language,
                    "imports": [],
                    "calls": [],
                    "parent_name": None,
                    "token_count": current_tokens,
                })
                
                overlap = current_lines[-2:] if len(current_lines) > 2 else []
                current_lines = list(overlap)
                current_tokens = sum(_count_tokens(l) for l in current_lines)
                chunk_idx += 1
            
            current_lines.append(line)
            current_tokens += line_tokens
        
        if current_lines:
            text = "".join(current_lines)
            chunks.append({
                "chunk_type": "text",
                "chunk_name": f"{file_path}_part{chunk_idx}" if chunk_idx > 0 else file_path,
                "content": text,
                "context_header": file_path,
                "start_line": len(lines) - len(current_lines) + 1,
                "end_line": len(lines),
                "language": language,
                "imports": [],
                "calls": [],
                "parent_name": None,
                "token_count": current_tokens,
            })
        
        return chunks
