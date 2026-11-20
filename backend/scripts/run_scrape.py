"""CLI: scrape Booking.com reviews for the configured properties and ingest them.

Usage
-----
Scrape every property:
    python -m scripts.run_scrape

Scrape one:
    python -m scripts.run_scrape --property olympic-paddington

Dry-run (parse without touching the DB):
    python -m scripts.run_scrape --dry-run

Designed to be run from cron or a GitHub Actions scheduled workflow. Exit
code is non-zero when every property failed, zero otherwise, so partial
failures do not block the next scheduled run.
"""
from __future__ import annotations

import asyncio
import logging
import sys

import typer
from rich.console import Console
from rich.table import Table

from app.db import init_db
from app.ingest import ingest_scrape_results
from app.properties import PROPERTIES, PROPERTIES_BY_SLUG
from app.scraper.booking import BookingScraper


console = Console()
cli = typer.Typer(add_completion=False, help="Scrape and ingest Booking.com reviews.")


@cli.command()
def main(
    property_slug: str = typer.Option(
        None,
        "--property",
        help="Scrape only one property (slug). Default: all configured properties.",
    ),
    dry_run: bool = typer.Option(False, help="Parse pages but do not write to the DB."),
    headless: bool = typer.Option(True, help="Run the browser headless."),
    max_pages: int = typer.Option(
        None, help="Hard cap on review pages per property. Overrides env."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Entry point for the CLI."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    targets = PROPERTIES
    if property_slug:
        if property_slug not in PROPERTIES_BY_SLUG:
            console.print(f"[red]unknown property: {property_slug}")
            raise typer.Exit(code=2)
        targets = [PROPERTIES_BY_SLUG[property_slug]]

    init_db()

    scraper = BookingScraper(headless=headless, max_pages=max_pages)

    try:
        results = asyncio.run(scraper.scrape(targets))
    except KeyboardInterrupt:
        console.print("[yellow]interrupted, no changes written.")
        raise typer.Exit(code=130)

    _report_scrape(results)

    if dry_run:
        console.print("[yellow]dry run, skipping DB ingest.")
        return

    stats = ingest_scrape_results(results)
    _report_ingest(stats)

    if all(r.new_review_count == 0 for r in results) and all(r.errors for r in results):
        raise typer.Exit(code=1)


def _report_scrape(results) -> None:
    table = Table(title="Scrape results")
    table.add_column("property")
    table.add_column("pages", justify="right")
    table.add_column("reviews", justify="right")
    table.add_column("errors", justify="right")
    for r in results:
        table.add_row(
            r.property_slug,
            str(r.pages_fetched),
            str(r.new_review_count),
            str(len(r.errors)),
        )
    console.print(table)
    for r in results:
        for err in r.errors:
            console.print(f"[red]{r.property_slug}: {err}")


def _report_ingest(stats) -> None:
    table = Table(title="Ingest results")
    table.add_column("property")
    table.add_column("inserted", justify="right")
    table.add_column("duplicates", justify="right")
    table.add_column("errors", justify="right")
    for s in stats:
        table.add_row(s.property_slug, str(s.inserted), str(s.duplicates), str(s.errors))
    console.print(table)


if __name__ == "__main__":
    cli()
