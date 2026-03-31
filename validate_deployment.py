#!/usr/bin/env python
"""
Pre-deployment validation script
Checks:
- Database connectivity
- API routes are registered
- Required environment variables
- Redis connectivity (optional)
- Critical module imports
"""

import sys
import asyncio
from pathlib import Path

async def validate_database():
    """Verify database connectivity and schema"""
    print("🔍 Validating database...")
    try:
        from app.database import init_db, engine
        from app.db_models import User, PDFUpload, Concept, Quiz, QuizResponse, SpacedRepState
        
        # Check engine created
        assert engine is not None, "Database engine not initialized"
        
        # Try to get connection
        async with engine.begin() as conn:
            result = await conn.run_sync(lambda sync_conn: sync_conn.connection)
            assert result is not None
        
        print("  ✓ Database engine initialized")
        print("  ✓ Database connection verified")
        
        # Verify all models exist
        models = [User, PDFUpload, Concept, Quiz, QuizResponse, SpacedRepState]
        print(f"  ✓ {len(models)} core models registered")
        
        return True
    except Exception as e:
        print(f"  ✗ Database error: {e}")
        return False


def validate_api_routes():
    """Verify API routes are registered"""
    print("🔍 Validating API routes...")
    try:
        from app.main import app
        
        # Count routes
        routes = app.routes
        print(f"  ✓ {len(routes)} API routes registered")
        
        # Check critical endpoints exist
        route_paths = [r.path for r in routes if hasattr(r, 'path')]
        
        critical_endpoints = [
            "/health",
            "/auth/signup",
            "/auth/login",
            "/auth/logout",
            "/auth/me",
            "/api/pdfs/upload",
            "/api/process",
        ]
        
        missing = [ep for ep in critical_endpoints if ep not in route_paths and not any(ep in rp for rp in route_paths)]
        
        if missing:
            print(f"  ⚠ Missing endpoints: {missing}")
        else:
            print(f"  ✓ All {len(critical_endpoints)} critical endpoints present")
        
        return len(missing) == 0
    except Exception as e:
        print(f"  ✗ Route validation error: {e}")
        return False


def validate_environment():
    """Verify required environment variables"""
    print("🔍 Validating environment configuration...")
    try:
        from app.config import (
            DATABASE_URL, AZURE_OPENAI_ENDPOINT, JWT_SECRET_KEY,
            ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
        )
        
        checks = {
            "Database URL": DATABASE_URL and "://" in DATABASE_URL,
            "JWT Secret Key": JWT_SECRET_KEY and "change-me" not in JWT_SECRET_KEY.lower(),
            "Access Token Expiry": ACCESS_TOKEN_EXPIRE_MINUTES > 0,
            "Refresh Token Expiry": REFRESH_TOKEN_EXPIRE_DAYS > 0,
        }
        
        all_pass = True
        for check_name, check_result in checks.items():
            status = "✓" if check_result else "⚠"
            print(f"  {status} {check_name}")
            if not check_result:
                all_pass = False
        
        # Azure OpenAI is optional but warn if not configured
        if not AZURE_OPENAI_ENDPOINT:
            print("  ⚠ Azure OpenAI not configured (optional - LLM features disabled)")
        else:
            print("  ✓ Azure OpenAI configured")
        
        return all_pass
    except Exception as e:
        print(f"  ✗ Environment validation error: {e}")
        return False


def validate_dependencies():
    """Verify critical dependencies are installed"""
    print("🔍 Validating dependencies...")
    
    critical_packages = {
        "fastapi": "FastAPI web framework",
        "sqlalchemy": "SQLAlchemy ORM",
        "pydantic": "Pydantic data validation",
        "redis": "Redis client (optional)",
        "celery": "Celery task queue (optional)",
        "openai": "OpenAI SDK (optional)",
    }
    
    missing = []
    optional_missing = []
    
    for pkg_name, description in critical_packages.items():
        try:
            __import__(pkg_name)
            is_optional = "optional" in description.lower()
            status = "⚠" if is_optional else "✓"
            print(f"  {status} {description}")
        except ImportError:
            is_optional = "optional" in description.lower()
            if is_optional:
                optional_missing.append(pkg_name)
                print(f"  ⚠ {description} (not installed - optional)")
            else:
                missing.append(pkg_name)
                print(f"  ✗ {description}")
    
    if missing:
        print(f"\n  Install missing packages: pip install {' '.join(missing)}")
        return False
    
    return True


async def validate_redis():
    """Verify Redis connectivity (optional)"""
    print("🔍 Validating Redis (optional)...")
    try:
        from redis.asyncio import from_url
        from app.config import REDIS_URL
        
        redis_client = await from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        ping = await redis_client.ping()
        await redis_client.close()
        
        if ping:
            print("  ✓ Redis connected and responding")
            return True
    except Exception as e:
        print(f"  ⚠ Redis not available (optional): {str(e)[:60]}")
        return True  # Redis is optional


def validate_frontend():
    """Verify frontend build exists"""
    print("🔍 Validating frontend build...")
    try:
        dist_path = Path("frontend/dist")
        if dist_path.exists():
            html_file = dist_path / "index.html"
            if html_file.exists():
                print(f"  ✓ Frontend built ({html_file.stat().st_size} bytes)")
                return True
        
        print("  ⚠ Frontend build not found - run: npm run build")
        return False
    except Exception as e:
        print(f"  ⚠ Frontend check error: {e}")
        return False


async def run_validations():
    """Run all validations and report results"""
    print("\n" + "="*60)
    print("EduVision V2 - Pre-Deployment Validation")
    print("="*60 + "\n")
    
    results = {
        "Dependencies": validate_dependencies(),
        "Environment": validate_environment(),
        "Database": await validate_database(),
        "API Routes": validate_api_routes(),
        "Redis": await validate_redis(),
        "Frontend": validate_frontend(),
    }
    
    print("\n" + "="*60)
    print("Validation Summary")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check_name, result in results.items():
        status = "✓" if result else "✗"
        print(f"  {status} {check_name}")
    
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🚀 All validations passed! Ready for deployment.")
        return True
    else:
        print(f"\n⚠️  {total - passed} validation(s) failed. Address issues before deployment.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_validations())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Validation script error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
