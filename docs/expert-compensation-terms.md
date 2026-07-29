# Expert compensation terms template (issue #14)

**Policy version:** `expert-compensation-v0.1`  
**Status:** template for funded pilots; rates are `TBD` until a funding schedule
is adopted by maintainers.

## Principles

1. Payment is tied to **task completion**, never to a particular scientific
   decision or outcome.
2. Compensation records are **private**; public scorecards must not embed payer
   identity or amounts.
3. Opt-in attribution is independent from payment
   ([expert-attribution-policy.md](expert-attribution-policy.md)).
4. Sponsors and system developers may not condition payment on desired
   adjudication outcomes ([GOVERNANCE.md](../GOVERNANCE.md)).

## Task classes (schedule slots)

| Task class | Unit | Rate (USD) | Notes |
|---|---|---:|---|
| Calibration attempt (domain profile) | attempt | TBD | Eligibility only; not a public rank |
| Primary adjudication (sample case) | concern task | TBD | Blinded payload |
| Primary adjudication (natural case) | concern task | TBD | Requires rights-cleared cases |
| Tie-break adjudication | concern task | TBD | Independent of primaries |
| Matcher-audit judgment | decision | TBD | See matcher-audit protocol |

Replace `TBD` with a published schedule before paying experts. Until funded,
volunteer / maintainer labor must be disclosed as non-independent for claim
gates that require paid independent adjudication.

Machine check: when any schedule `amount_minor` is `null`,
`assert_paid_pilot_rates_configured` fails with `paid_pilot_rates_unset` and
registry compensation creation is blocked (HTTP 409).

## Invoicing and retention

- Retain task completion receipts separately from scientific records.
- Do not store payment credentials in this repository.
- Withdrawal of an expert does not rewrite historical adjudication events.

## Claim boundary

Publishing this template does **not** authorize performance claims or assert that
a paid pilot has been executed.
