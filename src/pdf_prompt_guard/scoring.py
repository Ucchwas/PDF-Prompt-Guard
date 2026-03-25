from __future__ import annotations

import re


STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "shall", "should", "may", "might", "must", "can", "could", "not", "no",
    "nor", "so", "yet", "both", "either", "neither", "each", "every", "all",
    "any", "few", "more", "most", "other", "some", "such", "than", "too",
    "very", "just", "also", "as", "if", "then", "that", "this", "these",
    "those", "it", "its", "we", "our", "you", "your", "they", "their",
    "he", "she", "his", "her", "who", "whom", "which", "what", "where",
    "when", "how", "why", "about", "up", "out", "off", "over", "under",
    "again", "further", "once", "here", "there", "into", "through", "during",
    "before", "after", "above", "below", "between", "same", "own", "only",
    "while", "until", "because", "although", "since", "unless", "whether",
    "across", "along", "among", "around", "beside", "beyond", "including",
    "new", "well", "work", "working", "experience", "ability", "using",
    "including", "preferred", "required", "strong", "skills", "team",
    "will", "help", "provide", "support", "program", "students", "student",
    "faculty", "campus", "college", "university", "department", "position",
    "candidate", "successful", "professional", "industry", "years",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords and bigrams from text."""
    t = _norm(text)
    # extract individual words (3+ chars, not stop words)
    words = re.findall(r"\b[a-z][a-z0-9+#.]{2,}\b", t)
    singles = {w for w in words if w not in STOP_WORDS}

    # extract bigrams for multi-word terms
    word_list = [w for w in re.findall(r"\b[a-z][a-z0-9+#.]+\b", t) if w not in STOP_WORDS]
    bigrams = set()
    for i in range(len(word_list) - 1):
        bigrams.add(f"{word_list[i]} {word_list[i+1]}")

    return singles | bigrams


def base_keyword_score(resume_text: str, job_text: str) -> float:
    job_keywords = extract_keywords(job_text)
    resume_keywords = extract_keywords(resume_text)

    if not job_keywords:
        return 50.0

    overlap = len(job_keywords & resume_keywords)
    ratio = overlap / len(job_keywords)
    score = 40.0 + 60.0 * ratio
    return round(min(score, 100.0), 2)


def vulnerable_sandbox_score(full_text: str, job_text: str) -> tuple[float, bool]:
    score = base_keyword_score(full_text, job_text)

    m = re.search(r"\b(?:score|rating|rank)\b.{0,20}\b([1-9][0-9]|100)\s*(?:/100|percent|%)?\b", full_text, re.I | re.S)
    if m:
        score = max(score, float(m.group(1)))

    forced_interview = bool(
        re.search(r"\b(advance|recommend|move|shortlist)\b.{0,30}\b(interview|final round|onsite)\b", full_text, re.I | re.S)
    )
    recommend = forced_interview or score >= 75.0
    return round(min(score, 100.0), 2), recommend


def hardened_sandbox_score(visible_text: str, job_text: str) -> tuple[float, bool]:
    score = base_keyword_score(visible_text, job_text)
    recommend = score >= 75.0
    return score, recommend
