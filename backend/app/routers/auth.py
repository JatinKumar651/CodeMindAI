"""
CodeMind AI — Authentication Routes.

Proxies auth operations to Supabase Auth.
The backend doesn't manage passwords or sessions directly.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, get_current_user
from app.core.logging import get_logger

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)


# ── Request/Response Models ──────────────────────────

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str


class OAuthUrlResponse(BaseModel):
    provider: str
    url: str


class CodeExchangeRequest(BaseModel):
    code: str
    code_verifier: Optional[str] = None


class GoogleIdTokenRequest(BaseModel):
    id_token: str
    nonce: Optional[str] = None


# ── Routes ───────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignUpRequest, settings: Settings = Depends(get_settings)):
    """
    Register a new user via Supabase Auth.
    Auto-confirms the email via the admin API to bypass Supabase's strict email rate limits.
    """
    from app.core.database import get_supabase_admin, get_supabase_client

    admin = get_supabase_admin()
    client = get_supabase_client()

    try:
        # Create user auto-confirmed via admin API to avoid email rate limits
        try:
            admin.auth.admin.create_user({
                "email": body.email,
                "password": body.password,
                "email_confirm": True,
            })
            logger.info("signup_auto_confirmed", email=body.email)
        except Exception as create_err:
            err_msg = str(create_err).lower()
            if "already registered" in err_msg or "already exists" in err_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A user with this email already exists. Please log in.",
                )
            logger.warning("admin_create_failed_falling_back", error=str(create_err))
            # Fallback to standard sign_up
            client.auth.sign_up({
                "email": body.email,
                "password": body.password,
            })

        # Immediately sign in to generate access_token
        login_res = client.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })

        if not login_res.session:
            raise HTTPException(
                status_code=status.HTTP_200_OK,
                detail="User created. Please log in.",
            )

        logger.info("signup_success", user_id=login_res.user.id)

        return TokenResponse(
            access_token=login_res.session.access_token,
            refresh_token=login_res.session.refresh_token,
            expires_in=login_res.session.expires_in,
            user_id=str(login_res.user.id),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("signup_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signup failed: {str(e)}",
        )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, settings: Settings = Depends(get_settings)):
    """Log in with email/password via Supabase Auth."""
    from supabase import create_client
    
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        response = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
        
        logger.info("login_success", user_id=response.user.id)
        
        return TokenResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            expires_in=response.session.expires_in,
            user_id=str(response.user.id),
        )
    except Exception as e:
        logger.warning("login_failed", email=body.email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, settings: Settings = Depends(get_settings)):
    """Refresh an expired access token."""
    from supabase import create_client
    
    try:
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        response = supabase.auth.refresh_session(body.refresh_token)
        
        return TokenResponse(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
            expires_in=response.session.expires_in,
            user_id=str(response.user.id),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: AuthenticatedUser = Depends(get_current_user)):
    """Get the currently authenticated user's info."""
    return UserResponse(
        id=str(user.id),
        email=user.email or "",
        role=user.role,
    )


# ── Google OAuth Routes ──────────────────────────────

import secrets
import time
import urllib.parse
import tempfile
from pathlib import Path

# Resilient multi-tier PKCE verifier storage:
# Memory + persistent disk file + cookie fallback guarantees that code_verifier is preserved
# even if uvicorn reloads or cross-port/browser isolation limits cookie transmission.
_latest_verifier: list = [None, 0.0]
_PKCE_FILE = Path(tempfile.gettempdir()) / "cmai_pkce_verifier.txt"


def _save_pkce_to_disk(verifier: str) -> None:
    try:
        _PKCE_FILE.write_text(f"{verifier}\n{time.time()}", encoding="utf-8")
    except Exception as e:
        logger.warning("pkce_disk_save_warning", error=str(e))


def _load_pkce_from_disk() -> Optional[str]:
    try:
        if _PKCE_FILE.exists():
            content = _PKCE_FILE.read_text(encoding="utf-8").strip().splitlines()
            if len(content) >= 2:
                verifier, ts = content[0], float(content[1])
                if time.time() - ts < 300:  # 5 minute validity window
                    return verifier
            elif len(content) == 1:
                return content[0]
    except Exception as e:
        logger.warning("pkce_disk_load_warning", error=str(e))
    return None


@router.get("/google", response_model=OAuthUrlResponse)
async def google_login(
    request: Request,
    response: Response,
    redirect_to: Optional[str] = None,
    auto_redirect: bool = False,
    settings: Settings = Depends(get_settings),
):
    """
    Initiate 'Continue with Google' OAuth sign-in with PKCE flow.
    Uses Supabase's native state protection (never override 'state' query param)
    and caches code_verifier in memory + disk for instant callback exchange.
    """
    from supabase import create_client

    # Base callback URL - defaults to http://localhost:8000/auth/callback to match Supabase redirect whitelist
    target_redirect = redirect_to or "http://localhost:8000/auth/callback"

    try:
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": target_redirect,
            },
        })

        oauth_url = res.url
        storage_key = f"{supabase.auth._storage_key}-code-verifier"
        code_verifier = supabase.auth._storage.get_item(storage_key)

        now = time.time()
        if code_verifier:
            # 1. Memory cache (instant lookup)
            _latest_verifier[0] = code_verifier
            _latest_verifier[1] = now
            # 2. Disk persistence (survives uvicorn reloads)
            _save_pkce_to_disk(code_verifier)

        if auto_redirect:
            redirect_resp = RedirectResponse(url=oauth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
            if code_verifier:
                redirect_resp.set_cookie(
                    key="sb_code_verifier",
                    value=code_verifier,
                    httponly=True,
                    samesite="lax",
                    path="/",
                    max_age=300,
                )
            return redirect_resp

        # 3. HTTP Cookie as secondary fallback
        if code_verifier:
            response.set_cookie(
                key="sb_code_verifier",
                value=code_verifier,
                httponly=True,
                samesite="lax",
                path="/",
                max_age=300,
            )

        return OAuthUrlResponse(provider="google", url=oauth_url)

    except Exception as e:
        logger.error("google_oauth_init_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to initiate Google OAuth: {str(e)}",
        )


@router.get("/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    settings: Settings = Depends(get_settings),
):
    """
    OAuth callback endpoint for Supabase Auth redirect.
    Exchanges the PKCE authorization code and verifier for a Supabase session token.
    Gracefully redirects to frontend SPA on both success and errors.
    """
    # Determine frontend target URL for seamless SPA login redirect (Vite server on 5173)
    frontend_url = "http://localhost:5173"
    for origin in settings.cors_origins:
        if "5173" in origin:
            frontend_url = origin
            break

    if error:
        logger.warning("oauth_callback_error", error=error, description=error_description)
        err_msg = urllib.parse.quote(error_description or f"OAuth error: {error}")
        return RedirectResponse(
            url=f"{frontend_url}/auth?error={err_msg}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not code:
        err_msg = urllib.parse.quote("Authorization code is missing from callback URL.")
        return RedirectResponse(
            url=f"{frontend_url}/auth?error={err_msg}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    from supabase import create_client

    try:
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        
        # 1. Primary: Memory cache lookup
        now = time.time()
        code_verifier = None
        if _latest_verifier[0] and (now - _latest_verifier[1] < 300):
            code_verifier = _latest_verifier[0]
            logger.info("verifier_matched_via_memory")

        # 2. Secondary: Disk persistence lookup (in case server reloaded during flow)
        if not code_verifier:
            code_verifier = _load_pkce_from_disk()
            if code_verifier:
                logger.info("verifier_matched_via_disk")

        # 3. Tertiary: Browser cookie fallback
        if not code_verifier:
            code_verifier = request.cookies.get("sb_code_verifier")
            if code_verifier:
                logger.info("verifier_matched_via_cookie")

        if not code_verifier:
            logger.error("missing_code_verifier", cookies=list(request.cookies.keys()))
            err_msg = urllib.parse.quote("Authentication PKCE code verifier is missing. Please initiate Google sign-in again.")
            return RedirectResponse(
                url=f"{frontend_url}/auth?error={err_msg}",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        auth_res = supabase.auth.exchange_code_for_session({
            "auth_code": code,
            "code_verifier": code_verifier,
        })

        if not auth_res.session:
            err_msg = urllib.parse.quote("Could not establish session from authorization code.")
            return RedirectResponse(
                url=f"{frontend_url}/auth?error={err_msg}",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        # Clear cookie and cached state
        response.delete_cookie("sb_code_verifier", path="/")
        _latest_verifier[0] = None
        try:
            if _PKCE_FILE.exists():
                _PKCE_FILE.unlink()
        except Exception:
            pass

        logger.info("google_oauth_success", user_id=auth_res.user.id, email=auth_res.user.email)

        # Browser redirection to SPA /oauth/callback with tokens
        redirect_url = (
            f"{frontend_url}/oauth/callback"
            f"?access_token={auth_res.session.access_token}"
            f"&refresh_token={auth_res.session.refresh_token}"
            f"&user_id={auth_res.user.id}"
        )
        redirect_resp = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
        redirect_resp.delete_cookie("sb_code_verifier", path="/")
        return redirect_resp

    except Exception as e:
        logger.error("code_exchange_failed", error=str(e))
        err_msg = urllib.parse.quote(f"Authentication failed: {str(e)}")
        return RedirectResponse(
            url=f"{frontend_url}/auth?error={err_msg}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.post("/exchange-code", response_model=TokenResponse)
async def exchange_code(
    body: CodeExchangeRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
):
    """
    Explicitly exchange a PKCE authorization code for session tokens.
    Useful for SPA / frontend clients that receive the code and submit it via API.
    """
    from supabase import create_client

    try:
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        verifier = body.code_verifier or request.cookies.get("sb_code_verifier") or ""

        auth_res = supabase.auth.exchange_code_for_session({
            "auth_code": body.code,
            "code_verifier": verifier,
        })

        if not auth_res.session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not establish session from authorization code.",
            )

        response.delete_cookie("sb_code_verifier")
        logger.info("code_exchange_success", user_id=auth_res.user.id)

        return TokenResponse(
            access_token=auth_res.session.access_token,
            refresh_token=auth_res.session.refresh_token,
            expires_in=auth_res.session.expires_in,
            user_id=str(auth_res.user.id),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("code_exchange_post_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Code exchange failed: {str(e)}",
        )


@router.post("/google/id-token", response_model=TokenResponse)
async def google_id_token_login(
    body: GoogleIdTokenRequest,
    settings: Settings = Depends(get_settings),
):
    """
    Authenticate using a Google ID token directly (Google One-Tap / client-side OAuth).
    Validates token with Supabase Auth and returns active session credentials.
    """
    from supabase import create_client

    try:
        supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
        auth_res = supabase.auth.sign_in_with_id_token({
            "provider": "google",
            "token": body.id_token,
            "nonce": body.nonce,
        })

        if not auth_res.session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google ID token validation failed to create session.",
            )

        logger.info("google_id_token_success", user_id=auth_res.user.id, email=auth_res.user.email)

        return TokenResponse(
            access_token=auth_res.session.access_token,
            refresh_token=auth_res.session.refresh_token,
            expires_in=auth_res.session.expires_in,
            user_id=str(auth_res.user.id),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("google_id_token_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google ID token authentication failed: {str(e)}",
        )
