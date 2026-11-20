/**
 * Positive and negative review counts by day, last 30 days.
 */
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format, parseISO } from "date-fns";

interface Props {
  positive: { date: string; count: number }[];
  negative: { date: string; count: number }[];
}

export function SentimentChart({ positive, negative }: Props) {
  const data = positive.map((p, i) => ({
    date: p.date,
    positive: p.count,
    negative: negative[i]?.count ?? 0,
  }));

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Sentiment trend, last 30 days
      </h3>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="date"
              tickFormatter={(v) => format(parseISO(v), "MMM d")}
              fontSize={12}
              stroke="#94a3b8"
            />
            <YAxis allowDecimals={false} fontSize={12} stroke="#94a3b8" />
            <Tooltip
              labelFormatter={(v) => format(parseISO(String(v)), "PP")}
              contentStyle={{ fontSize: "0.85rem" }}
            />
            <Line
              type="monotone"
              dataKey="positive"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              name="Positive"
            />
            <Line
              type="monotone"
              dataKey="negative"
              stroke="#e11d48"
              strokeWidth={2}
              dot={false}
              name="Negative"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
