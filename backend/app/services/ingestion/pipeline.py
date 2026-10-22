"""
CodeMind AI — Ingestion Pipeline Orchestrator.

Orchestrates the full ingestion flow:
  clone → parse → chunk → embed → store → update repo status

Idempotent: can re-run without duplicating data (uses SHA256 checksums).
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.orm import CodeChunk, Dependency, Embedding, File, Repository
from app.services.ingestion.chunker import CodeChunker
from app.services.ingestion.cloner import RepoCloner
from app.services.ingestion.embedder import EmbeddingGenerator
from app.services.ingestion.parser import ASTParser

logger = get_logger(__name__)


class IngestionPipeline:
    """
    Full ingestion pipeline: clone → parse → chunk → embed → store.
    
    Usage:
        async with async_session_factory() as db:
            pipeline = IngestionPipeline(db)
            await pipeline.run(repo_id="...", user_id="...", github_url="...", branch="main")
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.cloner = RepoCloner()
        self.parser = ASTParser()
        self.chunker = CodeChunker()
        self.embedder = EmbeddingGenerator()

    async def run(
        self,
        repo_id: str,
        user_id: str,
        github_url: str,
        branch: str = "main",
    ) -> dict:
        """
        Execute the full ingestion pipeline.
        
        Returns a summary dict with counts.
        """
        repo_uuid = UUID(repo_id) if isinstance(repo_id, str) else repo_id
        
        logger.info(
            "ingestion_started",
            repo_id=str(repo_uuid),
            url=github_url,
        )
        
        # Update status to processing
        await self.db.execute(
            update(Repository)
            .where(Repository.id == repo_uuid)
            .values(status="processing", error_message=None)
        )
        await self.db.commit()
        
        repo_path = None
        
        try:
            # ── Step 1: Clone ──────────────────────
            repo_path = await self.cloner.clone(github_url, branch)
            raw_files = self.cloner.get_files(repo_path)
            
            logger.info("ingestion_cloned", repo_id=repo_id, file_count=len(raw_files))
            
            # ── Step 2: Clear old data (for re-ingestion) ──
            await self._clear_repo_data(UUID(repo_id))
            
            # ── Step 3: Process each file ──────────
            total_files = 0
            total_chunks = 0
            all_chunks_with_embeddings = []
            # Track file records and per-file imports for dependency resolution
            file_records = {}  # path -> File ORM object
            file_imports = {}  # source_file_id -> [import_strings]
            
            for file_info in raw_files:
                # Create file record
                sha256 = hashlib.sha256(file_info["content"].encode()).hexdigest()
                
                file_record = File(
                    repository_id=UUID(repo_id),
                    path=file_info["path"],
                    extension=file_info["extension"],
                    language=file_info["language"],
                    size_bytes=file_info["size_bytes"],
                    loc=file_info["loc"],
                    sha256=sha256,
                )
                self.db.add(file_record)
                await self.db.flush()  # Get file ID
                
                total_files += 1
                file_records[file_info["path"]] = file_record
                
                # Parse AST
                parsed_units = self.parser.parse_file(
                    content=file_info["content"],
                    language=file_info["language"],
                    file_path=file_info["path"],
                )
                
                # Chunk
                chunks = self.chunker.chunk_parsed_units(parsed_units, file_info["path"])
                
                # Create chunk records
                for chunk_data in chunks:
                    clean_content = (chunk_data.get("content") or "").replace("\x00", "")
                    clean_name = (chunk_data.get("chunk_name") or "").replace("\x00", "") or None
                    clean_header = (chunk_data.get("context_header") or "").replace("\x00", "") or None
                    clean_lang = (chunk_data.get("language") or "").replace("\x00", "") or None
                    clean_imports = [imp.replace("\x00", "") for imp in chunk_data.get("imports", []) if isinstance(imp, str)]
                    clean_calls = [c.replace("\x00", "") for c in chunk_data.get("calls", []) if isinstance(c, str)]

                    chunk_record = CodeChunk(
                        file_id=file_record.id,
                        repository_id=UUID(repo_id),
                        chunk_type=str(chunk_data.get("chunk_type", "code")).replace("\x00", ""),
                        chunk_name=clean_name,
                        start_line=chunk_data.get("start_line"),
                        end_line=chunk_data.get("end_line"),
                        content=clean_content,
                        context_header=clean_header,
                        language=clean_lang,
                        imports=clean_imports,
                        calls=clean_calls,
                        token_count=chunk_data.get("token_count"),
                    )
                    self.db.add(chunk_record)
                    await self.db.flush()
                    
                    # Store for batch embedding
                    all_chunks_with_embeddings.append({
                        "chunk_id": chunk_record.id,
                        "content": clean_content,
                        "context_header": clean_header or "",
                    })
                    total_chunks += 1
                    
                    # Collect imports for dependency resolution
                    if clean_imports:
                        fid = file_record.id
                        if fid not in file_imports:
                            file_imports[fid] = {"path": file_info["path"], "imports": []}
                        file_imports[fid]["imports"].extend(clean_imports)
            
            # ── Step 4: Generate embeddings in batches ──
            logger.info(
                "ingestion_embedding",
                repo_id=repo_id,
                chunk_count=len(all_chunks_with_embeddings),
            )
            
            embedded_chunks = await self.embedder.embed_chunks(all_chunks_with_embeddings)
            
            # Store embeddings
            for chunk_data in embedded_chunks:
                embedding_record = Embedding(
                    chunk_id=chunk_data["chunk_id"],
                    repository_id=UUID(repo_id),
                    model_name=self.settings.embedding_model_name,
                    model_version="v1",
                    embedding=chunk_data["embedding"],
                )
                self.db.add(embedding_record)
            
            # ── Step 5: Resolve file-to-file dependencies ──
            await self._resolve_dependencies(
                repo_id=UUID(repo_id),
                file_records=file_records,
                file_imports=file_imports,
            )
            
            # ── Step 6: Update repo status ─────────
            await self.db.execute(
                update(Repository)
                .where(Repository.id == repo_uuid)
                .values(
                    status="ready",
                    total_files=total_files,
                    total_chunks=total_chunks,
                    ingested_at=datetime.now(timezone.utc),
                    error_message=None,
                )
            )
            
            await self.db.commit()
            
            summary = {
                "repo_id": str(repo_uuid),
                "total_files": total_files,
                "total_chunks": total_chunks,
                "status": "ready",
            }
            
            logger.info("ingestion_complete", **summary)
            return summary
            
        except Exception as e:
            logger.exception(
                "ingestion_failed",
                repo_id=str(repo_uuid),
                error=str(e),
            )
            
            # Rollback aborted transaction to avoid: "This Session's transaction has been rolled back due to a previous exception during flush"
            try:
                await self.db.rollback()
            except Exception:
                pass

            # Update repo status to failed
            try:
                clean_err = (str(e) or repr(e))[:1000].replace("\x00", "")
                await self.db.execute(
                    update(Repository)
                    .where(Repository.id == repo_uuid)
                    .values(
                        status="failed",
                        error_message=clean_err,
                    )
                )
                await self.db.commit()
            except Exception as update_err:
                logger.error("failed_to_update_repo_failed_status", error=str(update_err))
            raise
            
        finally:
            # Cleanup cloned repo
            if repo_path:
                self.cloner.cleanup(repo_path)

    async def _clear_repo_data(self, repo_id: UUID) -> None:
        """
        Clear existing data for a repo before re-ingestion.
        Cascading deletes handle embeddings and chunks via FK constraints.
        """
        # Delete dependencies first (FK references files)
        await self.db.execute(
            delete(Dependency).where(Dependency.repository_id == repo_id)
        )
        # Delete files (cascades to chunks → embeddings)
        await self.db.execute(
            delete(File).where(File.repository_id == repo_id)
        )
        await self.db.flush()
        
        logger.info("ingestion_cleared_old_data", repo_id=str(repo_id))

    async def _resolve_dependencies(
        self,
        repo_id: UUID,
        file_records: dict,
        file_imports: dict,
    ) -> None:
        """
        Resolve import strings to file-to-file dependency edges.
        
        Strategy:
          1. Build a lookup from normalized path suffixes to File IDs
          2. For each file's import statements, try to match to a known file
          3. Insert Dependency rows for matches (import type)
        """
        import re as _re  # noqa: F811
        
        if not file_imports:
            logger.info("dependency_resolution_skipped", reason="no imports found")
            return
        
        # Build path lookup: normalized paths → file_id
        path_to_id = {}
        for path, file_record in file_records.items():
            normalized = path.replace("\\", "/").lstrip("/")
            path_to_id[normalized] = file_record.id
            
            # Store without extension for module-style imports
            for ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp"):
                if normalized.endswith(ext):
                    path_to_id[normalized[:-len(ext)]] = file_record.id
                    break
            
            # Store dot-notation for Python-style imports
            dot_path = normalized.replace("/", ".")
            for ext in (".py", ".js", ".ts"):
                if dot_path.endswith(ext):
                    dot_path = dot_path[:-len(ext)]
                    break
            path_to_id[dot_path] = file_record.id
        
        # Resolve imports to dependency edges
        deps_added = 0
        seen_edges = set()
        
        for source_file_id, data in file_imports.items():
            source_path = data["path"] if isinstance(data, dict) else ""
            import_strings = data["imports"] if isinstance(data, dict) else data
            for imp_str in import_strings:
                target_id = self._match_import_to_file(imp_str, source_path, path_to_id)
                
                if target_id and target_id != source_file_id:
                    edge = (str(source_file_id), str(target_id), "import")
                    if edge not in seen_edges:
                        seen_edges.add(edge)
                        dep = Dependency(
                            repository_id=repo_id,
                            source_file_id=source_file_id,
                            target_file_id=target_id,
                            dependency_type="import",
                        )
                        self.db.add(dep)
                        deps_added += 1
        
        if deps_added > 0:
            await self.db.flush()
        
        total_imp_count = sum(len(v["imports"]) if isinstance(v, dict) else len(v) for v in file_imports.values())
        logger.info(
            "dependency_resolution_complete",
            repo_id=str(repo_id),
            total_import_strings=total_imp_count,
            dependencies_resolved=deps_added,
        )

    @staticmethod
    def _match_import_to_file(import_str: str, source_path: str, path_to_id: dict):
        """
        Try to resolve an import string to a file ID.
        
        Handles various import formats:
          - JS/TS CommonJS: const { x } = require('./utils/helper')
          - JS/TS ESM:      import { x } from './utils/helper'
          - Python relative: from .schemas import User
          - Python absolute: from routers.astro_router import router
          - Python standard: import config
          - C/C++:          #include "utils/helper.h"
          - Rust:           use crate::services::auth;
        """
        import posixpath
        import re
        
        cleaned = import_str.strip()
        source_dir = posixpath.dirname(source_path.replace("\\", "/")) if source_path else ""

        # 1. JS/TS: require('...') or require("...")
        m_req = re.search(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", cleaned)
        if m_req:
            target = m_req.group(1)
            return IngestionPipeline._resolve_path_candidates(target, source_dir, path_to_id, is_file_path=True)

        # 2. JS/TS: import ... from '...' or import '...'
        m_esm = re.search(r"""(?:from\s+|import\s+)['"]([^'"]+)['"]""", cleaned)
        if m_esm:
            target = m_esm.group(1)
            return IngestionPipeline._resolve_path_candidates(target, source_dir, path_to_id, is_file_path=True)

        # 3. Python: from .something import ... (relative imports)
        m_py_rel = re.match(r"from\s+(\.+)([\w.]*)\s+import", cleaned)
        if m_py_rel:
            dots = len(m_py_rel.group(1))
            module = m_py_rel.group(2)
            curr_dir = source_dir
            for _ in range(dots - 1):
                curr_dir = posixpath.dirname(curr_dir)
            target = posixpath.join(curr_dir, module.replace(".", "/")) if module else curr_dir
            return IngestionPipeline._resolve_path_candidates(target, "", path_to_id, is_file_path=False)

        # 4. Python: from X import Y
        m_py_from = re.match(r"from\s+([\w.]+)\s+import", cleaned)
        if m_py_from:
            module = m_py_from.group(1)
            return IngestionPipeline._resolve_python_module(module, source_dir, path_to_id)

        # 5. Python: import X
        m_py_imp = re.match(r"import\s+([\w.]+)", cleaned)
        if m_py_imp and not cleaned.startswith("import {"):
            module = m_py_imp.group(1)
            return IngestionPipeline._resolve_python_module(module, source_dir, path_to_id)

        # 6. C/C++: #include "path/to/file.h"
        m_inc = re.match(r'#include\s+"([^"]+)"', cleaned)
        if m_inc:
            target = m_inc.group(1)
            return IngestionPipeline._resolve_path_candidates(target, source_dir, path_to_id, is_file_path=True)

        # 7. Rust: use crate::module::submodule;
        m_rust = re.match(r"use\s+crate::(.+?)(?:::\{.*\})?;", cleaned)
        if m_rust:
            rust_path = m_rust.group(1).replace("::", "/")
            return IngestionPipeline._resolve_path_candidates(rust_path, "", path_to_id, is_file_path=False)

        return None

    @staticmethod
    def _resolve_path_candidates(target: str, source_dir: str, path_to_id: dict, is_file_path: bool):
        """Resolve a relative or root file path against known file IDs."""
        import posixpath
        candidates = []
        if target.startswith("./") or target.startswith("../") or (is_file_path and source_dir):
            if target.startswith("./") or target.startswith("../"):
                norm = posixpath.normpath(posixpath.join(source_dir, target))
            else:
                norm = posixpath.normpath(posixpath.join(source_dir, target))
            candidates.append(norm)
        else:
            norm = target.lstrip("/")
            candidates.append(norm)
            if source_dir:
                candidates.append(posixpath.normpath(posixpath.join(source_dir, target)))

        extensions = ("", ".js", ".jsx", ".ts", ".tsx", ".py", "/index.js", "/index.ts", "/index.jsx", "/index.tsx")
        for c in candidates:
            for ext in extensions:
                cand = c + ext
                if cand in path_to_id:
                    return path_to_id[cand]
        for c in candidates:
            for known_path, fid in path_to_id.items():
                if known_path == c or known_path.endswith("/" + c):
                    return fid
        return None

    @staticmethod
    def _resolve_python_module(module: str, source_dir: str, path_to_id: dict):
        """Resolve a Python module path (dot-separated) against known file IDs."""
        import posixpath
        slash_path = module.replace(".", "/")
        candidates = [slash_path]
        if source_dir:
            candidates.append(posixpath.normpath(posixpath.join(source_dir, slash_path)))
        
        for c in candidates:
            for ext in ("", ".py", "/__init__.py"):
                cand = c + ext
                if cand in path_to_id:
                    return path_to_id[cand]
        for c in candidates:
            for known_path, fid in path_to_id.items():
                if known_path == c or known_path.endswith("/" + c) or known_path.endswith("/" + c + ".py"):
                    return fid
        return None

