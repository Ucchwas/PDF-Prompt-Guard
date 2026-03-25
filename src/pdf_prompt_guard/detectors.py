from __future__ import annotations

import re
from typing import Any


PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_instructions", re.compile(r"\bignore\b.{0,40}\b(previous|above|prior)\b.{0,40}\binstructions?\b", re.I | re.S)),
    ("advance_to_interview", re.compile(r"\b(advance|recommend|move|shortlist)\b.{0,30}\b(interview|final round|onsite)\b", re.I | re.S)),
    ("score_override", re.compile(r"\b(score|rating|rank)\b.{0,20}?\b(9[0-9]|100)\s*(/100|percent|%)?\b", re.I | re.S)),
    ("system_prompt_reference", re.compile(r"\b(system prompt|recruiter|ATS|screening model)\b", re.I)),
    ("prompt_injection_reference", re.compile(r"\b(prompt injection|hidden prompt|override instruction)\b", re.I)),
    ("must_hire", re.compile(r"\b(must hire|definitely hire|guaranteed fit|meets all qualifications)\b", re.I)),
]


def detect_instruction_like(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not text:
        return findings

    for label, pattern in PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                {
                    "type": label,
                    "span": [match.start(), match.end()],
                    "match": match.group(0).strip(),
                }
            )
    return findings


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in findings:
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    return counts
