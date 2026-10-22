"""
CodeMind AI — AST Parser.

Uses Tree-sitter to parse source code into ASTs and extract
semantic units (functions, classes, methods, imports).

Also builds a call graph (who calls whom) for dependency tracking.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Language → Tree-sitter mappings ──────────────────

# These will be initialized lazily on first use
_PARSERS: Dict[str, Any] = {}


def _get_parser(language: str):
    """
    Get or create a Tree-sitter parser for the given language.
    Lazily initializes to avoid import errors if tree-sitter bindings aren't installed.
    """
    if language in _PARSERS:
        return _PARSERS[language]
    
    try:
        import tree_sitter
        
        # Language bindings mapping
        lang_modules = {
            "python": "tree_sitter_python",
            "javascript": "tree_sitter_javascript",
            "typescript": "tree_sitter_typescript",
            "java": "tree_sitter_java",
            "go": "tree_sitter_go",
            "cpp": "tree_sitter_cpp",
            "c": "tree_sitter_c",
            "rust": "tree_sitter_rust",
        }
        
        if language not in lang_modules:
            return None
        
        mod = __import__(lang_modules[language])
        raw_lang = getattr(mod, "language")()
        # tree-sitter 0.22+ requires wrapping PyCapsule in tree_sitter.Language
        lang = tree_sitter.Language(raw_lang) if not isinstance(raw_lang, tree_sitter.Language) else raw_lang
        parser = tree_sitter.Parser(lang)
        
        _PARSERS[language] = (parser, language)
        return (parser, language)
    except (ImportError, AttributeError, Exception) as e:
        logger.warning("tree_sitter_unavailable", language=language, error=str(e))
        _PARSERS[language] = None
        return None


# ── Node type mappings per language ──────────────────

_FUNCTION_TYPES = {
    "python": ["function_definition", "async_function_definition"],
    "javascript": ["function_declaration", "arrow_function", "method_definition", "function_expression"],
    "typescript": ["function_declaration", "arrow_function", "method_definition", "function_expression"],
    "java": ["method_declaration", "constructor_declaration"],
    "go": ["function_declaration", "method_declaration"],
    "cpp": ["function_definition"],
    "c": ["function_definition"],
    "rust": ["function_item"],
}

_CLASS_TYPES = {
    "python": ["class_definition"],
    "javascript": ["class_declaration"],
    "typescript": ["class_declaration", "interface_declaration"],
    "java": ["class_declaration", "interface_declaration"],
    "go": ["type_declaration"],
    "cpp": ["class_specifier", "struct_specifier"],
    "c": ["struct_specifier"],
    "rust": ["struct_item", "impl_item", "trait_item"],
}

_IMPORT_TYPES = {
    "python": ["import_statement", "import_from_statement"],
    "javascript": ["import_statement"],
    "typescript": ["import_statement"],
    "java": ["import_declaration"],
    "go": ["import_declaration"],
    "cpp": ["preproc_include"],
    "c": ["preproc_include"],
    "rust": ["use_declaration"],
}


class ASTParser:
    """
    Parses source code files using Tree-sitter and extracts
    semantic units (functions, classes, methods, imports).
    """

    def parse_file(
        self,
        content: str,
        language: str,
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Parse a source file and extract semantic units.
        
        Returns a list of dicts, each representing a code chunk:
        {
            "chunk_type": "function" | "class" | "method" | "import_block" | "module",
            "chunk_name": "function_name",
            "content": "full source code of the unit",
            "context_header": "file.py :: ClassName :: method_name",
            "start_line": 10,
            "end_line": 25,
            "language": "python",
            "imports": [...],
            "calls": [...],
            "parent_name": "ClassName" | None,
        }
        """
        parser_info = _get_parser(language)
        
        if parser_info is None:
            # Fallback: return the entire file as one chunk
            return self._fallback_parse(content, language, file_path)
        
        parser, lang_name = parser_info
        
        try:
            content_bytes = content.encode("utf-8")
            tree = parser.parse(content_bytes)
            root = tree.root_node
            
            chunks = []
            
            # Extract imports
            import_chunks = self._extract_imports(root, content_bytes, language, file_path)
            chunks.extend(import_chunks)
            
            # Extract functions and classes (recursively)
            code_chunks = self._extract_definitions(
                root, content_bytes, language, file_path, parent_name=None
            )
            chunks.extend(code_chunks)
            
            # If no chunks were extracted, use the full file
            if not chunks:
                chunks = self._fallback_parse(content, language, file_path)
            
            return chunks
            
        except Exception as e:
            logger.error(
                "ast_parse_error",
                file=file_path,
                language=language,
                error=str(e),
            )
            return self._fallback_parse(content, language, file_path)

    @staticmethod
    def _slice_bytes(content_bytes: bytes, start: int, end: int) -> str:
        """Safely slice UTF-8 bytes by byte offsets and decode to str."""
        return content_bytes[start:end].decode("utf-8", errors="replace")

    def _extract_imports(
        self,
        root_node,
        content_bytes: bytes,
        language: str,
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """Extract import statements and group them into a single import block."""
        import_types = _IMPORT_TYPES.get(language, [])
        is_js_ts = language in ("javascript", "typescript")
        if not import_types and not is_js_ts:
            return []
        
        imports = []
        seen_texts = set()

        for node in self._walk_tree(root_node):
            if node.type in import_types:
                line_content = self._slice_bytes(content_bytes, node.start_byte, node.end_byte).strip()
                if line_content and line_content not in seen_texts:
                    seen_texts.add(line_content)
                    imports.append({
                        "text": line_content,
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                    })
            elif is_js_ts and node.type == "call_expression":
                # Detect CommonJS require("...") calls in JS/TS
                fn = node.child_by_field_name("function")
                if fn:
                    fn_name = self._slice_bytes(content_bytes, fn.start_byte, fn.end_byte).strip()
                    if fn_name == "require":
                        curr = node
                        while curr.parent and curr.parent.type not in ("program", "statement_block"):
                            curr = curr.parent
                        stmt_text = self._slice_bytes(content_bytes, curr.start_byte, curr.end_byte).strip()
                        if stmt_text and stmt_text not in seen_texts:
                            seen_texts.add(stmt_text)
                            imports.append({
                                "text": stmt_text,
                                "start_line": curr.start_point[0] + 1,
                                "end_line": curr.end_point[0] + 1,
                            })
        
        if not imports:
            return []
        
        # Group into a single import block
        all_import_text = "\n".join(i["text"] for i in imports)
        return [{
            "chunk_type": "import_block",
            "chunk_name": "imports",
            "content": all_import_text,
            "context_header": f"{file_path} :: imports",
            "start_line": imports[0]["start_line"],
            "end_line": imports[-1]["end_line"],
            "language": language,
            "imports": [i["text"] for i in imports],
            "calls": [],
            "parent_name": None,
        }]

    def _extract_definitions(
        self,
        node,
        content_bytes: bytes,
        language: str,
        file_path: str,
        parent_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recursively extract function and class definitions."""
        chunks = []
        func_types = _FUNCTION_TYPES.get(language, [])
        class_types = _CLASS_TYPES.get(language, [])
        
        for child in node.children:
            if child.type in class_types:
                # Extract class
                class_name = self._get_name(child, language)
                class_content = self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
                
                context_parts = [file_path]
                if parent_name:
                    context_parts.append(parent_name)
                context_parts.append(class_name or "anonymous_class")
                
                chunks.append({
                    "chunk_type": "class",
                    "chunk_name": class_name,
                    "content": class_content,
                    "context_header": " :: ".join(context_parts),
                    "start_line": child.start_point[0] + 1,
                    "end_line": child.end_point[0] + 1,
                    "language": language,
                    "imports": [],
                    "calls": self._extract_calls(child, content_bytes, language),
                    "parent_name": parent_name,
                })
                
                # Extract methods inside the class
                methods = self._extract_definitions(
                    child, content_bytes, language, file_path,
                    parent_name=class_name,
                )
                chunks.extend(methods)
                
            elif child.type in func_types:
                func_name = self._get_name(child, language)
                func_content = self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
                
                chunk_type = "method" if parent_name else "function"
                
                context_parts = [file_path]
                if parent_name:
                    context_parts.append(parent_name)
                context_parts.append(func_name or "anonymous")
                
                chunks.append({
                    "chunk_type": chunk_type,
                    "chunk_name": func_name,
                    "content": func_content,
                    "context_header": " :: ".join(context_parts),
                    "start_line": child.start_point[0] + 1,
                    "end_line": child.end_point[0] + 1,
                    "language": language,
                    "imports": [],
                    "calls": self._extract_calls(child, content_bytes, language),
                    "parent_name": parent_name,
                })
            else:
                # Recurse into other nodes (e.g., decorated definitions)
                nested = self._extract_definitions(
                    child, content_bytes, language, file_path, parent_name
                )
                chunks.extend(nested)
        
        return chunks

    def _get_name(self, node, language: str) -> Optional[str]:
        """Extract the name identifier from a definition node."""
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier", "type_identifier"):
                return child.text.decode("utf-8") if isinstance(child.text, bytes) else child.text
        return None

    def _extract_calls(self, node, content_bytes: bytes, language: str) -> List[str]:
        """Extract function call names from a node's subtree."""
        calls = set()
        for child in self._walk_tree(node):
            if child.type == "call" or child.type == "call_expression":
                # Get the function name being called
                for sub in child.children:
                    if sub.type in ("identifier", "attribute", "member_expression"):
                        call_text = self._slice_bytes(content_bytes, sub.start_byte, sub.end_byte)
                        calls.add(call_text)
                        break
        return list(calls)[:20]  # Cap at 20 to avoid huge lists

    def _walk_tree(self, node):
        """Depth-first walk of the AST."""
        yield node
        for child in node.children:
            yield from self._walk_tree(child)

    def _fallback_parse(
        self,
        content: str,
        language: str,
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Fallback parser for languages without Tree-sitter support.
        Returns the full file as a single chunk, or splits by regex patterns.
        """
        # For markdown/text files
        if language in ("markdown", "text"):
            return [{
                "chunk_type": "readme" if "readme" in file_path.lower() else "text",
                "chunk_name": Path(file_path).stem,
                "content": content,
                "context_header": file_path,
                "start_line": 1,
                "end_line": len(content.splitlines()),
                "language": language,
                "imports": [],
                "calls": [],
                "parent_name": None,
            }]
        
        # For code files: return as module chunk
        return [{
            "chunk_type": "module",
            "chunk_name": Path(file_path).stem,
            "content": content,
            "context_header": file_path,
            "start_line": 1,
            "end_line": len(content.splitlines()),
            "language": language,
            "imports": [],
            "calls": [],
            "parent_name": None,
        }]
