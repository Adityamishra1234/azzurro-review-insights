"""Keyword-first topic classifier for operational insights.

Why keywords first
------------------
Operations staff need insights they can trust and explain. A keyword rule
("review mentioned 'dirty' or 'stain' therefore tagged Cleanliness") is
auditable in a way that a black-box classifier is not. Precision beats recall
here: a false positive hides a different real problem, a false negative is
only a missed count.

Accuracy of a hand-tuned keyword set tops out below a good LLM on nuanced
reviews. For that reason, an LLM pass is available when the operator opts in
(settings.enable_llm_topics). The final topic set is the union of both.

Sentiment is coarse: positive, negative, or mixed. A review that filled in
both the positive and negative Booking fields is "mixed". When only one side
is present, the sign of the rating (or the presence of either side) decides.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

from ..config import settings
from ..scraper.parsing import ParsedReview


log = logging.getLogger(__name__)


# Canonical topic names used across the dashboard, and the keyword set per topic.
# Keep this synced with frontend copy. Order is alphabetical for readability,
# not priority (a review can carry many topics).
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Check-in experience": (
        "check in", "check-in", "checkin", "reception", "front desk",
        "arrival", "waited", "waiting", "queue", "key", "early check",
        "late check",
    ),
    "Cleanliness": (
        "clean", "cleanliness", "dirty", "dust", "dusty", "stain", "stains",
        "smell", "smelly", "hair", "mould", "mold", "bedsheet", "bedsheets",
        "sheets", "bathroom", "shower", "toilet", "hygiene", "hygienic",
    ),
    "Facilities": (
        "facility", "facilities", "gym", "pool", "spa", "sauna", "wifi",
        "wi-fi", "internet", "laundry", "breakfast", "elevator", "lift",
        "parking", "car park", "air con", "aircon", "heating", "ac ",
    ),
    "Location": (
        "location", "walk", "walking distance", "central", "near", "close to",
        "station", "train", "bus stop", "transport", "neighbourhood",
        "neighborhood", "area",
    ),
    "Noise": (
        "noise", "noisy", "quiet", "loud", "street noise", "traffic",
        "thin wall", "walls thin", "could hear", "music",
    ),
    "Room condition": (
        "room was", "rooms were", "bed", "mattress", "pillow", "pillows",
        "carpet", "furniture", "worn", "old", "tired", "dated",
        "renovate", "renovation", "paint", "cramped", "small room",
        "tiny room", "spacious",
    ),
    "Staff or receptionist behaviour": (
        "staff", "receptionist", "concierge", "rude", "helpful", "polite",
        "friendly", "unfriendly", "attitude", "manager", "service",
        "team",
    ),
    "Value for money": (
        "value", "overpriced", "expensive", "cheap", "worth", "price", "cost",
        "money", "charge", "charged", "fee", "fees",
    ),
}


# Precompile match patterns once at import time. Each entry is a regex that
# matches the keyword as a whole word (so "clean" does not fire on "cleaner").
_TOPIC_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    topic: [re.compile(rf"\b{re.escape(kw)}\b", flags=re.IGNORECASE) for kw in keywords]
    for topic, keywords in TOPIC_KEYWORDS.items()
}


@dataclass(slots=True)
class ClassificationResult:
    """What we learned about one review."""

    topics: list[str] = field(default_factory=list)
    sentiment: str = "neutral"  # positive | negative | mixed | neutral


def _match_topics_in_text(text: str) -> set[str]:
    if not text:
        return set()
    hits: set[str] = set()
    for topic, patterns in _TOPIC_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(text):
                hits.add(topic)
                break
    return hits


def _decide_sentiment(review: ParsedReview) -> str:
    """Rule set:

    * Both positive and negative text present → mixed
    * Only positive text present → positive
    * Only negative text present → negative
    * Neither (just a title and rating) → use the 1 to 10 rating as a tiebreak,
      defaulting to neutral when no rating is available.
    """
    has_pos = bool(review.positive_text and review.positive_text.strip())
    has_neg = bool(review.negative_text and review.negative_text.strip())

    if has_pos and has_neg:
        return "mixed"
    if has_pos:
        return "positive"
    if has_neg:
        return "negative"
    if review.rating is None:
        return "neutral"
    if review.rating >= 8:
        return "positive"
    if review.rating <= 5:
        return "negative"
    return "neutral"


def classify_review(review: ParsedReview) -> ClassificationResult:
    """Run the keyword classifier. The LLM pass, if enabled, is merged on top."""
    text_blob = " ".join(
        t for t in (review.title, review.positive_text, review.negative_text) if t
    )
    topics = _match_topics_in_text(text_blob)
    return ClassificationResult(topics=sorted(topics), sentiment=_decide_sentiment(review))


class ReviewClassifier:
    """Instance wrapper used by the ingest pipeline.

    Keeps a reference to any LLM client so callers do not re-instantiate it
    on every call. The LLM path is opt-in via settings.enable_llm_topics and
    fails open: if the model is unreachable we fall back to keyword-only.
    """

    def __init__(self) -> None:
        self._llm_ready = settings.enable_llm_topics and bool(settings.llm_api_key)
        if settings.enable_llm_topics and not settings.llm_api_key:
            log.warning("enable_llm_topics is on but no llm_api_key is set, falling back to keywords")

    def classify(self, review: ParsedReview) -> ClassificationResult:
        base = classify_review(review)
        if not self._llm_ready:
            return base
        try:
            extra = self._classify_with_llm(review)
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM topic classification failed, using keywords only: %s", exc)
            return base
        merged = sorted(set(base.topics).union(extra))
        return ClassificationResult(topics=merged, sentiment=base.sentiment)

    def _classify_with_llm(self, review: ParsedReview) -> Iterable[str]:
        """Thin wrapper that asks an OpenAI-compatible endpoint for topics.

        Kept inline (instead of a client class of its own) because this is the
        only call site and we want it easy to audit.
        """
        import httpx  # local import so the dependency is optional at runtime

        prompt_text = (
            "Classify the following hotel review into zero or more of these "
            "operational topics, returning only a JSON array of topic names "
            "from the list.\n\nTopics: "
            + ", ".join(TOPIC_KEYWORDS.keys())
            + "\n\nReview:\n"
            + " | ".join(
                t for t in (review.title, review.positive_text, review.negative_text) if t
            )
        )
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": "You are a strict JSON classifier."},
                {"role": "user", "content": prompt_text},
            ],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        resp = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        import json

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        valid = set(TOPIC_KEYWORDS.keys())
        return [t for t in parsed if isinstance(t, str) and t in valid]
