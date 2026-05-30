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
import { formatBDTShort } from "../lib/format";

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
        Not enough history yet — prices are tracked on every scrape.
      </div>
    );
  }

  return (
    <div className="h-64 w-full">
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
  );
}
