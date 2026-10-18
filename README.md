# Buildwise GH — Construction AI MVP

A Ghana-focused, early-stage construction planning workspace. A user writes a short building brief and receives a structured concept specification, schematic SVG room plan, downloadable GLB massing model, first-pass schedule, indicative GHS cost allocation and preliminary screening notes.

> **Important:** This is a software MVP for early planning only. It does not produce architectural or structural drawings, construction quantities, a professional cost estimate, permit approval or confirmation of legal/code compliance. Have designs and prices checked by qualified local professionals and the relevant authorities before making decisions or building.

## What's included

- Account registration and sign-in with hashed passwords and short-lived bearer tokens.
- Private user-owned project records, stored in SQLite locally and PostgreSQL on Render.
- Lightweight, deterministic brief parser — no large model download or paid AI API key.
- Generated schematic SVG floor plan and downloadable glTF 2.0 binary (`.glb`) massing model.
- Indicative sequential project schedule with a simple seasonal planning allowance.
- Preliminary rule-screening output with clear non-approval disclaimers.
- High-level GHS estimate with an editable starter rate table and visible uncertainty range.
- Contractor directory matcher. It starts **empty**; add and vet real listings before using it.
- Responsive same-origin web UI and Render Blueprint configuration.

## Run locally

Requirements: Python 3.11+ (the project is configured for Python 3.12), plus Docker if you prefer containers.

### Python

```bash
cd construction-ai
cp .env.example .env
# Edit .env and replace SECRET_KEY with a long, random development secret.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open <http://localhost:8000>. API documentation is at <http://localhost:8000/docs> and the health endpoint is <http://localhost:8000/api/health>.

The `build.sh` helper also creates a virtual environment, installs dependencies, loads `.env` and starts the app. It is a one-time setup plus server command; use the Python commands above on later runs if you do not want to reinstall packages.

### Docker

```bash
docker compose up --build
```

The local Compose setup persists its SQLite database in a Docker volume. For multi-user or deployed use, configure PostgreSQL.

## Deploy to Render

The included `render.yaml` is a Render Blueprint:

1. Push this folder to a GitHub repository.
2. In Render, choose **New → Blueprint**, connect the repository and select `render.yaml`.
3. Review the resources and current prices before confirming. The template uses a **free web service** and the smallest currently named paid PostgreSQL compute plan so the database does not expire after 30 days. The web service can spin down when idle; select a paid web plan for always-on production use.
4. Render generates `SECRET_KEY` and wires `DATABASE_URL` to the managed PostgreSQL service. Do not paste secrets into GitHub or commit `.env`.
5. Once the deploy is live, check `/api/health`, open the service URL and create an account.

Render plan names and prices can change. Review them in Render before applying the Blueprint. If you intentionally switch the database to Render's free PostgreSQL plan for a short preview, note that free Render Postgres expires after 30 days; upgrade or back up/export before then. The app regenerates files on demand, so it does not require a persistent web-service disk.

## Local configuration

Copy `.env.example` to `.env` and set:

- `SECRET_KEY`: long random value. Render uses a generated secret.
- `DATABASE_URL`: defaults to a local SQLite database; use a Postgres connection URL for deployment.
- `OUTPUT_DIR`: optional temporary artifact directory. Generated artifacts are recreated from the project record when requested.

## API overview

- `POST /api/auth/register` — create an account.
- `POST /api/auth/login` — obtain a bearer token.
- `GET /api/auth/me` — current account (`Authorization: Bearer ...`).
- `POST /api/project/generate` — generate and save a project concept (authenticated).
- `GET /api/projects` and `GET /api/projects/{id}` — list/open your projects (authenticated).
- `GET /api/projects/{id}/artifacts/plan.svg` — generated schematic SVG (authenticated).
- `GET /api/projects/{id}/artifacts/model.glb` — generated massing model (authenticated).
- `GET /api/projects/{id}/artifacts/schedule.json` — generated schedule (authenticated).
- `POST /api/contractors/match` — match directory records by city, budget and building type.
- `GET /api/health` — application/database health.

Interactive API docs: `/docs`.

## Update the starter data before real use

- `data/materials_gh.json` holds editable starter GHS rates and percentage allocations. They are not live market data and have not been independently verified. Update with current local supplier quotations and a quantity surveyor's guidance.
- `data/building_codes_gh.json` holds screening values only. Confirm current building, planning, fire, environmental, accessibility and municipal requirements for the actual site and project.
- `data/contractors_gh.json` intentionally contains `[]`. Add only vendors you have permission to list and whose contact details, licensing/registration and references you have checked. The UI labels added entries as unverified unless an administrator sets `is_verified` true.
- `data/weather_zones.json` controls a simple schedule buffer; it is not a weather forecast.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Before production

This is a prototype, not a security-audited construction or finance product. Add schema migrations (for example Alembic), database backups, account recovery/email verification, rate limits, audit logging, monitoring and a security review. Review data retention and privacy requirements before storing sensitive project briefs. Do not rely on the concept plan, model, estimate, schedule or compliance screen for construction or legal approval.
