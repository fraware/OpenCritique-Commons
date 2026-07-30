# Natural matcher-audit session manifests

Drop `MatcherAuditSessionManifest` JSON files here after natural audits run,
plus a companion `<stem>.agreement.json` (`AuditAgreementReport`) with completed
judgments.

This directory is intentionally empty of session evidence until then — gate #6
reads completed adjudication from these files (not `sampled_count`) and reports
natural=0 when none exist or judgments are incomplete.
