"""Playwright driver for Booking.com review pages.

Booking exposes no public review API, so this module uses a real browser to
load each property's reviews tab and iterate through the pagination. Each
page's HTML is passed to the stateless parser in parsing.py. The scraper
itself is responsible for navigation, retries, and graceful shutdown.

Reliability choices
-------------------
* Playwright with Chromium: handles the JavaScript-rendered pagination that
  plain HTTP cannot. More fragile against anti-bot responses than the mobile
  web site, but matches what a real guest sees.
* Retries with exponential backoff via tenacity, capped so one dead property
  does not stall the whole run.
* A hard per-property page cap (configurable) prevents a bug in pagination
  detection from scraping forever.
* Every page's raw HTML is written to data/snapshots/ so a parsing bug can
  be reproduced offline without hitting Booking again.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import DATA_DIR, settings
from ..properties import Property
from .hashing import review_hash
from .parsing import ParsedReview, parse_review_cards

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page


log = logging.getLogger(__name__)


@dataclass(slots=True)
class ScrapeResult:
    """Outcome of one property scrape, consumed by the ingest layer."""

    property_slug: str
    reviews: list[tuple[str, ParsedReview]] = field(default_factory=list)
    pages_fetched: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None

    @property
    def new_review_count(self) -> int:
        return len(self.reviews)


class BookingScraper:
    """Browse Booking.com review pages for the supplied properties."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        max_pages: int | None = None,
        snapshot_dir: Path | None = None,
    ) -> None:
        self._headless = settings.scrape_headless if headless is None else headless
        self._max_pages = max_pages or settings.scrape_max_pages_per_property
        self._snapshot_dir = snapshot_dir or (DATA_DIR / "snapshots")
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

    async def scrape(self, properties: list[Property]) -> list[ScrapeResult]:
        """Scrape each property sequentially. One failure does not abort the rest."""
        # Import inside the method so the module can still be imported in
        # environments where Playwright is not installed (unit tests, CI).
        from playwright.async_api import async_playwright

        results: list[ScrapeResult] = []
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._headless)
            try:
                for prop in properties:
                    result = ScrapeResult(property_slug=prop.slug)
                    try:
                        await self._scrape_property(browser, prop, result)
                    except Exception as exc:  # noqa: BLE001
                        log.exception("property %s failed", prop.slug)
                        result.errors.append(f"fatal: {exc!r}")
                    result.finished_at = datetime.utcnow()
                    results.append(result)
            finally:
                await browser.close()
        return results

    @retry(wait=wait_exponential(min=2, max=20), stop=stop_after_attempt(3), reraise=True)
    async def _open_property(self, browser: "Browser", prop: Property) -> "Page":
        context = await browser.new_context(
            user_agent=settings.scrape_user_agent,
            viewport={"width": 1366, "height": 900},
            locale="en-AU",
        )
        page = await context.new_page()
        reviews_url = f"{prop.booking_url}?tab=reviews"
        await page.goto(
            reviews_url,
            wait_until="domcontentloaded",
            timeout=settings.scrape_request_timeout_seconds * 1000,
        )
        # Dismiss the genius / cookie banners if they appear.
        for selector in (
            "button#onetrust-accept-btn-handler",
            "button[aria-label='Dismiss sign in information.']",
        ):
            try:
                await page.locator(selector).first.click(timeout=1500)
            except Exception:  # noqa: BLE001
                pass
        return page

    async def _scrape_property(
        self,
        browser: "Browser",
        prop: Property,
        result: ScrapeResult,
    ) -> None:
        import asyncio

        page = await self._open_property(browser, prop)
        try:
            for page_index in range(1, self._max_pages + 1):
                await asyncio.sleep(settings.scrape_page_delay_seconds)
                html = await page.content()
                self._write_snapshot(prop.slug, page_index, html)
                parsed = parse_review_cards(html)
                for review in parsed:
                    date_iso = review.review_date.date().isoformat() if review.review_date else None
                    rh = review_hash(
                        prop.slug,
                        review.reviewer_name,
                        date_iso,
                        review.positive_text,
                        review.negative_text,
                    )
                    result.reviews.append((rh, review))
                result.pages_fetched += 1

                # Pagination: try the aria-label next, then a generic next link.
                next_button = page.locator(
                    "button[aria-label='Next page'], a[aria-label='Next page']"
                ).first
                if await next_button.count() == 0 or not await next_button.is_enabled():
                    break
                try:
                    await next_button.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception as exc:  # noqa: BLE001
                    result.errors.append(f"pagination failed on page {page_index}: {exc!r}")
                    break
        finally:
            await page.context.close()

    def _write_snapshot(self, slug: str, page_index: int, html: str) -> None:
        """Keep every fetched page on disk for offline debugging."""
        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        out = self._snapshot_dir / f"{slug}-{stamp}-p{page_index:02d}.html"
        try:
            out.write_text(html, encoding="utf-8")
        except OSError as exc:  # noqa: BLE001
            log.warning("failed to persist snapshot %s: %s", out, exc)
