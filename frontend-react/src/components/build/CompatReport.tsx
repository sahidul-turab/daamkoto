import { AlertTriangle, CheckCircle2, ShieldCheck, XCircle } from "lucide-react";
import type { Issue } from "../../lib/compat";

const ICON = {
  ok: { Cmp: CheckCircle2, cls: "text-ok" },
  warn: { Cmp: AlertTriangle, cls: "text-warn" },
  error: { Cmp: XCircle, cls: "text-brand" },
} as const;

export function CompatReport({
  issues,
  partCount,
}: {
  issues: Issue[];
  partCount: number;
}) {
  const errors = issues.filter((i) => i.level === "error").length;
  const warns = issues.filter((i) => i.level === "warn").length;

  let banner: { cls: string; text: string };
  if (partCount < 2) {
    banner = { cls: "text-ink-3", text: "Add parts to check compatibility" };
  } else if (errors > 0) {
    banner = { cls: "text-brand", text: `${errors} compatibility ${errors === 1 ? "problem" : "problems"}` };
  } else if (warns > 0) {
    banner = { cls: "text-warn", text: `Compatible · ${warns} ${warns === 1 ? "note" : "notes"}` };
  } else {
    banner = { cls: "text-ok", text: "All checks passed" };
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-ink-3" />
        <span className={`text-sm font-bold ${banner.cls}`}>{banner.text}</span>
      </div>

      {issues.length === 0 ? (
        <p className="rounded-xl border border-dashed border-line px-3 py-6 text-center text-xs text-ink-4">
          Compatibility checks appear here as you add a CPU, motherboard, RAM, PSU
          and case.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {issues.map((iss, i) => {
            const { Cmp, cls } = ICON[iss.level];
            return (
              <li
                key={i}
                className="flex items-start gap-2.5 rounded-lg border border-line bg-surface-2/60 px-3 py-2"
              >
                <Cmp className={`mt-0.5 h-4 w-4 shrink-0 ${cls}`} />
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold text-ink">{iss.title}</div>
                  <div className="text-[11px] text-ink-3">{iss.detail}</div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
