import { Gauge, Zap } from "lucide-react";
import { useCountUp } from "../../lib/useCountUp";

interface Props {
  estimatedWatts: number;
  recommendedPsu: number;
  psuWatts: number | null;
  hasPowerParts?: boolean;
  hasPsu?: boolean;
}

/**
 * Compact power status. Power is supporting information in the builder, so a
 * horizontal meter communicates the useful numbers without dominating the
 * purchase workflow.
 */
export function WattageGauge({
  estimatedWatts,
  recommendedPsu,
  psuWatts,
  hasPowerParts = true,
  hasPsu = false,
}: Props) {
  const animated = useCountUp(hasPowerParts ? estimatedWatts : 0, 700) ?? 0;

  if (!hasPowerParts) {
    return (
      <div className="flex gap-3 rounded-xl border border-dashed border-line px-3.5 py-4">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-surface-2 text-ink-4">
          <Zap className="h-4 w-4" />
        </div>
        <div>
          <div className="text-[12px] font-semibold text-ink-2">Power estimate not ready</div>
          <p className="mt-1 text-[11px] leading-relaxed text-ink-4">
            Add a processor or graphics card and we will estimate your system draw and PSU headroom.
          </p>
        </div>
      </div>
    );
  }

  const capacity = psuWatts ?? recommendedPsu;
  const rawFraction = capacity > 0 ? estimatedWatts / capacity : 0;
  const barFraction = Math.min(1, rawFraction);
  const percentage = Math.round(rawFraction * 100);
  const colorClass = rawFraction < 0.7 ? "bg-ok" : rawFraction < 0.9 ? "bg-warn" : "bg-brand";
  const textClass = rawFraction < 0.7 ? "text-ok" : rawFraction < 0.9 ? "text-warn" : "text-brand";

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Gauge className={`h-4 w-4 ${textClass}`} />
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-4">Estimated power</div>
            <div className="mt-0.5 text-lg font-extrabold tabular-nums text-ink">
              {Math.round(animated)}W
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wide text-ink-4">
            {hasPsu ? "Selected PSU" : "Recommended PSU"}
          </div>
          <div className="mt-0.5 text-sm font-bold tabular-nums text-ink">
            {psuWatts != null ? `${psuWatts}W` : hasPsu ? "Unknown" : `${recommendedPsu}W+`}
          </div>
        </div>
      </div>

      <div className="mt-3 h-2 overflow-hidden rounded-full bg-line">
        <div
          className={`h-full rounded-full transition-[width] duration-700 ${colorClass}`}
          style={{ width: `${Math.max(3, barFraction * 100)}%` }}
        />
      </div>

      <div className="mt-2 flex items-start justify-between gap-3 text-[10px] text-ink-4">
        <span>
          {psuWatts != null
            ? `${percentage}% estimated load`
            : `Includes 40% recommended headroom`}
        </span>
        {hasPsu && psuWatts == null ? (
          <span className="text-right text-warn">PSU wattage unavailable</span>
        ) : psuWatts != null && psuWatts < recommendedPsu ? (
          <span className="text-right text-warn">Consider {recommendedPsu}W+</span>
        ) : (
          <span className={`text-right ${textClass}`}>{psuWatts != null ? "Capacity checked" : "Sizing guide"}</span>
        )}
      </div>
    </div>
  );
}
