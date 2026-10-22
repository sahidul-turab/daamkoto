import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PricePoint } from "../types";
import { retailerColor } from "../config";
import { formatBDT, formatBDTShort } from "../lib/format";

interface Row {
  t: number;
  label: string;
  [retailer: string]: number | string;
}

export function PriceHistoryChart({ history }: { history: PricePoint[] }) {
  const { rows, retailers } = useMemo(() => {
    const byTime = new Map<number, Row>();
    const sellers = new Set<string>();
    for (const p of history) {
      if (p.price_bdt == null) continue;
      sellers.add(p.retailer);
      const t = new Date(p.scraped_at).getTime();
      // bucket to the day so multiple scrapes on one day collapse
      const day = Math.floor(t / 86_400_000) * 86_400_000;
      let row = byTime.get(day);
      if (!row) {
        row = {
          t: day,
          label: new Date(day).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
          }),
        };
        byTime.set(day, row);
      }
      row[p.retailer] = p.price_bdt;
    }
    return {
      rows: [...byTime.values()].sort((a, b) => a.t - b.t),
      retailers: [...sellers],
    };
  }, [history]);

  if (rows.length < 2) {
    return (
      <div className="grid h-48 place-items-center rounded-xl border border-dashed border-line text-sm text-ink-4">
        Not enough history yet — more observations will appear as prices are updated.
      </div>
    );
  }

  const values = history
    .filter((point) => point.price_bdt != null)
    .map((point) => point.price_bdt as number);
  const latestTime = Math.max(...history.map((point) => new Date(point.scraped_at).getTime()));
  const latestValues = history
    .filter((point) => new Date(point.scraped_at).getTime() === latestTime && point.price_bdt != null)
    .map((point) => point.price_bdt as number);
  const currentBest = latestValues.length ? Math.min(...latestValues) : values[values.length - 1] ?? null;
  const allTimeLow = values.length ? Math.min(...values) : null;

  return (
    <div>
      <div className="mb-3 grid grid-cols-3 gap-2">
        <div className="rounded-lg border border-line bg-surface-2 px-2.5 py-2">
          <div className="text-[10px] uppercase tracking-wide text-ink-4">Current best</div>
          <div className="mt-0.5 text-sm font-bold text-ink">{formatBDT(currentBest)}</div>
        </div>
        <div className="rounded-lg border border-line bg-surface-2 px-2.5 py-2">
          <div className="text-[10px] uppercase tracking-wide text-ink-4">Recorded low</div>
          <div className="mt-0.5 text-sm font-bold text-ok">{formatBDT(allTimeLow)}</div>
        </div>
        <div className="rounded-lg border border-line bg-surface-2 px-2.5 py-2">
          <div className="text-[10px] uppercase tracking-wide text-ink-4">Observations</div>
          <div className="mt-0.5 text-sm font-bold text-ink">{history.length}</div>
        </div>
      </div>
      <div className="mb-2 flex flex-wrap gap-x-3 gap-y-1">
        {retailers.map((retailer) => (
          <span key={retailer} className="inline-flex items-center gap-1.5 text-[10px] text-ink-3">
            <span className="h-2 w-2 rounded-full" style={{ background: retailerColor(retailer) }} />
            {retailer}
          </span>
        ))}
      </div>
      <div className="h-56 w-full sm:h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
          <CartesianGrid stroke="#26262f" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#8a8a99", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#26262f" }}
          />
          <YAxis
            tick={{ fill: "#8a8a99", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => formatBDTShort(v as number)}
            width={56}
          />
          <Tooltip
            contentStyle={{
              background: "#16161f",
              border: "1px solid #313140",
              borderRadius: 12,
              fontSize: 12,
            }}
            labelStyle={{ color: "#b8b8c4" }}
            formatter={(value, name) => [formatBDTShort(value as number), name]}
          />
          {retailers.map((r) => (
            <Line
              key={r}
              type="monotone"
              dataKey={r}
              stroke={retailerColor(r)}
              strokeWidth={2}
              dot={false}
              connectNulls
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}
