#!/usr/bin/env python3
"""Generate OpenReviewer-shaped adapter fixtures from maintainer-owned samples."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from opencritique_adapters.openreviewer import (
    OPENREVIEWER_CONTRACT_VERSION,
    OPENREVIEWER_FIXTURE_KIND,
    OPENREVIEWER_SAMPLE_ADAPTER_CONTRACT_ID,
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
FIXTURES = ROOT / "fixtures" / "openreviewer"
REVIEWS = FIXTURES / "reviews"
MAPS = FIXTURES / "maps"
BENCH = ROOT / "benchmarks" / "openreviewer-synth-v0.1"
CASES = BENCH / "cases"

ACTOR = ActorReference(
    actor_id="opencritique-maintainer",
    actor_type=ActorType.ORGANIZATION,
    display_name="OpenCritique Commons maintainers",
)

SPECS = [
    {
        "slug": "orv-01",
        "sample": "corpus/samples/sample-ml-01/manuscript.md",
        "profile": "empirical_ml",
        "title": "Sample OpenReviewer: leakage concern",
        "weaknesses": [
            "Feature scaling appears to use the full dataset before splitting folds.",
            "Baseline comparisons lack matched compute budgets.",
        ],
        "findings": [
            {
                "finding_id": "f1",
                "title": "Possible train-test leakage",
                "body": "Feature scaling appears to use the full dataset before splitting folds.",
                "section": "weaknesses",
                "severity": None,
                "confidence": None,
                "quote": (
                    "Features were standardized using statistics computed on the full dataset."
                ),
                "page": 1,
            }
        ],
    },
    {
        "slug": "orv-02",
        "sample": "corpus/samples/sample-theory-01/manuscript.tex",
        "profile": "theory_heavy",
        "title": "Sample OpenReviewer: theory gap",
        "weaknesses": [
            "The main theorem statement omits the required regularity conditions.",
        ],
        "findings": [],
    },
    {
        "slug": "orv-03",
        "sample": "corpus/samples/sample-ml-01/manuscript.md",
        "profile": "empirical_ml",
        "title": "Sample OpenReviewer: with optional severity",
        "weaknesses": [],
        "findings": [
            {
                "finding_id": "f1",
                "title": "Untuned baseline comparison",
                "body": (
                    "Claims about proposed gains use an untuned library-default baseline."
                ),
                "section": "weaknesses",
                "severity": "minor",
                "confidence": 0.4,
                "quote": "The baseline uses default hyperparameters from the reference library.",
                "page": 1,
            }
        ],
    },
    {
        "slug": "orv-04",
        "sample": "corpus/samples/sample-multi-01/manuscript.md",
        "profile": "multilingual_ish",
        "title": "Sample OpenReviewer: multilingual methods note",
        "weaknesses": [
            "Evaluation languages are listed without per-language sample sizes.",
        ],
        "findings": [],
    },
    {
        "slug": "orv-05",
        "sample": "corpus/samples/sample-figtable-01/manuscript.md",
        "profile": "figure_table_heavy",
        "title": "Sample OpenReviewer: figure interpretation",
        "weaknesses": [
            "Figure trajectories are described qualitatively without absolute effect sizes.",
        ],
        "findings": [],
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


def _hashed(model_cls, payload: dict):
    payload = dict(payload)
    payload["content_hash"] = "0" * 64
    obj = model_cls.model_validate(payload)
    return obj.model_copy(update={"content_hash": content_hash(obj)})


def build_case(spec: dict) -> tuple[str, dict]:
    slug = spec["slug"]
    case_id = f"occase_orv_{slug.replace('-', '_')}"
    version_id = f"ocver_orv_{slug.replace('-', '_')}_v1"
    manuscript_id = f"ocms_orv_{slug.replace('-', '_')}"
    now = datetime(2026, 7, 29, tzinfo=UTC)
    sample_path = ROOT / spec["sample"]
    source_format = (
        SourceFormat.MARKDOWN if sample_path.suffix == ".md" else SourceFormat.TEX
    )
    manuscript = _hashed(
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
    version = _hashed(
        ManuscriptVersion,
        {
            "id": version_id,
            "version_id": version_id,
            "created_at": now,
            "created_by": ACTOR,
            "manuscript_id": manuscript_id,
            "source_format": source_format,
            "source_artifact": _artifact_from_sample(spec["sample"]),
            "language": "en",
            "domain_profile": spec["profile"],
            "page_count": 3,
            "ingestion_metadata": IngestionMetadata(
                method="sample_adapter_fixture",
                tool="scripts/generate_openreviewer_fixtures.py",
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
            "Sample OpenReviewer-shaped fixture; not an authentic upstream model run.",
            "Performance claims are not authorized.",
        ],
    }
    return case_id, bundle


def build_review(spec: dict) -> dict:
    weaknesses = (
        "\n".join(f"- {item}" for item in spec["weaknesses"])
        or "- (see structured findings)"
    )
    markdown = (
        f"# Review\n\n## Summary\n\n[SAMPLE] {spec['title']}\n\n"
        f"## Strengths\n\n- Clear problem framing in the sample manuscript.\n\n"
        f"## Weaknesses\n\n{weaknesses}\n\n"
        f"## Questions\n\n- Can the sample methods note be strengthened?\n"
    )
    return {
        "title": f"[SAMPLE] {spec['title']}",
        "venue_template": "ICLR2025-sample",
        "markdown": markdown,
        "recommendation_score": 5.0,
        "findings": spec["findings"],
        "model_identifiers": ["sample-openreviewer-fixture/none"],
        "opencritique_fixture": {
            "kind": OPENREVIEWER_FIXTURE_KIND,
            "performance_claims_authorized": False,
            "confidential_manuscript_text": False,
            "contract_version": OPENREVIEWER_CONTRACT_VERSION,
            "sample_adapter_contract_id": OPENREVIEWER_SAMPLE_ADAPTER_CONTRACT_ID,
            "sample_path": spec["sample"],
        },
    }


def main() -> None:
    REVIEWS.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    CASES.mkdir(parents=True, exist_ok=True)
    map_cases = []
    bench_cases = []
    for spec in SPECS:
        case_id, bundle = build_case(spec)
        case_dir = CASES / f"SYNTH-{spec['slug'].upper()}"
        case_dir.mkdir(parents=True, exist_ok=True)
        case_path = case_dir / "case.json"
        case_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        review = build_review(spec)
        review_name = f"{spec['slug']}.json"
        review_path = REVIEWS / review_name
        review_path.write_text(
            json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        map_cases.append(
            {
                "case_id": case_id,
                "case_version": "1.0.0",
                "review_path": f"../reviews/{review_name}",
            }
        )
        bench_cases.append(
            BenchmarkCaseRef(
                case_id=case_id,
                case_version="1.0.0",
                path=str(case_path.relative_to(BENCH)).replace("\\", "/"),
            )
        )

    case_set_material = json.dumps(
        [(c.case_id, c.case_version, c.path) for c in bench_cases],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    manifest = BenchmarkManifest(
        benchmark_id="ocbench_openreviewer_synth",
        version="0.1.0",
        title="OpenReviewer sample-adapter conformance benchmark",
        description=(
            "Maintainer-owned sample OpenReviewer-shaped fixtures. "
            "Not authorized for scientific performance claims."
        ),
        evidence_class=BenchmarkEvidenceClass.CONFORMANCE,
        reference_completeness=ReferenceCompleteness.UNKNOWN,
        domain_profiles=sorted({s["profile"] for s in SPECS}),
        cases=bench_cases,
        license="Apache-2.0",
        case_set_hash=hashlib.sha256(case_set_material).hexdigest(),
        created_at=datetime(2026, 7, 29, tzinfo=UTC),
        limitations=[
            "Sample fixtures only",
            "No performance claims",
            "Not authentic OpenReviewer production outputs (see issue #5)",
        ],
    )
    (BENCH / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    mapping = {
        "system_version": "openreviewer-sample-0.1",
        "openreviewer_commit": OPENREVIEWER_SAMPLE_ADAPTER_CONTRACT_ID,
        "contract_version": OPENREVIEWER_CONTRACT_VERSION,
        "model_identifiers": ["sample-openreviewer-fixture/none"],
        "configuration": {
            "fixture_kind": OPENREVIEWER_FIXTURE_KIND,
            "sample_adapter_contract_id": OPENREVIEWER_SAMPLE_ADAPTER_CONTRACT_ID,
        },
        "cases": map_cases,
    }
    (MAPS / "synth-map.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (FIXTURES / "UPSTREAM_CONTRACT.json").write_text(
        json.dumps(
            {
                "contract_version": OPENREVIEWER_CONTRACT_VERSION,
                "sample_adapter_contract_id": OPENREVIEWER_SAMPLE_ADAPTER_CONTRACT_ID,
                "repository": "https://github.com/maxidl/openreviewer",
                "fixture_kind": OPENREVIEWER_FIXTURE_KIND,
                "performance_claims_authorized": False,
                "authentic_outputs_available": False,
                "upstream_commit_pin": None,
                "notes": (
                    "Fixtures are hand-authored OpenReviewer-shaped reviews quoting "
                    "maintainer-owned samples. Contract id is "
                    "opencritique-sample-adapter-contract-v1 (not a pretend Git SHA). "
                    "Authentic redistributable OpenReviewer outputs remain blocked "
                    "on issue #5."
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(SPECS)} OpenReviewer sample fixtures")


if __name__ == "__main__":
    main()
