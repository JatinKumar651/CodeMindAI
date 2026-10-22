"""
CodeMind AI — Input Validation Utilities.

Provides validation functions used across routes:
  • GitHub URL validation with SSRF protection
  • File upload validation (size, content-type)
  • Generic input sanitization
"""

import ipaddress
import re
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def validate_github_url(url: str) -> str:
    """
    Validate that a URL is a legitimate GitHub repository URL.
    Blocks SSRF attempts (internal IPs, non-GitHub domains).
    
    Returns the cleaned URL.
    Raises HTTPException 400 if invalid.
    """
    url = url.strip()
    
    # Must be HTTPS GitHub URL
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only HTTPS URLs are accepted",
        )
    
    if parsed.hostname not in ("github.com", "www.github.com"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only github.com URLs are accepted",
        )
    
    # Must have at least owner/repo in path
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub URL: expected https://github.com/owner/repo",
        )
    
    # Block common SSRF bypass patterns
    _check_ssrf(parsed.hostname)
    
    # Strip .git suffix and trailing slashes
    clean_url = f"https://github.com/{path_parts[0]}/{path_parts[1]}"
    if clean_url.endswith(".git"):
        clean_url = clean_url[:-4]
    
    return clean_url


def _check_ssrf(hostname: str) -> None:
    """
    Check if a hostname resolves to a private/internal IP.
    Prevents SSRF attacks via DNS rebinding or direct IP usage.
    """
    import socket
    
    # Block direct IP usage
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Internal/private IP addresses are not allowed",
            )
    except ValueError:
        pass  # It's a hostname, not an IP — that's fine
    
    # Block known internal hostnames
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "metadata.google.internal"}
    if hostname.lower() in blocked_hosts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Internal hostnames are not allowed",
        )
    
    # Resolve hostname and check if it points to a private IP
    try:
        resolved_ips = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in resolved_ips:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                logger.warning(
                    "ssrf_blocked",
                    hostname=hostname,
                    resolved_ip=str(ip),
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="URL resolves to a private/internal IP address",
                )
    except socket.gaierror:
        pass  # DNS resolution failed — will fail later during clone


async def validate_upload(file: UploadFile) -> None:
    """
    Validate an uploaded file (e.g., ZIP of a repository).
    Checks: size, content-type, filename.
    """
    settings = get_settings()
    max_size = settings.max_upload_size_mb * 1024 * 1024  # Convert to bytes
    
    # Check content type
    allowed_types = {
        "application/zip",
        "application/x-zip-compressed",
        "application/x-tar",
        "application/gzip",
        "application/x-gzip",
    }
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Accepted: ZIP, TAR, GZ",
        )
    
    # Check filename
    if file.filename:
        # Block path traversal
        if ".." in file.filename or "/" in file.filename or "\\" in file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename: path traversal detected",
            )
    
    # Check size (read content to measure)
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large: {len(content) / 1024 / 1024:.1f}MB exceeds {settings.max_upload_size_mb}MB limit",
        )
    
    # Reset file pointer for downstream consumers
    await file.seek(0)


def sanitize_query_param(value: str, max_length: int = 500) -> str:
    """
    Sanitize a query parameter to prevent injection attacks.
    """
    # Truncate
    value = value[:max_length]
    
    # Remove null bytes
    value = value.replace("\x00", "")
    
    # Strip control characters
    value = "".join(c for c in value if c in ("\n", "\t") or ord(c) >= 32)
    
    # Basic SQL injection patterns (defense in depth — parameterized queries are primary defense)
    sql_patterns = re.compile(
        r"(--|;|\b(union|select|insert|update|delete|drop|alter|create|exec)\b)",
        re.I,
    )
    if sql_patterns.search(value):
        logger.warning("sql_injection_pattern_detected", value=value[:50])
        # Don't block — just log. Parameterized queries handle the actual protection.
    
    return value.strip()
