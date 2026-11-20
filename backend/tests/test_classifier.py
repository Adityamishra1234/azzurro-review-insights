"""Unit tests for the keyword classifier.

A small set of focused cases. Confirms the classifier picks up the right
topic for obvious signals (cleanliness, noise, staff) and that the sentiment
rule follows the stated logic.
"""
from __future__ import annotations

from app.insights.classifier import classify_review
from app.scraper.parsing import ParsedReview


def _review(positive: str | None = None, negative: str | None = None, rating: float | None = None):
    return ParsedReview(
        reviewer_name="Test",
        reviewer_country="AU",
        stayed_in=None,
        review_date=None,
        review_date_raw=None,
        rating=rating,
        title=None,
        positive_text=positive,
        negative_text=negative,
    )


def test_cleanliness_detected_from_negative_text() -> None:
    result = classify_review(_review(negative="Bathroom was dirty and sheets had stains."))
    assert "Cleanliness" in result.topics
    assert result.sentiment == "negative"


def test_noise_detected() -> None:
    result = classify_review(_review(negative="Street noise kept us awake all night."))
    assert "Noise" in result.topics


def test_staff_praise_marked_positive() -> None:
    result = classify_review(_review(positive="Staff were friendly and helpful at the front desk."))
    assert "Staff or receptionist behaviour" in result.topics
    assert result.sentiment == "positive"


def test_mixed_sentiment_when_both_sides_present() -> None:
    result = classify_review(
        _review(
            positive="Location was great, walking distance to the station.",
            negative="Room was small and overpriced.",
        )
    )
    assert "Location" in result.topics
    assert "Value for money" in result.topics
    assert result.sentiment == "mixed"


def test_neutral_when_no_signal() -> None:
    result = classify_review(_review(rating=7.0))
    assert result.topics == []
    assert result.sentiment == "neutral"
