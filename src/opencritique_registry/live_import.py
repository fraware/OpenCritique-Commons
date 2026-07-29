"""Import private live runner exports into the registry for Studio adjudication.

Stamps ``evidence_class=private_live``. Never promotes into
``fixtures/*/production/``. Claims stay locked.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from opencritique_adapters.coarse import CoarseReview
from opencritique_runners.openreviewer import OpenReviewerLiveExport, import_openreviewer_export
from opencritique_runners.paths import assert_not_production_fixtures_path, is_under_private_runs
from opencritique_schema.canonical import content_hash
from opencritique_schema.coarse_adapter import convert_coarse_review
from opencritique_schema.models import (
    ActorReference,
    ActorType,
    ArtifactReference,
    CaseBundle,
    Counterposition,
    CounterpositionSource,
    EvidenceDirection,
    EvidenceItem,
    EvidenceType,
    IngestionMetadata,
    Manuscript,
    ManuscriptVersion,
    ReproducibilityStatus,
    RightsClassification,
    Severity,
    SourceFormat,
)

from .artifacts import LocalArtifactStore
from .auth import issue_token
from .db import make_engine, make_session_factory
from .db_models import PrincipalORM
from .ids import new_id
from .migrate import upgrade_head
from .schemas import (
    CaseRegistration,
    DataUse,
    GrantBasis,
    PrincipalRole,
    RightsGrantInput,
)
from .service import RegistryService

EVIDENCE_CLASS = "private_live"
CLAIMS_BANNER = (
    "NOT AUTHORIZED - private live / sample gold != production authenticity "
    "!= scientific performance claims (performance_claims_authorized=false)."
)

ExportKind = Literal["coarse", "openreviewer"]


@dataclass(frozen=True)
class LiveImportResult:
    case_id: str
    case_version: str
    evidence_class: str
    seeded_tasks: int
    concern_titles: list[str]
    admin_token: str
    adjudicator_token: str
    studio_url: str
    export_kind: ExportKind
    claims_authorized: bool = False


def _stable_suffix(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def _actor() -> ActorReference:
    return ActorReference(
        actor_id="opencritique-live-import",
        actor_type=ActorType.SYSTEM,
        display_name="OpenCritique live import",
    )


def _guess_media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "text/markdown"
    if suffix == ".tex":
        return "application/x-tex"
    if suffix == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def _source_format(path: Path) -> SourceFormat:
    suffix = path.suffix.lower()
    mapping = {
        ".pdf": SourceFormat.PDF,
        ".tex": SourceFormat.TEX,
        ".docx": SourceFormat.DOCX,
        ".md": SourceFormat.MARKDOWN,
        ".markdown": SourceFormat.MARKDOWN,
        ".html": SourceFormat.HTML,
        ".htm": SourceFormat.HTML,
    }
    return mapping.get(suffix, SourceFormat.OTHER)


def resolve_export_path(from_path: Path) -> Path:
    """Accept a JSON file or a pipeline ``out_dir`` containing a known export."""
    path = from_path.resolve()
    if path.is_file():
        return path
    if not path.is_dir():
        raise FileNotFoundError(f"live export not found: {from_path}")
    candidates = (
        path / "coarse-review.json",
        path / "coarse-export.json",
        path / "openreviewer-review.json",
        path / "review.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"no coarse-review.json / openreviewer export under directory: {path}"
    )


def detect_export_kind(payload: dict[str, Any]) -> ExportKind:
    if "detailed_comments" in payload or (
        "overall_feedback" in payload and "taxonomy" in payload
    ):
        return "coarse"
    if "findings" in payload or "venue_template" in payload or "markdown" in payload:
        return "openreviewer"
    raise ValueError(
        "Unrecognized live export. Expected a Coarse review "
        "(detailed_comments) or OpenReviewer export (findings/markdown)."
    )


def _openreviewer_as_coarse_dict(export: OpenReviewerLiveExport) -> dict[str, Any]:
    comments: list[dict[str, Any]] = []
    for index, finding in enumerate(export.findings, start=1):
        quote = (finding.quote or finding.body[:240]).strip()
        if not quote:
            quote = finding.title
        severity = (finding.severity or "major").lower()
        if severity == "moderate":
            severity = "major"
        if severity not in {"critical", "major", "minor"}:
            severity = "major"
        confidence = "medium"
        if finding.confidence is not None:
            if finding.confidence >= 0.8:
                confidence = "high"
            elif finding.confidence < 0.45:
                confidence = "low"
        comments.append(
            {
                "number": index,
                "title": finding.title,
                "quote": quote,
                "feedback": finding.body,
                "severity": severity,
                "confidence": confidence,
                "status": "Pending",
            }
        )
    if not comments and export.markdown.strip():
        comments.append(
            {
                "number": 1,
                "title": export.title or "Imported OpenReviewer review",
                "quote": export.markdown.strip()[:240],
                "feedback": export.markdown.strip()[:2000],
                "severity": "major",
                "confidence": "medium",
                "status": "Pending",
            }
        )
    return {
        "title": export.title,
        "domain": "general",
        "taxonomy": "openreviewer.import",
        "date": datetime.now(UTC).date().isoformat(),
        "overall_feedback": {
            "summary": export.title,
            "assessment": "Private live OpenReviewer import; not production authenticity.",
            "issues": [],
            "recommendation": "",
            "revision_targets": [],
        },
        "detailed_comments": comments,
    }


def _with_hash(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["content_hash"] = "0" * 64
    payload["content_hash"] = content_hash(payload)
    return payload


def _counterposition_for(
    *,
    concern_id: str,
    anchor_id: str,
    actor: ActorReference,
    now: datetime,
) -> Counterposition:
    counter_id = new_id("occtr")
    payload = _with_hash(
        {
            "id": counter_id,
            "schema_version": "0.1.0",
            "created_at": now,
            "created_by": actor,
            "counterposition_id": counter_id,
            "concern_id": concern_id,
            "statement": (
                "The manuscript may intend a narrower claim than the live review "
                "inferred; residual disagreement remains for human adjudication."
            ),
            "supporting_anchor_ids": [anchor_id],
            "supporting_evidence_ids": [],
            "source": CounterpositionSource.REVIEWER_SYSTEM,
            "residual_disagreement": (
                "Private live import seed; not a production authenticity determination."
            ),
            "adequacy_status": "unreviewed",
        }
    )
    return Counterposition.model_validate(payload)


def _evidence_for(
    *,
    concern_id: str,
    anchor_id: str,
    artifact: ArtifactReference,
    actor: ActorReference,
    now: datetime,
    description: str,
) -> EvidenceItem:
    evidence_id = new_id("ocevd")
    payload = _with_hash(
        {
            "id": evidence_id,
            "schema_version": "0.1.0",
            "created_at": now,
            "created_by": actor,
            "evidence_id": evidence_id,
            "concern_id": concern_id,
            "evidence_type": EvidenceType.MANUSCRIPT_TEXT,
            "supports": EvidenceDirection.CONCERN,
            "description": description,
            "artifact_reference": artifact,
            "anchor_ids": [anchor_id],
            "method": "live_export_quote",
            "producer": actor,
            "tool_manifest": None,
            "reproducibility_status": ReproducibilityStatus.JUDGMENT_BASED,
            "limitations": (
                "Private live export seed; evidence_class=private_live; "
                "not production MANIFEST material."
            ),
            "independence_group": "live-import",
        }
    )
    return EvidenceItem.model_validate(payload)


def build_live_case_bundle(
    *,
    export_path: Path,
    manuscript_path: Path,
    case_version: str = "1.0.0",
    case_id: str | None = None,
) -> tuple[CaseBundle, ExportKind, bytes]:
    """Build a CaseBundle from a live Coarse or OpenReviewer export + manuscript."""
    assert_not_production_fixtures_path(export_path, action="import")
    manuscript_path = manuscript_path.resolve()
    if not manuscript_path.is_file():
        raise FileNotFoundError(f"manuscript not found: {manuscript_path}")

    raw = json.loads(export_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("live export must be a JSON object")
    if raw.get("performance_claims_authorized") is True:
        raise ValueError(
            "Refusing import: performance_claims_authorized must remain false "
            "for private live exports."
        )

    kind = detect_export_kind(raw)
    manuscript_bytes = manuscript_path.read_bytes()
    sha256 = hashlib.sha256(manuscript_bytes).hexdigest()
    media_type = _guess_media_type(manuscript_path)
    artifact = ArtifactReference(
        uri=str(manuscript_path.as_posix()),
        sha256=sha256,
        media_type=media_type,
        byte_size=len(manuscript_bytes),
    )

    actor = _actor()
    now = datetime.now(UTC)
    suffix = _stable_suffix(sha256, export_path.resolve().as_posix(), kind)
    resolved_case_id = case_id or f"occase_live_{suffix}"
    manuscript_id = f"ocms_live_{suffix}"
    version_id = f"ocver_live_{suffix}"
    run_id = f"ocrun_live_{suffix}"

    extracted_text: str | None = None
    if media_type.startswith("text/") or manuscript_path.suffix.lower() in {
        ".md",
        ".markdown",
        ".tex",
        ".txt",
        ".html",
        ".htm",
    }:
        try:
            extracted_text = manuscript_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted_text = None

    if kind == "coarse":
        review = CoarseReview.model_validate(raw)
        review_dict = review.model_dump(mode="json")
        title = review.title
        domain_profile = (review.domain or "general").replace(" ", "_")[:64] or "general"
        language = "en"
        if isinstance(review.language, dict) and review.language.get("primary"):
            language = str(review.language["primary"])
    else:
        export = import_openreviewer_export(export_path)
        review_dict = _openreviewer_as_coarse_dict(export)
        title = export.title
        domain_profile = "general"
        language = "en"

    anchors, claims, concerns = convert_coarse_review(
        review_dict,
        manuscript_version_id=version_id,
        run_id=run_id,
        extracted_text=extracted_text,
    )
    if not concerns:
        raise ValueError("live export produced no concerns to seed")

    # Relabel OpenReviewer concerns for clarity in Studio.
    if kind == "openreviewer":
        rewritten: list[Any] = []
        for concern in concerns:
            payload = concern.model_dump(mode="json")
            payload["concern_type"] = "adapter.openreviewer.unclassified"
            payload["origin"]["origin_id"] = "openreviewer"
            payload["content_hash"] = "0" * 64
            payload["content_hash"] = content_hash(payload)
            rewritten.append(type(concern).model_validate(payload))
        concerns = rewritten

    evidence: list[EvidenceItem] = []
    counterpositions: list[Counterposition] = []
    for concern in concerns:
        anchor_id = concern.anchor_ids[0]
        evidence.append(
            _evidence_for(
                concern_id=concern.concern_id,
                anchor_id=anchor_id,
                artifact=artifact,
                actor=actor,
                now=now,
                description=f"Quoted span supporting: {concern.title}",
            )
        )
        if concern.severity in {Severity.CRITICAL, Severity.MAJOR}:
            counterpositions.append(
                _counterposition_for(
                    concern_id=concern.concern_id,
                    anchor_id=anchor_id,
                    actor=actor,
                    now=now,
                )
            )

    manuscript = Manuscript.model_validate(
        _with_hash(
            {
                "id": manuscript_id,
                "schema_version": "0.1.0",
                "created_at": now,
                "created_by": actor,
                "manuscript_id": manuscript_id,
                "title": title,
                "rights_classification": RightsClassification.CONTRIBUTED,
                "consent_policy_id": "operator-private-live-v1",
                "current_version_id": version_id,
            }
        )
    )
    version = ManuscriptVersion.model_validate(
        _with_hash(
            {
                "id": version_id,
                "schema_version": "0.1.0",
                "created_at": now,
                "created_by": actor,
                "version_id": version_id,
                "manuscript_id": manuscript_id,
                "previous_version_id": None,
                "source_format": _source_format(manuscript_path),
                "source_artifact": artifact,
                "rendered_artifact": None,
                "extracted_artifact": None,
                "language": language,
                "domain_profile": domain_profile,
                "page_count": 1,
                "ingestion_metadata": IngestionMetadata(
                    method="live_runner_import",
                    tool="opencritique-registry import-live-run",
                    tool_version="0.5.0a1",
                    notes=(
                        f"evidence_class={EVIDENCE_CLASS}; export_kind={kind}; "
                        "performance_claims_authorized=false; "
                        "refuse fixtures/*/production/ promotion"
                    ),
                ),
            }
        )
    )

    bundle = CaseBundle(
        case_id=resolved_case_id,
        case_version=case_version,
        policy_version="case-policy-v0.1",
        case_type="microcase",
        manuscript=manuscript,
        manuscript_versions=[version],
        anchors=anchors,
        claims=claims,
        concerns=concerns,
        evidence=evidence,
        counterpositions=counterpositions,
        adjudications=[],
        resolutions=[],
        run_manifests=[],
        mutation=None,
        known_ambiguities=[
            f"evidence_class={EVIDENCE_CLASS}",
            "Private live operator import; not production authenticity.",
            "performance_claims_authorized=false",
            "Do not auto-promote runs/ into fixtures/*/production/.",
        ],
    )
    return bundle, kind, manuscript_bytes


def private_live_grants() -> list[RightsGrantInput]:
    """Operator-owned grants for Studio adjudication (not production release)."""
    scope = (
        "Private live operator import (evidence_class=private_live). "
        "Sample/operator grant template only. Not a production MANIFEST. "
        "performance_claims_authorized=false."
    )
    authority = "Operator-owned private live manuscript / sample grant template"
    uses = (
        DataUse.OPERATIONAL_PROCESSING,
        DataUse.RETENTION,
        DataUse.EXPERT_ADJUDICATION,
        DataUse.BENCHMARK_EVALUATION,
    )
    return [
        RightsGrantInput(
            use=use,
            basis=GrantBasis.PROJECT_CREATED,
            authority=authority,
            scope=scope,
        )
        for use in uses
    ]


def _ensure_principal(
    session,
    *,
    actor_id: str,
    role: PrincipalRole,
    display_name: str,
) -> None:
    row = session.get(PrincipalORM, actor_id)
    if row is None:
        session.add(
            PrincipalORM(
                actor_id=actor_id,
                role=role.value,
                display_name=display_name,
                active=True,
            )
        )
        session.flush()
        return
    if row.role != role.value:
        raise ValueError(
            f"principal {actor_id!r} exists with role {row.role!r}, expected {role.value!r}"
        )
    if not row.active:
        row.active = True
    if display_name and row.display_name != display_name:
        row.display_name = display_name


def resolve_manuscript_path(
    *,
    manuscript: Path | None,
    export_path: Path,
    export_payload: dict[str, Any] | None = None,
) -> Path:
    if manuscript is not None:
        return manuscript.resolve()
    payload = export_payload
    if payload is None:
        payload = json.loads(export_path.read_text(encoding="utf-8"))
    provenance = payload.get("opencritique_provenance")
    if isinstance(provenance, dict):
        candidate = provenance.get("manuscript_path")
        if isinstance(candidate, str) and candidate.strip():
            path = Path(candidate)
            if path.is_file():
                return path.resolve()
    raise FileNotFoundError(
        "Provide --manuscript; could not infer a readable manuscript_path "
        "from export provenance."
    )


def import_live_run(
    *,
    from_path: Path,
    manuscript: Path | None = None,
    database_url: str,
    artifact_root: Path,
    max_artifact_bytes: int = 50_000_000,
    admin_actor_id: str = "opencritique-admin",
    admin_display_name: str = "OpenCritique Administrator",
    adjudicator_actor_id: str = "adjudicator-sample",
    adjudicator_display_name: str = "Sample Adjudicator",
    studio_host: str = "127.0.0.1",
    studio_port: int = 8000,
    case_id: str | None = None,
    case_version: str = "1.0.0",
) -> LiveImportResult:
    """Register a live export as a case, seed tasks, and return Studio handoff info."""
    export_path = resolve_export_path(from_path)
    if is_under_private_runs(export_path):
        # Expected for operator demos; still refuse production fixture targets.
        pass
    assert_not_production_fixtures_path(export_path, action="import")

    payload = json.loads(export_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("live export must be a JSON object")
    manuscript_path = resolve_manuscript_path(
        manuscript=manuscript,
        export_path=export_path,
        export_payload=payload,
    )
    bundle, kind, manuscript_bytes = build_live_case_bundle(
        export_path=export_path,
        manuscript_path=manuscript_path,
        case_version=case_version,
        case_id=case_id,
    )

    upgrade_head(database_url)
    store = LocalArtifactStore(artifact_root, max_artifact_bytes)
    store.ensure_root()
    engine = make_engine(database_url)
    factory = make_session_factory(engine)

    with factory.begin() as session:
        _ensure_principal(
            session,
            actor_id=admin_actor_id,
            role=PrincipalRole.ADMIN,
            display_name=admin_display_name,
        )
        _ensure_principal(
            session,
            actor_id=adjudicator_actor_id,
            role=PrincipalRole.ADJUDICATOR,
            display_name=adjudicator_display_name,
        )
        admin_token = issue_token(session, actor_id=admin_actor_id).token
        adjudicator_token = issue_token(session, actor_id=adjudicator_actor_id).token
        registry = RegistryService(session, store)

        artifact_ref = bundle.manuscript_versions[0].source_artifact
        view = registry.put_artifact(
            data=manuscript_bytes,
            media_type=artifact_ref.media_type,
            rights_classification=bundle.manuscript.rights_classification,
            actor_id=admin_actor_id,
        )
        if view.sha256 != artifact_ref.sha256:
            raise ValueError("manuscript artifact hash mismatch during live import")

        # Also store the export JSON as a linked operational artifact (optional aid).
        export_bytes = export_path.read_bytes()
        registry.put_artifact(
            data=export_bytes,
            media_type="application/json",
            rights_classification=bundle.manuscript.rights_classification,
            actor_id=admin_actor_id,
        )

        registry.register_case(
            CaseRegistration(bundle=bundle, grants=private_live_grants()),
            actor_id=admin_actor_id,
        )
        seeded = registry.seed_tasks(
            case_id=bundle.case_id,
            case_version=bundle.case_version,
            concern_ids=None,
            actor_id=admin_actor_id,
        )

    studio_url = f"http://{studio_host}:{studio_port}/studio"
    return LiveImportResult(
        case_id=bundle.case_id,
        case_version=bundle.case_version,
        evidence_class=EVIDENCE_CLASS,
        seeded_tasks=len(seeded),
        concern_titles=[c.title for c in bundle.concerns],
        admin_token=admin_token,
        adjudicator_token=adjudicator_token,
        studio_url=studio_url,
        export_kind=kind,
        claims_authorized=False,
    )


_SECRET_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,}|"
    r"OPEN(?:AI|CRITIQUE_BYOK)_API_KEY\s*[=:]\s*\S+)"
)


def redact_secrets(text: str) -> str:
    """Strip key-shaped substrings from operator-facing error text."""
    return _SECRET_RE.sub("[REDACTED]", text)
