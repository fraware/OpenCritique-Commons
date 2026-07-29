# ADR-0003: Second reviewer-system adapter target

- Status: Accepted
- Date: 2026-07-28
- Issues: #5

## Decision

Adopt **OpenReviewer** ([maxidl/openreviewer](https://github.com/maxidl/openreviewer),
model [Llama-OpenReviewer-8B](https://huggingface.co/maxidl/Llama-OpenReviewer-8B),
paper arXiv:2412.11948) as the second independent reviewer-system adapter target.

## Architecture difference vs Coarse

| Dimension | Coarse | OpenReviewer |
|---|---|---|
| Primary output | Structured `Review` / `DetailedComment` JSON with severity/confidence/quote | Conference-template **Markdown** review sections (strengths, weaknesses, questions, scores) |
| Anchoring | Explicit quotation spans | Prose critiques; page/quote anchors usually **unavailable** |
| Severity/confidence | Explicit enums | Often absent or only ordinal recommendation scores |
| Runtime | External pipeline producing JSON exports | Fine-tuned LLM over PDF→markdown extraction |
| License / inspectability | MIT (upstream Coarse) | Open research release + model weights on Hugging Face; inspectable prompts/templates |

This pairing demonstrates system neutrality: OpenCritique must not reshape the core concern
schema to fit either contract.

## Data rights

- Adapter fixtures in this repository are **maintainer-owned sample fixtures**
  quoting text under `corpus/samples/`.
- They are not redistributed model outputs from real third-party manuscripts.
- Genuine OpenReviewer runs on third-party PDFs require separate rights clearance
  (issue #5 / #7 path).
- Adapter success does **not** authorize reviewer-quality or performance claims.
- Sample adapter contract id: `opencritique-sample-adapter-contract-v1`
  (not a pretend upstream Git SHA).

## Integration posture (alpha)

Full model execution is **not** required for adapter conformance. This repository ships:

1. A pinned output-contract version for OpenReviewer-style markdown/JSON reviews
2. Deterministic conversion into `EvaluationSubmission` without inventing missing fields
3. Provenance hashing of original fixture bytes
4. Semantic-loss analysis vs the Coarse adapter

When authentic redistributable outputs become available, they replace or supplement the
synthetic fixtures without changing the core schema.

## Alternatives considered

- **AliManjotho/open-reviewer** multi-agent issue maps: promising JSON outputs, but younger
  maintenance signal and less cited public contract for ML conference reviews.
- Building a toy second format in-repo: rejected; would not demonstrate external neutrality.
