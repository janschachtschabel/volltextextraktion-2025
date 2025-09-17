"""Lightweight content quality heuristics."""

from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, Tuple

logger = logging.getLogger(__name__)

# Keywords for simple content classification heuristics. The goal is not to be
# perfect but to provide a quick signal for downstream consumers.
_EDUCATIONAL_CONTENT_KEYWORDS = {
    "lernen",
    "learning",
    "lektion",
    "lesson",
    "kursinhalt",
    "curriculum",
    "übungen",
    "exercise",
    "aufgaben",
    "worksheet",
    "vorlesung",
    "lecture",
    "seminar",
    "tutorial",
    "kapitel",
    "module",
    "kompetenz",
    "kompetenzen",
    "kompetenzziel",
    "ziel",
    "ziele",
    "learning outcome",
    "skill",
    "kompetenzziele",
    "unterricht",
    "training",
    "übungsaufgaben",
    "präsentation",
}

_EDUCATIONAL_METADATA_KEYWORDS = {
    "ects",
    "credit",
    "credits",
    "semester",
    "term",
    "vorraussetzung",
    "voraussetzung",
    "prerequisite",
    "zulassung",
    "abschluss",
    "anmeldung",
    "registration",
    "dauer",
    "duration",
    "kontakt",
    "contact",
    "kursnummer",
    "module code",
    "modulnummer",
    "beschreibung",
    "description",
    "veranstalter",
    "provider",
    "zielgruppe",
    "target group",
    "dozent",
    "lecturer",
    "lehrende",
    "preis",
    "kosten",
    "fee",
    "location",
    "ort",
    "zeit",
    "schedule",
    "zeiten",
    "termin",
    "termine",
}

_ERROR_PAGE_KEYWORDS = {
    "404",
    "403",
    "500",
    "fehler",
    "error",
    "not found",
    "forbidden",
    "zugriff verweigert",
    "access denied",
    "seite nicht gefunden",
    "wartung",
    "maintenance",
    "unavailable",
    "temporarily unavailable",
    "problem",
    "oops",
    "kaputt",
    "blocked",
    "captcha",
    "try again",
}

def calculate_quality_metrics(text: str) -> Dict[str, object]:
    """Return simple quality indicators for the extracted text."""

    if not text:
        return _empty_metrics()

    stripped = text.strip()
    if not stripped:
        return _empty_metrics()

    character_length = len(stripped)
    lower_text = stripped.lower()

    category, confidence, signals = _classify_text(lower_text, character_length)

    metrics = {
        "character_length": character_length,
        "content_category": category,
        "confidence": round(confidence, 3),
        "matched_keywords": signals,
    }

    logger.debug(
        "Calculated quality metrics: category=%s, confidence=%.3f, chars=%d",
        category,
        confidence,
        character_length,
    )

    return metrics


def _classify_text(text: str, character_length: int) -> Tuple[str, float, Dict[str, int]]:
    """Classify content into educational content, metadata, error page or other."""

    error_matches = _count_matches(text, _ERROR_PAGE_KEYWORDS)
    content_matches = _count_matches(text, _EDUCATIONAL_CONTENT_KEYWORDS)
    metadata_matches = _count_matches(text, _EDUCATIONAL_METADATA_KEYWORDS)

    signals = {
        "error_page": error_matches,
        "educational_content": content_matches,
        "educational_metadata": metadata_matches,
    }

    # Strongly bias towards error pages when obvious indicators are present
    if error_matches > 0 and character_length < 800:
        confidence = min(1.0, error_matches / max(sum(signals.values()), 1))
        return "error_page", confidence, signals

    scores = {
        "educational_content": content_matches,
        "educational_metadata": metadata_matches,
        "error_page": error_matches,
    }

    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]
    total_score = sum(scores.values())

    if best_score == 0:
        return "other", 0.0, signals

    confidence = min(1.0, best_score / max(total_score, 1))
    return best_category, confidence, signals


def _count_matches(text: str, keywords: Iterable[str]) -> int:
    """Count occurrences of the provided keywords in ``text``."""

    count = 0
    for keyword in keywords:
        if len(keyword.split()) > 1:
            count += len(re.findall(re.escape(keyword), text))
        else:
            count += len(re.findall(rf"\b{re.escape(keyword)}\b", text))
    return count


def _empty_metrics() -> Dict[str, object]:
    """Return the default metrics structure for empty content."""

    return {
        "character_length": 0,
        "content_category": "other",
        "confidence": 0.0,
        "matched_keywords": {
            "error_page": 0,
            "educational_content": 0,
            "educational_metadata": 0,
        },
    }


def calculate_simplified_quality_metrics(text: str) -> Dict[str, object]:
    """Backward compatibility alias for older imports."""

    return calculate_quality_metrics(text)


__all__ = ["calculate_quality_metrics", "calculate_simplified_quality_metrics"]

