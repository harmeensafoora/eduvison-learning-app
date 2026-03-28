import secrets
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from .config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_DELTA, REFRESH_TOKEN_EXPIRE_DELTA

# Prefer PBKDF2 to avoid bcrypt backend issues and bcrypt's 72-byte password limit.
# Keep bcrypt in the context so existing hashes (if any) remain verifiable.
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: str, email: str) -> str:
    exp = utcnow() + ACCESS_TOKEN_EXPIRE_DELTA
    payload = {"sub": user_id, "email": email, "type": "access", "exp": exp}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    exp = utcnow() + REFRESH_TOKEN_EXPIRE_DELTA
    payload = {"sub": user_id, "type": "refresh", "exp": exp, "jti": secrets.token_urlsafe(12)}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def generate_magic_token() -> str:
    return secrets.token_urlsafe(32)


def hash_value(value: str) -> str:
    return pwd_context.hash(value, scheme="pbkdf2_sha256")


def verify_hash(value: str, hashed: str) -> bool:
    return pwd_context.verify(value, hashed)
