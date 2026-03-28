import secrets
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from .config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_DELTA, REFRESH_TOKEN_EXPIRE_DELTA

# Prefer PBKDF2 to avoid bcrypt backend issues and bcrypt's 72-byte password limit.
# Keep bcrypt in the context so existing hashes (if any) remain verifiable.
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# JWT Token Management (Task 1.3)
# ============================================================================


def create_access_token(user_id: str, email: str = "", expires_delta: timedelta = None) -> str:
    """
    Create JWT access token with 15-minute expiry.
    
    Args:
        user_id: Unique user identifier
        email: User email (optional, for audit)
        expires_delta: Custom expiry (default: 15 minutes from config)
    
    Returns:
        JWT token string
    """
    if expires_delta is None:
        expires_delta = ACCESS_TOKEN_EXPIRE_DELTA
    
    exp = utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": exp,
        "iat": utcnow()
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, expires_delta: timedelta = None) -> str:
    """
    Create JWT refresh token with rotation capability.
    
    Contains JWT ID (jti) for tracking and verification.
    Encodes user_id + jti to enable refresh token validation against DB.
    
    Args:
        user_id: Unique user identifier
        expires_delta: Custom expiry (default: 30 days from config)
    
    Returns:
        JWT token string
    """
    if expires_delta is None:
        expires_delta = REFRESH_TOKEN_EXPIRE_DELTA
    
    exp = utcnow() + expires_delta
    jti = str(uuid.uuid4())  # Unique token ID for rotation tracking
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": exp,
        "iat": utcnow(),
        "jti": jti
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """
    Decode and validate JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Token payload dict if valid, None if invalid/expired
    """
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# ============================================================================
# CSRF Protection (Task 1.3)
# ============================================================================


def generate_csrf_token() -> str:
    """
    Generate cryptographically secure CSRF token.
    
    Returns:
        Base64-encoded 32-byte random token
    """
    return secrets.token_urlsafe(32)


def verify_csrf_token(token_from_header: str, token_from_session: str) -> bool:
    """
    Verify CSRF token from request header matches session token.
    
    Args:
        token_from_header: CSRF token from X-CSRF-Token header
        token_from_session: CSRF token stored in session/cookie
    
    Returns:
        True if tokens match (constant-time comparison to prevent timing attacks)
    """
    if not token_from_header or not token_from_session:
        return False
    
    # Use secrets.compare_digest to prevent timing attacks
    return secrets.compare_digest(token_from_header, token_from_session)


# ============================================================================
# Session Recovery (Task 1.3 & Wave 2)
# ============================================================================


def create_session_id() -> str:
    """
    Create unique session identifier for quiz resumption.
    
    Returns:
        Base64-encoded UUID (browser-safe format)
    """
    return secrets.token_urlsafe(16)


# ============================================================================
# Password Management
# ============================================================================


def generate_magic_token() -> str:
    return secrets.token_urlsafe(32)


def hash_value(value: str) -> str:
    return pwd_context.hash(value, scheme="pbkdf2_sha256")


def verify_hash(value: str, hashed: str) -> bool:
    return pwd_context.verify(value, hashed)
