# Deferred: hosted production ops beyond Compose (#18)

Spec only / runbook gap analysis. Local + BYOK runbooks and the Compose
reference stack are in-tree today
([deployment-local.md](deployment-local.md),
[deployment-byok.md](deployment-byok.md), `docker-compose.yml`). Tracked as
[issue #18](https://github.com/fraware/OpenCritique-Commons/issues/18).

## Goal

Define and operate a **hosted** production deployment mode beyond the reference
Compose stack without weakening claim boundaries or signing custody.

## Gap analysis vs Compose reference

| Area | Compose reference today | Hosted DoD gap |
|---|---|---|
| Networking | Localhost ports | Ingress, TLS, private DB network |
| Secrets | Env / operator `.env` | Managed secret store; rotation |
| Backups | Named volume only | Scheduled backup + restore drill |
| Upgrades / rollback | Rebuild compose | Versioned release + rollback runbook |
| Health | `/healthz` + `/readyz` | SLOs + alerting sketch |
| Signing | Dev/prod public trust store; private keys offline (#4) | No production private keys on app hosts |
| Multi-tenant | Single-operator assumed | Isolation threat-model delta if shared |

## Hard DoD

- Hosted deployment runbook: networking, secrets, backups, upgrades, rollback.
- Postgres + artifact-root durability and restore drill documented.
- `/healthz` + `/readyz` SLOs and alerting sketch.
- No production private signing keys on shared app hosts (ties to #4).
- Explicit statement that hosting does **not** authorize scientific performance
  claims.
- Threat model delta vs local/BYOK.

## Non-goals

- Replacing the development trust store with production private keys in-repo.
- Multi-cloud marketing without a working restore drill.
- Full hosted SaaS product in this roadmap phase.

## Dependencies

Production signing ceremony (#4); expert/ops ownership for on-call (#14 / #19).
