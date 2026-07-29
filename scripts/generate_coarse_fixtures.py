#!/usr/bin/env python3
"""Generate Coarse-shaped adapter fixtures from maintainer-owned sample manuscripts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from opencritique_adapters.contract import (
    COARSE_FIXTURE_KIND,
    COARSE_SAMPLE_ADAPTER_CONTRACT_ID,
    COARSE_UPSTREAM_COMMIT_PIN,
    COARSE_UPSTREAM_CONTRACT_VERSION,
)
from opencritique_evaluation.models import (
    BenchmarkCaseRef,
    BenchmarkEvidenceClass,
    BenchmarkManifest,
    ReferenceCompleteness,
)
from opencritique_schema.canonical import content_hash
from opencritique_schema.models import (
    ActorReference,
    ActorType,
    ArtifactReference,
    IngestionMetadata,
    Manuscript,
    ManuscriptVersion,
    RightsClassification,
    SourceFormat,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "coarse"
REVIEWS = FIXTURES / "reviews"
MAPS = FIXTURES / "maps"
BENCH = ROOT / "benchmarks" / "coarse-synth-v0.1"
CASES = BENCH / "cases"

ACTOR = ActorReference(
    actor_id="opencritique-maintainer",
    actor_type=ActorType.ORGANIZATION,
    display_name="OpenCritique Commons maintainers",
)

# Quotes are taken verbatim from corpus/samples/ manuscripts.
SPECS: list[dict] = [
    {
        "slug": "econ-01",
        "domain": "economics",
        "profile": "economics_statistics",
        "sample": "corpus/samples/sample-econ-01/manuscript.md",
        "title": "Sample: Identification under clustered sampling",
        "quote": "Under clustered sampling the sandwich estimator understates variance.",
        "feedback": (
            "The variance discussion omits cluster-robust alternatives and finite-sample caveats."
        ),
        "severity": "major",
        "confidence": "high",
        "extra": {
            "number": 2,
            "title": "Sample: Parallel-trends assumption unstated",
            "quote": "We interpret the coefficient as a causal effect of the policy.",
            "feedback": "Causal language appears without an explicit parallel-trends discussion.",
            "severity": "critical",
            "confidence": "medium",
        },
    },
    {
        "slug": "econ-02",
        "domain": "statistics",
        "profile": "economics_statistics",
        "sample": "corpus/samples/sample-stats-01/manuscript.md",
        "title": "Sample: Multiple-testing correction missing",
        "quote": (
            "All eighteen secondary endpoints are reported as significant at p < 0.05."
        ),
        "feedback": (
            "Secondary endpoints lack multiplicity control; false discoveries remain plausible."
        ),
        "severity": "major",
        "confidence": "high",
    },
    {
        "slug": "ml-01",
        "domain": "machine_learning",
        "profile": "empirical_ml",
        "sample": "corpus/samples/sample-ml-01/manuscript.md",
        "title": "Sample: Train-test leakage risk",
        "quote": (
            "Features were standardized using statistics computed on the full dataset."
        ),
        "feedback": (
            "Standardization on the full dataset risks optimistic evaluation through leakage."
        ),
        "severity": "critical",
        "confidence": "high",
    },
    {
        "slug": "ml-02",
        "domain": "machine_learning",
        "profile": "empirical_ml",
        "sample": "corpus/samples/sample-ml-01/manuscript.md",
        "title": "Sample: Baseline under-tuned",
        "quote": "The baseline uses default hyperparameters from the reference library.",
        "feedback": "Untuned baselines weaken comparative claims about proposed gains.",
        "severity": "minor",
        "confidence": "medium",
    },
    {
        "slug": "theory-01",
        "domain": "mathematics",
        "profile": "theory_heavy",
        "sample": "corpus/samples/sample-theory-01/manuscript.tex",
        "title": "Sample: Bound depends on unstated Lipschitz constant",
        "quote": r"Therefore the excess risk decays as $O(1/\sqrt{n})$ uniformly.",
        "feedback": "Uniformity appears to require a Lipschitz constant that is never stated.",
        "severity": "major",
        "confidence": "high",
    },
    {
        "slug": "theory-02",
        "domain": "theoretical_cs",
        "profile": "theory_heavy",
        "sample": "corpus/samples/sample-theory-01/manuscript.tex",
        "title": "Sample: Existence vs constructive algorithm conflated",
        "quote": (
            "An efficient algorithm follows immediately from the probabilistic method."
        ),
        "feedback": (
            "Probabilistic existence does not by itself yield an efficient constructive algorithm."
        ),
        "severity": "major",
        "confidence": "medium",
    },
    {
        "slug": "fig-01",
        "domain": "biology",
        "profile": "figure_table_heavy",
        "sample": "corpus/samples/sample-figtable-01/manuscript.md",
        "title": "Sample: Figure axis scale obscures effect size",
        "quote": "Figure 3 shows a clear separation between treatment and control trajectories.",
        "feedback": "The truncated y-axis may exaggerate separation; report absolute effect sizes.",
        "severity": "minor",
        "confidence": "medium",
        "object_hint": "Figure 3",
    },
    {
        "slug": "table-01",
        "domain": "epidemiology",
        "profile": "figure_table_heavy",
        "sample": "corpus/samples/sample-figtable-01/manuscript.md",
        "title": "Sample: Table omits confidence intervals",
        "quote": "Table 2 reports point estimates for each adjusted risk ratio.",
        "feedback": "Point estimates without intervals impede severity assessment of uncertainty.",
        "severity": "major",
        "confidence": "high",
        "object_hint": "Table 2",
    },
    {
        "slug": "multi-01",
        "domain": "linguistics",
        "profile": "multilingual_ish",
        "sample": "corpus/samples/sample-multi-01/manuscript.md",
        "title": "Sample: Non-English quote preserved",
        "quote": "La precision del modelo aumenta cuando se excluyen los casos ambiguos.",
        "feedback": "Excluding ambiguous cases after seeing labels can inflate reported precision.",
        "severity": "major",
        "confidence": "medium",
        "language": {
            "primary": "es",
            "notes": "Spanish excerpt from maintainer-owned multilingual sample.",
        },
    },
    {
        "slug": "multi-02",
        "domain": "social_science",
        "profile": "multilingual_ish",
        "sample": "corpus/samples/sample-multi-01/manuscript.md",
        "title": "Sample: Mixed-language methods description",
        "quote": "Wir verwenden eine zweistufige Regression mit robusten Standardfehlern.",
        "feedback": (
            "Two-stage procedure needs clearer exclusion restrictions; language alone is fine."
        ),
        "severity": "minor",
        "confidence": "low",
        "language": {
            "primary": "de",
            "notes": "German excerpt from maintainer-owned multilingual sample.",
        },
    },
    {
        "slug": "stats-03",
        "domain": "statistics",
        "profile": "economics_statistics",
        "sample": "corpus/samples/sample-stats-01/manuscript.md",
        "title": "Sample: Unresolved quotation by design",
        "quote": "THIS QUOTE DOES NOT APPEAR IN ANY SAMPLE MANUSCRIPT TEXT BODY.",
        "feedback": (
            "Adapter must leave unmatched quotations unresolved rather than inventing anchors."
        ),
        "severity": "major",
        "confidence": "high",
        "force_unresolved": True,
    },
    {
        "slug": "ml-03",
        "domain": "machine_learning",
        "profile": "empirical_ml",
        "sample": "corpus/samples/sample-ml-01/manuscript.md",
        "title": "Sample: Calibration plot misread",
        "quote": "Calibration curves indicate near-perfect probability estimates.",
        "feedback": "Visual near-overlap is not a substitute for reported Brier or ECE statistics.",
        "severity": "minor",
        "confidence": "medium",
    },
]


def _artifact_from_sample(relpath: str) -> ArtifactReference:
    path = ROOT / relpath
    data = path.read_bytes()
    media = "text/markdown" if path.suffix == ".md" else "application/x-tex"
    return ArtifactReference(
        uri=relpath.replace("\\", "/"),
        sha256=hashlib.sha256(data).hexdigest(),
        media_type=media,
        byte_size=len(data),
    )


def _hashed_record(model_cls, payload: dict):
    payload = dict(payload)
    payload["content_hash"] = "0" * 64
    obj = model_cls.model_validate(payload)
    return obj.model_copy(update={"content_hash": content_hash(obj)})


def build_case(spec: dict) -> tuple[str, dict, str]:
    slug = spec["slug"]
    case_id = f"occase_synth_{slug.replace('-', '_')}"
    version_id = f"ocver_synth_{slug.replace('-', '_')}_v1"
    manuscript_id = f"ocms_synth_{slug.replace('-', '_')}"
    now = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
    sample_path = ROOT / spec["sample"]
    sample_text = sample_path.read_text(encoding="utf-8")
    if not spec.get("force_unresolved") and spec["quote"] not in sample_text:
        raise ValueError(f"quote missing from {spec['sample']}: {spec['quote']!r}")
    extracted = "" if spec.get("force_unresolved") else spec["quote"]
    if spec.get("extra") and not spec.get("force_unresolved"):
        if spec["extra"]["quote"] not in sample_text:
            raise ValueError(f"extra quote missing from {spec['sample']}")
        extracted = extracted + "\n" + spec["extra"]["quote"]

    source_format = (
        SourceFormat.MARKDOWN if sample_path.suffix == ".md" else SourceFormat.TEX
    )
    manuscript = _hashed_record(
        Manuscript,
        {
            "id": manuscript_id,
            "manuscript_id": manuscript_id,
            "created_at": now,
            "created_by": ACTOR,
            "title": f"[SAMPLE] {spec['title']}",
            "rights_classification": RightsClassification.PUBLIC,
            "consent_policy_id": "maintainer-sample-corpus-v1",
            "current_version_id": version_id,
        },
    )
    version = _hashed_record(
        ManuscriptVersion,
        {
            "id": version_id,
            "version_id": version_id,
            "created_at": now,
            "created_by": ACTOR,
            "manuscript_id": manuscript_id,
            "source_format": source_format,
            "source_artifact": _artifact_from_sample(spec["sample"]),
            "extracted_artifact": ArtifactReference(
                uri=f"{spec['sample']}#extracted",
                sha256=hashlib.sha256(extracted.encode()).hexdigest(),
                media_type="text/plain",
                byte_size=len(extracted.encode()),
            ),
            "language": (spec.get("language") or {}).get("primary", "en"),
            "domain_profile": spec["profile"],
            "page_count": 2,
            "ingestion_metadata": IngestionMetadata(
                method="sample_adapter_fixture",
                tool="scripts/generate_coarse_fixtures.py",
                tool_version="0.5.0a1",
                notes=f"sample={spec['sample']}",
            ),
        },
    )
    bundle = {
        "case_id": case_id,
        "case_version": "1.0.0",
        "policy_version": "case-policy-v0.1",
        "case_type": "microcase",
        "manuscript": manuscript.model_dump(mode="json"),
        "manuscript_versions": [version.model_dump(mode="json")],
        "anchors": [],
        "claims": [],
        "concerns": [],
        "evidence": [],
        "counterpositions": [],
        "adjudications": [],
        "resolutions": [],
        "run_manifests": [],
        "known_ambiguities": [
            "Sample fixture: reconstructed claims remain provisional.",
            "Not authorized for scientific performance claims.",
        ],
    }
    return case_id, bundle, extracted


def build_review(spec: dict, case_id: str) -> dict:
    comments = [
        {
            "number": 1,
            "title": spec["title"],
            "quote": spec["quote"],
            "feedback": spec["feedback"],
            "status": "Pending",
            "severity": spec["severity"],
            "confidence": spec["confidence"],
        }
    ]
    if spec.get("extra"):
        comments.append({**spec["extra"], "status": "Pending"})
    return {
        "title": f"[SAMPLE] {spec['title']}",
        "domain": spec["domain"],
        "taxonomy": "sample.maintainer.fixture",
        "date": "2026-07-29",
        "overall_feedback": {
            "summary": "Sample overview feedback for adapter contract exercise.",
            "assessment": "Not a scientific judgment of any natural manuscript.",
            "issues": [
                {"title": "Sample issue", "body": "Overview issue for contract coverage."}
            ],
            "recommendation": "Use only for sample adapter conformance.",
            "revision_targets": ["methods"],
        },
        "detailed_comments": comments,
        "language": spec.get("language")
        or {"primary": "en", "notes": "English excerpt from sample corpus."},
        "opencritique_fixture": {
            "kind": COARSE_FIXTURE_KIND,
            "performance_claims_authorized": False,
            "confidential_manuscript_text": False,
            "case_id": case_id,
            "upstream_contract_version": COARSE_UPSTREAM_CONTRACT_VERSION,
            "sample_adapter_contract_id": COARSE_SAMPLE_ADAPTER_CONTRACT_ID,
            "sample_path": spec["sample"],
        },
    }


def main() -> None:
    REVIEWS.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    CASES.mkdir(parents=True, exist_ok=True)

    map_cases = []
    bench_cases = []
    extracted_index = {}
    for spec in SPECS:
        case_id, bundle, extracted = build_case(spec)
        case_dir = CASES / f"SYNTH-{spec['slug'].upper()}"
        case_dir.mkdir(parents=True, exist_ok=True)
        case_path = case_dir / "case.json"
        case_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rel = str(case_path.relative_to(BENCH)).replace("\\", "/")
        review = build_review(spec, case_id)
        review_name = f"{spec['slug']}.json"
        (REVIEWS / review_name).write_text(
            json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        map_cases.append(
            {
                "case_id": case_id,
                "case_version": "1.0.0",
                "review_path": f"../reviews/{review_name}",
                "run_id": f"ocrun_sample_{spec['slug'].replace('-', '_')}",
            }
        )
        bench_cases.append(BenchmarkCaseRef(case_id=case_id, case_version="1.0.0", path=rel))
        extracted_index[f"{case_id}:1.0.0"] = extracted

    case_set_material = json.dumps(
        [(c.case_id, c.case_version, c.path) for c in bench_cases],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    manifest = BenchmarkManifest(
        benchmark_id="ocbench_coarse_synth",
        version="0.1.0",
        title="Coarse sample-adapter conformance benchmark",
        description=(
            "Maintainer-owned sample fixtures for Coarse adapter validation. "
            "Not authorized for scientific performance claims."
        ),
        evidence_class=BenchmarkEvidenceClass.CONFORMANCE,
        reference_completeness=ReferenceCompleteness.UNKNOWN,
        domain_profiles=sorted({s["profile"] for s in SPECS}),
        cases=bench_cases,
        independent_evaluation=False,
        expert_adjudicated=False,
        license="Apache-2.0",
        case_set_hash=hashlib.sha256(case_set_material).hexdigest(),
        created_at=datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC),
        limitations=[
            "Maintainer-owned sample fixtures only.",
            "No confidential manuscript text.",
            "Performance claims are not authorized.",
            "Not genuine Coarse production exports (see issue #3).",
        ],
    )
    (BENCH / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    mapping = {
        "system_version": "coarse-sample-adapter-test-0.1",
        "coarse_commit": COARSE_UPSTREAM_COMMIT_PIN,
        "model_identifiers": ["sample-fixture/none"],
        "configuration": {
            "upstream_contract_version": COARSE_UPSTREAM_CONTRACT_VERSION,
            "fixture_kind": COARSE_FIXTURE_KIND,
            "sample_adapter_contract_id": COARSE_SAMPLE_ADAPTER_CONTRACT_ID,
        },
        "cases": map_cases,
        "declared_cost_currency": "USD",
        "declared_cost_minor": 0,
        "declared_latency_seconds": 0.0,
    }
    (MAPS / "synth-map.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (FIXTURES / "extracted_texts.json").write_text(
        json.dumps(extracted_index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (FIXTURES / "UPSTREAM_CONTRACT.json").write_text(
        json.dumps(
            {
                "upstream_contract_version": COARSE_UPSTREAM_CONTRACT_VERSION,
                "sample_adapter_contract_id": COARSE_SAMPLE_ADAPTER_CONTRACT_ID,
                "upstream_commit_pin": None,
                "fixture_kind": COARSE_FIXTURE_KIND,
                "performance_claims_authorized": False,
                "genuine_production_exports_available": False,
                "notes": (
                    "Fixtures quote maintainer-owned samples under corpus/samples/. "
                    "Contract id is opencritique-sample-adapter-contract-v1 "
                    "(not a pretend upstream Git SHA). Genuine Coarse production "
                    "exports remain blocked on issue #3."
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(SPECS)} sample Coarse fixtures under {FIXTURES}")


if __name__ == "__main__":
    main()
