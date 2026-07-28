## Summary

<!-- 1–3 bullets: why this change exists -->

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
