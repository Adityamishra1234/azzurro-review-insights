/**
 * Dashboard shell.
 *
 * State owned here (property filter, topic filter, sentiment filter, pagination)
 * drives both the headline summary query and the paginated review feed. Keeps
 * the child components dumb: they render props, they don't fetch.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Property,
  Review,
  Summary,
  fetchProperties,
  fetchReviews,
  fetchSummary,
} from "./api";
import { StatCard } from "./components/StatCard";
import { PropertyTable } from "./components/PropertyTable";
import { TopicList } from "./components/TopicList";
import { SentimentChart } from "./components/SentimentChart";
import { ReviewFeed } from "./components/ReviewFeed";

const PAGE_SIZE = 20;

export default function App() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [reviewTotal, setReviewTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selectedProperty, setSelectedProperty] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [selectedSentiment, setSelectedSentiment] =
    useState<Review["sentiment"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchProperties()
      .then(setProperties)
      .catch((e) => setError(String(e)));
  }, []);

  const loadSummary = useCallback(() => {
    fetchSummary(selectedProperty)
      .then(setSummary)
      .catch((e) => setError(String(e)));
  }, [selectedProperty]);

  const loadReviews = useCallback(() => {
    setLoading(true);
    fetchReviews({
      propertySlug: selectedProperty,
      topic: selectedTopic,
      sentiment: selectedSentiment,
      limit: PAGE_SIZE,
      offset,
    })
      .then((res) => {
        setReviews(res.items);
        setReviewTotal(res.total);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [selectedProperty, selectedTopic, selectedSentiment, offset]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    loadReviews();
  }, [loadReviews]);

  const propertyNameBySlug = useMemo(() => {
    const map = new Map<string, string>();
    properties.forEach((p) => map.set(p.slug, p.name));
    return (slug: string) => map.get(slug) ?? slug;
  }, [properties]);

  const ratingDelta = summary?.rating_change;
  const deltaKind: "up" | "down" | "flat" | undefined =
    ratingDelta == null
      ? undefined
      : ratingDelta > 0.05
        ? "up"
        : ratingDelta < -0.05
          ? "down"
          : "flat";

  function resetFilters() {
    setSelectedProperty(null);
    setSelectedTopic(null);
    setSelectedSentiment(null);
    setOffset(0);
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">
              Azzurro Hotels, review insights
            </h1>
            <p className="text-sm text-slate-500">
              Weekly operations view, built from Booking.com guest reviews.
            </p>
          </div>
          <div className="flex gap-2 text-sm">
            <select
              value={selectedProperty ?? ""}
              onChange={(e) => {
                setOffset(0);
                setSelectedProperty(e.target.value || null);
              }}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 shadow-sm"
            >
              <option value="">All properties</option>
              {properties.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              value={selectedSentiment ?? ""}
              onChange={(e) => {
                setOffset(0);
                setSelectedSentiment(
                  (e.target.value as Review["sentiment"]) || null,
                );
              }}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 shadow-sm"
            >
              <option value="">All sentiment</option>
              <option value="positive">Positive</option>
              <option value="negative">Negative</option>
              <option value="mixed">Mixed</option>
              <option value="neutral">Neutral</option>
            </select>
            <button
              type="button"
              onClick={resetFilters}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 shadow-sm hover:bg-slate-50"
            >
              Reset
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-6">
        {error && (
          <div className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">
            {error}
          </div>
        )}

        {summary && (
          <section className="grid gap-4 md:grid-cols-4">
            <StatCard
              label="This week, avg rating"
              value={summary.this_week_average_rating?.toFixed(2) ?? "—"}
              delta={
                ratingDelta == null
                  ? undefined
                  : `${ratingDelta > 0 ? "+" : ""}${ratingDelta.toFixed(2)}`
              }
              deltaKind={deltaKind}
              hint={`${summary.this_week_review_count} reviews this week`}
            />
            <StatCard
              label="Previous week"
              value={summary.previous_week_average_rating?.toFixed(2) ?? "—"}
              hint={`${summary.previous_week_review_count} reviews`}
            />
            <StatCard
              label="This week, reviews"
              value={summary.this_week_review_count}
              hint="Across all tracked properties"
            />
            <StatCard
              label="Topics tracked"
              value={summary.topic_breakdown.length}
              hint="Topics with at least one mention"
            />
          </section>
        )}

        <section className="grid gap-4 lg:grid-cols-5">
          <div className="lg:col-span-3">
            {summary && (
              <PropertyTable
                rows={summary.property_breakdown}
                onSelect={(slug) => {
                  setOffset(0);
                  setSelectedProperty(slug === selectedProperty ? null : slug);
                }}
                selectedSlug={selectedProperty}
              />
            )}
          </div>
          <div className="lg:col-span-2">
            {summary && (
              <TopicList
                rows={summary.topic_breakdown}
                onSelect={(topic) => {
                  setOffset(0);
                  setSelectedTopic(topic === selectedTopic ? null : topic);
                }}
                selectedTopic={selectedTopic}
              />
            )}
          </div>
        </section>

        {summary && (
          <section>
            <SentimentChart
              positive={summary.positive_trend}
              negative={summary.negative_trend}
            />
          </section>
        )}

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Review feed</h2>
            {loading && <span className="text-sm text-slate-500">Loading…</span>}
          </div>
          <ReviewFeed
            reviews={reviews}
            total={reviewTotal}
            offset={offset}
            limit={PAGE_SIZE}
            onPageChange={setOffset}
            propertyName={propertyNameBySlug}
          />
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        Operations dashboard for Azzurro Hotels, review data sourced from
        Booking.com.
      </footer>
    </div>
  );
}
