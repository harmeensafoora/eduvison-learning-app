#!/usr/bin/env powershell
<#
.SYNOPSIS
Phase 01 Validation Gates - Quick Launch Script
Prepares environment and shows exact commands to execute

.DESCRIPTION
Creates test folders, verifies setup, and provides copy-paste commands for 3 terminals
#>

Write-Host "`n╔════════════════════════════════════════════════════════════════╗"
Write-Host "║  🚀 PHASE 01 VALIDATION GATES - QUICK LAUNCH                  ║"
Write-Host "║     Ready to execute in parallel                              ║"
Write-Host "╚════════════════════════════════════════════════════════════════╝`n"

# 1. Create test_pdfs folder
Write-Host "📁 Creating test_pdfs folder..." -ForegroundColor Cyan
if (-Not (Test-Path "test_pdfs")) {
    New-Item -ItemType Directory -Path "test_pdfs" | Out-Null
    Write-Host "   ✅ test_pdfs folder created`n"
} else {
    $pdfCount = (Get-ChildItem "test_pdfs" -Filter "*.pdf" | Measure-Object).Count
    Write-Host "   ✅ test_pdfs exists ($pdfCount PDFs found)`n"
}

# 2. Show environment setup
Write-Host "🔧 Environment Variables" -ForegroundColor Cyan
Write-Host @"
Add these to your PowerShell before running gates:

`$env:DATABASE_URL = "postgresql://postgres:password@localhost:5432/eduvision_v2"
`$env:REDIS_URL = "redis://localhost:6379"
`$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
`$env:AZURE_OPENAI_KEY = "your-key-here"
`$env:AZURE_OPENAI_API_VERSION = "2024-02-15-preview"

"@

# 3. Show exact terminal commands
Write-Host "════════════════════════════════════════════════════════════════`n" -ForegroundColor Green
Write-Host "📱 EXACT COMMANDS FOR YOUR 3 TERMINALS" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════`n"

Write-Host "TERMINAL 1: Quality Gate (Manual scoring, 1-2 hours)" -ForegroundColor Yellow
Write-Host "─────────────────────────────────────────────────────" -ForegroundColor Yellow
Write-Host @"
cd d:\eduvision-v2
`$env:DATABASE_URL = "postgresql://postgres:password@localhost:5432/eduvision_v2"
`$env:REDIS_URL = "redis://localhost:6379"
`$env:AZURE_OPENAI_ENDPOINT = "https://..."
`$env:AZURE_OPENAI_KEY = "..."
python scripts/validate_quality_gate.py --pdf-dir ./test_pdfs --count 20

" -ForegroundColor White

Write-Host "TERMINAL 2: Latency Gate (Automated, 5-10 min)" -ForegroundColor Yellow
Write-Host "───────────────────────────────────────────────" -ForegroundColor Yellow
Write-Host @"
cd d:\eduvision-v2
`$env:DATABASE_URL = "postgresql://postgres:password@localhost:5432/eduvision_v2"
`$env:REDIS_URL = "redis://localhost:6379"
`$env:AZURE_OPENAI_ENDPOINT = "https://..."
`$env:AZURE_OPENAI_KEY = "..."
python scripts/validate_latency_gate.py --requests 1000

" -ForegroundColor White

Write-Host "TERMINAL 3: Security Gate (Automated, 2-5 min)" -ForegroundColor Yellow
Write-Host "──────────────────────────────────────────────" -ForegroundColor Yellow
Write-Host @"
cd d:\eduvision-v2
`$env:DATABASE_URL = "postgresql://postgres:password@localhost:5432/eduvision_v2"
`$env:REDIS_URL = "redis://localhost:6379"
`$env:AZURE_OPENAI_ENDPOINT = "https://..."
`$env:AZURE_OPENAI_KEY = "..."
python scripts/validate_security_gate.py --submissions 100

" -ForegroundColor White

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "⏱️  TIMELINE" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host @"
Terminal 1 (Quality Gate): ~1-2 hours (MANUAL - you score PDFs)
Terminal 2 (Latency Gate): ~5-10 min (AUTOMATED)
Terminal 3 (Security Gate): ~2-5 min (AUTOMATED)

💡 All 3 can run SIMULTANEOUSLY in parallel terminals

" -ForegroundColor Cyan

Write-Host "✅ RESULTS WILL BE SAVED TO:" -ForegroundColor Green
Write-Host @"
.planning/phases/01-foundations/QUALITY_GATE_RESULTS.md
.planning/phases/01-foundations/LATENCY_GATE_RESULTS.md
.planning/phases/01-foundations/SECURITY_AUDIT_RESULTS.md

" -ForegroundColor White

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "🎯 PREREQUISITES (MUST RUN FIRST)" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host @"
Before running the gates above, ensure:

1. PostgreSQL running on localhost:5432
   - Command: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15
   - Or use your local PostgreSQL installation

2. Redis running on localhost:6379
   - Command: docker run -d -p 6379:6379 redis:alpine
   - Or use your local Redis installation

3. FastAPI backend running
   - Open NEW terminal and run:
   uvicorn app.main:app --reload --port 8000

4. test_pdfs folder with 20 PDFs
   - Folder already created: d:\eduvision-v2\test_pdfs
   - Add 20 sample PDFs (any format - research papers, tutorials, etc.)

Check status: psql -U postgres -d eduvision_v2 -c "SELECT 1"
Check Redis: redis-cli ping (should return PONG)

" -ForegroundColor Cyan

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "🚀 YOU'RE READY!" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host @"
Next steps:

1. Open 3 NEW PowerShell terminals
2. In each, copy-paste the command above for that terminal
3. Terminal 1 will be interactive (you score PDFs 1-5)
4. Terminals 2 & 3 run automatically
5. Check results as they complete

Phase 02 Wave 1 (backend tasks) runs AUTONOMOUSLY in parallel:
  - Monitor via: git log --oneline -f

Questions? See: .planning/LAUNCH_PARALLEL_NOW.md

" -ForegroundColor Cyan

Write-Host "════════════════════════════════════════════════════════════════`n" -ForegroundColor Green

Write-Host "Status: ✅ READY FOR EXECUTION" -ForegroundColor Green
Write-Host ""
