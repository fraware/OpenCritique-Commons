#!/usr/bin/env python3
"""Generate six rights-candidate placeholder cases (PR10 / issue #7)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from opencritique_acquisition.models import (
    AcquisitionLedger,
    AcquisitionSource,
    AcquisitionStatus,
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
CASES = ROOT / "cases" / "rights-candidates"
RIGHTS = ROOT / "corpus" / "rights"
LEDGER = ROOT / "corpus" / "acquisition-ledger.json"

ACTOR = ActorReference(
    actor_id="opencritique-maintainer",
    actor_type=ActorType.ORGANIZATION,
    display_name="OpenCritique Commons maintainers",
)

CANDIDATES = [
    ("rc-01", "economics", "Synthetic rights candidate: identification discussion"),
    ("rc-02", "statistics", "Synthetic rights candidate: multiplicity control"),
    ("rc-03", "empirical_ml", "Synthetic rights candidate: leakage risk"),
    ("rc-04", "theory_heavy", "Synthetic rights candidate: regularity conditions"),
    ("rc-05", "figure_table_heavy", "Synthetic rights candidate: table intervals"),
    ("rc-06", "multilingual_ish", "Synthetic rights candidate: non-English methods note"),
]


def _hashed(model_cls, payload: dict):
    payload = dict(payload)
    payload["content_hash"] = "0" * 64
    obj = model_cls.model_validate(payload)
    return obj.model_copy(update={"content_hash": content_hash(obj)})


def main() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    RIGHTS.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    records = []
    for slug, profile, title in CANDIDATES:
        case_id = f"occase_rights_{slug.replace('-', '_')}"
        version_id = f"ocver_rights_{slug.replace('-', '_')}_v1"
        manuscript_id = f"ocms_rights_{slug.replace('-', '_')}"
        digest = hashlib.sha256(f"{case_id}-source".encode()).hexdigest()
        manuscript = _hashed(
            Manuscript,
            {
                "id": manuscript_id,
                "manuscript_id": manuscript_id,
                "created_at": now,
                "created_by": ACTOR,
                "title": f"[SYNTHETIC][RIGHTS-CLEARED] {title}",
                "rights_classification": RightsClassification.PUBLIC,
                "consent_policy_id": "synthetic-maintainer-rights-v1",
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
                "source_artifact": ArtifactReference(
                    uri=f"synthetic://rights/{slug}",
                    sha256=digest,
                    media_type="text/plain",
                    byte_size=32,
                ),
                "language": "en",
                "domain_profile": profile,
                "page_count": 1,
                "ingestion_metadata": IngestionMetadata(
                    method="rights_cleared_placeholder",
                    tool="scripts/generate_rights_candidates.py",
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
            "known_ambiguities": [
                "Synthetic rights-path placeholder; not a natural manuscript.",
                "Scientific performance claims remain disabled.",
            ],
        }
        case_dir = CASES / slug
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "case.json").write_text(
            json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        rights = {
            "case_id": case_id,
            "case_version": "1.0.0",
            "source_artifact_sha256": digest,
            "rights_classification": "public",
            "evaluation_use_authorized": True,
            "redistribution_authorized": True,
            "declared_license": "Apache-2.0",
            "natural_manuscript_imported": False,
            "synthetic_placeholder": True,
            "performance_claims_authorized": False,
            "attribution": "OpenCritique Commons maintainers (synthetic fixture)",
            "withdrawal_contact": "repository maintainers via GitHub Security Advisories / CITATION.cff",
            "notes": [
                "Placeholder authorized only as synthetic maintainer material.",
                "Not derived from PeerQA or any uncleared external PDF.",
            ],
        }
        (RIGHTS / f"{slug}.json").write_text(
            json.dumps(rights, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        records.append(rights)

    source = AcquisitionSource(
        source_id="synthetic-maintainer-rights-candidates",
        title="Synthetic rights-cleared candidate cases (PR10 placeholders)",
        paper_url="https://github.com/fraware/OpenCritique-Commons",
        status=AcquisitionStatus.IMPORTED,
        declared_license="Apache-2.0",
        license_evidence_url="https://github.com/fraware/OpenCritique-Commons/blob/main/LICENSE",
        redistribution_authorized=True,
        evaluation_use_authorized=True,
        imported_case_count=6,
        notes=[
            "Six synthetic placeholders exercising the rights path.",
            "Natural PeerQA/manuscript import remains blocked pending written clearance.",
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
    print(f"Wrote {len(records)} rights candidates and acquisition ledger")


if __name__ == "__main__":
    main()
