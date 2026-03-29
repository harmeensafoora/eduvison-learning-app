#!/usr/bin/env python3
"""
Quick Phase 01 Setup Check
Verifies environment is ready before running gates
"""

import os
import sys
import subprocess

print("=" * 70)
print("✅ PHASE 01 VALIDATION GATES - SETUP CHECK")
print("=" * 70)
print()

# 1. Check venv
print("1️⃣  Virtual Environment")
if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    print("   ✅ Venv ACTIVE")
else:
    print("   ⚠️  Venv not active - run: .\\venv\\Scripts\\Activate.ps1")

# 2. Check services
print("\n2️⃣  Required Services")

services = {
    "PostgreSQL": ("psql", "--version"),
    "Redis": ("redis-cli", "ping")
}

for service, cmd in services.items():
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=2)
        if result.returncode == 0:
            print(f"   ✅ {service} running")
        else:
            print(f"   ⚠️  {service} - check connection")
    except:
        print(f"   ⚠️  {service} - not found or not running")

# 3. Check env vars
print("\n3️⃣  Environment Variables")

env_vars = {
    "DATABASE_URL": "PostgreSQL connection",
    "REDIS_URL": "Redis connection",
    "AZURE_OPENAI_ENDPOINT": "Azure OpenAI",
}

for var, desc in env_vars.items():
    if os.environ.get(var):
        print(f"   ✅ {var}: configured")
    else:
        print(f"   ⚠️  {var}: NOT set (needed: {desc})")

# 4. Check test data
print("\n4️⃣  Test Data")

if os.path.exists("test_pdfs"):
    pdf_count = len([f for f in os.listdir("test_pdfs") if f.endswith(".pdf")])
    print(f"   ✅ test_pdfs folder exists ({pdf_count} PDFs)")
else:
    print("   ⚠️  test_pdfs folder missing - create it and add 20 sample PDFs")

print("\n" + "=" * 70)
print("📋 SETUP CHECKLIST")
print("=" * 70)
print("""
Before running gates, ensure:

[ ] PostgreSQL running (check: psql --version)
[ ] Redis running (check: redis-cli ping)
[ ] FastAPI running (uvicorn app.main:app --reload)
[ ] Environment variables set (DATABASE_URL, REDIS_URL, AZURE_OPENAI_*)
[ ] test_pdfs folder created with 20 sample PDFs

═══════════════════════════════════════════════════════════════════
🚀 READY TO START GATES
═══════════════════════════════════════════════════════════════════

Open 3 separate PowerShell terminals and run:

TERMINAL 1: Quality Gate (manual scoring, 1-2 hours)
─────────────────────────────────────────────────
.\\venv\\Scripts\\Activate.ps1
python scripts/validate_quality_gate.py --pdf-dir ./test_pdfs --count 20

TERMINAL 2: Latency Gate (automated, 5-10 min)
─────────────────────────────────────────────────
.\\venv\\Scripts\\Activate.ps1
python scripts/validate_latency_gate.py --requests 1000

TERMINAL 3: Security Gate (automated, 2-5 min)
─────────────────────────────────────────────────
.\\venv\\Scripts\\Activate.ps1
python scripts/validate_security_gate.py --submissions 100

═══════════════════════════════════════════════════════════════════
""")
