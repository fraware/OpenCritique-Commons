# Adapter skeleton (third-adapter template)

Copy these stubs into `src/opencritique_adapters/` (and a matching
`fixtures/<slug>/` tree when you have maintainer-owned samples). Rename
`example` → your adapter slug.

This directory does **not** ship a real third upstream. It is a DX scaffold
only. See [docs/adapter-authoring.md](../../docs/adapter-authoring.md).

## Files

| File | Role |
|---|---|
| `contract.py` | Sample contract pins; claims locked |
| `adapter.py` | Review models, map models, `convert_example_benchmark` |
| `loss.py` | Conversion-loss report stub |
| `cli_snippet.py` | Typer command to paste into `opencritique_adapters.cli` |
| `map.example.json` | Benchmark map shape |
| `tests/test_adapter_placeholder.py` | Expand once fixtures exist |

## Rules

- `EXAMPLE_PERFORMANCE_CLAIMS_AUTHORIZED = False` always.
- Sample `code_commit` / map pin = sample contract id, not a fabricated Git SHA.
- Do not create `fixtures/*/production/` reviews until rights + authentic exports
  exist ([adapter-authenticity.md](../../docs/adapter-authenticity.md)).
