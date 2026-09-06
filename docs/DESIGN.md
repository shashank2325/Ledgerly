# Ledgerly — Design & Build Plan

Companion to `Ledgerly — Project Master Specification & Development Context.md`.
That doc defines the **architecture**. This doc defines the **product, the visual language, and the order we build in.**

Status: pre-code. Nothing is built. Plaid dev account setup in progress (parallel track, §8).

---

## 0. How to use this document

- §1–2 are positioning and competitive research — read once, refer back when a feature decision feels arbitrary.
- §3 is the design system. This is the contract. Every screen we build gets checked against it.
- §4 is the screen inventory.
- §5 is the full feature list, tiered. **We are not building all of it.** T0 is the target.
- §6 is the actual build order with checkpoints.
- §7 is open decisions that need answers before certain phases.

---

## 1. Positioning — what Ledgerly is that the others aren't

Monarch, Copilot, and Lunch Money are all **budgeting apps that happen to store data**. Ledgerly is a **personal financial data platform that happens to have a UI**.

That's not a slogan, it's a product constraint with three consequences:

**1. The ledger is the product, the dashboard is a view of it.**
Every number on screen must be traceable to source transactions. No black-box aggregates. If the dashboard says "Food $680," clicking it shows the 34 transactions that add to $680. Always. This is the thing budgeting apps quietly fail at and it's free for us because we're keeping raw + curated + derived layers anyway.

**2. Transfers are solved, not managed.**
This is the sharpest wedge. From the research:
- Monarch's own help docs concede that a debt payment appearing as two transactions "can result in double counting" and that they are "actively exploring better ways to handle this."
- Copilot classifies credit-card payments as "Internal Transfer" and excludes them — but it's a *category assignment on one transaction*, not a *link between two*.

Both treat a transfer as a label. It's actually a **relationship between two transactions**. Our spec already calls for `transfer_group_id` pairing both legs. So we can do something neither does: **show the link in the UI.** Two rows, visually joined, with the money visibly moving from one account to the other. You don't have to trust that it was excluded — you can see the pair.

**3. Reprocessable history.**
Because raw is immutable and derived tables are rebuildable, changing a categorization rule can retroactively fix five years of history. Every hosted app makes you accept whatever it decided at ingest time. This is a genuine capability, not a nice-to-have — it should be surfaced in the UI eventually ("apply rule to all past transactions → 412 affected").

**Non-goals:** budgets-as-envelopes, goals, bill pay, financial advice, investment trading, household/shared accounts, AI assistant. Some may come later. None are v1.

---

## 2. Competitive teardown

### What each does well

| | Strength | What we take | What we skip |
|---|---|---|---|
| **Monarch** | Best-in-class transaction categorization (~90% correct out of the box, learns from corrections). Customizable drag-and-drop dashboard. Strong net-worth + account views. | Category quality bar. Recategorize-and-remember behaviour. Account grouping by institution. | Dashboard customization (over-engineering for one user), goals, household features, AI assistant, receipt scanning. |
| **Copilot** | Widely called the best-designed money app. Design philosophy of "constraint, not addition" — no decorative chrome competes with data. Charts are the primary interface, not decoration. Progressive disclosure: summaries first, detail on interaction. | The restraint principle. Progressive disclosure. Semantic-only color. Direct chart interaction. | The whole aesthetic (deep-navy cinematic, 112px display type) — that's *their* identity, copying it makes us a knockoff. Also skip: rebalancing, AI categorization, investment depth. |
| **Lunch Money** | Built by a solo dev, so the scope is realistic for us. Rules engine with real conditions. Developer API as a first-class feature. Split / group / tag transactions. CSV import. | Rules engine design. The "power user wants control" posture. Manual + CSV entry as an escape hatch. | Multi-currency, crypto portfolio, email-triggered rules. |
| **YNAB** | Envelope method, strong pedagogy. | Nothing structurally — different philosophy (prescriptive budgeting vs. our descriptive ledger). | All of it, for v1. |

### The 2026 fintech design consensus (and where we deviate)

Current dominant look: **dark backgrounds, monospace type, minimal color, bento grids.** Neutral palette where color only ever means state. Numerals treated as the real typography decision — tabular figures, units set lighter than values.

We keep the *principles* (semantic-only color, tabular numerals, restraint) and deliberately break the *look*: everyone is shipping dark bento grids. We go light-first and card-less. Details in §3.

---

## 3. Design language — "Ledger"

> **Ink on paper. Hairlines, not boxes. Numbers are the typography. Color is a fact, never a decoration.**

The reference points are a well-set financial statement, a Swiss timetable, and a terminal — not a SaaS dashboard.

### 3.1 The one big differentiator: no cards

Every competitor builds from rounded, shadowed, bordered cards on a tinted background. It's the default and it reads as generic.

**Ledgerly has no cards.** Structure comes from:
- 1px hairline rules (never 2px, never a shadow)
- Whitespace and consistent baseline rhythm
- Alignment — everything sits on a shared grid

No drop shadows anywhere. No elevation system. No colored section backgrounds. The page is one continuous sheet. This single choice makes the app instantly not-look-like-Monarch, costs nothing to implement, and is *easier* for a non-frontend developer than maintaining a card/elevation system.

Exception: modals and dropdowns get a hairline border + one very soft shadow, because they genuinely float.

### 3.2 Canvas & color

Light-first. Full dark mode as a peer, not an afterthought — but light is the identity.

```
LIGHT (default)
  canvas        #FAFAF8   warm off-white — paper, not #FFF
  surface       #FFFFFF   only for floating things (modal, dropdown)
  rule          #E6E4DE   hairlines
  rule-strong   #C9C6BE   section dividers, table header underline
  ink           #1A1917   primary text
  ink-muted     #6B6862   labels, secondary
  ink-faint     #9A968E   units, cents, timestamps, placeholders

DARK
  canvas        #171614   warm near-black, matching the paper's warmth
  surface       #1F1E1B
  rule          #2E2C28
  rule-strong   #423F39
  ink           #EDEBE6
  ink-muted     #A5A199
  ink-faint     #6E6A62
```

**Semantic color — the only color in the app:**

```
  income     #2F6F4E   deep green
  expense    #1A1917   INK. Expenses are not red.
  transfer   #7A5CA8   muted violet — the signature color
  pending    #B07A29   amber
  negative   #A33B2A   only for a genuinely bad state (sync failure, overdrawn)
  accent     #7A5CA8   same violet: links, focus rings, active nav
```

Two deliberate decisions:

- **Expenses are ink, not red.** Spending money is the normal state of a ledger, not an error. Reds everywhere is what makes finance apps feel anxious. Red is reserved for things that are actually wrong. (The research phrase for this: *designing for a steady heart rate.*)
- **Transfers get their own color and it's the brand color.** Our differentiator is visible in the palette. Violet reads as neither good nor bad — which is exactly what a transfer is.

Never use color to distinguish categories. Categories are distinguished by *label*. This kills the rainbow-pie-chart look and is a large part of why the app will feel calm.

### 3.3 Typography

Two families, one job each:

- **UI / text:** IBM Plex Sans
- **Numbers / IDs / dates:** IBM Plex Mono

Why Plex: it's free, it has genuinely good tabular figures, the mono is a real design face rather than a code fallback, and — practically — *no one in consumer fintech uses it*. Inter would be the safe choice and would look like everything else. (Alternative if Plex feels too technical: Geist Sans + Geist Mono.)

**Amendment (Phase 1, from looking at the real render):** display numerals use Plex **Sans** with
tabular figures, not Mono. Monospacing exists to align columns; a hero number has nothing to align
against, so it buys nothing and costs legibility — Plex Mono sets the comma on a full advance
width, which opens a visible gap (`$85 , 540`) at 28px. Mono remains the rule everywhere a column
exists, which is everywhere alignment is actually visible.

```
display   32px / 600 / -0.02em   page-level hero number
h1        22px / 600 / -0.01em   page titles
h2        15px / 600 / 0         section headings
body      14px / 400
label     11px / 500 / 0.06em / uppercase / ink-muted
num-lg    28px / mono / 500 / tabular
num       14px / mono / 400 / tabular
num-sm    12px / mono / 400 / tabular
```

### 3.4 Numerals — the actual craft

The research is right that numerals are the typography decision that separates credible financial UI from amateur. Rules:

1. **Always tabular** (`font-variant-numeric: tabular-nums`). Columns of numbers must align on the decimal, always.
2. **Right-align every amount.** No exceptions.
3. **Units recede.** The `$` and the cents render at `ink-faint`, one step smaller. Magnitude reads first:
   `<span class="faint">$</span>1,284<span class="faint">.30</span>`
4. **Sign convention:** expenses render bare (`$42.10`), income renders `+$3,500.00` in income green, transfers render with a directional glyph (`→ $2,000.00`) in transfer violet. The sign carries the meaning; the color confirms it. Never rely on color alone — that's an accessibility failure and we have colorblind users eventually.
5. **Round in summaries, exact in the ledger.** Dashboard shows `$1,284`. The transaction row shows `$1,284.30`. Never round where a user might be reconciling.
6. **Pending amounts are italic** + amber dot. Fine — they may change.

### 3.5 Layout

- Left sidebar nav, fixed, 200px, hairline right border. No icons-only collapse — text labels, always readable.
- Content max-width 1100px, left-aligned within the pane (not centered — centered content in a wide viewport reads as marketing).
- 8px spacing scale: `4 8 12 16 24 32 48 64`. Nothing else.
- Border radius: `2px` on inputs/buttons, `0` on everything else. Sharp corners are part of the identity. No pills.
- Density: transaction rows are 40px tall. Dense enough to scan 20 at once, loose enough to click.

### 3.6 Charts

Skip the dataviz library maximalism. Four chart types, that's the whole vocabulary:

1. **Horizontal bars** — spending by category. Ranked descending, label left, bar, amount right. No axis, no gridlines, no legend.
2. **Sparkline** — trend context next to a number. 40px tall, 1.5px stroke, no axes.
3. **Stepped area** — net worth / balance over time. Single series, one fill at 8% opacity.
4. **Bar pair** — income vs. expenses per month. Two bars, income green, expense ink.

**No pie charts. No donuts. No radial anything.** They're the visual signature of every budgeting app and they're bad at the one job — comparing magnitudes.

Every chart element is hoverable and every hover reveals the underlying number. Every chart segment is clickable and navigates to the filtered transaction list. This is the "traceable to source" principle expressed in the UI.

### 3.7 Signature patterns

These are the three things a user would recognize as *ours*:

**A. The transfer link.**
When two transactions are paired, the ledger renders them as a joined pair — a violet rule connecting the two rows, source above, destination below, with the account names and a `→`. Collapsed by default into one line (`Transfer · Checking → Savings · $2,000.00`), expandable to show both legs. Unmatched-but-suspected transfers show the same treatment with a dashed rule and a "confirm / reject" affordance.

Nobody else shows this. It's the product thesis made visible.

**B. The provenance popover.**
Every derived number has a small `·` affordance. Clicking it shows: how this was computed, which table it came from, how many source rows, and when it was last refreshed. Sounds like a developer feature — it's actually the trust feature, and for a personal data platform it's the point.

**C. Keyboard-first ledger.**
`j/k` to move rows, `c` to categorize, `t` to mark transfer, `/` to search, `Enter` to open detail. The transaction list is a tool you operate, not a page you browse. Cheap to build, and it's what makes daily triage not feel like a chore.

### 3.8 Empty, loading, error

- **Loading:** hairline skeleton rows at the exact height of real rows. No spinners, no shimmer.
- **Empty:** one sentence in `ink-muted` + the single action that fixes it. No illustrations.
- **Error:** one sentence, the actual reason, and a retry. Never "Something went wrong."
- **Stale data:** if analytics are older than the last sync, say so inline — `Computed 2h ago` in `ink-faint`. Never silently show stale numbers.

### 3.9 Accessibility floor

Non-negotiable, cheap if done from the start: all text ≥ 4.5:1 contrast, visible focus rings (2px violet), full keyboard operability, semantic HTML tables for the ledger, `aria-live` on async results, no meaning conveyed by color alone (see §3.4 rule 4).

---

## 4. Information architecture

Four top-level destinations. Resist adding a fifth.

```
Ledgerly
├── Overview      the dashboard
├── Ledger        all transactions
├── Accounts      connected institutions + balances
└── Settings      connections, categories, rules, data
```

### Overview
Single column, top to bottom, decreasing importance:
1. **Net worth** — `display` number, change vs. last month, stepped-area sparkline.
2. **This month** — three numbers in a row: Income / Spending / Net. Bare, hairline-separated, no boxes.
3. **Cash flow** — 12-month income-vs-expense bar pair.
4. **Spending by category** — horizontal bars, top 8, "show all" link.
5. **Recent activity** — last 10 ledger rows, same component as the Ledger page.
6. **Needs attention** — unconfirmed transfer pairs, uncategorized transactions, sync failures. Only renders if non-empty.

### Ledger
- Sticky filter bar: search, date range, account, category, type (income/expense/transfer).
- Table: Date · Merchant · Category · Account · Amount. Transfers render as pairs (§3.7A).
- Row click → right-side detail panel (not a modal — keeps list context).
- Detail panel: full normalized record, raw Plaid payload behind a disclosure, category override, note, transfer pairing control, rule-creation shortcut ("always categorize *Whole Foods* as Groceries").
- Bulk select → bulk categorize.

### Accounts
- Grouped by institution. Per account: name, mask, type, current balance, available, last synced, sync status.
- Assets and liabilities subtotaled separately, then net worth.
- Per-account click → the Ledger, pre-filtered.
- Add-account button → Plaid Link.

### Settings
Tabs: **Connections** (Plaid items, reconnect, remove) · **Categories** (tree, rename, merge) · **Rules** (list, priority ordering, enable/disable) · **Data** (last sync, manual sync trigger, reprocess history, export CSV).

---

## 5. Feature inventory

Everything from the spec, tiered. **T0 is what we're building.** The rest is written down so it isn't forgotten, not so it gets built.

### T0 — MVP (the end-to-end slice)
Definition of done: real bank connected, real transactions in Iceberg, queryable via Athena, visible in the browser, transfers correctly excluded from spending.

- [ ] Terraform: S3, DynamoDB, Lambda, API Gateway, IAM, Secrets Manager, CloudWatch
- [ ] Plaid Link → public token → exchange → access token in Secrets Manager
- [ ] Accounts fetch + persist to DynamoDB
- [ ] `/transactions/sync` incremental sync with stored cursor
- [ ] Raw Plaid payloads → immutable S3
- [ ] Normalization → `finance.transactions` Iceberg table
- [ ] Glue Catalog registration, Athena queries validated
- [ ] Pending → posted handling, idempotent re-sync
- [ ] Basic transfer detection (amount + date window + opposite sign + different account)
- [ ] Credit-card payments classified as transfers
- [ ] Plaid category → Ledgerly category mapping
- [ ] API: `GET /accounts`, `GET /transactions`, `GET /dashboard`, `POST /sync`
- [ ] Frontend: Overview, Ledger, Accounts, Settings/Connections
- [ ] Single-user auth (Cognito, one user)
- [ ] Deployed via CloudFront + S3

### T1 — Makes it genuinely usable daily
- [ ] Transaction detail panel with raw-payload disclosure
- [ ] Manual category override, persisted and respected on reprocess
- [ ] Manual transfer pairing / unpairing
- [ ] Rules engine: conditions, actions, priority, enable/disable
- [ ] Apply-rule-retroactively (the reprocess capability, surfaced)
- [ ] Merchant normalization (alias → canonical)
- [ ] Search + full filter set
- [ ] Plaid webhooks → event-driven sync
- [ ] EventBridge scheduled reconciliation
- [ ] Derived tables: `monthly_spending`, `monthly_income`, `cash_flow`
- [ ] Net worth over time
- [ ] Keyboard navigation (§3.7C)
- [ ] Dark mode

### T2 — Depth
- [ ] Recurring transaction / subscription detection
- [ ] Year-over-year and month-over-month comparison
- [ ] Spending by merchant
- [ ] Transaction splitting
- [ ] Tags (orthogonal to categories)
- [ ] CSV import and export
- [ ] Provenance popover (§3.7B)
- [ ] Data-quality checks surfaced in UI
- [ ] Iceberg compaction / maintenance job
- [ ] Notes and attachments

### T3 — Later, maybe never
- [ ] Multi-user (the 5–20 trusted friends case)
- [ ] Budgets / targets
- [ ] Investment holdings detail
- [ ] Loan and mortgage amortization
- [ ] Manual assets (real estate, vehicles)
- [ ] Mobile-native app
- [ ] Public read-only API for own data
- [ ] Natural-language query over the Iceberg tables

### Explicitly not building
Goals, bill pay, credit-score tracking, receipt scanning, financial advice, social features, ML categorization, tax prep, household sharing.

---

## 6. Build order

Each phase ends at a checkpoint that produces something observable. We don't start the next phase until the checkpoint holds.

**Phase 0 — Repo & decisions** *(no AWS)* — ✅ **done**
Scaffold `backend/ frontend/ infrastructure/ data/ docs/`, git init, Python env, Vite+React+TS+Tailwind, Terraform skeleton. Resolve §7 open decisions. Write the Iceberg schema DDL before any pipeline code.
→ *Checkpoint: `terraform validate` passes, frontend dev server runs, schema is written down.*

**Phase 1 — Design system in code** — ✅ **done**
Build the Tailwind theme from §3 (colors, type scale, spacing), the Plex font setup, and a component kit: `Table`, `Row`, `Amount`, `Money`, `Label`, `Bar`, `Sparkline`, `FilterBar`, `DetailPanel`, `EmptyState`. Render all four screens against **mocked JSON**.
→ *Checkpoint: all four screens exist and look right, with fake data. No AWS involved. This is where we iterate on the look, cheaply.*
→ **Met.** Verified in a real browser, light and dark. Two bugs found by looking rather than by
reading: cash-flow bars collapsed to zero height (flex child without `min-h-0`), and — more
importantly — the expanded transfer pair rendered both legs as `$2,000.00` with no sign, so the
cancellation the whole product claims to show was invisible. Both fixed; the pair now reads
`−$2,000.00 / +$2,000.00 / Net effect on spending $0.00`.

**Phase 2 — AWS foundation** — ✅ **done**
Terraform S3, DynamoDB, IAM, Lambda, API Gateway, Secrets Manager, CloudWatch. One Lambda returning a hardcoded response through API Gateway.
→ *Checkpoint: `curl` the deployed API and get JSON back.*
→ **Met.** `<api_url — see `terraform output api_url`>/health` returns 200; `/ready`
confirms all wiring. 29 resources, ~$0.40/month. IAM boundary verified by policy simulation: the
API role is denied on both the items table and the Plaid secret (ADR 0004).

**Phase 3 — Plaid connection**
Link token, Plaid Link in the frontend, public-token exchange, access token to Secrets Manager, item + accounts to DynamoDB. **One institution only.**
→ *Checkpoint: Accounts page shows a real bank account with a real balance.*

**Phase 4 — Ingestion pipeline**
`/transactions/sync`, raw → S3, normalize → Iceberg, Glue registration. Test: initial backfill, incremental, duplicate re-run, pending→posted, removal.
→ *Checkpoint: Athena query returns correct transaction count; running sync twice does not change it.*

**Phase 5 — Serving layer**
`GET /transactions`, `GET /accounts`, `GET /dashboard`. Swap the frontend off mocks. Resolve the DynamoDB-vs-Athena read split (§7.3).
→ *Checkpoint: Ledger page shows real transactions from a real bank.*

**Phase 6 — Transfers**
Detection, pairing, `transfer_group_id`, credit-card payment handling, exclusion from income/expense totals, the transfer-link UI (§3.7A), manual override.
→ *Checkpoint: a $2,000 checking→savings move appears once, as a transfer, and changes neither income nor spending totals. A credit-card payment does the same.*

**Phase 7 — Overview**
Derived tables, real dashboard numbers, charts, drill-through from every number to its source rows.
→ *Checkpoint: every number on Overview is clickable and lands on a filtered Ledger view that sums to it.*

**Phase 8 — Rules & categories**
Rules engine, category management, merchant normalization, retroactive reprocess.
→ *Checkpoint: creating a rule reclassifies historical transactions and the dashboard updates.*

**Phase 9 — Hardening**
Cognito properly, error handling, structured logging + correlation IDs, data-quality checks, CI/CD, AWS Budgets alert, Iceberg compaction.
→ *Checkpoint: the spec's §48 Definition of Success list is fully true.*

Phases 1 and 2–4 are independent. Frontend can be iterated on while the pipeline is being built.

---

## 7. Open decisions

These need answers; some block phases.

**7.1 — How does Lambda write to Iceberg?** *(blocks Phase 4)*
Options: PyIceberg direct writes from Lambda (simple, no extra service, but Lambda packaging and memory limits), Athena `MERGE INTO` (SQL-native, handles upserts/pending→posted cleanly, costs per query), or a Glue job (heavier, more ops, better for large batches). Leaning **Athena `MERGE INTO`** — the pending→posted upsert is exactly what MERGE is for, and volume is tiny. Needs a decision before pipeline code.

**7.2 — Iceberg partition spec.** *(blocks Phase 4)*
Personal-scale data is small — a few thousand rows a year. `month(transaction_date)` is probably right; `day()` would create far too many tiny files. Possibly no partitioning at all initially, with sort ordering on `transaction_date`, letting Iceberg metadata pruning do the work. Decide with a real row-count estimate.

**7.3 — What serves the Ledger page?** *(blocks Phase 5)*
Spec says don't use Athena for every interactive read. Options: mirror recent transactions into DynamoDB as a serving layer (fast, adds sync complexity), or Athena with aggressive result caching (simpler, ~1s latency, per-query cost). Leaning **Athena + caching** for T0 and revisiting if it feels slow.

**7.4 — Category taxonomy.**
Design our own tree, or adopt Plaid's Personal Finance Categories as the base and layer overrides? Leaning adopt-and-override — Plaid's taxonomy is decent and it means we start with ~90% correct rather than 0%.

**7.5 — Transfer matching parameters.**
Date window (±3 days? ±5?), amount tolerance (exact? ±$0.01?), confidence threshold for auto-pairing vs. suggest-and-confirm. Needs real data to tune — revisit in Phase 6.

**7.6 — Typeface confirmation.**
IBM Plex Sans + Mono is the recommendation. Alternative: Geist Sans + Mono. Worth deciding in Phase 1 since it's threaded through everything.

---

## 8. Parallel track — Plaid setup checklist

While the repo is being scaffolded:

- [ ] Create Plaid developer account, note **client_id** and **sandbox secret**
- [ ] Request **Development** access (real bank data, limited item count) — has an approval delay, start early
- [ ] Choose products at request time: `transactions` (required), `auth`/`liabilities` optional. Requesting fewer products = faster approval.
- [ ] Note the sandbox test credentials (`user_good` / `pass_good`)
- [ ] Identify the **one** institution to connect first in Phase 3
- [ ] Do **not** put credentials anywhere in the repo — they go straight to AWS Secrets Manager in Phase 2

Sandbox is enough for Phases 0–5. Development access is needed for Phase 6 onward (real transfer patterns can't be tested meaningfully in sandbox).

---

## Sources

Competitive research, September 2026:
- [Copilot Money — design system teardown](https://blakecrosley.com/guides/design/copilot-money)
- [Copilot Money — product site](https://www.copilot.money/)
- [Copilot Help — Transaction Types](https://help.copilot.money/en/articles/3971267-transaction-types)
- [Monarch Help — Transfers and Credit Card Payments](https://help.monarch.com/hc/en-us/articles/360048393292-Transfers-and-Credit-Card-Payments)
- [Monarch Money Review 2026 — Forbes Advisor](https://www.forbes.com/advisor/banking/monarch-budget-app-review/)
- [Lunch Money — features](https://lunchmoney.app/features)
- [Lunch Money — developer tools](https://lunchmoney.app/developers)
- [Fintech Design Trends 2026 — WANDR](https://www.wandr.studio/blog/fintech-design-trends-2026)
- [Fintech Dashboard Design: 9 Real Products, Analyzed](https://adminlte.io/blog/fintech-dashboard-design-examples/)
