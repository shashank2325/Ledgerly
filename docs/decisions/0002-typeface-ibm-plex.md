# ADR 0002 — Typeface: IBM Plex Sans + IBM Plex Mono

**Status:** Accepted · 2026-09-06
**Blocks:** Phase 1 (design system)

## Context

Per DESIGN.md §3.3 the UI needs two faces: one for interface text, one for numerals. In a
financial UI the numerals are the load-bearing typographic decision — they must be tabular so
columns align on the decimal, and they must read as trustworthy.

Candidates: Inter (+ a mono), Geist Sans/Mono, IBM Plex Sans/Mono.

## Decision

**IBM Plex Sans** for interface text, **IBM Plex Mono** for numbers, IDs, and dates.

## Rationale

- Genuine tabular figures in both faces, and the two are metrically related — a number set in
  Mono sits correctly beside a label set in Sans.
- Plex Mono is a designed text face, not a code fallback. It carries the "ledger document"
  quality DESIGN.md §3 is aiming at.
- Effectively unused in consumer fintech. Inter is the default choice and would make us look like
  every other product in the category; differentiation here is free.
- Open source (SIL OFL), served from Google Fonts, no licensing cost or vendor risk.

## Consequences

- Two font families to load. Subset to Latin and load only the weights in the type scale
  (400/500/600) to keep the payload down.
- `font-variant-numeric: tabular-nums` must be set on the numeric utility classes — Plex does not
  default to tabular.
- Needs a real fallback stack (`system-ui`) so a font-load failure degrades rather than breaks.

## Revisit if

Plex reads as too technical once real screens exist. Geist Sans/Mono is the fallback choice; the
swap is confined to the Tailwind theme and a font import.
