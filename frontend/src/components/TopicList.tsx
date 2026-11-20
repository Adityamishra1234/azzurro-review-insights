/**
 * Topic breakdown for the current week.
 *
 * Shows how many reviews mentioned each topic and the share that were
 * negative. Negative share is the operational lever: a topic with a high
 * negative share is the team's prompt to investigate.
 */
import { TopicBreakdown } from "../api";

interface Props {
  rows: TopicBreakdown[];
  onSelect?: (topic: string) => void;
  selectedTopic?: string | null;
}

export function TopicList({ rows, onSelect, selectedTopic }: Props) {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
        No topic signal this week. Either not enough reviews yet or none matched
        a tracked topic.
      </div>
    );
  }

  const maxCount = Math.max(...rows.map((r) => r.count));

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Topics this week
      </h3>
      <ul className="space-y-2">
        {rows.map((r) => {
          const isSelected = selectedTopic === r.topic;
          const negPct = Math.round(r.negative_share * 100);
          return (
            <li
              key={r.topic}
              className={`cursor-pointer rounded-lg border px-3 py-2 ${
                isSelected
                  ? "border-brand-500 bg-brand-50"
                  : "border-transparent hover:border-slate-200 hover:bg-slate-50"
              }`}
              onClick={() => onSelect?.(r.topic)}
            >
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-slate-900">{r.topic}</span>
                <span className="text-slate-500">
                  {r.count} reviews, {negPct}% negative
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-slate-100">
                <div
                  className="h-full bg-brand-500"
                  style={{ width: `${(r.count / maxCount) * 100}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
