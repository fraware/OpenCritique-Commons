#!/usr/bin/env python3
"""Generate maintainer-owned sample rights cases, REF cases, and acquisition ledger.

Reads manuscripts under corpus/samples/ (Apache-2.0 maintainer authorship).
Does not set synthetic_placeholder. Performance claims stay unauthorized.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import HttpUrl, TypeAdapter

from opencritique_acquisition.models import (
    AcquisitionLedger,
    AcquisitionSource,
    AcquisitionStatus,
)
from opencritique_schema.canonical import content_hash
from opencritique_schema.models import (
    ActorReference,
    ActorType,
    Anchor,
    AnchorResolutionStatus,
    AnchorType,
    ArtifactReference,
    Claim,
    ClaimType,
    Concern,
    ConcernOrigin,
    ConcernOriginType,
    ConcernStatus,
    Counterposition,
    CounterpositionSource,
    EvidenceDirection,
    EvidenceItem,
    EvidenceType,
    Explicitness,
    IngestionMetadata,
    Manuscript,
    ManuscriptVersion,
    ReproducibilityStatus,
    RightsClassification,
    Severity,
    SourceFormat,
    VerificationGrade,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "corpus" / "samples"
CASES = ROOT / "cases" / "rights-candidates"
REF_CASES = ROOT / "cases" / "reference"
RIGHTS = ROOT / "corpus" / "rights"
LEDGER = ROOT / "corpus" / "acquisition-ledger.json"

ACTOR = ActorReference(
    actor_id="opencritique-maintainer",
    actor_type=ActorType.ORGANIZATION,
    display_name="OpenCritique Commons maintainers",
)

# (slug, domain_profile, title, source_relpath, source_format, quote, claim, concern)
SAMPLES_SPEC: list[dict[str, str]] = [
    {
        "slug": "rc-01",
        "sample_id": "sample-econ-01",
        "profile": "economics_statistics",
        "title": "Sample: Identification under clustered sampling",
        "relpath": "corpus/samples/sample-econ-01/manuscript.md",
        "format": "markdown",
        "quote": "Under clustered sampling the sandwich estimator understates variance.",
        "claim": (
            "Clustered sampling causes the sandwich estimator to understate variance "
            "in the reported setting."
        ),
        "concern_title": "Variance discussion omits cluster-robust alternatives",
        "concern_summary": (
            "The variance discussion omits cluster-robust alternatives and "
            "finite-sample caveats."
        ),
        "concern_type": "statistical.variance",
    },
    {
        "slug": "rc-02",
        "sample_id": "sample-stats-01",
        "profile": "economics_statistics",
        "title": "Sample: Multiplicity control for secondary endpoints",
        "relpath": "corpus/samples/sample-stats-01/manuscript.md",
        "format": "markdown",
        "quote": (
            "All eighteen secondary endpoints are reported as significant at p < 0.05."
        ),
        "claim": "All eighteen secondary endpoints are significant at p < 0.05.",
        "concern_title": "Missing multiplicity control",
        "concern_summary": (
            "Secondary endpoints lack multiplicity control; false discoveries remain plausible."
        ),
        "concern_type": "statistical.multiplicity",
    },
    {
        "slug": "rc-03",
        "sample_id": "sample-ml-01",
        "profile": "empirical_ml",
        "title": "Sample: Train-test leakage risk",
        "relpath": "corpus/samples/sample-ml-01/manuscript.md",
        "format": "markdown",
        "quote": (
            "Features were standardized using statistics computed on the full dataset."
        ),
        "claim": "Feature standardization used full-dataset statistics before splitting.",
        "concern_title": "Train-test leakage risk",
        "concern_summary": (
            "Standardization on the full dataset risks optimistic evaluation through leakage."
        ),
        "concern_type": "methodological.leakage",
    },
    {
        "slug": "rc-04",
        "sample_id": "sample-theory-01",
        "profile": "theory_heavy",
        "title": "Sample: Uniform risk bounds and constructive algorithms",
        "relpath": "corpus/samples/sample-theory-01/manuscript.tex",
        "format": "tex",
        "quote": "Therefore the excess risk decays as $O(1/\\sqrt{n})$ uniformly.",
        "claim": "Excess risk decays as O(1/sqrt(n)) uniformly under the stated conditions.",
        "concern_title": "Unstated Lipschitz constant",
        "concern_summary": (
            "Uniformity appears to require a Lipschitz constant that is never stated."
        ),
        "concern_type": "theoretical.assumptions",
    },
    {
        "slug": "rc-05",
        "sample_id": "sample-figtable-01",
        "profile": "figure_table_heavy",
        "title": "Sample: Figure and table reporting gaps",
        "relpath": "corpus/samples/sample-figtable-01/manuscript.md",
        "format": "markdown",
        "quote": "Table 2 reports point estimates for each adjusted risk ratio.",
        "claim": "Table 2 reports adjusted risk-ratio point estimates for each arm.",
        "concern_title": "Table omits confidence intervals",
        "concern_summary": (
            "Point estimates without intervals impede severity assessment of uncertainty."
        ),
        "concern_type": "reporting.uncertainty",
    },
    {
        "slug": "rc-06",
        "sample_id": "sample-multi-01",
        "profile": "multilingual_ish",
        "title": "Sample: Multilingual methods notes",
        "relpath": "corpus/samples/sample-multi-01/manuscript.md",
        "format": "markdown",
        "quote": "La precision del modelo aumenta cuando se excluyen los casos ambiguos.",
        "claim": (
            "Model precision increases when ambiguous cases are excluded "
            "(Spanish methods note)."
        ),
        "concern_title": "Post-hoc exclusion of ambiguous cases",
        "concern_summary": (
            "Excluding ambiguous cases after seeing labels can inflate reported precision."
        ),
        "concern_type": "methodological.selection",
    },
]


def _hashed(model_cls, payload: dict):
    payload = dict(payload)
    payload["content_hash"] = "0" * 64
    obj = model_cls.model_validate(payload)
    return obj.model_copy(update={"content_hash": content_hash(obj)})


def _artifact_for(path: Path, uri: str) -> ArtifactReference:
    data = path.read_bytes()
    return ArtifactReference(
        uri=uri,
        sha256=hashlib.sha256(data).hexdigest(),
        media_type="text/markdown" if path.suffix == ".md" else "application/x-tex",
        byte_size=len(data),
    )


def _build_bundle(
    spec: dict, *, case_prefix: str, id_prefix: str
) -> tuple[dict, ArtifactReference]:
    now = datetime(2026, 7, 29, tzinfo=UTC)
    source_path = ROOT / spec["relpath"]
    text = source_path.read_text(encoding="utf-8")
    if spec["quote"] not in text and spec["quote"].replace("\\\\", "\\") not in text:
        # TeX file stores single backslashes; quote may be escaped for JSON specs.
        plain = spec["quote"].replace("\\\\", "\\")
        if plain not in text:
            raise ValueError(f"quote missing from {source_path}: {spec['quote']!r}")

    slug_key = spec["slug"].replace("-", "_")
    case_id = f"occase_{id_prefix}_{slug_key}"
    version_id = f"ocver_{id_prefix}_{slug_key}_v1"
    manuscript_id = f"ocms_{id_prefix}_{slug_key}"
    anchor_id = f"ocanc_{id_prefix}_{slug_key}_q1"
    claim_id = f"occlm_{id_prefix}_{slug_key}_c1"
    concern_id = f"occon_{id_prefix}_{slug_key}_k1"
    evidence_id = f"ocevd_{id_prefix}_{slug_key}_e1"

    artifact = _artifact_for(source_path, spec["relpath"].replace("\\", "/"))
    source_format = (
        SourceFormat.MARKDOWN if spec["format"] == "markdown" else SourceFormat.TEX
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
            "source_artifact": artifact,
            "language": "en" if spec["profile"] != "multilingual_ish" else "es",
            "domain_profile": spec["profile"],
            "page_count": 1,
            "ingestion_metadata": IngestionMetadata(
                method="maintainer_sample_import",
                tool="scripts/generate_rights_candidates.py",
                tool_version="0.5.0a1",
                notes=f"sample_id={spec['sample_id']}",
            ),
        },
    )
    quote = spec["quote"].replace("\\\\", "\\")
    anchor = _hashed(
        Anchor,
        {
            "id": anchor_id,
            "anchor_id": anchor_id,
            "created_at": now,
            "created_by": ACTOR,
            "manuscript_version_id": version_id,
            "anchor_type": AnchorType.TEXT_SPAN,
            "page_start": 1,
            "page_end": 1,
            "source_text": quote,
            "normalized_text": quote.casefold(),
            "section_path": ["Methods"] if "Methods" in text or "Bound" in text else [],
            "resolution_status": AnchorResolutionStatus.EXACT,
            "extraction_confidence": 1.0,
        },
    )
    claim = _hashed(
        Claim,
        {
            "id": claim_id,
            "claim_id": claim_id,
            "created_at": now,
            "created_by": ACTOR,
            "manuscript_version_id": version_id,
            "statement": spec["claim"],
            "claim_type": ClaimType.METHODOLOGICAL,
            "explicitness": Explicitness.EXPLICIT,
            "scope": "sample conformance manuscript",
            "anchor_ids": [anchor_id],
            "reconstruction_notes": "Quoted directly from maintainer-owned sample text.",
            "approval_status": "candidate",
        },
    )
    concern = _hashed(
        Concern,
        {
            "id": concern_id,
            "concern_id": concern_id,
            "created_at": now,
            "created_by": ACTOR,
            "manuscript_version_id": version_id,
            "title": spec["concern_title"],
            "summary": spec["concern_summary"],
            "concern_type": spec["concern_type"],
            "claim_ids": [claim_id],
            "anchor_ids": [anchor_id],
            "severity": Severity.MAJOR,
            "confidence": 0.8,
            "verification_grade": VerificationGrade.V1,
            "status": ConcernStatus.PROPOSED,
            "potential_consequence": (
                "Readers may overstate evidential strength of the sample claim."
            ),
            "required_resolution": "Clarify assumptions and reporting gaps in a revision.",
            "origin": ConcernOrigin(
                origin_type=ConcernOriginType.HUMAN,
                origin_id="opencritique-maintainer-sample-curation",
            ),
        },
    )
    evidence = _hashed(
        EvidenceItem,
        {
            "id": evidence_id,
            "evidence_id": evidence_id,
            "created_at": now,
            "created_by": ACTOR,
            "concern_id": concern_id,
            "evidence_type": EvidenceType.MANUSCRIPT_TEXT,
            "supports": EvidenceDirection.CONCERN,
            "description": "Quoted sample manuscript span supporting the concern.",
            "artifact_reference": artifact,
            "anchor_ids": [anchor_id],
            "method": "direct_quotation",
            "producer": ACTOR,
            "reproducibility_status": ReproducibilityStatus.REPRODUCIBLE,
            "limitations": "Sample text only; not natural science evidence.",
            "independence_group": "maintainer-sample",
        },
    )
    counter_id = f"occtr_{id_prefix}_{slug_key}_cp1"
    counter = _hashed(
        Counterposition,
        {
            "id": counter_id,
            "counterposition_id": counter_id,
            "created_at": now,
            "created_by": ACTOR,
            "concern_id": concern_id,
            "statement": (
                "The sample note may intend a stylized illustration rather than a "
                "complete empirical claim; residual gap remains for conformance."
            ),
            "supporting_anchor_ids": [anchor_id],
            "supporting_evidence_ids": [],
            "source": CounterpositionSource.AUTHOR,
            "residual_disagreement": (
                "Even as illustration, the quoted span still lacks stated safeguards."
            ),
            "adequacy_status": "unreviewed",
        },
    )
    bundle = {
        "case_id": case_id,
        "case_version": "1.0.0",
        "policy_version": "case-policy-v0.1",
        "case_type": "microcase",
        "manuscript": manuscript.model_dump(mode="json"),
        "manuscript_versions": [version.model_dump(mode="json")],
        "anchors": [anchor.model_dump(mode="json")],
        "claims": [claim.model_dump(mode="json")],
        "concerns": [concern.model_dump(mode="json")],
        "evidence": [evidence.model_dump(mode="json")],
        "counterpositions": [counter.model_dump(mode="json")],
        "adjudications": [],
        "resolutions": [],
        "run_manifests": [],
        "known_ambiguities": [
            "Maintainer-authored sample conformance material; not a natural manuscript.",
            "Scientific performance claims remain disabled.",
        ],
    }
    # case_prefix retained for directory naming clarity by callers
    _ = case_prefix
    return bundle, artifact


def main() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    REF_CASES.mkdir(parents=True, exist_ok=True)
    RIGHTS.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 7, 29, tzinfo=UTC)
    records = []

    for spec in SAMPLES_SPEC:
        bundle, artifact = _build_bundle(spec, case_prefix="rc", id_prefix="rights")
        case_dir = CASES / spec["slug"]
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "case.json").write_text(
            json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        # REF-* import-reference cases share the same manuscript bytes.
        ref_slug = f"REF-{spec['slug'].split('-', 1)[1].upper()}"
        ref_bundle, _ = _build_bundle(spec, case_prefix="ref", id_prefix="sample")
        # Stable REF case ids for import-reference.
        ref_key = spec["slug"].replace("-", "_")
        ref_bundle["case_id"] = f"occase_sample_{ref_key}"
        ref_dir = REF_CASES / ref_slug
        ref_dir.mkdir(parents=True, exist_ok=True)
        (ref_dir / "case.json").write_text(
            json.dumps(ref_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        rights = {
            "case_id": bundle["case_id"],
            "case_version": "1.0.0",
            "sample_id": spec["sample_id"],
            "source_artifact_sha256": artifact.sha256,
            "source_artifact_uri": artifact.uri,
            "rights_classification": "public",
            "evaluation_use_authorized": True,
            "redistribution_authorized": True,
            "declared_license": "Apache-2.0",
            "natural_manuscript_imported": False,
            "performance_claims_authorized": False,
            "attribution": "OpenCritique Commons maintainers (owned sample corpus)",
            "withdrawal_contact": (
                "repository maintainers via GitHub Security Advisories / CITATION.cff"
            ),
            "notes": [
                "Maintainer-authored open sample; Apache-2.0.",
                "Not derived from PeerQA or any uncleared external PDF.",
                "Sample conformance only; not natural science evidence.",
            ],
        }
        (RIGHTS / f"{spec['slug']}.json").write_text(
            json.dumps(rights, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        records.append(rights)

    _http_url = TypeAdapter(HttpUrl)
    source = AcquisitionSource(
        source_id="maintainer-owned-sample-corpus",
        title="Maintainer-owned open sample manuscripts (sample conformance)",
        paper_url=_http_url.validate_python(
            "https://github.com/fraware/OpenCritique-Commons/tree/main/corpus/samples"
        ),
        status=AcquisitionStatus.IMPORTED,
        declared_license="Apache-2.0",
        license_evidence_url=_http_url.validate_python(
            "https://github.com/fraware/OpenCritique-Commons/blob/main/LICENSE"
        ),
        redistribution_authorized=True,
        evaluation_use_authorized=True,
        imported_case_count=6,
        grant_authority="OpenCritique Commons maintainers",
        grant_scope=(
            "Apache-2.0 maintainer-authored samples for tooling conformance only; "
            "no performance claims."
        ),
        notes=[
            "Six maintainer-authored open samples under corpus/samples/.",
            "Natural PeerQA/manuscript import remains blocked pending written clearance (#7).",
            "performance_claims_authorized stays false on the ledger.",
        ],
    )
    ledger = AcquisitionLedger(
        ledger_version="0.1",
        sources=[source],
        total_imported_cases=6,
        performance_claims_authorized=False,
        generated_at=now,
    )
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(
        json.dumps(ledger.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} sample rights cases, REF cases, and acquisition ledger")


if __name__ == "__main__":
    main()
