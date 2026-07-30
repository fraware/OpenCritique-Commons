## Summary

<!-- 1–3 bullets: why this change exists -->

## Newcomer / track links

<!-- Delete rows that do not apply -->

- Orientation: [START_HERE.md](../START_HERE.md) (Track A adapters / Track B pilots)
- Reading tier: [docs/CONTRIBUTING_TIERS.md](../docs/CONTRIBUTING_TIERS.md)
- Interchange (adapter / external tool PRs): [docs/compatibility-checklist.md](../docs/compatibility-checklist.md)
- Registry listing (when adding or updating an adapter entry): [docs/community-adapters.md](../docs/community-adapters.md)

## Scope

-
-

## Out of scope

-
-

## Linked issue / ADR

-
-

## Verification

```bash
python -m pip install -e ".[dev]"
bash scripts/check.sh
```

<!-- Add any additional commands actually run -->

## Claim boundary

- [ ] This PR does **not** authorize scientific performance claims (precision, recall, calibration, comparative reviewer quality, or coverage).
- [ ] README / release notes / scorecards remain non-authorizing unless an explicit authorized gate is documented.
- [ ] Sample fixtures and private `runs/` are not presented as production authenticity.

## North Star checklist

- [ ] Traceability from manuscript material through claim, anchors, evidence, defense, adjudication, and resolution is preserved or improved.
- [ ] Failures remain visible; no silent overwrite of historical scientific records.
- [ ] Schema or policy semantics are unchanged, or an ADR records the decision.
- [ ] Fixtures contain no confidential manuscript text.
- [ ] Required public source paths remain present; prohibited transport residue is absent.

## Role-overlap disclosure (alpha staffing)

<!-- Required while staffing is thin. Example: "Author implemented matcher and wrote conformance fixtures; not an independent evaluation." -->

-

## Reviewer notes

-
