"""HTML parsing for Booking.com review cards.

Isolated from the Playwright driver so it can be unit-tested against saved
HTML fixtures without a browser. Selectors are grouped by card version
(classic and the 2024 redesign). The parser tries each in order and returns
whichever yields at least one card.

Design notes
------------
* Every selector is fallback-first. If Booking changes a class name we lose
  that *field* on that card, not the whole run.
* Dates are parsed from several English and ISO formats then returned as
  naive UTC datetimes. We keep the original string too so an analyst can
  cross-check.
* Ratings on Booking are published on a 1 to 10 scale.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from bs4 import BeautifulSoup, Tag


@dataclass(slots=True)
class ParsedReview:
    """One review as extracted from the page, before dedupe or topic tagging."""

    reviewer_name: str | None
    reviewer_country: str | None
    stayed_in: str | None
    review_date: datetime | None
    review_date_raw: str | None
    rating: float | None
    title: str | None
    positive_text: str | None
    negative_text: str | None


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _first_text(node: Tag | None, selectors: Iterable[str]) -> str | None:
    """Return the trimmed text of the first selector that matches."""
    if node is None:
        return None
    for sel in selectors:
        hit = node.select_one(sel)
        if hit and hit.get_text(strip=True):
            return hit.get_text(" ", strip=True)
    return None


def _parse_date(raw: str | None) -> datetime | None:
    """Best-effort parsing of Booking's several date formats."""
    if not raw:
        return None
    raw = raw.strip()

    # "Reviewed: 12 October 2025" / "Reviewed 12 October 2025"
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m:
        day, month, year = m.group(1), m.group(2).lower(), m.group(3)
        if month in _MONTHS:
            try:
                return datetime(int(year), _MONTHS[month], int(day))
            except ValueError:
                return None

    # "October 2025" (stay month)
    m = re.match(r"([A-Za-z]+)\s+(\d{4})$", raw)
    if m and m.group(1).lower() in _MONTHS:
        try:
            return datetime(int(m.group(2)), _MONTHS[m.group(1).lower()], 1)
        except ValueError:
            return None

    # ISO "2025-10-12"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _parse_rating(raw: str | None) -> float | None:
    if not raw:
        return None
    # Booking shows "9.3" or "Scored 9.3"
    m = re.search(r"(\d+(?:\.\d+)?)", raw)
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    # Guard against stray "10" being treated as percent vs 1-10 scale
    if val > 10:
        return None
    return val


def parse_review_cards(html: str) -> list[ParsedReview]:
    """Return all reviews found on one page of Booking.com HTML."""
    soup = BeautifulSoup(html, "lxml")

    card_selectors = [
        "div[data-testid='review-card']",         # 2024 redesign
        "li.review_list_new_item_block",          # classic list
        "div.c-review-block",                     # another variant
    ]
    cards: list[Tag] = []
    for sel in card_selectors:
        hit = soup.select(sel)
        if hit:
            cards = hit
            break
    reviews: list[ParsedReview] = []
    for card in cards:
        reviews.append(_parse_single_card(card))
    return [r for r in reviews if r.positive_text or r.negative_text or r.title]


def _parse_single_card(card: Tag) -> ParsedReview:
    name = _first_text(card, [
        "[data-testid='review-avatar-name']",
        ".bui-avatar-block__title",
        ".c-review-block__guest .bui-avatar-block__title",
    ])
    country = _first_text(card, [
        "[data-testid='review-avatar-country']",
        ".bui-avatar-block__subtitle",
    ])
    stayed_in_raw = _first_text(card, [
        "[data-testid='review-stay-date']",
        ".c-review-block__stay-date",
    ])
    review_date_raw = _first_text(card, [
        "[data-testid='review-date']",
        ".c-review-block__date",
    ])
    rating_raw = _first_text(card, [
        "[data-testid='review-score']",
        ".bui-review-score__badge",
    ])
    title = _first_text(card, [
        "[data-testid='review-title']",
        "h3.c-review-block__title",
    ])
    positive = _first_text(card, [
        "[data-testid='review-positive-text']",
        ".c-review__body--positive",
    ])
    negative = _first_text(card, [
        "[data-testid='review-negative-text']",
        ".c-review__body--negative",
    ])

    return ParsedReview(
        reviewer_name=name,
        reviewer_country=country,
        stayed_in=stayed_in_raw,
        review_date=_parse_date(review_date_raw),
        review_date_raw=review_date_raw,
        rating=_parse_rating(rating_raw),
        title=title,
        positive_text=positive,
        negative_text=negative,
    )
