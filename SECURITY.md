# Security policy

Scientific documents, contributor uploads, supplementary files, reviewer-system outputs, calibration cases, and browser tokens are untrusted inputs.

## Implemented alpha controls

- content-addressed artifact storage with SHA-256 verification on every read;
- atomic artifact writes and configured size limits;
- bearer tokens generated from high-entropy randomness and stored only as hashes;
- immediate token expiry and revocation enforcement;
- role- and task-scoped API authorization;
- purpose-specific data-use grants;
- server-side blinding for production and calibration tasks;
- immutable case bundles, submissions, and determinations;
- rights-attested contributor intake;
- contributor prohibition on self-declaring public artifacts;
- calibration evidence identifier validation;
- studio token storage in browser `sessionStorage`, never URL parameters;
- local-only studio assets with a restrictive content-security policy;
- no third-party frontend scripts, fonts, or analytics;
- audit events for expert profiles, calibration, intake, claims, credits, compensation, and adjudication;
- conformance checks that detect missing or corrupted artifacts and inconsistent human-evaluation records;
- Ed25519 scorecard signing with separately distributed trusted public keys;
- explicit separation between signature validity and scientific correctness.

## Browser studio

The studio is served from the same origin as the API. It uses bearer authentication and is intended for controlled expert deployments. Operators must configure TLS and must not embed the studio in third-party frames. Tokens should be short-lived and revoked after a pilot or suspected exposure.

## Deployment requirements

Production deployments must additionally provide:

- TLS termination;
- managed secrets and rotation;
- PostgreSQL with least-privilege roles;
- encrypted object storage;
- backups and restoration testing;
- request-rate and upload limits;
- malware and file-structure scanning;
- isolated parsing and code-execution workers;
- outbound network restrictions;
- centralized security logs;
- privacy and research-ethics review;
- incident response ownership;
- external penetration testing.

The alpha service is not approved for regulated health data, classified information, export-controlled research, or manuscripts requiring contractual security controls.

## Reporting

Use GitHub's private security-advisory mechanism for suspected vulnerabilities. Do not disclose confidential manuscripts, access tokens, private signing keys, or personal data in public issues.
