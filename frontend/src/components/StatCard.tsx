/**
 * Single large number with context. Used for the headline row.
 *
 * The delta slot renders colour by sign so an ops user can glance at it.
 */
import React from "react";

interface Props {
  label: string;
  value: React.ReactNode;
  delta?: React.ReactNode;
  deltaKind?: "up" | "down" | "flat";
  hint?: string;
}

export function StatCard({ label, value, delta, deltaKind, hint }: Props) {
  const deltaColor =
    deltaKind === "up"
      ? "text-emerald-700 bg-emerald-50"
      : deltaKind === "down"
        ? "text-rose-700 bg-rose-50"
        : "text-slate-600 bg-slate-100";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-sm font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="mt-2 flex items-baseline gap-3">
        <div className="text-3xl font-semibold text-slate-900">{value}</div>
        {delta != null && (
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${deltaColor}`}>
            {delta}
          </span>
        )}
      </div>
      {hint && <div className="mt-2 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}
