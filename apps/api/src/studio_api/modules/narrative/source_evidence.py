"""Ground sourced stories in quotations from the selected article."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from studio_api.core.errors import ErrorCode, StudioError


@dataclass(frozen=True)
class SourceEvidence:
    subject_name: str
    subject_type: str
    verified_location: str
    verified_facts: list[str]
    forbidden_locations: list[str]
    source_url: str
    source_date: str


def _fold(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def ground_source_evidence(payload: dict[str, Any], source: dict[str, str]) -> SourceEvidence:
    """Only accept extracted quotations that occur in the RSS title or summary."""
    source_text = f"{source.get('title', '')} {source.get('summary', '')}"
    normalized_source = _fold(source_text)
    subject = str(payload.get("subject_name") or "").strip()
    location = str(payload.get("verified_location") or "").strip()
    if not subject or _fold(subject) not in normalized_source:
        raise StudioError(ErrorCode.FACTUAL_VALIDATION_FAILED, "Source subject is not quoted")
    title = _fold(source.get("title", ""))
    subject_terms = re.findall(r"[\w]+(?:-[\w]+)*", _fold(subject))
    if not any(len(term) >= 3 and term in title for term in subject_terms):
        # The article title is itself trusted source text. It is safer than
        # letting a small model promote a comparison or opening anecdote.
        subject = source.get("title", "").strip()
    if location and _fold(location) not in normalized_source:
        raise StudioError(ErrorCode.FACTUAL_VALIDATION_FAILED, "Source location is not quoted")
    raw_facts = payload.get("verified_facts")
    if not isinstance(raw_facts, list):
        raise StudioError(ErrorCode.FACTUAL_VALIDATION_FAILED, "Source facts are missing")
    facts = [
        fact.strip()
        for item in raw_facts
        if isinstance(item, str)
        if (fact := item.strip()) and len(fact) >= 15 and _fold(fact) in normalized_source
    ]
    if not facts:
        raise StudioError(ErrorCode.FACTUAL_VALIDATION_FAILED, "No source facts are quoted")
    raw_forbidden = payload.get("forbidden_locations")
    forbidden = (
        [
            value.strip()
            for value in raw_forbidden
            if isinstance(value, str)
            and value.strip()
            and _fold(value) in normalized_source
            and _fold(value) != _fold(location)
        ]
        if isinstance(raw_forbidden, list)
        else []
    )
    # These translations are deterministic contradictions, not model-extracted facts.
    if re.search(r"\bAntarcti(?:ca|c)\b|Nam Cực", source_text, re.I) and not re.search(
        r"\bArctic\b|Bắc Cực", source_text, re.I
    ):
        forbidden.append("Bắc Cực")
    if re.search(r"\bArctic\b|Bắc Cực", source_text, re.I) and not re.search(
        r"\bAntarcti(?:ca|c)\b|Nam Cực", source_text, re.I
    ):
        forbidden.append("Nam Cực")
    return SourceEvidence(
        subject_name=subject,
        subject_type=str(payload.get("subject_type") or "").strip(),
        verified_location=location,
        verified_facts=facts[:6],
        forbidden_locations=list(dict.fromkeys(forbidden)),
        source_url=source.get("source_url", ""),
        source_date=source.get("published_at", ""),
    )


def validate_geography_claims(script_json: dict[str, Any], evidence: SourceEvidence) -> list[str]:
    violations: list[str] = []
    sections = [("Title", str(script_json.get("title", "")))] + [
        (f"Scene {scene.get('id', index + 1)}", str(scene.get("narration", "")))
        for index, scene in enumerate(script_json.get("scenes", []))
        if isinstance(scene, dict)
    ]
    for section, value in sections:
        normalized = _fold(value)
        for forbidden in evidence.forbidden_locations:
            if _fold(forbidden) in normalized:
                violations.append(f"{section}: mentions forbidden location '{forbidden}'")
        if re.search(r"điểm\s+cực\s+nam\s+của\s+nam\s+cực", normalized):
            violations.append(f"{section}: nonsensical South Pole phrasing")
    return violations
