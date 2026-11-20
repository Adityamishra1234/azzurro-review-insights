/**
 * Thin fetch client for the FastAPI backend.
 *
 * Centralised so a change to the base URL, auth header, or error handling
 * touches one file. VITE_API_BASE_URL overrides the default dev proxy path.
 */

const BASE = import.meta.env.VITE_API_BASE_URL || "";

export interface Property {
  slug: string;
  name: string;
  city: string;
}

export interface Review {
  review_hash: string;
  property_slug: string;
  reviewer_name: string | null;
  reviewer_country: string | null;
  stayed_in: string | null;
  review_date: string | null;
  rating: number | null;
  positive_text: string | null;
  negative_text: string | null;
  title: string | null;
  topics: string[];
  sentiment: "positive" | "negative" | "mixed" | "neutral";
}

export interface ReviewList {
  total: number;
  items: Review[];
}

export interface PropertyBreakdown {
  property_slug: string;
  property_name: string;
  review_count: number;
  average_rating: number | null;
  positive_count: number;
  negative_count: number;
}

export interface TopicBreakdown {
  topic: string;
  count: number;
  positive_share: number;
  negative_share: number;
}

export interface Summary {
  week_start: string;
  week_end: string;
  this_week_average_rating: number | null;
  this_week_review_count: number;
  previous_week_average_rating: number | null;
  previous_week_review_count: number;
  rating_change: number | null;
  property_breakdown: PropertyBreakdown[];
  topic_breakdown: TopicBreakdown[];
  positive_trend: { date: string; count: number }[];
  negative_trend: { date: string; count: number }[];
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!resp.ok) {
    throw new Error(`GET ${path} failed: ${resp.status} ${resp.statusText}`);
  }
  return (await resp.json()) as T;
}

export function fetchProperties(): Promise<Property[]> {
  return get<Property[]>("/api/properties");
}

export function fetchSummary(propertySlug?: string | null): Promise<Summary> {
  const q = propertySlug ? `?property_slug=${encodeURIComponent(propertySlug)}` : "";
  return get<Summary>(`/api/summary${q}`);
}

export function fetchReviews(params: {
  propertySlug?: string | null;
  topic?: string | null;
  sentiment?: Review["sentiment"] | null;
  startDate?: string | null;
  endDate?: string | null;
  limit?: number;
  offset?: number;
}): Promise<ReviewList> {
  const search = new URLSearchParams();
  if (params.propertySlug) search.set("property_slug", params.propertySlug);
  if (params.topic) search.set("topic", params.topic);
  if (params.sentiment) search.set("sentiment", params.sentiment);
  if (params.startDate) search.set("start_date", params.startDate);
  if (params.endDate) search.set("end_date", params.endDate);
  search.set("limit", String(params.limit ?? 50));
  search.set("offset", String(params.offset ?? 0));
  return get<ReviewList>(`/api/reviews?${search.toString()}`);
}
