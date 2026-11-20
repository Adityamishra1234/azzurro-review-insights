/**
 * Scrollable review feed with simple pagination.
 *
 * Each card shows positive and negative text side by side so an ops user
 * does not have to click through to read the full review.
 */
import { Review } from "../api";
import { format, parseISO } from "date-fns";

interface Props {
  reviews: Review[];
  total: number;
  offset: number;
  limit: number;
  onPageChange: (newOffset: number) => void;
  propertyName: (slug: string) => string;
}

const sentimentColor: Record<Review["sentiment"], string> = {
  positive: "bg-emerald-100 text-emerald-800",
  negative: "bg-rose-100 text-rose-800",
  mixed: "bg-amber-100 text-amber-800",
  neutral: "bg-slate-100 text-slate-700",
};

export function ReviewFeed({
  reviews,
  total,
  offset,
  limit,
  onPageChange,
  propertyName,
}: Props) {
  if (reviews.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
        No reviews match the current filters.
      </div>
    );
  }

  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="space-y-3">
      {reviews.map((r) => (
        <article
          key={r.review_hash}
          className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <header className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${sentimentColor[r.sentiment]}`}>
                {r.sentiment}
              </span>
              <span className="text-sm font-medium text-slate-900">
                {propertyName(r.property_slug)}
              </span>
              <span className="text-xs text-slate-500">
                {r.review_date ? format(parseISO(r.review_date), "d MMM yyyy") : "—"}
              </span>
            </div>
            <div className="text-sm font-semibold text-slate-800">
              {r.rating != null ? r.rating.toFixed(1) : "—"}
            </div>
          </header>
          {r.title && (
            <h4 className="mt-2 text-base font-semibold text-slate-900">{r.title}</h4>
          )}
          <div className="mt-2 grid gap-3 md:grid-cols-2">
            {r.positive_text && (
              <div className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-900">
                <div className="text-xs font-semibold uppercase text-emerald-700">
                  Liked
                </div>
                <p className="mt-1 leading-snug">{r.positive_text}</p>
              </div>
            )}
            {r.negative_text && (
              <div className="rounded-md bg-rose-50 p-3 text-sm text-rose-900">
                <div className="text-xs font-semibold uppercase text-rose-700">
                  Disliked
                </div>
                <p className="mt-1 leading-snug">{r.negative_text}</p>
              </div>
            )}
          </div>
          <footer className="mt-3 flex flex-wrap gap-2">
            {r.topics.map((t) => (
              <span
                key={t}
                className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
              >
                {t}
              </span>
            ))}
            <span className="ml-auto text-xs text-slate-500">
              {r.reviewer_name} {r.reviewer_country && `, ${r.reviewer_country}`}
            </span>
          </footer>
        </article>
      ))}

      <div className="flex items-center justify-between pt-2 text-sm text-slate-600">
        <div>
          Page {page} of {pages}, {total} reviews
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
            disabled={offset === 0}
            onClick={() => onPageChange(Math.max(0, offset - limit))}
          >
            Previous
          </button>
          <button
            type="button"
            className="rounded-md border border-slate-300 px-3 py-1 disabled:opacity-40"
            disabled={offset + limit >= total}
            onClick={() => onPageChange(offset + limit)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
