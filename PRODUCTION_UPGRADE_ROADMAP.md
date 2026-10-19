# Buildwise GH — production upgrade roadmap

This roadmap distinguishes completed hardening from larger changes that require a staged rollout, credentials, paid services, or professional product decisions.

## Completed in this release

- **Interactive 3D preview:** `@google/model-viewer` 4.2.0, vendored locally and used only for authenticated, generated GLB concept models.
  - Upstream: https://github.com/google/model-viewer
  - License: Apache-2.0
- **GLB quality gate:** the generated 3-floor concept model was validated with Khronos glTF Validator: zero errors and zero warnings.
  - Upstream: https://github.com/KhronosGroup/glTF-Validator
  - License: Apache-2.0
- **Dependency remediation:** migrated JWT implementation from `python-jose` to `PyJWT`, upgraded FastAPI/Starlette through FastAPI 0.146.0, upgraded `python-dotenv`, and removed unused multipart parsing.
  - `pip-audit -r requirements.txt` result: no known vulnerabilities.
- **Security headers:** content-type sniffing, framing, referrer, and browser-permission protections are set on every response.

## Next upgrades — approve and stage individually

### 1. Database migrations — highest priority before more schema changes

Use Alembic to replace `create_all()` as the production schema-management mechanism. This must be introduced with a baseline migration and a Render database backup, because the live Postgres database already contains application tables.

- Upstream: https://github.com/sqlalchemy/alembic
- License: MIT
- Required rollout: backup database, generate/review a baseline migration, stamp the existing production database, then use migrations for all future schema changes.

### 2. Account lifecycle and abuse protection

Add email verification, password reset, account deletion, login/registration throttling, audit records, and optionally secure cookie sessions. Moving to a full account framework requires a carefully planned migration from the existing user table and JWTs.

- Candidate upstream: https://github.com/fastapi-users/fastapi-users
- License: MIT
- Do not introduce it as a drop-in replacement without an account/data migration plan.

### 3. Observability and error monitoring

Add request IDs and structured logs first. Then connect OpenTelemetry traces and metrics only after selecting a collector/monitoring vendor and defining data-retention rules.

- Upstream: https://github.com/open-telemetry/opentelemetry-python
- License: Apache-2.0
- Required configuration: an OTLP collector or supported monitoring endpoint; no telemetry exporter is enabled by default.

### 4. Browser-level end-to-end tests

Add Playwright tests for registration, concept creation, model preview/load failure fallback, plan display, and handoff downloads. These should run in CI and on a staging service, never create arbitrary records in production.

- Upstream: https://github.com/microsoft/playwright
- License: Apache-2.0

### 5. Performance and resilience testing

Create a Locust test suite for the health, login, list-projects, and concept-generation paths. Run it only against a dedicated staging database and a clearly defined load budget.

- Upstream: https://github.com/locustio/locust
- License: MIT

### 6. Continuous security scanning

Run the following locally or in CI on each dependency update:

```bash
python -m pip install pip-audit bandit
pip-audit -r requirements.txt
bandit -r backend
```

- `pip-audit`: https://github.com/pypa/pip-audit — Apache-2.0
- Bandit: https://github.com/PyCQA/bandit — Apache-2.0

Bandit findings should be reviewed individually. The current source has only low/operational false positives for the literal `Bearer` scheme, Uvicorn's required `0.0.0.0` bind, and safe in-memory DOM construction; it does not parse untrusted XML.

## Product boundary

No repository or library turns concept plans, GLB massing models, estimates, or the professional handoff pack into construction drawings, code determinations, or permits. Those outputs require site-specific information and work/review by licensed professionals and the relevant authority.
