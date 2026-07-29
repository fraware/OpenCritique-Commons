# Core integrity review (recovered / rebuilt paths)

Review date: 2026-07-29  
Scope: evaluation engine/signing/trust, registry migrate/config/readyz, PDF
security, studio CSP — paths rebuilt during stubs-closed hardening
([PR #15](https://github.com/fraware/OpenCritique-Commons/pull/15)).

## Verdict

**No P0 integrity defects remaining** after the fixes listed below.

Residual items are tracked as non-blocking follow-ups (P2/P3), not silent
assumptions.

## Findings

| ID | Area | Severity | Finding | Disposition |
|---|---|---|---|---|
| CIR-01 | `pdf_security.py` | P1 | Substring match on `/Trapped` treated ordinary catalog metadata as a fail-closed block, risking false refusals of benign PDFs. | **Fixed** — removed `/Trapped` from block list; active-content markers matched as PDF name tokens. |
| CIR-02 | `pdf_security.py` | P2 | `/JS` and related markers used bare substring search, allowing prefix collisions with longer names. | **Fixed** — `_pdf_name_present` requires a PDF name delimiter after the token. |
| CIR-03 | `studio.py` | P2 | `/studio/app.js` and `/studio/styles.css` returned only `Cache-Control`, omitting CSP / nosniff / referrer policy present on `/studio`. | **Fixed** — shared security headers on all studio asset routes; CSP adds `object-src 'none'` and `base-uri 'self'`. |
| CIR-04 | `signing.py` | P3 | `verify_envelope` previously accepted any cryptographically valid signature when called without trust material. | **Fixed** — requires trust store / trusted PEM, or explicit `allow_untrusted_test=True`. Production and development policies fail closed without trust material. Prefer `verify_envelope_detailed`. |
| CIR-05 | `engine.py` | OK | Case path traversal guarded via `is_relative_to`; metrics withhold division-by-zero; performance claims gated by manifest. | No change |
| CIR-06 | `migrate.py` | OK | Locates `alembic.ini` from package/repo root; restores prior `OPENCRITIQUE_DATABASE_URL` after upgrade. | No change |
| CIR-07 | `config.py` / `/readyz` | OK | Execution modes validated; BYOK requires provider + API key; `performance_claims_authorized` cannot be enabled; readiness probes DB + artifact root and fails startup when not ready. | No change |
| CIR-08 | `trust.py` | OK | Production rejects test and development-only keys; revocation and superseded/historical policies fail closed. | No change |

## Fixes applied in this review

1. Token-bounded PDF active-content detection; drop `/Trapped` false positive.
2. Studio asset routes share CSP and related headers.
3. Regression tests cover benign `/Trapped` PDFs, `/JS` token boundaries, and studio asset headers.

## Residual tracked items (non-P0)

- CIR-04 closed: `verify_envelope` now requires trust material or `allow_untrusted_test=True`.
- Deeper PDF parser coverage (cross-reference streams, encrypted PDFs) remains out of scope until OCR/document-intelligence depth work (deferred product issue).

## Statement

Recovered/rebuilt integrity risk for the scoped paths is documented. P0/P1
defects found in this pass are fixed with tests. No P0 integrity defects remain
open.
