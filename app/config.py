import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH, override=True)

BASE_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
IMAGE_OUTPUT_DIR = os.path.join(BASE_UPLOAD_DIR, "generated")
ORGAN_IMAGE_DIR = os.path.join(BASE_DIR, "static", "organs")

os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)
os.makedirs(ORGAN_IMAGE_DIR, exist_ok=True)

# PostgreSQL with fallback to SQLite for local dev
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    # Default: PostgreSQL local, fallback to SQLite if not available
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "eduvision")
    db_password = os.getenv("DB_PASSWORD", "eduvision_dev")
    db_name = os.getenv("DB_NAME", "eduvision_v2")
    _db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

DATABASE_URL = _db_url
ALEMBIC_DATABASE_URL = os.getenv("ALEMBIC_DATABASE_URL", DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", ""))

# Redis configuration (Task 1.2)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") or ""
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY") or ""
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT") or ""

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-prod")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
MAGIC_LINK_EXPIRE_MINUTES = int(os.getenv("MAGIC_LINK_EXPIRE_MINUTES", "20"))

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "http://localhost:8000")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "eduvision_access")
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "eduvision_refresh")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
EVENT_FLUSH_SIZE = int(os.getenv("EVENT_FLUSH_SIZE", "5"))
EVENT_FLUSH_INTERVAL_SECONDS = int(os.getenv("EVENT_FLUSH_INTERVAL_SECONDS", "30"))

ACCESS_TOKEN_EXPIRE_DELTA = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
REFRESH_TOKEN_EXPIRE_DELTA = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
MAGIC_LINK_EXPIRE_DELTA = timedelta(minutes=MAGIC_LINK_EXPIRE_MINUTES)
