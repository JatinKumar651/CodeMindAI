"""
CodeMind AI — Repository Cloner.

Clones GitHub repositories to a temporary directory for ingestion.
Includes SSRF protection and cleanup utilities.
"""

import asyncio
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.middleware.input_validator import validate_github_url

logger = get_logger(__name__)


def _remove_readonly(func, path, excinfo):
    """Clear readonly bit and reattempt deletion (Windows fix for git repos)."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _safe_rmtree(path: Path | str) -> None:
    """Robust rmtree that handles Windows file locks and git readonly permissions."""
    target = Path(path)
    if not target.exists():
        return
    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(target, onexc=_remove_readonly)
        else:
            shutil.rmtree(target, onerror=lambda f, p, e: _remove_readonly(f, p, e[1]))
    except Exception as e:
        logger.warning("safe_rmtree_error", path=str(target), error=str(e))


class RepoCloner:
    """
    Clones a GitHub repository to a temp directory.
    
    Usage:
        cloner = RepoCloner()
        repo_path = await cloner.clone("https://github.com/user/repo", branch="main")
        try:
            # process files...
        finally:
            cloner.cleanup(repo_path)
    """

    def __init__(self):
        self.settings = get_settings()

    async def clone(
        self,
        github_url: str,
        branch: str = "main",
        depth: int = 1,
    ) -> Path:
        """
        Clone a GitHub repo to a temporary directory.
        
        Args:
            github_url: validated GitHub URL
            branch: branch to clone
            depth: clone depth (1 = shallow clone, saves time/space)
        
        Returns:
            Path to the cloned repository
        """
        # Validate URL (SSRF protection)
        clean_url = validate_github_url(github_url)
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="codemind_")
        repo_path = Path(temp_dir) / "repo"
        
        logger.info(
            "cloning_repo",
            url=clean_url,
            branch=branch,
            target=str(repo_path),
        )
        
        try:
            # Build git clone command
            cmd = ["git", "clone"]
            
            # Add GitHub token for private repos
            if self.settings.github_token:
                # Inject token into URL: https://TOKEN@github.com/...
                authed_url = clean_url.replace(
                    "https://github.com",
                    f"https://{self.settings.github_token}@github.com",
                )
                cmd.append(authed_url)
            else:
                cmd.append(clean_url)
            
            cmd.extend([
                "--branch", branch,
                "--depth", str(depth),
                "--single-branch",
                str(repo_path),
            ])
            
            # Run git clone in thread pool (works reliably on all OS/event-loops including Windows SelectorEventLoop)
            def _execute_clone():
                return subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,
                    text=True,
                )

            try:
                result = await asyncio.to_thread(_execute_clone)
            except subprocess.TimeoutExpired:
                self.cleanup(Path(temp_dir))
                raise RuntimeError(f"Clone timed out after 5 minutes: {clean_url}")

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                if self.settings.github_token:
                    error_msg = error_msg.replace(self.settings.github_token, "[REDACTED_TOKEN]")
                import re
                error_msg = re.sub(r"https://[^@]+@github\.com", "https://github.com", error_msg)
                self.cleanup(Path(temp_dir))
                raise RuntimeError(f"Git clone failed: {error_msg}")
            
            # Remove .git directory (save space, not needed for analysis)
            git_dir = repo_path / ".git"
            if git_dir.exists():
                _safe_rmtree(git_dir)
            
            # Get repo size
            total_size = sum(
                f.stat().st_size for f in repo_path.rglob("*") if f.is_file()
            )
            logger.info(
                "clone_success",
                url=clean_url,
                size_mb=round(total_size / 1024 / 1024, 2),
            )
            
            return repo_path
            
        except RuntimeError:
            raise
        except Exception as e:
            self.cleanup(Path(temp_dir))
            raise RuntimeError(f"Clone failed: {str(e)}")

    def cleanup(self, path: Path) -> None:
        """Remove a temporary clone directory."""
        try:
            if path.exists():
                _safe_rmtree(path)
                logger.info("clone_cleanup", path=str(path))
        except Exception as e:
            logger.error("clone_cleanup_failed", path=str(path), error=str(e))

    def get_files(
        self,
        repo_path: Path,
        supported_extensions: Optional[set] = None,
    ) -> list:
        """
        Walk the repository and return a list of file info dicts.
        Skips binary files, hidden directories, and common non-code files.
        """
        if supported_extensions is None:
            supported_extensions = {
                ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
                ".cpp", ".c", ".h", ".hpp", ".rs", ".rb", ".php",
                ".cs", ".swift", ".kt", ".scala", ".r", ".sql",
                ".md", ".txt", ".yml", ".yaml", ".json", ".toml",
                ".cfg", ".ini", ".env.example", ".gitignore",
                ".html", ".css", ".scss", ".less",
            }
        
        # Exact filenames to skip (lockfiles, secrets, environment files, OS junk)
        skip_filenames = {
            # Package manager lockfiles (massive, machine-generated, zero semantic code value)
            "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "pnpm-lock.yml",
            "composer.lock", "cargo.lock", "poetry.lock", "pipfile.lock",
            "gemfile.lock", "flake.lock", "packages.lock.json", "bun.lockb",
            # Environment and secrets (security hazard to store or embed)
            ".env", ".env.local", ".env.development", ".env.production",
            ".env.test", ".env.staging", ".env.prod", ".secrets", ".credentials",
            # OS / Editor junk
            ".ds_store", "thumbs.db", "desktop.ini",
        }

        # Directories to skip (dependencies, build outputs, caches, IDEs)
        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
            ".next", ".nuxt", ".output", ".turbo", "dist", "build", "out",
            ".tox", ".mypy_cache", ".pytest_cache", "coverage", ".nyc_output",
            ".idea", ".vscode", "vendor", "target", "bin", "obj",
            "bower_components", ".pnpm", ".cache", ".parcel-cache",
        }
        
        files = []
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Skip hidden and dependency/build directories
            parts = file_path.relative_to(repo_path).parts
            if any(p.startswith(".") or p in skip_dirs for p in parts[:-1]):
                continue
            
            file_name = file_path.name
            lower_name = file_name.lower()
            ext = file_path.suffix.lower()

            # 1. Skip exact filenames
            if lower_name in skip_filenames:
                continue

            # 2. Skip lockfiles and package locks
            if lower_name.endswith(".lock") or lower_name.endswith("-lock.json") or lower_name.endswith(".lockb"):
                continue

            # 3. Skip minified files and bundles
            if (
                lower_name.endswith(".min.js")
                or lower_name.endswith(".min.css")
                or lower_name.endswith(".bundle.js")
                or lower_name.endswith(".chunk.js")
            ):
                continue

            # 4. Skip source maps
            if lower_name.endswith(".map") or lower_name.endswith(".js.map") or lower_name.endswith(".css.map"):
                continue

            # 5. Skip keys, certificates, and secrets
            if ext in (".pem", ".key", ".cert", ".crt", ".pfx", ".p12") or lower_name.startswith("id_rsa") or lower_name.startswith("id_ed25519"):
                continue

            # 6. Skip environment files (keep .env.example)
            if lower_name.startswith(".env.") and not lower_name.endswith(".example"):
                continue

            # Check supported extension
            if ext not in supported_extensions and lower_name not in supported_extensions:
                continue
            
            size = file_path.stat().st_size

            # Skip oversized data/config files (>150KB for JSON/YAML/data dumps, except package.json/tsconfig.json)
            if ext in (".json", ".yaml", ".yml", ".xml", ".csv", ".tsv") and size > 150_000:
                if lower_name not in ("package.json", "tsconfig.json"):
                    continue

            # Skip very large files (>500KB)
            if size > 500_000:
                continue
            
            try:
                raw_bytes = file_path.read_bytes()
                # Check for UTF-16 BOM
                if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
                    content = raw_bytes.decode("utf-16", errors="replace")
                elif raw_bytes.startswith(b"\xef\xbb\xbf"):
                    content = raw_bytes.decode("utf-8-sig", errors="replace")
                else:
                    try:
                        content = raw_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            if b"\x00" in raw_bytes[:512] and len(raw_bytes) % 2 == 0:
                                content = raw_bytes.decode("utf-16-le", errors="replace")
                            else:
                                content = raw_bytes.decode("latin-1", errors="replace")
                        except Exception:
                            content = raw_bytes.decode("utf-8", errors="replace")

                # PostgreSQL strictly forbids 0x00 in UTF-8 text/varchar (CharacterNotInRepertoireError)
                content = content.replace("\x00", "")
                loc = len(content.splitlines())

                # Skip non-code files with excessive lines (>3000 lines)
                if ext in (".json", ".yaml", ".yml", ".txt", ".md", ".csv") and loc > 3000:
                    continue
            except Exception:
                continue
            
            rel_path = str(file_path.relative_to(repo_path)).replace("\\", "/")
            
            files.append({
                "path": rel_path,
                "extension": ext,
                "language": _detect_language(ext),
                "size_bytes": size,
                "loc": loc,
                "content": content,
                "absolute_path": str(file_path),
            })
        
        return files


def _detect_language(ext: str) -> str:
    """Map file extension to language name."""
    mapping = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "javascript", ".tsx": "typescript",
        ".java": "java", ".go": "go", ".rs": "rust",
        ".cpp": "cpp", ".c": "c", ".h": "c", ".hpp": "cpp",
        ".rb": "ruby", ".php": "php", ".cs": "csharp",
        ".swift": "swift", ".kt": "kotlin", ".scala": "scala",
        ".r": "r", ".sql": "sql",
        ".md": "markdown", ".txt": "text",
        ".json": "json", ".yml": "yaml", ".yaml": "yaml",
        ".toml": "toml",
        ".html": "html", ".css": "css",
        ".scss": "scss", ".less": "less",
    }
    return mapping.get(ext, "unknown")
