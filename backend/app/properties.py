"""Hard-coded property list for the trial.

The four Azzurro Hotels properties the ops team cares about. Kept in code
(rather than a config file) because the task brief names them explicitly and
the dataset is small. Add or edit entries here, no schema changes needed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Property:
    """A Booking.com property we scrape reviews for."""

    slug: str
    name: str
    booking_url: str
    city: str


PROPERTIES: list[Property] = [
    Property(
        slug="olympic-paddington",
        name="Olympic Hotel Paddington",
        booking_url="https://www.booking.com/hotel/au/olympic-paddington.html",
        city="Sydney",
    ),
    Property(
        slug="venus-potts-point",
        name="Potts Point",
        booking_url="https://www.booking.com/hotel/au/venus-potts-point-sydney.html",
        city="Sydney",
    ),
    Property(
        slug="venus-surry-hills",
        name="Central Sydney",
        booking_url="https://www.booking.com/hotel/au/venus-surry-hills.html",
        city="Sydney",
    ),
    Property(
        slug="chateau-de-venus",
        name="Darling Harbour",
        booking_url="https://www.booking.com/hotel/au/chateau-de-venus.html",
        city="Sydney",
    ),
]

PROPERTIES_BY_SLUG: dict[str, Property] = {p.slug: p for p in PROPERTIES}
