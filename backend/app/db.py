"""Database setup and ORM models.

One table (reviews) keeps the schema trivial and the dedupe story clear: each
row is identified by a stable hash that survives small formatting changes to
the source page. Topic tags are stored as a JSON blob to avoid a second table
for a small dataset. If the volume grows past a few million rows, split topics
into their own normalised table.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Index, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import settings


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class Review(Base):
    """A single Booking.com guest review.

    review_hash is the primary key so re-runs of the scraper are idempotent.
    created_at tracks when we first saw the review in our dataset, so we can
    distinguish "new since last scrape" from "stale rows we already had".
    """

    __tablename__ = "reviews"

    review_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    property_slug: Mapped[str] = mapped_column(String(64), index=True)
    reviewer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewer_country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stayed_in: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    positive_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    topics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_reviews_property_date", "property_slug", "review_date"),
    )

    @property
    def topics(self) -> list[str]:
        """Parsed topics list. Empty when the JSON is missing or malformed."""
        if not self.topics_json:
            return []
        try:
            parsed = json.loads(self.topics_json)
        except json.JSONDecodeError:
            return []
        return [str(t) for t in parsed] if isinstance(parsed, list) else []

    @topics.setter
    def topics(self, value: list[str]) -> None:
        self.topics_json = json.dumps(sorted(set(value)))


def init_db() -> None:
    """Create tables if they do not yet exist. Safe to call on every boot."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context-managed session that commits on success and rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
