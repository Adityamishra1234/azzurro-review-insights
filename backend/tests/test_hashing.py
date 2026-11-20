"""Hash stability tests."""
from __future__ import annotations

from app.scraper.hashing import review_hash


def test_same_inputs_same_hash() -> None:
    a = review_hash("prop", "Emma", "2025-10-01", "Great stay", None)
    b = review_hash("prop", "Emma", "2025-10-01", "Great stay", None)
    assert a == b


def test_whitespace_differences_do_not_change_hash() -> None:
    a = review_hash("prop", " emma ", "2025-10-01", "Great   stay", None)
    b = review_hash("prop", "Emma", "2025-10-01", "Great stay", None)
    assert a == b


def test_different_property_different_hash() -> None:
    a = review_hash("prop-a", "Emma", "2025-10-01", "Great stay", None)
    b = review_hash("prop-b", "Emma", "2025-10-01", "Great stay", None)
    assert a != b
