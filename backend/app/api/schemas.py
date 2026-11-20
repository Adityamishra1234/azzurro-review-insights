"""Pydantic response models for the dashboard API.

Kept separate from the ORM so a schema change on the DB does not accidentally
leak to the frontend. Field names mirror what the React code expects.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PropertyOut(BaseModel):
    slug: str
    name: str
    city: str


class ReviewOut(BaseModel):
    review_hash: str
    property_slug: str
    reviewer_name: str | None
    reviewer_country: str | None
    stayed_in: str | None
    review_date: datetime | None
    rating: float | None
    positive_text: str | None
    negative_text: str | None
    title: str | None
    topics: list[str]
    sentiment: Literal["positive", "negative", "mixed", "neutral"]


class ReviewListOut(BaseModel):
    total: int
    items: list[ReviewOut]


class PropertyBreakdown(BaseModel):
    property_slug: str
    property_name: str
    review_count: int
    average_rating: float | None
    positive_count: int
    negative_count: int


class TopicBreakdown(BaseModel):
    topic: str
    count: int
    positive_share: float
    negative_share: float


class SummaryOut(BaseModel):
    """Headline numbers for the dashboard."""

    week_start: datetime
    week_end: datetime
    this_week_average_rating: float | None
    this_week_review_count: int
    previous_week_average_rating: float | None
    previous_week_review_count: int
    rating_change: float | None
    property_breakdown: list[PropertyBreakdown]
    topic_breakdown: list[TopicBreakdown]
    positive_trend: list[dict]
    negative_trend: list[dict]
