"""Ingest layer: scrape results in, DB rows out.

Keeps the scraper agnostic of storage and the DB agnostic of parsing. One
place to look when a review is dropped silently (hint: either the hash
matched an existing row, or the classifier tagged nothing and we still kept
it, just without topics).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from .db import Review, session_scope
from .insights.classifier import ReviewClassifier
from .scraper.booking import ScrapeResult


log = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestStats:
    """Counts surfaced on the CLI so operators can tell if a run was useful."""

    property_slug: str
    inserted: int = 0
    duplicates: int = 0
    errors: int = 0


def ingest_scrape_results(results: list[ScrapeResult]) -> list[IngestStats]:
    """Write the scraped reviews into the DB, deduped by review_hash."""
    classifier = ReviewClassifier()
    stats: list[IngestStats] = []

    for result in results:
        s = IngestStats(property_slug=result.property_slug)
        for review_h, parsed in result.reviews:
            try:
                classification = classifier.classify(parsed)
                with session_scope() as session:
                    stmt = sqlite_insert(Review).values(
                        review_hash=review_h,
                        property_slug=result.property_slug,
                        reviewer_name=parsed.reviewer_name,
                        reviewer_country=parsed.reviewer_country,
                        stayed_in=parsed.stayed_in,
                        review_date=parsed.review_date,
                        rating=parsed.rating,
                        positive_text=parsed.positive_text,
                        negative_text=parsed.negative_text,
                        title=parsed.title,
                        topics_json=None,
                        sentiment=classification.sentiment,
                    )
                    # On conflict, do nothing. We do NOT update existing rows so
                    # the created_at field continues to mark first discovery.
                    stmt = stmt.on_conflict_do_nothing(index_elements=["review_hash"])
                    inserted = session.execute(stmt).rowcount
                    if inserted:
                        # topics live in a getter / setter so we update the row
                        # in a second statement. Done inside the same session
                        # so it rolls back together on error.
                        review_obj = session.get(Review, review_h)
                        if review_obj is not None:
                            review_obj.topics = classification.topics
                        s.inserted += 1
                    else:
                        s.duplicates += 1
            except SQLAlchemyError as exc:
                log.exception("DB error for %s hash=%s: %s", result.property_slug, review_h, exc)
                s.errors += 1
        stats.append(s)
    return stats
