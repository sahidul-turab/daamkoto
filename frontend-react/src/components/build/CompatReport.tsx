import { useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ShieldCheck, XCircle } from "lucide-react";
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
  const [showPassed, setShowPassed] = useState(false);
  const errors = issues.filter((issue) => issue.level === "error");
  const warnings = issues.filter((issue) => issue.level === "warn");
  const passed = issues.filter((issue) => issue.level === "ok");
  const needsAttention = [...errors, ...warnings];

  let banner: { cls: string; text: string };
  if (partCount < 2) {
    banner = { cls: "text-ink-3", text: "Add another part to begin checks" };
  } else if (errors.length > 0) {
    banner = {
      cls: "text-brand",
      text: `${errors.length} compatibility ${errors.length === 1 ? "conflict" : "conflicts"}`,
    };
  } else if (warnings.length > 0) {
    banner = {
      cls: "text-warn",
      text: `No conflicts found · ${warnings.length} to verify`,
    };
  } else if (passed.length > 0) {
    banner = { cls: "text-ok", text: "No conflicts found" };
  } else {
    banner = { cls: "text-ink-3", text: "No matching checks available yet" };
  }

  const renderIssue = (issue: Issue, index: number) => {
    const { Cmp, cls } = ICON[issue.level];
    return (
      <li
        key={`${issue.title}-${index}`}
        className="flex items-start gap-2.5 rounded-xl border border-line bg-surface-2/60 px-3 py-2.5"
      >
        <Cmp className={`mt-0.5 h-4 w-4 shrink-0 ${cls}`} />
        <div className="min-w-0">
          <div className="text-[12px] font-semibold text-ink">{issue.title}</div>
          <div className="mt-0.5 text-[10px] leading-relaxed text-ink-3">{issue.detail}</div>
        </div>
      </li>
    );
  };

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-ink-3" />
        <span className={`text-sm font-bold ${banner.cls}`}>{banner.text}</span>
      </div>

      {needsAttention.length === 0 && passed.length === 0 ? (
        <p className="rounded-xl border border-dashed border-line px-3 py-5 text-center text-[11px] leading-relaxed text-ink-4">
          Compatibility checks appear as you combine a processor, motherboard, memory, power supply, cooler, and case.
        </p>
      ) : (
        <div className="space-y-2">
          {needsAttention.length > 0 && <ul className="space-y-2">{needsAttention.map(renderIssue)}</ul>}

          {passed.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setShowPassed((open) => !open)}
                className="flex w-full items-center justify-between gap-3 rounded-xl border border-ok/20 bg-ok/[0.05] px-3 py-2.5 text-left"
                aria-expanded={showPassed}
              >
                <span className="flex items-center gap-2 text-[11px] font-semibold text-ok">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {passed.length} {passed.length === 1 ? "check" : "checks"} passed
                </span>
                <ChevronDown className={`h-3.5 w-3.5 text-ok transition-transform ${showPassed ? "rotate-180" : ""}`} />
              </button>
              {showPassed && <ul className="mt-2 space-y-2">{passed.map(renderIssue)}</ul>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
