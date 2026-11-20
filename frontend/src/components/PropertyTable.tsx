/**
 * Property-by-property breakdown. Readable at a glance by non-tech staff:
 * name, review count, average rating, positive and negative share.
 */
import { PropertyBreakdown } from "../api";

interface Props {
  rows: PropertyBreakdown[];
  onSelect?: (slug: string) => void;
  selectedSlug?: string | null;
}

export function PropertyTable({ rows, onSelect, selectedSlug }: Props) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3 text-left">Property</th>
            <th className="px-4 py-3 text-right">Reviews</th>
            <th className="px-4 py-3 text-right">Avg rating</th>
            <th className="px-4 py-3 text-right">Positive</th>
            <th className="px-4 py-3 text-right">Negative</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => {
            const isSelected = selectedSlug === r.property_slug;
            return (
              <tr
                key={r.property_slug}
                className={`cursor-pointer hover:bg-slate-50 ${
                  isSelected ? "bg-brand-50" : ""
                }`}
                onClick={() => onSelect?.(r.property_slug)}
              >
                <td className="px-4 py-3 font-medium text-slate-900">
                  {r.property_name}
                </td>
                <td className="px-4 py-3 text-right text-slate-700">{r.review_count}</td>
                <td className="px-4 py-3 text-right text-slate-700">
                  {r.average_rating?.toFixed(2) ?? "—"}
                </td>
                <td className="px-4 py-3 text-right text-emerald-700">
                  {r.positive_count}
                </td>
                <td className="px-4 py-3 text-right text-rose-700">{r.negative_count}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
