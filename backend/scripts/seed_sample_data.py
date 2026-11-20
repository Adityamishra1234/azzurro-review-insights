"""Seed the DB with a small synthetic dataset.

Useful for demo and for the trial reviewer: they can `pip install`, run this
script, then launch the API and dashboard without a browser scrape round-trip.
The data is fictional but shaped like real Booking reviews (positive and
negative text, 1 to 10 ratings, varied topics).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from app.db import Review, init_db, session_scope
from app.insights.classifier import classify_review
from app.scraper.hashing import review_hash
from app.scraper.parsing import ParsedReview


SAMPLE_REVIEWS: list[dict] = [
    # Olympic Paddington
    {
        "property_slug": "olympic-paddington",
        "reviewer_name": "Emma",
        "reviewer_country": "Australia",
        "stayed_in": "October 2025",
        "days_ago": 4,
        "rating": 9.2,
        "title": "Great location near the park",
        "positive": "The staff at reception were friendly and check-in was quick. Walking distance to Centennial Park.",
        "negative": None,
    },
    {
        "property_slug": "olympic-paddington",
        "reviewer_name": "Daniel",
        "reviewer_country": "United Kingdom",
        "stayed_in": "October 2025",
        "days_ago": 6,
        "rating": 6.0,
        "title": "Tired room, noisy street",
        "positive": "Breakfast was decent and wifi worked well.",
        "negative": "The room was tired and dated, carpet was worn. Street noise kept us up.",
    },
    {
        "property_slug": "olympic-paddington",
        "reviewer_name": "Priya",
        "reviewer_country": "India",
        "stayed_in": "November 2025",
        "days_ago": 2,
        "rating": 8.4,
        "title": "Comfortable stay",
        "positive": "Bed was comfortable, bathroom clean. Receptionist helped us store luggage after check-out.",
        "negative": "Lift was slow during peak hours.",
    },
    {
        "property_slug": "olympic-paddington",
        "reviewer_name": "Hiro",
        "reviewer_country": "Japan",
        "stayed_in": "November 2025",
        "days_ago": 10,
        "rating": 5.5,
        "title": "Not clean enough",
        "positive": None,
        "negative": "Found hair in the bathroom and sheets had stains. Not acceptable for the price.",
    },
    # Potts Point
    {
        "property_slug": "venus-potts-point",
        "reviewer_name": "Olivia",
        "reviewer_country": "New Zealand",
        "stayed_in": "November 2025",
        "days_ago": 3,
        "rating": 9.5,
        "title": "Loved it",
        "positive": "Staff went out of their way, location is unbeatable, close to transport and cafes.",
        "negative": None,
    },
    {
        "property_slug": "venus-potts-point",
        "reviewer_name": "Marcus",
        "reviewer_country": "Germany",
        "stayed_in": "October 2025",
        "days_ago": 8,
        "rating": 4.8,
        "title": "Overpriced",
        "positive": None,
        "negative": "Room was small and cramped, walls were thin. Not worth the money.",
    },
    {
        "property_slug": "venus-potts-point",
        "reviewer_name": "Sophie",
        "reviewer_country": "France",
        "stayed_in": "November 2025",
        "days_ago": 1,
        "rating": 7.2,
        "title": "Good for a short stay",
        "positive": "Clean and convenient for exploring Sydney. Breakfast was okay.",
        "negative": "Wifi dropped a few times.",
    },
    {
        "property_slug": "venus-potts-point",
        "reviewer_name": "Kaito",
        "reviewer_country": "Japan",
        "stayed_in": "November 2025",
        "days_ago": 12,
        "rating": 8.0,
        "title": "Nice area",
        "positive": "The neighborhood is lively with great restaurants. Staff friendly at check-in.",
        "negative": None,
    },
    # Central Sydney (Surry Hills)
    {
        "property_slug": "venus-surry-hills",
        "reviewer_name": "Chen",
        "reviewer_country": "China",
        "stayed_in": "November 2025",
        "days_ago": 5,
        "rating": 8.8,
        "title": "Spacious room, central",
        "positive": "Room was spacious and modern. Central Sydney location. Good value.",
        "negative": None,
    },
    {
        "property_slug": "venus-surry-hills",
        "reviewer_name": "Lauren",
        "reviewer_country": "United States",
        "stayed_in": "October 2025",
        "days_ago": 7,
        "rating": 6.5,
        "title": "Noisy and mixed",
        "positive": "Location is central, easy walking distance to everything.",
        "negative": "Street noise was loud all night, could hear music from a nearby bar.",
    },
    {
        "property_slug": "venus-surry-hills",
        "reviewer_name": "Ravi",
        "reviewer_country": "India",
        "stayed_in": "November 2025",
        "days_ago": 15,
        "rating": 9.0,
        "title": "Exceeded expectations",
        "positive": "Excellent service, very clean, comfortable bed. Receptionist was polite and helpful.",
        "negative": None,
    },
    # Darling Harbour (Chateau de Venus)
    {
        "property_slug": "chateau-de-venus",
        "reviewer_name": "Isabella",
        "reviewer_country": "Italy",
        "stayed_in": "November 2025",
        "days_ago": 3,
        "rating": 9.7,
        "title": "Perfect view of Darling Harbour",
        "positive": "The view was amazing, room was spotless, staff was very friendly.",
        "negative": None,
    },
    {
        "property_slug": "chateau-de-venus",
        "reviewer_name": "Jack",
        "reviewer_country": "United Kingdom",
        "stayed_in": "October 2025",
        "days_ago": 9,
        "rating": 5.0,
        "title": "Not what we expected",
        "positive": "Location was good for the harbour area.",
        "negative": "Room smelled musty, aircon did not work properly, front desk unhelpful.",
    },
    {
        "property_slug": "chateau-de-venus",
        "reviewer_name": "Mei",
        "reviewer_country": "Taiwan",
        "stayed_in": "November 2025",
        "days_ago": 2,
        "rating": 8.1,
        "title": "Comfortable",
        "positive": "Comfortable stay, clean room, good breakfast.",
        "negative": "Check-in took a while on arrival.",
    },
    {
        "property_slug": "chateau-de-venus",
        "reviewer_name": "Diego",
        "reviewer_country": "Spain",
        "stayed_in": "November 2025",
        "days_ago": 6,
        "rating": 7.0,
        "title": "Decent value",
        "positive": "Decent value for the central location. Wifi fast.",
        "negative": "Bathroom was quite small.",
    },
]


def run() -> None:
    random.seed(7)
    init_db()
    now = datetime.utcnow().replace(microsecond=0)
    with session_scope() as session:
        inserted = 0
        for row in SAMPLE_REVIEWS:
            review_date = now - timedelta(days=row["days_ago"])
            parsed = ParsedReview(
                reviewer_name=row["reviewer_name"],
                reviewer_country=row["reviewer_country"],
                stayed_in=row["stayed_in"],
                review_date=review_date,
                review_date_raw=review_date.date().isoformat(),
                rating=row["rating"],
                title=row["title"],
                positive_text=row.get("positive"),
                negative_text=row.get("negative"),
            )
            classification = classify_review(parsed)
            rh = review_hash(
                row["property_slug"],
                parsed.reviewer_name,
                review_date.date().isoformat(),
                parsed.positive_text,
                parsed.negative_text,
            )
            exists = session.get(Review, rh)
            if exists:
                continue
            review = Review(
                review_hash=rh,
                property_slug=row["property_slug"],
                reviewer_name=parsed.reviewer_name,
                reviewer_country=parsed.reviewer_country,
                stayed_in=parsed.stayed_in,
                review_date=parsed.review_date,
                rating=parsed.rating,
                positive_text=parsed.positive_text,
                negative_text=parsed.negative_text,
                title=parsed.title,
                sentiment=classification.sentiment,
            )
            review.topics = classification.topics
            session.add(review)
            inserted += 1
        print(f"seeded {inserted} sample reviews")


if __name__ == "__main__":
    run()
