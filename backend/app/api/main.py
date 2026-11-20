"""FastAPI application exposing the operations dashboard endpoints.

Endpoints
---------
* GET /api/properties: static list of the tracked properties.
* GET /api/reviews: paginated review feed with date, property, topic filters.
* GET /api/summary: everything the headline cards and charts need in one call.
* GET /api/health: trivial liveness probe.

The one-call /summary endpoint keeps the frontend simple: one fetch per page
load, one source of truth for the numbers. For a larger app we would split
these into per-widget endpoints that can be refreshed independently.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import Review, SessionLocal, init_db
from ..properties import PROPERTIES, PROPERTIES_BY_SLUG
from .schemas import (
    PropertyBreakdown,
    PropertyOut,
    ReviewListOut,
    ReviewOut,
    SummaryOut,
    TopicBreakdown,
)


log = logging.getLogger(__name__)
app = FastAPI(
    title="Azzurro Hotels Review Insights",
    version="0.1.0",
    description="Operations-facing API that serves Booking.com review insights.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _db() -> Session:
    return SessionLocal()


def _week_bounds(reference: datetime | None = None) -> tuple[datetime, datetime]:
    """Monday 00:00 to next Monday 00:00 (UTC). Reference defaults to now."""
    ref = reference or datetime.utcnow()
    start = (ref - timedelta(days=ref.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=7)


def _review_to_out(r: Review) -> ReviewOut:
    return ReviewOut(
        review_hash=r.review_hash,
        property_slug=r.property_slug,
        reviewer_name=r.reviewer_name,
        reviewer_country=r.reviewer_country,
        stayed_in=r.stayed_in,
        review_date=r.review_date,
        rating=r.rating,
        positive_text=r.positive_text,
        negative_text=r.negative_text,
        title=r.title,
        topics=r.topics,
        sentiment=r.sentiment or "neutral",
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/properties", response_model=list[PropertyOut])
def list_properties() -> list[PropertyOut]:
    return [PropertyOut(slug=p.slug, name=p.name, city=p.city) for p in PROPERTIES]


@app.get("/api/reviews", response_model=ReviewListOut)
def list_reviews(
    property_slug: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    sentiment: Literal["positive", "negative", "mixed", "neutral"] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ReviewListOut:
    """Paginated review list. Topic filter is case-sensitive, matching the dashboard chips."""
    if property_slug and property_slug not in PROPERTIES_BY_SLUG:
        raise HTTPException(status_code=400, detail="unknown property_slug")

    with _db() as session:
        stmt = select(Review)
        if property_slug:
            stmt = stmt.where(Review.property_slug == property_slug)
        if sentiment:
            stmt = stmt.where(Review.sentiment == sentiment)
        if start_date:
            stmt = stmt.where(Review.review_date >= start_date)
        if end_date:
            stmt = stmt.where(Review.review_date < end_date)
        stmt = stmt.order_by(Review.review_date.desc().nullslast())

        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = session.execute(stmt.limit(limit).offset(offset)).scalars().all()

    items = [_review_to_out(r) for r in rows if (topic is None or topic in r.topics)]
    return ReviewListOut(total=total, items=items)


@app.get("/api/summary", response_model=SummaryOut)
def summary(
    property_slug: str | None = Query(default=None),
) -> SummaryOut:
    """All headline metrics for the current week, previous week, and trends."""
    if property_slug and property_slug not in PROPERTIES_BY_SLUG:
        raise HTTPException(status_code=400, detail="unknown property_slug")

    this_start, this_end = _week_bounds()
    prev_start = this_start - timedelta(days=7)

    with _db() as session:
        def base_query():
            s = select(Review)
            if property_slug:
                s = s.where(Review.property_slug == property_slug)
            return s

        this_week_rows = session.execute(
            base_query().where(Review.review_date >= this_start, Review.review_date < this_end)
        ).scalars().all()
        prev_week_rows = session.execute(
            base_query().where(Review.review_date >= prev_start, Review.review_date < this_start)
        ).scalars().all()
        all_rows = session.execute(base_query()).scalars().all()

    this_avg = _avg_rating(this_week_rows)
    prev_avg = _avg_rating(prev_week_rows)
    change = None if this_avg is None or prev_avg is None else round(this_avg - prev_avg, 2)

    property_breakdown = _property_breakdown(this_week_rows)
    topic_breakdown = _topic_breakdown(this_week_rows)
    positive_trend, negative_trend = _sentiment_trend(all_rows)

    return SummaryOut(
        week_start=this_start,
        week_end=this_end,
        this_week_average_rating=this_avg,
        this_week_review_count=len(this_week_rows),
        previous_week_average_rating=prev_avg,
        previous_week_review_count=len(prev_week_rows),
        rating_change=change,
        property_breakdown=property_breakdown,
        topic_breakdown=topic_breakdown,
        positive_trend=positive_trend,
        negative_trend=negative_trend,
    )


def _avg_rating(rows: list[Review]) -> float | None:
    values = [r.rating for r in rows if r.rating is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _property_breakdown(rows: list[Review]) -> list[PropertyBreakdown]:
    """One row per property, always returning all four even when a property has no reviews."""
    by_slug: dict[str, list[Review]] = {p.slug: [] for p in PROPERTIES}
    for r in rows:
        if r.property_slug in by_slug:
            by_slug[r.property_slug].append(r)

    breakdown = []
    for slug, items in by_slug.items():
        prop = PROPERTIES_BY_SLUG[slug]
        pos = sum(1 for r in items if r.sentiment == "positive")
        neg = sum(1 for r in items if r.sentiment == "negative")
        breakdown.append(
            PropertyBreakdown(
                property_slug=slug,
                property_name=prop.name,
                review_count=len(items),
                average_rating=_avg_rating(items),
                positive_count=pos,
                negative_count=neg,
            )
        )
    return breakdown


def _topic_breakdown(rows: list[Review]) -> list[TopicBreakdown]:
    counter: Counter[str] = Counter()
    pos_by_topic: Counter[str] = Counter()
    neg_by_topic: Counter[str] = Counter()
    for r in rows:
        for t in r.topics:
            counter[t] += 1
            if r.sentiment == "positive":
                pos_by_topic[t] += 1
            elif r.sentiment == "negative":
                neg_by_topic[t] += 1

    out: list[TopicBreakdown] = []
    for topic, count in counter.most_common():
        out.append(
            TopicBreakdown(
                topic=topic,
                count=count,
                positive_share=round(pos_by_topic[topic] / count, 2) if count else 0,
                negative_share=round(neg_by_topic[topic] / count, 2) if count else 0,
            )
        )
    return out


def _sentiment_trend(rows: list[Review]) -> tuple[list[dict], list[dict]]:
    """Daily positive and negative review counts for the last 30 days."""
    today = datetime.utcnow().date()
    window_start = today - timedelta(days=30)
    buckets: dict[str, dict[str, int]] = {}
    for r in rows:
        if not r.review_date:
            continue
        d = r.review_date.date()
        if d < window_start or d > today:
            continue
        key = d.isoformat()
        bucket = buckets.setdefault(key, {"positive": 0, "negative": 0})
        if r.sentiment == "positive":
            bucket["positive"] += 1
        elif r.sentiment == "negative":
            bucket["negative"] += 1

    # Fill empty days so the chart line does not jump gaps.
    positive: list[dict] = []
    negative: list[dict] = []
    for offset in range(31):
        d = window_start + timedelta(days=offset)
        key = d.isoformat()
        b = buckets.get(key, {"positive": 0, "negative": 0})
        positive.append({"date": key, "count": b["positive"]})
        negative.append({"date": key, "count": b["negative"]})
    return positive, negative
