# Sample Studio walkthrough

Text steps for the **sample** Studio adjudication path from the README golden
path. Uses maintainer-owned bootstrap data only.

**Non-claims:** sample Studio tasks are software conformance, not production
authenticity or scientific performance. Scorecards and claim surfaces stay
`NOT AUTHORIZED`.

## Preconditions

1. Install: `python -m pip install -e ".[dev]"`
2. Optional offline adapter demo first:
   - POSIX: `bash scripts/demo_adapter_path.sh`
   - Windows: `powershell -File scripts/demo_adapter_path.ps1`
3. Local SQLite is enough for this walkthrough. Compose / Postgres users: see
   [deployment-local.md](../deployment-local.md).

## Steps

### 1. Bootstrap the sample workspace

```bash
opencritique-registry bootstrap-sample-workspace
```

The command prints role tokens. Keep the **adjudicator** token for the next
steps. Do not commit tokens or local DB files.

### 2. Serve the registry / Studio UI

```bash
opencritique-registry serve
```

Default Studio URL: `http://127.0.0.1:8000/studio`

Compose users: `docker compose up --build` migrates automatically; run bootstrap
against Postgres, then open Studio as documented in
[deployment-local.md](../deployment-local.md).

### 3. Connect as adjudicator

1. Open `http://127.0.0.1:8000/studio`
2. Paste the **adjudicator** token from bootstrap
3. Click **Connect**

### 4. Claim and inspect

1. Click **Claim adjudication**
2. Open the sample case (REF-01 in the sample workspace)
3. Inspect manuscript / concern context as presented in the UI
4. Submit the adjudication decision for the sample task

This exercises the adjudication UX and claimable-task flow. It does **not**
authorize public performance metrics.

### 5. Optional: private live handoff (not this demo)

Live Coarse / OpenReviewer exports under `runs/` can be imported for
**operator-local** Studio work on rights-owned material. That path is separate
from sample bootstrap, stamps `evidence_class=private_live`, and still keeps
claims unauthorized. See [private-evaluation-pilot.md](../private-evaluation-pilot.md)
and the README live-upstream track. Do not promote `runs/` into
`fixtures/*/production/`.

## Optional screenshots

If you add UI captures, place non-sensitive shots under
`docs/examples/assets/` (no tokens, no private manuscripts, no API keys).

## Related

- [examples README](README.md)
- [method-pilot-report.md](method-pilot-report.md)
- [deployment-local.md](../deployment-local.md)
- Offline demo: [`scripts/demo_adapter_path.sh`](../../scripts/demo_adapter_path.sh)
