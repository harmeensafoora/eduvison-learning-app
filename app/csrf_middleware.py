"""
CSRF Protection Middleware for FastAPI (Task 1.3)

Purpose:
- Protect POST, PUT, DELETE endpoints from cross-site request forgery
- Generate CSRF tokens on signup/login
- Validate CSRF tokens on state-changing requests
- Skip CSRF check for GET, HEAD, OPTIONS, and auth endpoints (safe methods)

Implementation:
- CSRF token stored in response header (X-CSRF-Token)
- Client sends token in request header (X-CSRF-Token)
- Middleware validates token before routing to endpoint
"""

import logging
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from .auth_utils import generate_csrf_token, verify_csrf_token

logger = logging.getLogger(__name__)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware to protect against CSRF attacks on state-changing methods."""
    
    # HTTP methods that should trigger CSRF protection
    PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
    
    # Routes that skip CSRF protection (safe or explicitly excluded)
    # Typically: auth endpoints, health checks, publicly accessible routes
    SKIP_CSRF_PATHS = {
        "/auth/signup",
        "/auth/login",
        "/auth/logout",
        "/auth/refresh",
        "/auth/verify-email",
        "/auth/request-password-reset",
        "/auth/reset-password",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request through CSRF protection middleware.
        
        For protected methods: validate CSRF token from X-CSRF-Token header
        For safe methods: pass through (GET, HEAD, OPTIONS, etc.)
        """
        
        # Safe HTTP methods — skip CSRF check
        if request.method not in self.PROTECTED_METHODS:
            response = await call_next(request)
            return response
        
        # Skip CSRF for specific paths (auth endpoints, health checks)
        if request.url.path in self.SKIP_CSRF_PATHS or any(
            request.url.path.startswith(p) for p in ["/static", "/files"]
        ):
            response = await call_next(request)
            return response
        
        # Validate CSRF token for protected methods
        csrf_token_header = request.headers.get("X-CSRF-Token", "")
        session_cookie = request.cookies.get("eduvision_csrf", "")
        
        if not csrf_token_header or not session_cookie:
            logger.warning(f"CSRF token missing: {request.method} {request.url.path}")
            raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
        
        if not verify_csrf_token(csrf_token_header, session_cookie):
            logger.warning(f"CSRF token mismatch: {request.method} {request.url.path}")
            raise HTTPException(status_code=403, detail="CSRF token invalid")
        
        logger.debug(f"✓ CSRF validated: {request.method} {request.url.path}")
        response = await call_next(request)
        return response
