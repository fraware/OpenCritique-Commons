#!/usr/bin/env python3
"""Generate synthetic OpenReviewer-style fixtures (≥5)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from opencritique_adapters.openreviewer import (
    OPENREVIEWER_CONTRACT_VERSION,
    OPENREVIEWER_FIXTURE_KIND,
    provenance_hash,
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
        "title": "Synthetic OpenReviewer: leakage concern",
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
                "quote": None,
                "page": None,
            }
        ],
    },
    {
        "slug": "orv-02",
        "title": "Synthetic OpenReviewer: theory gap",
        "weaknesses": [
            "The main theorem statement omits the required regularity conditions.",
        ],
        "findings": [],
    },
    {
        "slug": "orv-03",
        "title": "Synthetic OpenReviewer: with optional severity",
        "weaknesses": [],
        "findings": [
            {
                "finding_id": "f1",
                "title": "Missing ablation on encoder depth",
                "body": "Claims about architecture benefits lack depth ablations on the encoder stack.",
                "section": "weaknesses",
                "severity": "minor",
                "confidence": 0.4,
                "quote": "Deeper encoders consistently improve downstream accuracy.",
                "page": 4,
            }
        ],
    },
    {
        "slug": "orv-04",
        "title": "Synthetic OpenReviewer: multilingual methods note",
        "weaknesses": [
            "Evaluation languages are listed without per-language sample sizes.",
        ],
        "findings": [],
    },
    {
        "slug": "orv-05",
        "title": "Synthetic OpenReviewer: figure interpretation",
        "weaknesses": [
            "Figure 2 confidence bands are described qualitatively without numeric widths.",
        ],
        "findings": [],
    },
]


def _artifact(label: str) -> ArtifactReference:
    digest = hashlib.sha256(label.encode()).hexdigest()
    return ArtifactReference(
        uri=f"synthetic://opencritique/{label}",
        sha256=digest,
        media_type="text/plain",
        byte_size=len(label),
    )


def _hashed(model_cls, payload: dict):
    payload = dict(payload)
    payload["content_hash"] = "0" * 64
    obj = model_cls.model_validate(payload)
    return obj.model_copy(update={"content_hash": content_hash(obj)})


def build_case(slug: str, title: str) -> tuple[str, dict]:
    case_id = f"occase_orv_{slug.replace('-', '_')}"
    version_id = f"ocver_orv_{slug.replace('-', '_')}_v1"
    manuscript_id = f"ocms_orv_{slug.replace('-', '_')}"
    now = datetime(2026, 3, 1, tzinfo=timezone.utc)
    manuscript = _hashed(
        Manuscript,
        {
            "id": manuscript_id,
            "manuscript_id": manuscript_id,
            "created_at": now,
            "created_by": ACTOR,
            "title": f"[SYNTHETIC] {title}",
            "rights_classification": RightsClassification.PUBLIC,
            "consent_policy_id": "synthetic-maintainer-fixture-v1",
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
            "source_format": SourceFormat.MARKDOWN,
            "source_artifact": _artifact(f"{slug}-source"),
            "language": "en",
            "domain_profile": "empirical_ml",
            "page_count": 3,
            "ingestion_metadata": IngestionMetadata(
                method="synthetic_fixture",
                tool="scripts/generate_openreviewer_fixtures.py",
                tool_version="0.5.0a1",
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
            "Synthetic OpenReviewer fixture; not a real model output.",
            "Performance claims are not authorized.",
        ],
    }
    return case_id, bundle


def build_review(spec: dict) -> dict:
    weaknesses = "\n".join(f"- {item}" for item in spec["weaknesses"]) or "- (see structured findings)"
    markdown = (
        f"# Review\n\n## Summary\n\n[SYNTHETIC] {spec['title']}\n\n"
        f"## Strengths\n\n- Synthetic strength placeholder.\n\n"
        f"## Weaknesses\n\n{weaknesses}\n\n"
        f"## Questions\n\n- Synthetic clarifying question?\n"
    )
    payload = {
        "title": f"[SYNTHETIC][RIGHTS-CLEARED] {spec['title']}",
        "venue_template": "ICLR2025-synthetic",
        "markdown": markdown,
        "recommendation_score": 5.0,
        "findings": spec["findings"],
        "model_identifiers": ["synthetic-openreviewer-fixture/none"],
        "opencritique_fixture": {
            "kind": OPENREVIEWER_FIXTURE_KIND,
            "performance_claims_authorized": False,
            "confidential_manuscript_text": False,
            "contract_version": OPENREVIEWER_CONTRACT_VERSION,
        },
    }
    return payload


def main() -> None:
    REVIEWS.mkdir(parents=True, exist_ok=True)
    MAPS.mkdir(parents=True, exist_ok=True)
    CASES.mkdir(parents=True, exist_ok=True)
    map_cases = []
    bench_cases = []
    for spec in SPECS:
        case_id, bundle = build_case(spec["slug"], spec["title"])
        case_dir = CASES / f"SYNTH-{spec['slug'].upper()}"
        case_dir.mkdir(parents=True, exist_ok=True)
        case_path = case_dir / "case.json"
        case_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        review = build_review(spec)
        raw = json.dumps(review, indent=2, sort_keys=True).encode("utf-8")
        review["original_sha256"] = provenance_hash(raw)
        # Re-serialize with hash included and refresh hash to match final bytes.
        provisional = json.dumps(review, indent=2, sort_keys=True).encode("utf-8")
        review["original_sha256"] = provenance_hash(provisional)
        final = json.dumps(review, indent=2, sort_keys=True) + "\n"
        review_name = f"{spec['slug']}.json"
        # Fix chicken-egg: set hash of final content without the hash field, store alongside.
        body = {k: v for k, v in review.items() if k != "original_sha256"}
        body_bytes = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")
        body["original_sha256"] = provenance_hash(body_bytes)
        # Store hash of the file including the hash field by writing body then computing —
        # converter hashes full file. Embed hash of full file after write via two-step.
        review_path = REVIEWS / review_name
        review_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        digest = provenance_hash(review_path.read_bytes())
        body["original_sha256"] = digest
        review_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # After rewriting, digest changes — store hash of *content excluding hash* in converter
        # OR update converter to accept mismatch when regenerating. Better: don't embed
        # self-referential hash; store sidecar. Simpler: converter sets hash if missing and
        # only verifies when present matches. For fixtures, omit original_sha256 from file
        # and let converter fill it; tests check converter output provenance separately.
        body.pop("original_sha256", None)
        review_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        title="OpenReviewer synthetic adapter conformance benchmark",
        description=(
            "Synthetic rights-cleared OpenReviewer-style fixtures. "
            "Not authorized for scientific performance claims."
        ),
        evidence_class=BenchmarkEvidenceClass.CONFORMANCE,
        reference_completeness=ReferenceCompleteness.UNKNOWN,
        domain_profiles=["empirical_ml", "theory_heavy"],
        cases=bench_cases,
        license="Apache-2.0",
        case_set_hash=hashlib.sha256(case_set_material).hexdigest(),
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        limitations=["Synthetic fixtures only", "No performance claims"],
    )
    (BENCH / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    mapping = {
        "system_version": "openreviewer-synth-0.1",
        "openreviewer_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "contract_version": OPENREVIEWER_CONTRACT_VERSION,
        "model_identifiers": ["synthetic-openreviewer-fixture/none"],
        "configuration": {"fixture_kind": OPENREVIEWER_FIXTURE_KIND},
        "cases": map_cases,
    }
    (MAPS / "synth-map.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (FIXTURES / "UPSTREAM_CONTRACT.json").write_text(
        json.dumps(
            {
                "contract_version": OPENREVIEWER_CONTRACT_VERSION,
                "repository": "https://github.com/maxidl/openreviewer",
                "fixture_kind": OPENREVIEWER_FIXTURE_KIND,
                "performance_claims_authorized": False,
                "authentic_outputs_available": False,
                "notes": (
                    "Integration is stubbed at the adapter interface with synthetic fixtures. "
                    "Authentic redistributable OpenReviewer outputs remain pending rights clearance."
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(SPECS)} OpenReviewer fixtures")


if __name__ == "__main__":
    main()
