# ADR 0005 — Transfer detection must pair transactions, not trust Plaid's category

**Status:** Accepted · 2026-09-06
**Blocks:** Phase 6
**Evidence:** live Plaid sandbox data, `ins_109508`, 17 transactions

## Context

Plaid's `personal_finance_category` includes `TRANSFER_IN` and `TRANSFER_OUT`. The cheap
implementation of transfer detection is to trust those labels — which is broadly what competing
products do, and it is why they double-count (DESIGN.md §1).

Before building Phase 6 we checked what those labels actually contain. From a single sandbox item:

| Amount | Description | Plaid category |
|---|---|---|
| −4.22 | `INTRST PYMNT` | `TRANSFER_IN` |
| 1000 | `CD DEPOSIT .INITIAL.` | `TRANSFER_OUT` |
| 5850 | `ACH Electronic Credit GUSTO PAY 123456` | `TRANSFER_OUT` |

`INTRST PYMNT` is **interest income**, not a transfer. `GUSTO PAY` is **payroll**. Neither has a
counterparty account inside the user's own set, so neither is a transfer under our definition. Two
of three `TRANSFER_*`-labelled rows are misclassified for our purposes.

The category also ships a `confidence_level`; the sampled Uber transaction came back `LOW`.

## Decision

Plaid's transfer categories are a **hint that raises a candidate's score, never a classification**.
A transaction becomes `TRANSFER` only when it is paired with an opposing leg in another account
belonging to the same user, recorded in `finance.transfer_groups`.

## Rationale

- A transfer is defined by having two legs. A label on one transaction cannot express that, so it
  cannot be sufficient evidence.
- The failure mode of trusting the label is silent and financial: interest income vanishes from
  the income total because it was labelled `TRANSFER_IN`.
- Requiring a counterparty makes the classification *checkable* — the pair must sum to zero, which
  is a testable invariant (see `test_transfer_pair_nets_to_zero_in_spending`).

## Consequences

- One-sided transfers (money moving to an account the user has not connected) can never be
  auto-confirmed. They stay `EXPENSE`, which is the correct conservative answer — the money did
  leave the user's tracked accounts.
- Transfer detection cannot run on a single item in isolation; it needs the full account set.
- Scoring inputs: amount match, opposite sign, date proximity, account pair, description tokens,
  `transaction_code == "transfer"`, and Plaid category as one weak signal among several.

## Also observed

- **Default sandbox data contains zero pending transactions** (`pending: 0` of 17), so the
  pending→posted path cannot be tested with the stock institution. Sandbox Studio custom users, or
  `/sandbox/transactions/create`, are required — noted for Phase 4 testing.
- All 14 fields the schema assumes are present on live payloads.
