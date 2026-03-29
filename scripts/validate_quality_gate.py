#!/usr/bin/env python3
"""
Phase 01 Quality Gate: Concept Extraction Validation
Scores 20 diverse PDFs on concept quality (3.5/5 target)

Usage:
  python validate_quality_gate.py --pdf-dir ./test_pdfs --output ./QUALITY_GATE_RESULTS.md
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import argparse

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm_pipelines import extract_concepts
from app.pdf_processing import extract_pdf_text

async def score_concept_quality(pdf_path: str, manual_review: bool = True) -> Dict:
    """
    Extract concepts from PDF and score quality (1-5 scale).
    
    Quality criteria:
    - Relevance: Concepts match document content (4-5: all match, 2-3: some off-topic, 1: mostly hallucinated)
    - Clarity: Concepts are understandable without context (4-5: clear, 2-3: vague, 1: unclear)
    - Completeness: Key concepts captured (4-5: comprehensive, 2-3: missing some, 1: sparse)
    - Accuracy: No hallucinations or false claims (4-5: accurate, 2-3: minor errors, 1: major errors)
    """
    try:
        # Extract text
        text = extract_pdf_text(pdf_path)
        if not text or len(text.strip()) < 100:
            return {
                "pdf": os.path.basename(pdf_path),
                "status": "SKIP",
                "reason": "PDF too short or unreadable",
                "score": 0
            }
        
        # Extract concepts
        concepts = await extract_concepts(text, pdf_id=os.path.basename(pdf_path))
        
        # Manual scoring (human review)
        if manual_review:
            print(f"\n{'='*60}")
            print(f"PDF: {os.path.basename(pdf_path)}")
            print(f"Extracted Concepts ({len(concepts)}):")
            for i, concept in enumerate(concepts, 1):
                print(f"  {i}. {concept.get('name', 'N/A')} - {concept.get('description', '')[:100]}")
            
            while True:
                try:
                    score = int(input("\nScore (1-5) or 0 to skip: "))
                    if 0 <= score <= 5:
                        break
                except ValueError:
                    pass
                print("Invalid input. Enter 1-5.")
            
            if score == 0:
                return {"pdf": os.path.basename(pdf_path), "status": "SKIP", "score": 0}
            
            hallucinations = int(input("Hallucination count (0-5): ") or "0")
            
            return {
                "pdf": os.path.basename(pdf_path),
                "status": "SCORED",
                "score": score,
                "concept_count": len(concepts),
                "hallucinations": hallucinations,
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "pdf": os.path.basename(pdf_path),
            "status": "ERROR",
            "reason": "Non-interactive mode not supported"
        }
    
    except Exception as e:
        return {
            "pdf": os.path.basename(pdf_path),
            "status": "ERROR",
            "reason": str(e)
        }

async def run_quality_gate(pdf_dir: str, output_file: str, target_pdfs: int = 20):
    """Execute quality gate across PDF sample."""
    
    pdf_dir = Path(pdf_dir)
    if not pdf_dir.exists():
        print(f"❌ PDF directory not found: {pdf_dir}")
        sys.exit(1)
    
    pdf_files = sorted(list(pdf_dir.glob("*.pdf")))[:target_pdfs]
    
    if len(pdf_files) < target_pdfs:
        print(f"⚠️  Warning: Found {len(pdf_files)} PDFs, target was {target_pdfs}")
    
    print(f"📊 Phase 01 Quality Gate: Concept Extraction Validation")
    print(f"📁 PDFs to score: {len(pdf_files)}")
    print(f"🎯 Target: Mean score ≥3.5/5")
    print()
    
    results = []
    for pdf_file in pdf_files:
        result = await score_concept_quality(str(pdf_file), manual_review=True)
        results.append(result)
    
    # Calculate statistics
    scored = [r for r in results if r.get("status") == "SCORED"]
    scores = [r["score"] for r in scored]
    
    if not scores:
        print("❌ No PDFs scored")
        sys.exit(1)
    
    mean_score = sum(scores) / len(scores)
    total_hallucinations = sum(r.get("hallucinations", 0) for r in scored)
    
    # Generate report
    report = f"""# Phase 01: Quality Gate Results
    
**Date:** {datetime.now().isoformat()}  
**Target:** Mean concept quality ≥3.5/5  
**Result:** {mean_score:.1f}/5  
**Decision:** {'✅ PASS' if mean_score >= 3.5 else '❌ FAIL'}

## Score Distribution

| Score | Count | Percentage |
|-------|-------|-----------|
| 5 | {scores.count(5)} | {100*scores.count(5)/len(scores):.0f}% |
| 4 | {scores.count(4)} | {100*scores.count(4)/len(scores):.0f}% |
| 3 | {scores.count(3)} | {100*scores.count(3)/len(scores):.0f}% |
| 2 | {scores.count(2)} | {100*scores.count(2)/len(scores):.0f}% |
| 1 | {scores.count(1)} | {100*scores.count(1)/len(scores):.0f}% |

## Hallucination Report

- Total hallucinations detected: {total_hallucinations} across {len(scored)} PDFs
- Average hallucinations per PDF: {total_hallucinations/len(scored):.1f}
- **Verdict:** {'✅ ACCEPTABLE (<5%)' if total_hallucinations < len(scored) else '❌ UNACCEPTABLE (≥5%)'}

## Individual Scores

"""
    
    for result in scored:
        report += f"- {result['pdf']}: **{result['score']}/5** ({result['concept_count']} concepts, {result.get('hallucinations', 0)} hallucinations)\n"
    
    report += f"\n## Recommendation\n\n"
    report += f"Mean score: {mean_score:.1f}/5\n"
    report += f"**GO/NO-GO Decision:** {'✅ GO - Proceed to Phase 2' if mean_score >= 3.5 and total_hallucinations <= len(scored) else '❌ NO-GO - Investigate concept extraction quality'}\n"
    
    # Write report
    Path(output_file).write_text(report)
    print(f"\n✅ Report saved: {output_file}")
    
    # Exit with status
    sys.exit(0 if mean_score >= 3.5 else 1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 01 Quality Gate Validator")
    parser.add_argument("--pdf-dir", type=str, default="./test_pdfs", help="Directory with test PDFs")
    parser.add_argument("--output", type=str, default=".planning/phases/01-foundations/QUALITY_GATE_RESULTS.md", help="Output report path")
    parser.add_argument("--count", type=int, default=20, help="Number of PDFs to score")
    
    args = parser.parse_args()
    
    asyncio.run(run_quality_gate(args.pdf_dir, args.output, args.count))
