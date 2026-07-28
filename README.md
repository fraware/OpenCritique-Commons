# OpenCritique Commons

OpenCritique Commons is open, system-neutral infrastructure for representing, adjudicating, and evaluating scientific concerns. It makes automated criticism inspectable without allowing synthetic fixtures, incomplete reference sets, or model-judge preferences to masquerade as scientific evidence.

## North Star

A serious scientific criticism should remain traceable from manuscript material through claim reconstruction, anchors, evidence, the strongest manuscript defense, independent adjudication, and resolution.

## Included packages

- `opencritique_schema` — normative scientific-concern, evidence, adjudication, resolution, and run schemas.
- `opencritique_registry` — immutable artifacts, rights controls, blinded expert workflows, and the adjudication API/studio.
- `opencritique_evaluation` — deterministic matching, scoring, sensitivity analysis, novel-concern queues, and signed scorecards.
- `opencritique_adapters` — reviewer-system ingestion, beginning with Coarse.
- `opencritique_acquisition` — rights-first external-source acquisition records.

## Install

```bash
python -m pip install -e '.[dev]'
bash scripts/check.sh
```

## Evidentiary boundary

The current implementation is infrastructure. It does not authorize claims about reviewer precision, recall, calibration, comparative performance, or scientific coverage. Those claims require rights-cleared natural cases, independent expert adjudication, frozen evaluations, and published limitations.

## Status

The repository is at `v0.5-alpha`. Engineering and public-case acquisition proceed independently of expert-panel recruitment. Expert recruitment will open after the repository, case pipeline, compensation terms, and calibration tasks are mature enough to justify serious participation.
