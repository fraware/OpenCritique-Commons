# Deferred: expert qualification and calibration at scale (#19)

Spec only. Sample studio / appeals / matcher-audit paths exist; natural-case
expert operations do not. Tracked as
[issue #19](https://github.com/fraware/OpenCritique-Commons/issues/19) under
epic [#14](https://github.com/fraware/OpenCritique-Commons/issues/14).

## Goal

Operationalize expert qualification, calibration, compensation logistics, and
conflict handling at a scale sufficient for natural-case adjudication — without
fabricating natural evidence or unlocking §12 claims.

## Hard DoD

- Qualification rubric and calibration set (sample-first; natural only after
  #7).
- Compensation and operational ownership documented (shared with #14;
  see [expert-compensation-terms.md](expert-compensation-terms.md) /
  [expert-program-ops.md](expert-program-ops.md)).
- Conflict-of-interest and blinding procedure for matcher-audit (#6) and
  adjudication.
- Throughput plan for ≥40 public claim cases (Milestone 4 / §14).
- Withdrawal and attribution handling aligned with the rights memorandum.
- No reviewer-quality leaderboard until the §12 matrix authorizes it.

## Non-goals

- Closing #14 with sample-only workflows alone.
- Paying experts against uncleared natural manuscripts.
- Implementing full scale ops in this roadmap phase.

## Dependencies

- Epic #14 pilot execution (external).
- Natural corpus (#7), matcher-audit volume (#6), production signing (#4).
- Staffing roster evidence remains fail-closed until filled with real IDs
  (`scripts/check_v09_gates.py`).

## Sequencing note

This deferred depth depends on external pilot execution more than engineering
spikes. Spec readiness ≠ claim unlock.
