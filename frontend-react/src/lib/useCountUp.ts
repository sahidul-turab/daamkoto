import { useEffect, useRef, useState } from "react";

// Smoothly animates a number from 0 → target on mount (and whenever target
// changes). Uses an easeOutExpo curve so prices "settle" rather than crawl.
// Respects prefers-reduced-motion.
export function useCountUp(target: number | null, duration = 650): number | null {
  const [value, setValue] = useState<number | null>(target);
  const frame = useRef<number>(0);

  useEffect(() => {
    if (target == null) {
      setValue(null);
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setValue(target);
      return;
    }

    const start = performance.now();
    const from = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(2, -10 * t);
      setValue(from + (target - from) * (t === 1 ? 1 : eased));
      if (t < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [target, duration]);

  return value;
}
