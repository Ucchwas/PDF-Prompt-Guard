from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pdf_prompt_guard.detectors import detect_instruction_like, summarize_findings
from pdf_prompt_guard.extract import extract_pdf
from pdf_prompt_guard.scoring import hardened_sandbox_score, vulnerable_sandbox_score


def analyze_pdf_to_report(pdf_path: str | Path, job_text: str, use_ocr: bool = False) -> dict[str, Any]:
    extraction = extract_pdf(pdf_path, use_ocr=use_ocr)

    full_findings = detect_instruction_like(extraction.full_text)
    visible_findings = detect_instruction_like(extraction.visible_text)
    filtered_findings = detect_instruction_like(extraction.filtered_out_text)

    vulnerable_score, vulnerable_recommend = vulnerable_sandbox_score(extraction.full_text, job_text)
    hardened_score, hardened_recommend = hardened_sandbox_score(extraction.visible_text, job_text)

    report: dict[str, Any] = {
        "pdf_path": str(pdf_path),
        "extraction_method": extraction.method,
        "full_text_chars": len(extraction.full_text),
        "visible_text_chars": len(extraction.visible_text),
        "filtered_out_text_chars": len(extraction.filtered_out_text),
        "full_findings": full_findings,
        "visible_findings": visible_findings,
        "filtered_out_findings": filtered_findings,
        "full_findings_summary": summarize_findings(full_findings),
        "visible_findings_summary": summarize_findings(visible_findings),
        "filtered_out_findings_summary": summarize_findings(filtered_findings),
        "vulnerable_score": vulnerable_score,
        "vulnerable_recommend_interview": vulnerable_recommend,
        "hardened_score": hardened_score,
        "hardened_recommend_interview": hardened_recommend,
        "suspicious_hidden_like_content": bool(filtered_findings) or len(extraction.filtered_out_text) > 50,
        "excerpts": {
            "full_text": extraction.full_text[:1200],
            "visible_text": extraction.visible_text[:1200],
            "filtered_out_text": extraction.filtered_out_text[:1200],
        },
    }
    return report


def write_report(report: dict[str, Any], out_path: str | Path) -> None:
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
