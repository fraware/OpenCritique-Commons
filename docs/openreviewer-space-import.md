# OpenReviewer Space import (no GPU)

OpenReviewer is **Llama-OpenReviewer-8B** (Hugging Face). It is **not** OpenAI
Chat Completions.

**Blunt:** an `OPENAI_API_KEY` / `OPENCRITIQUE_BYOK_API_KEY` does **not** run
OpenReviewer. BYOK credentials are for the Coarse live runner and registry BYOK
mode only.

Private imports under `runs/` stamp `evidence_class=private_live` and
`performance_claims_authorized=false`. They do **not** auto-promote into
`fixtures/*/production/`.

## Preferred path: HF Space → `--from-export`

1. Open the upstream Space: https://huggingface.co/spaces/maxidl/openreviewer
2. Run a review on a manuscript you have rights to process.
3. Save the Space output as JSON or Markdown (for example
   `runs/openreviewer/space-export.json`). A fixture-shaped example lives at
   `fixtures/openreviewer/reviews/orv-01.json` (sample only — copy shape into
   `runs/`, never into `fixtures/*/production/`).
4. Normalize into a private live export:

```bash
opencritique runners openreviewer \
  --from-export runs/openreviewer/space-export.json \
  --output runs/openreviewer/review.json
```

5. Register for Studio adjudication (shared handoff with live Coarse):

```bash
opencritique-registry import-live-run \
  --from runs/openreviewer/review.json \
  --manuscript path/to/your-manuscript.md
```

Or combine steps:

```bash
opencritique runners openreviewer \
  --from-export runs/openreviewer/space-export.json \
  --output runs/openreviewer/review.json \
  --register \
  --register-manuscript path/to/your-manuscript.md
```

6. Start Studio (`opencritique-registry serve`), paste the adjudicator token,
   Connect, then Claim adjudication.

## Optional: HF local GPU

```bash
pip install -e ".[live-openreviewer]"
opencritique runners openreviewer \
  --manuscript path/to/paper.md \
  --output runs/openreviewer/hf-local.json
```

CPU requires an explicit `--allow-cpu` override (slow; not recommended).

## Non-claims

- Private live ≠ production authenticity ≠ scientific performance claims.
- Default CI does not call HF downloads or paid APIs for this path.
- See also [deployment-byok.md](deployment-byok.md) and the README live extras section.
