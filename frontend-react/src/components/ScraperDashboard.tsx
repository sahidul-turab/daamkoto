import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  CheckCircle,
  Loader2,
  Play,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { api, ApiError } from "../api";
import type { ScraperRun, ScraperStatus } from "../types";

const ALL_CATEGORIES = [
  "ram", "laptop_ram", "gpu", "processor", "motherboard",
  "ssd", "portable_ssd", "hdd", "portable_hdd",
  "psu", "cooler", "casing_cooler", "casing",
];

const ALL_RETAILERS = [
  "startech", "ryans", "techland", "potakait", "ucc",
  "ultratech", "binarylogic", "skyland", "creatus",
  "selltech", "computersource", "trusttech", "pchouse",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function freshnessColor(lastScraped: string | null): string {
  if (!lastScraped) return "var(--color-ink-4, #5f5f6e)";
  const hours = (Date.now() - new Date(lastScraped).getTime()) / 3_600_000;
  if (hours < 24) return "#2dd4a7";  // ok / teal
  if (hours < 72) return "#f5b14c";  // warn / amber
  return "#f43f4b";                  // brand / red
}

function relativeAge(iso: string | null): string {
  if (!iso) return "Never";
  const hours = (Date.now() - new Date(iso).getTime()) / 3_600_000;
  if (hours < 1)   return "< 1h ago";
  if (hours < 24)  return `${Math.floor(hours)}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1)  return "Yesterday";
  if (days < 14)   return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-BD", { month: "short", day: "numeric" });
}

function runDuration(run: ScraperRun): string {
  if (!run.finished_at) return "—";
  const s = Math.floor(
    (new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000,
  );
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ScraperDashboard() {
  const [data, setData]       = useState<ScraperStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchErr, setFetchErr] = useState<string | null>(null);

  // Trigger form
  const [selCat,  setSelCat]  = useState("ram");
  const [selRets, setSelRets] = useState<Set<string>>(
    new Set(["startech", "ryans", "techland"]),
  );
  const [triggering,  setTriggering]  = useState(false);
  const [triggerMsg, setTriggerMsg]   = useState<{ ok: boolean; text: string } | null>(null);

  const refresh = useCallback(async () => {
    try {
      const d = await api.scraperStatus();
      setData(d);
      setFetchErr(null);
    } catch (e) {
      setFetchErr(e instanceof ApiError ? e.message : "Failed to load scraper status");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => { refresh(); }, [refresh]);

  // Auto-refresh every 8 s while a run is active
  useEffect(() => {
    if (!data) return;
    if (Object.keys(data.active_runs).length === 0) return;
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, [data, refresh]);

  async function triggerRun() {
    if (selRets.size === 0) {
      setTriggerMsg({ ok: false, text: "Select at least one retailer." });
      return;
    }
    setTriggering(true);
    setTriggerMsg(null);
    try {
      const res = await api.triggerRun(selCat, [...selRets]);
      setTriggerMsg({ ok: true, text: `Run #${res.run_id} started for ${selCat}. Auto-refreshing…` });
      setTimeout(refresh, 2500);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.status === 409
            ? "A run for this category is already active."
            : `API error ${e.status}`
          : "Failed to trigger run.";
      setTriggerMsg({ ok: false, text: msg });
    } finally {
      setTriggering(false);
    }
  }

  function toggleRetailer(r: string) {
    setSelRets((prev) => {
      const next = new Set(prev);
      if (next.has(r)) next.delete(r);
      else next.add(r);
      return next;
    });
  }

  // ---------------------------------------------------------------------------
  // Loading / error states
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-ink-4">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  if (fetchErr) {
    return (
      <div className="glass rounded-2xl p-8 text-center">
        <p className="font-semibold text-[#f43f4b]">{fetchErr}</p>
        <p className="mt-1 text-sm text-ink-3">
          Make sure the backend is running:{" "}
          <code className="rounded bg-surface-2 px-1 py-0.5 text-xs">
            uvicorn backend.main:app --reload --port 8000
          </code>
        </p>
        <button className="btn-ghost mt-4" onClick={refresh}>
          Retry
        </button>
      </div>
    );
  }

  const activeRuns = data?.active_runs ?? {};
  const isRunning  = Object.keys(activeRuns).length > 0;

  // ---------------------------------------------------------------------------
  // Dashboard
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* ── Title bar ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="h-5 w-5 text-brand" />
          <h2 className="text-xl font-bold">Scraper Health</h2>
        </div>
        <button className="btn-ghost !gap-1.5 !rounded-xl text-sm" onClick={refresh}>
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* ── Status banner ── */}
      {isRunning ? (
        <div className="flex items-center gap-3 rounded-2xl border border-[#f5b14c]/40 bg-[#f5b14c]/10 px-5 py-4">
          <Loader2 className="h-5 w-5 shrink-0 animate-spin text-[#f5b14c]" />
          <div>
            <div className="font-semibold text-[#f5b14c]">Pipeline Running</div>
            <div className="text-sm text-ink-3">
              {Object.entries(activeRuns)
                .map(([cat, id]) => `${cat.toUpperCase()} (run #${id})`)
                .join(" · ")}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-2xl border border-[#2dd4a7]/30 bg-[#2dd4a7]/10 px-5 py-4">
          <CheckCircle className="h-5 w-5 shrink-0 text-[#2dd4a7]" />
          <div>
            <div className="font-semibold text-[#2dd4a7]">Idle</div>
            {data?.recent_runs[0] && (
              <div className="text-sm text-ink-3">
                Last run:{" "}
                <span className="font-medium text-ink-2">
                  {data.recent_runs[0].category.toUpperCase()}
                </span>
                {" — "}
                {relativeAge(data.recent_runs[0].started_at)} (
                {data.recent_runs[0].status})
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Retailer freshness grid ── */}
      <section>
        <p className="label mb-3">Retailer Freshness</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5">
          {(data?.freshness ?? []).map((row) => {
            const color = freshnessColor(row.last_scraped);
            return (
              <div key={row.retailer} className="glass rounded-xl p-3">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: color }}
                  />
                  {row.retailer}
                </div>
                <div className="mt-1 text-xs text-ink-3">{relativeAge(row.last_scraped)}</div>
                <div className="text-xs text-ink-4">
                  {(row.product_count ?? 0).toLocaleString()} products
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Two-column: Run history + Manual trigger ── */}
      <div className="grid gap-6 xl:grid-cols-2">
        {/* Recent runs */}
        <section className="glass rounded-2xl p-5">
          <p className="label mb-4">Recent Pipeline Runs</p>
          {data?.recent_runs.length ? (
            <div className="space-y-2">
              {data.recent_runs.slice(0, 10).map((run) => (
                <RunRow key={run.id} run={run} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-4">
              No runs recorded yet. Trigger one below, or run{" "}
              <code className="rounded bg-surface-2 px-1 text-xs">
                python scheduler.py --once
              </code>
            </p>
          )}
        </section>

        {/* Manual trigger */}
        <section className="glass rounded-2xl p-5">
          <p className="label mb-4">Manual Trigger</p>

          {/* Category select */}
          <div className="mb-3">
            <label className="label mb-1.5 block">Category</label>
            <select
              value={selCat}
              onChange={(e) => setSelCat(e.target.value)}
              className="field w-full"
            >
              {ALL_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* Retailer chips */}
          <div className="mb-4">
            <div className="label mb-1.5 flex items-center justify-between">
              <span>Retailers ({selRets.size} selected)</span>
              <div className="flex gap-3">
                <button
                  className="text-[10px] text-brand hover:underline"
                  onClick={() => setSelRets(new Set(ALL_RETAILERS))}
                >
                  All
                </button>
                <button
                  className="text-[10px] text-ink-4 hover:text-ink"
                  onClick={() => setSelRets(new Set())}
                >
                  None
                </button>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {ALL_RETAILERS.map((r) => (
                <button
                  key={r}
                  onClick={() => toggleRetailer(r)}
                  className={`chip cursor-pointer !py-1 !text-[11px] transition-all ${
                    selRets.has(r)
                      ? "!border-brand/50 !bg-brand/15 !text-brand"
                      : "opacity-40 hover:opacity-70"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          {/* Run button */}
          <button
            className="btn-brand w-full"
            onClick={triggerRun}
            disabled={triggering || selRets.size === 0}
          >
            {triggering ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {triggering ? "Starting…" : "Run Pipeline Now"}
          </button>

          {triggerMsg && (
            <p
              className={`mt-2 text-sm ${triggerMsg.ok ? "text-[#2dd4a7]" : "text-brand"}`}
            >
              {triggerMsg.text}
            </p>
          )}

          {/* Scheduler hint */}
          <div className="mt-5 border-t border-line pt-4">
            <p className="mb-1.5 text-xs font-semibold text-ink-3">
              Scheduler daemon (runs automatically):
            </p>
            <pre className="rounded-xl bg-surface-2 px-3 py-2.5 font-mono text-[11px] leading-relaxed text-ink-3">
              {`# Run every category once, then exit:\npython scheduler.py --once\n\n# 12-hour repeating daemon:\npython scheduler.py`}
            </pre>
          </div>
        </section>
      </div>

      {/* ── Log console ── */}
      <section>
        <p className="label mb-2">Scheduler Log</p>
        {data?.log_tail?.trim() ? (
          <pre className="max-h-96 overflow-y-auto rounded-2xl border border-line bg-[#0d0d14] p-4 font-mono text-[11.5px] leading-relaxed text-[#c9d1d9] whitespace-pre-wrap break-words">
            {data.log_tail}
          </pre>
        ) : (
          <div className="glass rounded-2xl p-6 text-center text-sm text-ink-4">
            No log entries yet — logs appear here after the first pipeline run.
          </div>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Run row sub-component
// ---------------------------------------------------------------------------

function RunRow({ run }: { run: ScraperRun }) {
  const retailers = (run.retailers ?? []).slice(0, 3).join(", ") +
    ((run.retailers ?? []).length > 3 ? ` +${run.retailers.length - 3}` : "");

  return (
    <div className="flex items-start gap-3 rounded-xl border border-line-2 bg-surface-2 px-4 py-3 text-sm">
      {/* Status icon */}
      {run.status === "SUCCESS" && (
        <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#2dd4a7]" />
      )}
      {run.status === "FAILED" && (
        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
      )}
      {run.status === "RUNNING" && (
        <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-[#f5b14c]" />
      )}

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold uppercase tracking-wide">
            {run.category}
          </span>
          <span
            className={`chip !py-0 !text-[10px] ${
              run.status === "SUCCESS"
                ? "!border-[#2dd4a7]/40 !text-[#2dd4a7]"
                : run.status === "FAILED"
                ? "!border-brand/40 !text-brand"
                : "!border-[#f5b14c]/40 !text-[#f5b14c]"
            }`}
          >
            {run.status}
          </span>
        </div>
        <div className="mt-0.5 truncate text-xs text-ink-4">
          {relativeAge(run.started_at)}
          {" · "}
          {runDuration(run)}
          {run.status === "SUCCESS" &&
            ` · ${run.products_count} products / ${run.prices_count} prices`}
          {retailers && ` · ${retailers}`}
          {run.error_message && (
            <span className="text-brand"> · {run.error_message}</span>
          )}
        </div>
      </div>

      <span className="shrink-0 text-xs text-ink-4">#{run.id}</span>
    </div>
  );
}
