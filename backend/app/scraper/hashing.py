"""Stable review identifiers.

Booking.com does not expose a public review ID in the DOM, so we synthesise
one from fields that are unlikely to change for the same comment: the
property slug, the reviewer's first name, the stay month, and the first 200
characters of the combined text. Trailing whitespace and case are normalised
first so a cosmetic HTML change does not create a duplicate row.
"""
from __future__ import annotations

import hashlib
import re


_whitespace_re = re.compile(r"\s+")


def _normalise(text: str | None) -> str:
    if not text:
        return ""
    collapsed = _whitespace_re.sub(" ", text.strip()).lower()
    return collapsed[:400]


def review_hash(
    property_slug: str,
    reviewer_name: str | None,
    review_date_iso: str | None,
    positive_text: str | None,
    negative_text: str | None,
) -> str:
    """Return a 40-character hex digest that uniquely identifies the review.

    Hash inputs are all normalised, so trivial reformatting on Booking.com's
    side does not change the digest and therefore does not create a duplicate
    database row on the next scrape.
    """
    parts = [
        property_slug.strip().lower(),
        _normalise(reviewer_name),
        (review_date_iso or "").strip()[:10],
        _normalise(positive_text),
        _normalise(negative_text),
    ]
    digest = hashlib.sha1("||".join(parts).encode("utf-8"))
    return digest.hexdigest()
