# DevOps

CI/CD, infrastructure, deployment, and platform observability — at the **engineering-decision** level.

## Scope

- Environment separation and promotion policy
- Reproducible builds and immutable deploy artifacts
- Configuration and secrets boundaries at the platform layer
- CI/CD as an engineering contract (not tool syntax)
- Platform observability ownership (metrics, logs, traces)
- Operational failure planning (rollback, health, blast radius)
- Infrastructure-as-code as an explicit decision
- Operational feedback loops and post-incident learning

## Does not belong here

- Application-level logging practices → see `engineering/logging-and-observability.md` (EKP-LO)
- Application error semantics → see `engineering/error-handling.md` (EKP-EH)
- Security hardening details → see `security/security-fundamentals.md` (EKP-SF)
- Test philosophy and unit/integration strategy → see `testing/testing.md` (EKP-TS)
- Performance profiling mindset → see `performance/performance-mindset.md` (EKP-PM)
- Database schema and migrations → see `database/database-design.md` (EKP-DB)
- Stack-specific language/framework guides → see `php/`, `symfony/`, `typescript/`, `frontend/`

## Boundary with L0 and application code

| Concern | Owner | This domain |
|---------|-------|-------------|
| What to log in application code | EKP-LO | Cite — platform collects and routes |
| How failures surface to users/API | EKP-EH | Cite — ops plans rollback and incident hooks |
| Secrets in code review | EKP-SF | Cite — platform owns rotation and injection |
| What tests prove before merge | EKP-TS | Cite — CI gates enforce contract |
| Environment/layer responsibilities | EKP-LB | Apply — especially LB06 |

**Out of scope:** Docker/Kubernetes/Terraform/AWS command references, GitHub Actions cookbooks, manifest encyclopedias, cloud service catalogs.

## Published

- [devops-fundamentals.md](devops-fundamentals.md) — EKP-DV01–DV08; applies EKP-P01, P04, P06, P07, P09, P10
