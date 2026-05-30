import { useCountUp } from "../../lib/useCountUp";

interface Props {
  estimatedWatts: number;
  recommendedPsu: number;
  psuWatts: number | null;
}

/**
 * Radial gauge showing estimated system draw against the PSU's capacity
 * (or the recommended size when no PSU is picked yet).
 */
export function WattageGauge({ estimatedWatts, recommendedPsu, psuWatts }: Props) {
  const animated = useCountUp(estimatedWatts, 700) ?? 0;
  const capacity = psuWatts ?? recommendedPsu;
  const frac = capacity > 0 ? Math.min(1, estimatedWatts / capacity) : 0;

  const color = frac < 0.7 ? "#2dd4a7" : frac < 0.9 ? "#f5b14c" : "#f43f4b";

  // Geometry — a 270° arc gauge.
  const R = 52;
  const C = 2 * Math.PI * R;
  const arc = 0.75; // fraction of circle used (270°)
  const dash = C * arc;
  const offset = dash * (1 - frac);

  return (
    <div className="flex flex-col items-center">
      <div className="relative h-36 w-36">
        <svg viewBox="0 0 140 140" className="h-full w-full -rotate-[135deg]">
          <circle
            cx="70"
            cy="70"
            r={R}
            fill="none"
            stroke="#26262f"
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${C}`}
          />
          <circle
            cx="70"
            cy="70"
            r={R}
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${C}`}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 0.7s cubic-bezier(0.22,1,0.36,1), stroke 0.3s" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-2xl font-extrabold tabular-nums text-ink">
            {Math.round(animated)}
            <span className="text-sm font-bold text-ink-3">W</span>
          </div>
          <div className="text-[10px] uppercase tracking-wider text-ink-4">est. draw</div>
        </div>
      </div>
      <div className="mt-1 text-center text-xs text-ink-3">
        {psuWatts != null ? (
          <>
            PSU <span className="font-semibold text-ink">{psuWatts}W</span> ·{" "}
            {Math.round(frac * 100)}% load
          </>
        ) : (
          <>
            Recommended PSU{" "}
            <span className="font-semibold text-ink">{recommendedPsu}W+</span>
          </>
        )}
      </div>
    </div>
  );
}
