# Deferred: additional verifiers — R / Lean / SMT (#17)

Spec only. Current ship surface remains table, citation, and Python sandbox
verifiers under `opencritique_verification`. Tracked as
[issue #17](https://github.com/fraware/OpenCritique-Commons/issues/17).

## Goal

Add **fully specified** verifier packages (not empty stubs) for R, Lean, and
SMT-style checks when maintainers own runtime sandboxes and deterministic
grading.

## Suggested package names (when opened)

- `opencritique_verification_r`
- `opencritique_verification_lean`
- `opencritique_verification_smt`

Or submodules under `opencritique_verification` with the same DoD. Mirror
patterns in `src/opencritique_verification/base.py` (`build_verifier_result`,
evidence-hash binding, fail-closed timeouts).

## Hard DoD (per verifier)

- Public API, version pin, fail-closed timeout / resource limits.
- Deterministic golden tests on maintainer-owned sample inputs.
- Explicit unsupported-surface documentation (what will not be claimed).
- CLI wiring without enabling scientific performance claims.
- Security review for interpreter / prover sandbox escape.

## Non-goals

- Placeholder modules that import-fail or no-op.
- Claiming formal verification of arbitrary papers.
- Enabling leaderboard / performance claims.

## Dependencies

Existing verification package patterns; hosted/local ops capacity if prover
toolchains must be provisioned (ties loosely to #18).
