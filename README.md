# OpenCritique Commons v0.5-alpha

OpenCritique Commons is system-neutral infrastructure for representing, adjudicating, and evaluating scientific concerns. It is designed to make automated criticism inspectable and testable without allowing synthetic fixtures, incomplete reference sets, or model-judge preferences to masquerade as scientific evidence.

The v0.5-alpha release hardens the evaluation boundary with a production-compatible Coarse converter, Ed25519-signed scorecards, matcher sensitivity reports, governed novel-concern queue exports, and a rights-first external-source acquisition ledger. Expert recruitment remains parallel to engineering execution.

## North Star

A serious scientific criticism should remain traceable from manuscript material through claim reconstruction, anchors, evidence, the strongest manuscript defense, independent adjudication, and resolution. The project measures the validity and calibration of concerns. Report length, model fluency, and agent count remain secondary.

## What v0.5 adds

### Production Coarse ingestion

- validates Coarse's public `Review` and `DetailedComment` structure while permitting additive upstream fields;
- preserves verbatim quotations, severity, confidence, commit, model, cost, and latency provenance;
- converts missing benchmark cases into explicit abstentions;
- keeps claim reconstruction and concern taxonomy provisional;
- refuses mappings outside the frozen benchmark manifest.

### Cryptographically verifiable scorecards

- generates Ed25519 key pairs;
- signs canonical scorecard JSON;
- embeds payload hashes and public-key fingerprints;
- detects payload, signature, and key-substitution tampering;
- supports verification against a separately distributed trusted public key.

A valid signature establishes artifact integrity and signer identity relative to a trusted key. It does not establish scientific correctness.

### Matcher sensitivity and governed novel concerns

- evaluates six predefined matcher configurations;
- reports stable and unstable concern-reference pairs;
- reports metric and match-count ranges;
- exports unmatched submitted concerns with immutable result and submission hashes;
- keeps all novel candidates in `pending_expert_adjudication` state until qualified human review occurs.

### Rights-first acquisition

The external-source ledger records PaperAudit-Bench, LimitGen, CLAIMCHECK, MMReview, and PeerQA as acquisition candidates. No case content is imported. Public accessibility, paper metadata, and dataset availability are treated separately from authorization to process or redistribute manuscripts and annotations.

## Evidentiary layers

The repository maintains four distinct layers:

1. **Synthetic conformance fixtures** validate software and policy behavior.
2. **Calibration cases** qualify experts against stable reference decisions.
3. **Rights-cleared natural cases** support scientific evaluation.
4. **Live private cases** measure generalization against unreleased material.

Only the first layer is bundled in this release. The natural-case pilot manifest continues to report zero included cases. No reviewer-quality claim is made.

## Repository layout

```text
src/opencritique_schema/            concern, evidence, adjudication, and manifest schemas
src/opencritique_registry/          immutable registry, rights, expert workflows, studio
src/opencritique_evaluation/        evaluator, sensitivity, signing, novel queues
src/opencritique_adapters/          production external-review converters
src/opencritique_acquisition/       rights-first external-source ledgers
benchmarks/reference-v0.1/          synthetic conformance benchmark and echo submission
cases/reference/                    ten synthetic scientific-critique fixtures
corpus/pilot-v0.1/                  empty rights-cleared natural-case pilot manifest
corpus/acquisition-v0.1/            external-source ledger with zero imported cases
docs/community/                     contributor and expert organic-growth program
docs/evaluation/                    evaluation contract and claim-boundary policy
roadmap/                             public workstreams and issue-ready backlog
.github/                             CI, security, release, and contribution workflows
openapi/                             generated API contract
reports/                             release validation evidence
```

## Installation

Python 3.12 or later is required.

```bash
python -m pip install --no-build-isolation -e ".[dev]"
```

## Run the synthetic conformance evaluation

```bash
opencritique evaluation run \
  --manifest benchmarks/reference-v0.1/manifest.json \
  --benchmark-root . \
  --submission benchmarks/reference-v0.1/reference-echo-submission.json \
  --output scorecards/reference-echo-result.json

opencritique evaluation scorecard \
  --result scorecards/reference-echo-result.json \
  --json-output scorecards/reference-echo-scorecard.json \
  --html-output scorecards/reference-echo-scorecard.html
```

The reference-echo adapter copies fixture fields and exists only to validate the contract. A perfect score from it provides no evidence of scientific generalization. The generated scorecard therefore displays `Performance-claim status: NOT AUTHORIZED`.

## v0.5 commands

Convert a set of Coarse JSON reviews into the frozen evaluation contract:

```bash
opencritique adapters coarse \
  --manifest benchmarks/reference-v0.1/manifest.json \
  --benchmark-root . \
  --mapping adapters/coarse/examples/reference-map.json \
  --output /tmp/coarse-submission.json
```

Inspect matcher dependence:

```bash
opencritique evaluation sensitivity \
  --manifest benchmarks/reference-v0.1/manifest.json \
  --benchmark-root . \
  --submission benchmarks/reference-v0.1/reference-echo-submission.json \
  --output /tmp/matcher-sensitivity.json
```

Sign and verify a scorecard:

```bash
opencritique evaluation keygen \
  --private-key /secure/scorecard-private.pem \
  --public-key scorecard-public.pem
opencritique evaluation sign-scorecard \
  --scorecard scorecards/reference-echo-scorecard.json \
  --private-key /secure/scorecard-private.pem \
  --output scorecards/reference-echo-scorecard.signed.json
opencritique evaluation verify-scorecard \
  --envelope scorecards/reference-echo-scorecard.signed.json \
  --trusted-public-key scorecard-public.pem
```

Validate the acquisition ledger:

```bash
opencritique acquisition validate corpus/acquisition-v0.1/SOURCES.json
```

## Registry and expert-program quick start

```bash
opencritique registry init \
  --database-url sqlite:///./opencritique.db \
  --artifact-root ./opencritique-artifacts

opencritique registry bootstrap-admin \
  --actor-id opencritique-admin \
  --database-url sqlite:///./opencritique.db
```

Import the synthetic reference cases and run conformance:

```bash
opencritique registry import-reference cases/reference \
  --project-root . \
  --actor-id opencritique-admin \
  --database-url sqlite:///./opencritique.db \
  --artifact-root ./opencritique-artifacts

opencritique conformance run cases/reference
opencritique registry conformance \
  --database-url sqlite:///./opencritique.db \
  --artifact-root ./opencritique-artifacts
```

Start the service:

```bash
opencritique registry serve \
  --database-url sqlite:///./opencritique.db \
  --artifact-root ./opencritique-artifacts \
  --host 127.0.0.1 \
  --port 8000
```

- OpenAPI documentation: `/docs`
- Adjudication studio: `/studio`

## Work that does not wait for the expert panel

The following workstreams are immediately open:

- reviewer-system adapters;
- benchmark loaders and rights manifests;
- deterministic anchor resolution;
- multimodal artifact representation;
- statistical and formal-tool integrations;
- prompt-injection and malicious-document testing;
- local deployment and reproducible packaging;
- scorecard and observatory design;
- privacy, retention, and consent controls;
- documentation, examples, accessibility, and internationalization;
- synthetic mutation generation and validation tooling.

Experts are required for calibration gold labels, natural-case concern validation, novel-concern adjudication, domain taxonomies, and final scientific claims. Their future arrival increases the evidence base; it does not hold the codebase idle.

## Organic expert-panel growth

The project does not need to recruit a large panel before public credibility exists. The intended sequence is:

1. publish a serious repository with executable schemas, tests, security posture, and a bounded roadmap;
2. attract engineers, evaluation researchers, and early scientific collaborators through useful open work;
3. publish a transparent call on X and adjacent communities once the expert program can show concrete tasks, honoraria, attribution rules, and a functioning studio;
4. qualify experts through calibration before assigning production work;
5. compensate completed scientific labor under written engagements.

See [`docs/community/EXPERT_PANEL_GROWTH.md`](docs/community/EXPERT_PANEL_GROWTH.md).

## Validation

The complete release gate runs:

```bash
bash scripts/check.sh
```

It executes the test suite, static checks, schema conformance, registry import and audit, cumulative migrations, deterministic evaluation, claim-boundary assertions, OpenAPI generation, acquisition-ledger validation, Coarse conversion, matcher sensitivity, and signed-scorecard verification.

## Explicit limitations

- No rights-cleared natural manuscript is bundled.
- No independent system comparison is included.
- Deterministic matching is a transparent baseline whose sensitivity must be reported; it does not replace expert novel-concern adjudication.
- The reference-echo system has direct access to fixture answers and must never appear on a performance leaderboard.
- The claim gate checks benchmark metadata and case count; independent governance must verify that those declarations are true.
- No external security, privacy, research-ethics, signing-key governance, or scientific audit has been completed.

The complete validation record is available at [`reports/release-validation-v0.5.md`](reports/release-validation-v0.5.md).

## License

Software is licensed under Apache License 2.0. Manuscripts, annotations, benchmark cases, calibration material, and other data retain separate rights metadata.
