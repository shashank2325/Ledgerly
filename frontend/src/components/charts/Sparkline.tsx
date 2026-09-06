import { parseAmount } from "@/utils/money";

/**
 * Stepped-area sparkline — DESIGN.md §3.6 chart type 3.
 * 40px tall, 1.5px stroke, single fill at 8%, no axes, no gridlines.
 */
export function Sparkline({
  data,
  height = 40,
  className = "",
}: {
  data: { date: string; value: string }[];
  height?: number;
  className?: string;
}) {
  if (data.length < 2) return null;

  const values = data.map((d) => parseAmount(d.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  // Flat series would divide by zero; give it a nominal range so it renders
  // as a centered horizontal line rather than collapsing.
  const range = max - min || 1;

  const W = 100;
  const points = values.map((v, i) => ({
    x: (i / (values.length - 1)) * W,
    y: height - ((v - min) / range) * (height - 4) - 2,
  }));

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const area = `${line} L${W},${height} L0,${height} Z`;

  return (
    <svg
      viewBox={`0 0 ${W} ${height}`}
      preserveAspectRatio="none"
      className={`w-full ${className}`}
      style={{ height }}
      role="img"
      aria-label={`Trend from ${data[0]?.date} to ${data[data.length - 1]?.date}`}
    >
      <path d={area} fill="currentColor" opacity="0.08" />
      <path
        d={line}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  );
}
