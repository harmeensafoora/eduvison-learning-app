#!/usr/bin/env python3
"""
GSD Parallel Workstream Coordinator
Launches Phase 01 validation gates + Phase 02 Wave 1 execution simultaneously

Usage:
  python launch_parallel_workstreams.py
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

def print_header():
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║  🚀 GSD PARALLEL WORKSTREAM COORDINATOR                        ║
║     Phase 01 Validation Gates + Phase 02 Wave 1 Execution     ║
╚════════════════════════════════════════════════════════════════╝

📅 Launch Time: {datetime.now().isoformat()}
🎯 Strategy: Parallel execution (no blocking dependencies)

""")

def check_prerequisites():
    """Verify environment setup"""
    print("📋 Checking Prerequisites...")
    
    checks = []
    
    # Python virtual env
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        checks.append(("✅", "Python venv activated"))
    else:
        checks.append(("❌", "Python venv NOT activated"))
    
    # Required files
    required_files = [
        "scripts/validate_quality_gate.py",
        "scripts/validate_latency_gate.py",
        "scripts/validate_security_gate.py",
        ".planning/phases/02-cognitive-engines/02-01-PLAN.md",
        ".planning/WORKSTREAMS.md"
    ]
    
    for file in required_files:
        if Path(file).exists():
            checks.append(("✅", f"Found: {file}"))
        else:
            checks.append(("❌", f"Missing: {file}"))
    
    # Environment variables
    env_vars = ["DATABASE_URL", "REDIS_URL", "AZURE_OPENAI_ENDPOINT"]
    for var in env_vars:
        if os.environ.get(var):
            checks.append(("✅", f"Env: {var} configured"))
        else:
            checks.append(("⚠️ ", f"Env: {var} NOT configured"))
    
    # Print results
    print()
    for status, msg in checks:
        print(f"  {status} {msg}")
    
    print()
    return all(status == "✅" for status, _ in checks)

def print_terminal_setup():
    """Print instructions for setting up terminals"""
    print("""
═══════════════════════════════════════════════════════════════════
📱 TERMINAL SETUP (4 independent terminals recommended)
═══════════════════════════════════════════════════════════════════

Terminal 1: Phase 01 Quality Gate (MANUAL - interactive scoring)
─────────────────────────────────────────────────────────────────
cd d:\\eduvision-v2
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\\venv\\Scripts\\Activate.ps1
python scripts/validate_quality_gate.py --pdf-dir ./test_pdfs --count 20

Output: .planning/phases/01-foundations/QUALITY_GATE_RESULTS.md


Terminal 2: Phase 01 Latency Gate (AUTOMATED - 5-10 min)
─────────────────────────────────────────────────────────────────
cd d:\\eduvision-v2
.\\venv\\Scripts\\Activate.ps1
python scripts/validate_latency_gate.py --requests 1000

Output: .planning/phases/01-foundations/LATENCY_GATE_RESULTS.md


Terminal 3: Phase 01 Security Gate (AUTOMATED - 2-5 min)
─────────────────────────────────────────────────────────────────
cd d:\\eduvision-v2
.\\venv\\Scripts\\Activate.ps1
python scripts/validate_security_gate.py --submissions 100

Output: .planning/phases/01-foundations/SECURITY_AUDIT_RESULTS.md


Terminal 4: Phase 02 Wave 1 Execution (AUTOMATIC - 4 days)
─────────────────────────────────────────────────────────────────
cd d:\\eduvision-v2
.\\venv\\Scripts\\Activate.ps1
# (Will be started by subagent)

Output: Multiple commits + .planning/phases/02-cognitive-engines/02-01-SUMMARY.md

═══════════════════════════════════════════════════════════════════

⏱️  TIMING:
  - Quality Gate: ~1-2 hours (manual scoring)
  - Latency Gate: ~5-10 minutes (automated)
  - Security Gate: ~2-5 minutes (automated)
  - Phase 02 Wave 1: ~4 days (backend tasks 3.1-3.3)

✅ All can run SIMULTANEOUSLY — no blocking dependencies

═══════════════════════════════════════════════════════════════════
""")

def print_workflow():
    """Print coordination workflow"""
    print("""
═══════════════════════════════════════════════════════════════════
🔄 PARALLEL WORKFLOW
═══════════════════════════════════════════════════════════════════

PHASE 01 (Validation Track):
  ├─ Quality Gate ............ (Day 1-2) Manual PDF scoring
  ├─ Latency Gate ............ (Day 2-3) Load test (automated)
  └─ Security Gate ........... (Day 3-4) Auth stability (automated)
     └─ DELIVERABLE: 3 result markdown files
     └─ DECISION: All gates pass → Phase 01 VERIFIED ✅

PHASE 02 (Execution Track):
  ├─ Wave 1 (Days 1-4) ....... Backend foundation
  │  ├─ Task 3.1: Leitner Scheduler
  │  ├─ Task 3.2: Elaboration Pipeline
  │  └─ Task 3.3: Dashboard APIs
  │  └─ CHECKPOINT: Day 7 (100+ schedules, <1.5s latency, <100ms queries)
  │
  ├─ Wave 2 (Days 5-10) ...... Frontend + optimization
  │  ├─ Task 3.4: Dashboard React Components
  │  ├─ Task 3.5: Mobile Lighthouse (≥80)
  │  └─ Task 3.6: Beta Tester Recruitment
  │  └─ CHECKPOINT: Day 10 (UI rendering, Lighthouse ≥80, beta onboarded)
  │
  └─ Wave 3 (Days 11-14) .... User validation
     ├─ Task 3.7: Beta User Testing
     ├─ Task 3.8: Design Iteration
     └─ CHECKPOINT: Day 14 (5+ testers, <30s tasks, 4/5 "weekly use")
        └─ DELIVERABLE: 02-01-SUMMARY.md + atomic commits

═══════════════════════════════════════════════════════════════════

🎯 SUCCESS CRITERIA (both must PASS):

  Phase 01 Validation: ✅ All 3 gates pass
    - Quality: mean ≥3.5/5, hallucinations <5%
    - Latency: P95 <1.5s, error rate <0.5%
    - Security: 0 session losses, token refresh working

  Phase 02 Execution: ✅ All 8 tasks + 3 checkpoints pass
    - Wave 1: Backend complete, verified in tests
    - Wave 2: Frontend rendering + mobile optimized
    - Wave 3: 5+ beta testers engaged, design locked

═══════════════════════════════════════════════════════════════════
""")

def print_discord_setup():
    """Print Discord coordination channel setup"""
    print("""
═══════════════════════════════════════════════════════════════════
💬 COORDINATION CHANNELS (Discord)
═══════════════════════════════════════════════════════════════════

#phase-01-validation
  └─ Quality gate progress (manual scoring milestones)
  └─ Latency gate results (when complete)
  └─ Security gate results (when complete)
  └─ Thread: Issues & troubleshooting

#phase-02-execution
  └─ Wave 1 checkpoint updates (Day 7)
  └─ Wave 2 checkpoint updates (Day 10)
  └─ Wave 3 checkpoint updates (Day 14)
  └─ Thread: Blockers & decisions

#general
  └─ Daily standup: Status of both tracks
  └─ Escalations: If either track hits critical blocker

═══════════════════════════════════════════════════════════════════
""")

def print_next_steps():
    """Print next steps"""
    print("""
═══════════════════════════════════════════════════════════════════
✅ NEXT STEPS (START NOW)
═══════════════════════════════════════════════════════════════════

[ ] 1. Create 4 PowerShell terminals
[ ] 2. In Terminal 1: Run Phase 01 Quality Gate (manual scoring)
[ ] 3. In Terminal 2: Run Phase 01 Latency Gate (automated)
[ ] 4. In Terminal 3: Run Phase 01 Security Gate (automated)
[ ] 5. In Terminal 4: Await Phase 02 Wave 1 execution launch
[ ] 6. Monitor .planning/phases/01-foundations/ for results
[ ] 7. Monitor .planning/phases/02-cognitive-engines/ for commits

═══════════════════════════════════════════════════════════════════

⏰ Check-in Points:
  - Day 2 (Sat): Quality gate + Latency gate progress
  - Day 4 (Mon): Security gate complete, Phase 02 Wave 1 progress
  - Day 7 (Thu): Phase 02 Wave 1 checkpoint (backend verified)
  - Day 10 (Sun): Phase 02 Wave 2 checkpoint (mobile polished)
  - Day 14 (Thu): All gates pass → Ready for Phase 3

═══════════════════════════════════════════════════════════════════
""")

def main():
    print_header()
    
    if not check_prerequisites():
        print("\n⚠️  Prerequisites check failed. Fix issues above before proceeding.")
        print("\nTo activate venv on Windows:")
        print("  .\\venv\\Scripts\\Activate.ps1")
        sys.exit(1)
    
    print("\n✅ All prerequisites met! Ready for parallel execution.\n")
    
    # Print all instructions
    print_terminal_setup()
    print_workflow()
    print_discord_setup()
    print_next_steps()
    
    print("""
═══════════════════════════════════════════════════════════════════
📊 REAL-TIME MONITORING
═══════════════════════════════════════════════════════════════════

Watch these directories for updates:

  Phase 01 Results:
    .planning/phases/01-foundations/QUALITY_GATE_RESULTS.md
    .planning/phases/01-foundations/LATENCY_GATE_RESULTS.md
    .planning/phases/01-foundations/SECURITY_AUDIT_RESULTS.md

  Phase 02 Execution:
    .planning/phases/02-cognitive-engines/02-01-SUMMARY.md
    git log --oneline (watch for atomic commits)

═══════════════════════════════════════════════════════════════════

🎬 LET'S GO!
  Terminal 1: python scripts/validate_quality_gate.py --pdf-dir ./test_pdfs

═══════════════════════════════════════════════════════════════════
""")

if __name__ == "__main__":
    main()
