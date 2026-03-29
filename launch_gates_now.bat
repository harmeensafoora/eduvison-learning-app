@echo off
REM Phase 01 Validation Gates - Quick Launch Setup

echo.
echo ================================================================
echo PHASE 01 VALIDATION GATES - QUICK LAUNCH
echo ================================================================
echo.

REM Create test_pdfs folder
if not exist "test_pdfs" (
    mkdir test_pdfs
    echo [OK] Created test_pdfs folder
) else (
    echo [OK] test_pdfs folder exists
)

echo.
echo ================================================================
echo SETUP: Environment Variables
echo ================================================================
echo.
echo Add these to your PowerShell terminal before running gates:
echo.
echo $env:DATABASE_URL = "postgresql://postgres:password@localhost:5432/eduvision_v2"
echo $env:REDIS_URL = "redis://localhost:6379"
echo $env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
echo $env:AZURE_OPENAI_KEY = "your-key-here"
echo $env:AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
echo.

echo ================================================================
echo EXACT COMMANDS FOR YOUR 3 TERMINALS
echo ================================================================
echo.
echo TERMINAL 1: Quality Gate (Manual scoring, 1-2 hours)
echo -------------------------------------------------------
echo cd d:\eduvision-v2
echo python scripts/validate_quality_gate.py --pdf-dir ./test_pdfs --count 20
echo.

echo TERMINAL 2: Latency Gate (Automated, 5-10 min)
echo -------------------------------------------------------
echo cd d:\eduvision-v2
echo python scripts/validate_latency_gate.py --requests 1000
echo.

echo TERMINAL 3: Security Gate (Automated, 2-5 min)
echo -------------------------------------------------------
echo cd d:\eduvision-v2
echo python scripts/validate_security_gate.py --submissions 100
echo.

echo ================================================================
echo Prerequisites (must run FIRST)
echo ================================================================
echo.
echo 1. PostgreSQL running on localhost:5432
echo    docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15
echo.
echo 2. Redis running on localhost:6379
echo    docker run -d -p 6379:6379 redis:alpine
echo.
echo 3. FastAPI backend running (separate terminal)
echo    uvicorn app.main:app --reload --port 8000
echo.
echo 4. test_pdfs folder populated with 20 sample PDFs
echo    Folder already created: d:\eduvision-v2\test_pdfs
echo.
echo ================================================================
echo Next Steps
echo ================================================================
echo.
echo 1. Open 3 NEW PowerShell terminals
echo 2. Set env vars in EACH terminal (see above)
echo 3. Copy-paste the command for each terminal (Terminal 1, 2, 3)
echo 4. Terminal 1 will ask you to score PDFs (1-5 scale)
echo 5. Terminals 2 & 3 run automatically
echo 6. Results save to .planning/phases/01-foundations/
echo.
echo Status: READY FOR EXECUTION
echo.
