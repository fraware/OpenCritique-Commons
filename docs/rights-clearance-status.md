# Rights clearance status — formal negative finding

**Date:** 2026-07-29  
**Issue:** [#7](https://github.com/fraware/OpenCritique-Commons/issues/7)  
**Checklist:** [rights-memorandum.md](rights-memorandum.md)

## Verdict

**No affirmative written clearance** is available for importing natural manuscript
PDFs (or production adapter exports that embed uncleared manuscript text) into
the public OpenCritique Commons corpus at this time.

Accordingly: **no external natural cases are imported** in this workstream.
`performance_claims_authorized` remains **false**.

## Investigation summary (PeerQA and alternates)

| Checklist step | Finding |
|---|---|
| Identify artifact class | PeerQA publishes QA pairs; many linked PDFs are **not** redistributed by PeerQA maintainers |
| Locate controlling license / ToS | PeerQA QA pairs: **CC-BY-NC-SA 4.0**; code: Apache-2.0; OpenReview-sourced PDFs explicitly **without** redistributable license in PeerQA release |
| Written grant for evaluation use | **Absent** for OpenCritique public import of full manuscript PDFs / figures |
| Written grant for redistribution | **Absent** for uncleared PDFs; PeerQA states it cannot provide raw PDFs for copyright reasons |
| Training / model-use restriction | CC-BY-NC-SA imposes non-commercial + share-alike constraints even on QA pairs; not assessed as sufficient for unrestricted public corpus import without counsel sign-off |
| Attribution / share-alike | Would apply to QA pairs under CC-BY-NC-SA; **not** a substitute for manuscript PDF clearance |
| Withdrawal / cancel contact | Not established for a would-be OpenCritique import profile |
| Case-level rights record | **Not created** for natural imports (none imported) |
| Ledger entry | No new natural source enrolled for public redistributable bytes |
| Import dry-run | Existing reject paths for missing grants remain in force; no uncleared PDFs added |

### Sources consulted (public)

- PeerQA paper (NAACL 2025): https://aclanthology.org/2025.naacl-long.22/
- PeerQA GitHub: https://github.com/UKPLab/PeerQA
- Hugging Face dataset card: https://huggingface.co/datasets/UKPLab/PeerQA

PeerQA maintainers document that papers without a permissible license are **not**
published in their release; users must download PDFs independently and respect
original copyright. That is **not** an affirmative written grant authorizing
OpenCritique to copy, transform, benchmark, or redistribute those manuscripts.

No alternate external source under investigation produced archived written
clearance covering manuscript PDF / figure redistribution for this repository.

## Artifact classes decision

| Class | Decision |
|---|---|
| PeerQA QA pairs only | Not imported in this pass (NC/SA counsel review still open; not required to close #7 DoD via negative finding) |
| Natural manuscript PDFs / figures | **Not imported** |
| Derived OpenCritique records from natural text | **Not imported** |
| Maintainer-owned samples under `corpus/samples/` | Unchanged; tooling conformance only |

## What would unblock a future import

1. Archived written grant (or explicit license clause) covering evaluation use
   **and**, if public, redistribution of the chosen artifact classes.
2. Case-level rights records + acquisition ledger entry with source hashes.
3. Proven reject path for artifacts outside the approved profile (already present).

Until then, issues #3 / #5 production fixture trees remain blocked on the same
rights prerequisite for any export embedding manuscript text.

## Claim boundary

This finding closes the **process** DoD option on issue #7 (documented that no
compliant import is currently possible). It does **not** authorize scientific
performance claims or fabricate natural evidence.
