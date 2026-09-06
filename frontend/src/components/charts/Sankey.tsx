import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { Money } from "@/components/ui/Money";
import { moneyToString, parseAmount } from "@/utils/money";
import type { FlowKind, SankeyData, SankeyLink, SankeyNode, TransactionType } from "@/types";

/**
 * Cash-flow Sankey — hand-rolled SVG, no charting dependency.
 *
 * The layout is only three columns (sources → Income → destinations), so the
 * general-purpose iterative relaxation that d3-sankey exists for buys nothing:
 * column order is given by the backend and there is nothing to untangle.
 *
 * DESIGN.md §3.2 — NO RAINBOW. Magnitude is carried by ribbon THICKNESS.
 * Color carries meaning and nothing else: income green, expense ink, net
 * violet. Categories are told apart by their label, never by hue. That single
 * restraint is what stops this reading like every other budgeting app.
 *
 * Money is parsed to a number here for LAYOUT GEOMETRY ONLY. Every displayed
 * amount goes through <Money> with the original string — the frontend never
 * does financial arithmetic (SPEC §3).
 */

/* Geometry. All px. */
const NODE_W = 9;
const NODE_GAP = 10; // vertical breathing room between nodes in a column
const MIN_NODE = 2; // a $30 category next to a $41,000 one is a hairline, not nothing
const MIN_LINK = 1.5;
const LEFT_ZONE = 172; // label gutter: category name + right-aligned amount
const RIGHT_ZONE = 232;
const HEADER = 26; // band above the plot for middle-column labels
const LABEL_H = 18;
const LABEL_STEP = 16; // minimum distance between two label baselines
const TARGET_H = 400;
const MIN_W = 720; // below this the chart scrolls rather than crushes

interface Placed {
  id: string;
  label: string;
  value: string;
  kind: FlowKind;
  column: number;
  x: number;
  y: number;
  h: number;
  /** Height actually accounted for by inbound flow. Less than `h` only when a
   *  node emits more than it receives — see the shortfall note below. */
  filled: number;
  labelY: number;
}

interface Ribbon {
  key: string;
  d: string;
  kind: FlowKind;
  from: string;
  to: string;
  value: string;
  midX: number;
  midY: number;
}

interface Layout {
  height: number;
  nodes: Placed[];
  ribbons: Ribbon[];
  /** Columns present, ascending. Used to decide which side labels sit on. */
  firstColumn: number;
  lastColumn: number;
}

/** The ONLY place a flow kind becomes a color. Three meanings, three colors. */
const STROKE: Record<FlowKind, string> = {
  income: "var(--c-income)",
  expense: "var(--c-ink)",
  net: "var(--c-transfer)",
};

/** Sign convention per kind, delegated to <Money>. Expenses render bare — a
 *  minus on every expense is noise in a ledger where most rows are expenses. */
const MONEY_TYPE: Record<FlowKind, TransactionType | undefined> = {
  income: "INCOME",
  expense: undefined,
  net: "TRANSFER", // violet; forceSign suppresses the → glyph
};

function push<K, V>(map: Map<K, V[]>, key: K, value: V) {
  const list = map.get(key);
  if (list) list.push(value);
  else map.set(key, [value]);
}

function layout(data: SankeyData, width: number): Layout | null {
  const byId = new Map<string, SankeyNode>(data.nodes.map((n) => [n.id, n]));

  // Zero-value links would render as a MIN_LINK hairline claiming a flow that
  // does not exist. Drop them, along with any link to a node we were not given.
  const links = data.links.filter(
    (l) => parseAmount(l.value) > 0 && byId.has(l.source) && byId.has(l.target),
  );

  const inbound = new Map<string, SankeyLink[]>();
  const outbound = new Map<string, SankeyLink[]>();
  for (const l of links) {
    push(inbound, l.target, l);
    push(outbound, l.source, l);
  }

  const sum = (ls: SankeyLink[] | undefined) =>
    (ls ?? []).reduce((t, l) => t + parseAmount(l.value), 0);

  /**
   * Conservation: a node must be tall enough to hold everything entering AND
   * everything leaving it, whichever is larger — not merely its own stated
   * value.
   *
   * This is what makes negative net income render correctly. With a $3,033
   * Income node emitting $66,896 of expenses, sizing the node by its own value
   * would force 22× more ribbon than there is edge to attach it to, and the
   * ribbons would pile up on top of each other. Sizing by max(in, out, value)
   * gives every ribbon its own slice of edge, and the difference shows up as
   * an unfilled region of the node — the shortfall, drawn rather than hidden.
   */
  const demand = new Map<string, number>();
  for (const n of data.nodes) {
    demand.set(
      n.id,
      Math.max(parseAmount(n.value), sum(inbound.get(n.id)), sum(outbound.get(n.id))),
    );
  }

  const visible = data.nodes.filter((n) => (demand.get(n.id) ?? 0) > 0);
  if (visible.length === 0) return null;

  const columnKeys = [...new Set(visible.map((n) => n.column))].sort((a, b) => a - b);
  const byColumn = new Map<number, SankeyNode[]>();
  for (const n of visible) push(byColumn, n.column, n);

  // One scale for the whole chart. Scaling each column independently to a
  // common height would flatter the numbers: it would make $3,033 of income
  // look the same size as $66,896 of spending. The asymmetry is the finding.
  let scale = Number.POSITIVE_INFINITY;
  for (const c of columnKeys) {
    const list = byColumn.get(c) ?? [];
    const total = list.reduce((t, n) => t + (demand.get(n.id) ?? 0), 0);
    if (total <= 0) continue;
    const available = Math.max(60, TARGET_H - Math.max(0, list.length - 1) * NODE_GAP);
    scale = Math.min(scale, available / total);
  }
  if (!Number.isFinite(scale) || scale <= 0) return null;

  const thickness = new Map<SankeyLink, number>(
    links.map((l) => [l, Math.max(MIN_LINK, parseAmount(l.value) * scale)]),
  );
  const thickOf = (ls: SankeyLink[] | undefined) =>
    (ls ?? []).reduce((t, l) => t + (thickness.get(l) ?? 0), 0);

  // Height is driven by the RENDERED ribbon thicknesses, not the raw values, so
  // the MIN_LINK floor can never make a node's ribbons overflow its edge.
  const heights = new Map<string, number>();
  for (const n of visible) {
    heights.set(
      n.id,
      Math.max(
        MIN_NODE,
        (demand.get(n.id) ?? 0) * scale,
        thickOf(inbound.get(n.id)),
        thickOf(outbound.get(n.id)),
      ),
    );
  }

  // Let the chart grow rather than let anything overlap.
  let plotH = TARGET_H;
  for (const c of columnKeys) {
    const list = byColumn.get(c) ?? [];
    const extent =
      list.reduce((t, n) => t + (heights.get(n.id) ?? 0), 0) +
      Math.max(0, list.length - 1) * NODE_GAP;
    plotH = Math.max(plotH, extent);
  }

  const left = LEFT_ZONE;
  const right = Math.max(left + 200, width - RIGHT_ZONE - NODE_W);
  const xFor = (column: number) => {
    const i = columnKeys.indexOf(column);
    if (columnKeys.length <= 1) return left;
    return left + ((right - left) * i) / (columnKeys.length - 1);
  };

  // Columns are TOP-aligned, not centered. Centering would send the two small
  // income ribbons diagonally across the chart to reach the top of the Income
  // node; top-aligning keeps them horizontal and puts the unfunded remainder of
  // the Income node at the bottom, where it reads as "the rest came from
  // somewhere other than income this period".
  const placed: Placed[] = [];
  for (const c of columnKeys) {
    let y = 0;
    for (const n of byColumn.get(c) ?? []) {
      const h = heights.get(n.id) ?? MIN_NODE;
      const inboundH = thickOf(inbound.get(n.id));
      placed.push({
        id: n.id,
        label: n.label,
        value: n.value,
        kind: n.kind,
        column: n.column,
        x: xFor(n.column),
        y,
        h,
        filled: inbound.has(n.id) ? Math.min(h, inboundH) : h,
        labelY: y + h / 2,
      });
      y += h + NODE_GAP;
    }
  }
  const placedById = new Map(placed.map((p) => [p.id, p]));

  // Attach ribbons to each edge ordered by the vertical position of the node at
  // the far end. With a 3-column layout that is sufficient to guarantee no two
  // ribbons cross, whatever order the backend emitted links in.
  const offsetOut = new Map<SankeyLink, number>();
  const offsetIn = new Map<SankeyLink, number>();
  const yOf = (id: string) => placedById.get(id)?.y ?? 0;

  for (const p of placed) {
    let cursor = p.y;
    for (const l of [...(outbound.get(p.id) ?? [])].sort((a, b) => yOf(a.target) - yOf(b.target))) {
      offsetOut.set(l, cursor);
      cursor += thickness.get(l) ?? MIN_LINK;
    }
    cursor = p.y;
    for (const l of [...(inbound.get(p.id) ?? [])].sort((a, b) => yOf(a.source) - yOf(b.source))) {
      offsetIn.set(l, cursor);
      cursor += thickness.get(l) ?? MIN_LINK;
    }
  }

  const ribbons: Ribbon[] = [];
  for (const l of links) {
    const s = placedById.get(l.source);
    const t = placedById.get(l.target);
    if (!s || !t) continue;
    const th = thickness.get(l) ?? MIN_LINK;
    const y0s = offsetOut.get(l) ?? s.y;
    const y0t = offsetIn.get(l) ?? t.y;
    const y1s = y0s + th;
    const y1t = y0t + th;
    const xs = s.x + NODE_W;
    const xt = t.x;
    const cx = xs + (xt - xs) / 2; // symmetric cubic — flat where the flow is flat
    ribbons.push({
      key: `${l.source}->${l.target}`,
      d:
        `M${xs},${y0s} C${cx},${y0s} ${cx},${y0t} ${xt},${y0t} ` +
        `L${xt},${y1t} C${cx},${y1t} ${cx},${y1s} ${xs},${y1s} Z`,
      kind: l.kind,
      from: s.label,
      to: t.label,
      value: l.value,
      midX: (xs + xt) / 2,
      midY: (y0s + y1s + y0t + y1t) / 4,
    });
  }

  // Labels track their node's centre until two of them would collide, then they
  // are pushed apart. A $33 source is a sub-pixel sliver; its name still has to
  // be readable next to the $3,000 one directly above it.
  for (const c of columnKeys) {
    const column = placed.filter((p) => p.column === c).sort((a, b) => a.y - b.y);
    for (let i = 1; i < column.length; i++) {
      const prev = column[i - 1];
      const cur = column[i];
      if (prev && cur) cur.labelY = Math.max(cur.labelY, prev.labelY + LABEL_STEP);
    }
    for (let i = column.length - 1; i >= 0; i--) {
      const cur = column[i];
      if (!cur) continue;
      const next = column[i + 1];
      const ceiling = next ? next.labelY - LABEL_STEP : plotH - LABEL_H / 2;
      cur.labelY = Math.max(LABEL_H / 2, Math.min(cur.labelY, ceiling));
    }
  }

  return {
    height: plotH,
    nodes: placed,
    ribbons,
    firstColumn: columnKeys[0] ?? 0,
    lastColumn: columnKeys[columnKeys.length - 1] ?? 0,
  };
}

export function Sankey({ data, label }: { data: SankeyData; label: string }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  const [hovered, setHovered] = useState<string | null>(null);

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const measure = () => setWidth(Math.max(MIN_W, el.clientWidth));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const computed = useMemo(() => layout(data, width), [data, width]);

  if (!computed) return null;
  const { height, nodes, ribbons, firstColumn, lastColumn } = computed;
  const active = ribbons.find((r) => r.key === hovered);

  return (
    <div ref={wrap} className="w-full overflow-x-auto">
      <div className="relative" style={{ width, height: height + HEADER }}>
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          className="absolute left-0 block"
          style={{ top: HEADER }}
          role="img"
          aria-label={label}
        >
          {/* Ribbons first so nodes read as the edge they attach to. */}
          <g>
            {ribbons.map((r) => (
              <path
                key={r.key}
                d={r.d}
                fill={STROKE[r.kind]}
                /* Low-opacity fills: overlapping ribbons stay legible and the
                   chart never turns into a block of solid color. */
                opacity={hovered === null ? 0.14 : hovered === r.key ? 0.3 : 0.06}
                className="transition-opacity duration-150"
                onMouseEnter={() => setHovered(r.key)}
                onMouseLeave={() => setHovered(null)}
              />
            ))}
          </g>
          <g>
            {nodes.map((n) => (
              <g key={n.id}>
                {/* Ghost: the part of this node no inbound flow accounts for.
                    Only ever visible on the Income node when spending exceeded
                    income for the period. */}
                {n.filled < n.h - 0.5 && (
                  <rect x={n.x} y={n.y} width={NODE_W} height={n.h} fill={STROKE[n.kind]} opacity={0.2} />
                )}
                <rect
                  x={n.x}
                  y={n.y}
                  width={NODE_W}
                  height={Math.max(MIN_NODE, n.filled)}
                  fill={STROKE[n.kind]}
                  opacity={0.85}
                />
              </g>
            ))}
          </g>
        </svg>

        {/* Text layer in HTML, not SVG <text>: every amount has to go through
            <Money>, which owns tabular figures, the receding units and the
            accessible label — none of which survive being reimplemented in
            SVG. It also lets amounts right-align on a shared edge. */}
        <div className="absolute inset-0 pointer-events-none">
          {nodes.map((n) => {
            const money = (
              <Money
                amount={n.value}
                type={MONEY_TYPE[n.kind]}
                forceSign={n.kind === "net"}
                exact={false}
                size="sm"
              />
            );

            if (n.column === firstColumn) {
              return (
                <div
                  key={n.id}
                  className="absolute flex items-center justify-end gap-2 pr-2.5"
                  style={{ left: 0, width: n.x, top: HEADER + n.labelY - LABEL_H / 2, height: LABEL_H }}
                >
                  <span className="t-small text-ink-muted truncate">{n.label}</span>
                  {money}
                </div>
              );
            }

            if (n.column === lastColumn) {
              return (
                <div
                  key={n.id}
                  className="absolute flex items-center justify-between gap-3 pl-2.5"
                  style={{
                    left: n.x + NODE_W,
                    width: RIGHT_ZONE,
                    top: HEADER + n.labelY - LABEL_H / 2,
                    height: LABEL_H,
                  }}
                >
                  <span className="t-small text-ink-muted truncate">{n.label}</span>
                  {money}
                </div>
              );
            }

            // Middle column (the single Income node): labelled above its bar,
            // where there is room. There is no gutter in the middle of a chart.
            return (
              <div
                key={n.id}
                className="absolute -translate-x-1/2 flex items-baseline gap-2 whitespace-nowrap"
                style={{ left: n.x + NODE_W / 2, top: HEADER + n.y - 22 }}
              >
                <span className="t-label">{n.label}</span>
                {money}
              </div>
            );
          })}

          {/* Hover readout. A ribbon's thickness gives the magnitude; this
              gives the number, on demand, without a permanent legend. */}
          {active && (
            <div
              className="absolute floats px-2.5 py-1.5 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap"
              style={{ left: active.midX, top: HEADER + active.midY }}
            >
              <div className="t-small text-ink-muted">
                {active.from} <span aria-hidden="true">→</span> {active.to}
              </div>
              <Money amount={active.value} type={MONEY_TYPE[active.kind]} />
            </div>
          )}
        </div>
      </div>

      {/* A Sankey is meaningless to a screen reader. Give it the flows as text.
          role="img" above makes the SVG's own contents presentational, so this
          list is the only accessible description of the data. */}
      <ul className="sr-only">
        {ribbons.map((r) => (
          <li key={r.key}>
            {r.from} to {r.to}: {moneyToString(r.value)}
          </li>
        ))}
      </ul>
    </div>
  );
}
