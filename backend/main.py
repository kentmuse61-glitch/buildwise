"""Construction AI Ghana — FastAPI application and same-origin static frontend."""

from __future__ import annotations

import csv
import html
import io
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

# Load local configuration before importing modules that read environment values.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from fastapi.responses import FileResponse

from .auth import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .compliance import ComplianceChecker
from .contractors import ContractorMatcher
from .database import Base, Project, User, engine, get_db
from .model_3d import Model3DGenerator
from .market_directions import MarketDirectionBuilder
from .nlp_engine import parse_construction_request
from .plan_generator import PlanGenerator
from .schedule_4d import Schedule4D
from .review_tools import ReviewTools
from .workbench import ProjectWorkbench


DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))).expanduser().resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Public concepts intentionally never enter the project database.  Their
# unguessable artifact links are process-local, time-limited and regenerated on
# demand; this keeps legacy authenticated projects private when public concept
# mode is enabled.
_PUBLIC_ARTIFACT_TTL = timedelta(hours=1)
_PUBLIC_GENERATION_WINDOW_SECONDS = 60.0
_PUBLIC_GENERATION_LIMIT = 5
_public_artifacts: dict[str, dict[str, Any]] = {}
_public_generation_history: dict[str, list[float]] = {}

# For a new MVP deployment this creates the initial tables. Use Postgres on Render;
# SQLite is intended for local development and single-process testing only.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Buildwise GH",
    version="1.2.4",
    description="Early-stage design-to-delivery planning tools. Generated outputs are illustrative, not professional approvals.",
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add low-risk browser protections without blocking same-origin artifacts."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    return response


plan_gen = PlanGenerator(str(OUTPUT_DIR))
model_3d = Model3DGenerator(str(OUTPUT_DIR))
schedule_4d = Schedule4D(str(OUTPUT_DIR), str(DATA_DIR))
workbench = ProjectWorkbench(plan_gen, schedule_4d)
market_directions = MarketDirectionBuilder()
review_tools = ReviewTools()
compliance = ComplianceChecker(str(DATA_DIR))
contractors = ContractorMatcher(str(DATA_DIR))


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)
    email: str = Field(min_length=5, max_length=100)
    company_name: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=32)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("Enter a valid email address")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class ProfessionalHandoffRequest(BaseModel):
    """Optional site and programme data for a licensed professional's brief."""

    site_width_m: float | None = Field(default=None, gt=0, le=100_000)
    site_depth_m: float | None = Field(default=None, gt=0, le=100_000)
    building_footprint_sqm: float | None = Field(default=None, gt=0, le=1_000_000)
    road_orientation: str = Field(default="", max_length=40)
    local_authority: str = Field(default="", max_length=160)
    planning_priorities: str = Field(default="", max_length=1500)


class ProjectRequest(BaseModel):
    description: str = Field(min_length=10, max_length=4000)
    name: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=100)
    budget: float | None = Field(default=None, gt=0, le=1_000_000_000_000)
    apply_bathroom_template: bool = False
    market_focus: str = Field(default="balanced", min_length=1, max_length=40, validation_alias=AliasChoices("market_focus", "target_market"))
    handoff: ProfessionalHandoffRequest | None = None

    @field_validator("market_focus")
    @classmethod
    def normalize_market_focus(cls, value: str) -> str:
        aliases = {
            "ghana_context": "ghana_context", "ghana": "ghana_context", "local": "ghana_context",
            "global_modern": "global_modern", "international": "global_modern", "global": "global_modern",
            "balanced": "balanced", "both": "balanced",
        }
        normalized = aliases.get(value.strip().lower().replace("-", "_").replace(" ", "_"))
        if normalized is None:
            raise ValueError("Choose Ghana-context, global-modern or balanced market focus")
        return normalized


class MarketVariantRequest(BaseModel):
    """Bounded public input for review-first client-briefing directions."""

    description: str = Field(min_length=10, max_length=4000)
    location: str | None = Field(default=None, max_length=100)
    budget: float | None = Field(default=None, gt=0, le=1_000_000_000_000)
    apply_bathroom_template: bool = False
    market_focus: str = Field(default="balanced", min_length=1, max_length=40, validation_alias=AliasChoices("market_focus", "target_market"))

    @field_validator("market_focus")
    @classmethod
    def normalize_market_focus(cls, value: str) -> str:
        return ProjectRequest.normalize_market_focus(value)


class ContractorQuery(BaseModel):
    location: str = Field(min_length=1, max_length=100)
    budget: float = Field(gt=0, le=1_000_000_000_000)
    building_type: str = Field(default="residential", max_length=50)


class DesignRoomRequest(BaseModel):
    """Bounded concept geometry for the original Design Studio."""

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    label: str = Field(min_length=1, max_length=60)
    room_type: str = Field(default="room", min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    floor: int = Field(default=1, ge=1, le=50)
    x: float = Field(ge=0, le=1_000)
    y: float = Field(ge=0, le=1_000)
    width: float = Field(gt=0.49, le=200)
    depth: float = Field(gt=0.49, le=200)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Room label cannot be blank")
        return normalized


class DesignStudioRequest(BaseModel):
    """A single project-owned editable layout variant."""

    active_floor: int = Field(default=1, ge=1, le=50)
    variant_name: str = Field(default="Working concept", min_length=1, max_length=80)
    rooms: list[DesignRoomRequest] = Field(min_length=1, max_length=120)

    @field_validator("variant_name")
    @classmethod
    def normalize_variant_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Variant name cannot be blank")
        return normalized


class DeliveryProgressRequest(BaseModel):
    """User-entered progress only; it never certifies work or payment."""

    phase_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    progress_percent: int = Field(ge=0, le=100)
    status: Literal["Not started", "In progress", "Blocked", "Complete"] = "Not started"
    note: str = Field(default="", max_length=800)


class SeismicTraceRequest(BaseModel):
    """Bounded user-provided waveform values for a non-engineering visual summary."""

    sample_rate_hz: float = Field(ge=0.1, le=10_000)
    acceleration_g: list[float] = Field(min_length=8, max_length=4096)
    source_note: str = Field(default="", max_length=240)


class CaptureManifestRequest(BaseModel):
    """Capture metadata only; Buildwise does not receive images through this route."""

    image_count: int = Field(ge=1, le=100_000)
    ground_control_points: int = Field(default=0, ge=0, le=10_000)
    overlap_percent: float = Field(ge=0, le=100)
    coverage_area_sqm: float | None = Field(default=None, gt=0, le=1_000_000)
    capture_note: str = Field(default="", max_length=500)


class IfcManifestRequest(BaseModel):
    """An owner-entered BIM inventory before future private IFC import review."""

    ifc_schema: Literal["IFC2X3", "IFC4", "IFC4X3", "UNKNOWN"] = Field(default="UNKNOWN", alias="schema")
    filename: str = Field(min_length=1, max_length=160)
    element_counts: dict[str, int] = Field(min_length=1, max_length=80)
    author_note: str = Field(default="", max_length=500)


class VectorInventoryRequest(BaseModel):
    """A human-confirmed vector inventory; no DXF/PDF source file is accepted."""

    filename: str = Field(min_length=1, max_length=160)
    unit: Literal["m", "mm", "ft", "unknown"] = "unknown"
    layer_counts: dict[str, int] = Field(min_length=1, max_length=100)
    closed_area_sqm: list[float] = Field(default_factory=list, max_length=500)
    source_note: str = Field(default="", max_length=500)


def _prune_public_artifacts() -> None:
    """Remove expired in-memory public artifact records and their known files."""
    now = datetime.now(timezone.utc)
    for token, record in list(_public_artifacts.items()):
        expires_at = record.get("expires_at")
        if not isinstance(expires_at, datetime) or expires_at > now:
            continue
        for path in record.get("paths", {}).values():
            try:
                resolved = Path(path).resolve()
                if resolved.parent == OUTPUT_DIR and resolved.is_file():
                    resolved.unlink()
            except OSError:
                pass
        _public_artifacts.pop(token, None)


def _check_public_generation_limit(request: Request) -> None:
    """Apply a small per-process abuse guard to anonymous artifact generation."""
    address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = [entry for entry in _public_generation_history.get(address, []) if now - entry < _PUBLIC_GENERATION_WINDOW_SECONDS]
    if len(recent) >= _PUBLIC_GENERATION_LIMIT:
        raise HTTPException(status_code=429, detail="Please wait before generating another public concept")
    recent.append(now)
    _public_generation_history[address] = recent


def _load_materials_data() -> dict[str, Any]:
    path = DATA_DIR / "materials_gh.json"
    try:
        with path.open(encoding="utf-8") as source:
            data = json.load(source)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _estimate_cost(spec: dict[str, Any]) -> dict[str, Any]:
    """Return an indicative high-level estimate, not a quantity-surveyor quote."""
    materials_data = _load_materials_data()
    location = str(spec.get("location", "Accra"))
    rates = materials_data.get("base_cost_per_sqm", {})
    base_rate = float(rates.get(location, rates.get("Accra", 1700)))
    area = max(20.0, float(spec.get("area_sqm", 100.0)))
    base_total = area * base_rate

    default_allocation = {"materials": 0.52, "labour": 0.28, "professional_fees": 0.08, "contingency": 0.12}
    allocation = materials_data.get("cost_allocation", default_allocation)
    allocation = {key: max(0.0, float(allocation.get(key, fallback))) for key, fallback in default_allocation.items()}
    allocation_sum = sum(allocation.values()) or 1.0
    allocation = {key: value / allocation_sum for key, value in allocation.items()}

    materials_total = base_total * allocation["materials"]
    material_breakdown = materials_data.get("materials_breakdown", [])
    share_sum = sum(max(0.0, float(item.get("share_of_materials", 0))) for item in material_breakdown) or 1.0
    materials = []
    for item in material_breakdown:
        share = max(0.0, float(item.get("share_of_materials", 0))) / share_sum
        amount = round(materials_total * share, 2)
        materials.append({
            "name": str(item.get("name", "Materials")),
            "category": "materials",
            "share_of_materials": round(share, 4),
            "estimated_amount_ghs": amount,
            "note": "Budget allocation only; no measured quantities or supplier quote.",
        })

    budget = spec.get("budget_constraint")
    return {
        "location": location,
        "currency": "GHS",
        "gross_floor_area_sqm": round(area, 1),
        "floors": int(spec.get("floors", 1)),
        "base_rate_per_sqm_ghs": round(base_rate, 2),
        "total_materials_ghs": round(base_total * allocation["materials"], 2),
        "labour_cost_ghs": round(base_total * allocation["labour"], 2),
        "professional_fees_ghs": round(base_total * allocation["professional_fees"], 2),
        "contingency_ghs": round(base_total * allocation["contingency"], 2),
        "materials": materials,
        "total_ghs": round(base_total, 2),
        "indicative_range_low_ghs": round(base_total * 0.85, 2),
        "indicative_range_high_ghs": round(base_total * 1.15, 2),
        "budget_constraint_ghs": round(float(budget), 2) if budget is not None else None,
        "within_budget": (base_total <= float(budget)) if budget is not None else None,
        "rate_note": materials_data.get(
            "rate_note",
            "Starter rate only. Obtain current local supplier and quantity-surveyor prices before relying on this estimate.",
        ),
        "disclaimer": "Illustrative concept estimate only; not a bill of quantities, tender price, or construction quote. Rates and scope must be checked locally.",
    }


def _prepare_concept_spec(
    description: str,
    location: str | None,
    budget: float | None,
    apply_bathroom_template: bool,
    market_focus: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse one bounded brief and attach review-first market directions."""
    spec = parse_construction_request(description)
    if location and location.strip().lower() not in {"auto", "automatic"}:
        spec["location"] = location.strip()
    if budget is not None:
        spec["budget_constraint"] = budget
    spec = plan_gen.prepare_residential_guidance(spec, apply_bathroom_template)
    directions = market_directions.build(spec, market_focus)
    spec["market_focus"] = directions["selected_focus"]
    return spec, directions


def _load_project_spec(project: Project) -> dict[str, Any]:
    try:
        value = json.loads(project.spec_json or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _project_summary(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "location": project.location,
        "building_type": project.building_type,
        "floors": project.floors,
        "rooms": project.rooms,
        "area_sqm": project.area_sqm,
        "estimated_cost_ghs": project.estimated_cost_ghs,
        "compliance_status": project.compliance_status,
        "plan_url": project.plan_svg_path,
        "model_3d_url": project.model_3d_path,
        "schedule_url": project.schedule_json_path,
        "workbench_url": f"/api/projects/{project.id}/workbench",
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


def _professional_handoff_payload(project: Project) -> dict[str, Any]:
    """Return a transparent brief for external professional review, not approval."""
    spec = _load_project_spec(project)
    raw_handoff = spec.get("professional_handoff")
    handoff = raw_handoff if isinstance(raw_handoff, dict) else {}
    guidance = spec.get("planning_guidance")
    return {
        "title": "Buildwise GH — Professional Handoff Pack",
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "location": project.location,
            "building_type": project.building_type,
            "floors": project.floors,
            "bedrooms": spec.get("bedrooms"),
            "bathrooms": spec.get("bathrooms"),
            "total_floor_area_sqm": project.area_sqm,
            "budget_target_ghs": spec.get("budget_constraint"),
            "created_at": project.created_at.isoformat() if project.created_at else None,
        },
        "site_and_programme": {
            "site_width_m": handoff.get("site_width_m"),
            "site_depth_m": handoff.get("site_depth_m"),
            "building_footprint_sqm": handoff.get("building_footprint_sqm"),
            "road_orientation": handoff.get("road_orientation") or "Not supplied",
            "local_authority": handoff.get("local_authority") or "Not supplied",
            "planning_priorities": handoff.get("planning_priorities") or "Not supplied",
        },
        "planning_context": guidance if isinstance(guidance, dict) else {},
        "professional_checklist": [
            "Verify title, boundaries, survey coordinates, road reserve and site dimensions.",
            "Confirm zoning, setbacks, planning constraints and MMDA requirements for the actual parcel.",
            "Complete architectural, structural, drainage, electrical and plumbing design as applicable.",
            "Obtain site investigation and any required geotechnical, environmental or utility information.",
            "Prepare, sign and submit permit drawings through appropriately licensed professionals and the relevant authority.",
        ],
        "disclaimer": "This is an early-planning handoff brief only. It is not a site survey, code determination, architectural or engineering drawing, bill of quantities, permit package, or approval to construct.",
    }


def _professional_handoff_html(payload: dict[str, Any]) -> str:
    """Render a self-contained, printable HTML handoff sheet."""
    project = payload["project"]
    site = payload["site_and_programme"]

    def safe(value: Any) -> str:
        return html.escape("Not supplied" if value in {None, ""} else str(value))

    rows = [
        ("Project", project["name"]), ("Location", project["location"]), ("Building type", project["building_type"]),
        ("Floors", project["floors"]), ("Bedrooms", project["bedrooms"]), ("Bathrooms", project["bathrooms"]),
        ("Total floor area", f"{project['total_floor_area_sqm']} m²"), ("Budget target", f"GHS {project['budget_target_ghs']}" if project["budget_target_ghs"] else None),
        ("Site width", f"{site['site_width_m']} m" if site["site_width_m"] else None),
        ("Site depth", f"{site['site_depth_m']} m" if site["site_depth_m"] else None),
        ("Target footprint", f"{site['building_footprint_sqm']} m²" if site["building_footprint_sqm"] else None),
        ("Road orientation", site["road_orientation"]), ("Local authority / assembly", site["local_authority"]),
    ]
    rows_html = "".join(f"<tr><th>{safe(label)}</th><td>{safe(value)}</td></tr>" for label, value in rows)
    checklist_html = "".join(f"<li>{safe(item)}</li>" for item in payload["professional_checklist"])
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Professional Handoff — {safe(project['name'])}</title><style>
body{{font:14px/1.5 Arial,sans-serif;color:#1e2f29;margin:32px;max-width:900px}}h1{{font-size:25px;margin:0 0 4px}}h2{{font-size:17px;margin:28px 0 8px}}.eyebrow{{color:#587267;font-size:11px;font-weight:700;letter-spacing:.09em}}.warning{{background:#fff3d4;border-left:4px solid #b77a00;padding:12px 14px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #cfd9d4;padding:8px;text-align:left;vertical-align:top}}th{{width:32%;background:#f1f5f2}}.box{{background:#f7faf8;border:1px solid #d8e2dd;padding:12px}}@media print{{body{{margin:15mm}}}}
</style></head><body><div class=\"eyebrow\">BUILDWISE GH · PROFESSIONAL HANDOFF PACK</div><h1>{safe(project['name'])}</h1><p>{safe(payload['disclaimer'])}</p><div class=\"warning\"><strong>Do not build from this document.</strong> Appoint suitably licensed Ghanaian professionals to verify all site, legal, planning, structural and services requirements.</div><h2>Project and site brief</h2><table>{rows_html}</table><h2>Original brief</h2><div class=\"box\">{safe(project['description'])}</div><h2>Planning priorities</h2><div class=\"box\">{safe(site['planning_priorities'])}</div><h2>Professional completion checklist</h2><ul>{checklist_html}</ul></body></html>"""


def _get_owned_project(project_id: int, current_user: User, db) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db=Depends(get_db)):
    existing = db.query(User).filter((User.username == req.username) | (User.email == req.email)).first()
    if existing:
        if existing.username == req.username:
            raise HTTPException(status_code=409, detail="Username already taken")
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        company_name=req.company_name.strip(),
        phone=req.phone.strip(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email already registered")
    db.refresh(user)
    return {"id": user.id, "username": user.username, "message": "Account created"}


@app.post("/api/auth/login")
def login(req: LoginRequest, db=Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not user.is_active or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Username or password is incorrect")
    token = create_access_token({"sub": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "expires_in_hours": ACCESS_TOKEN_EXPIRE_HOURS,
    }


@app.get("/api/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "company": current_user.company_name,
    }


@app.post("/api/project/generate")
def generate_project(
    req: ProjectRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    # The selected focus produces briefing prompts only; it never alters legal,
    # structural, permit or compliance status.
    spec, market_direction_result = _prepare_concept_spec(
        req.description, req.location, req.budget, req.apply_bathroom_template, req.market_focus
    )
    if req.handoff is not None:
        handoff = req.handoff.model_dump()
        if any(value not in (None, "") for value in handoff.values()):
            spec["professional_handoff"] = handoff

    compliance_result = compliance.check(spec)
    cost_result = _estimate_cost(spec)
    project_name = req.name.strip() if req.name and req.name.strip() else f"{str(spec['building_type']).title()} concept · {spec['location']}"
    project = Project(
        user_id=current_user.id,
        name=project_name[:200],
        description=req.description.strip(),
        location=spec["location"],
        building_type=spec["building_type"],
        floors=int(spec["floors"]),
        rooms=int(spec["rooms_total"]),
        area_sqm=float(spec["area_sqm"]),
        estimated_cost_ghs=cost_result["total_ghs"],
        compliance_status=compliance_result["status"],
        materials_json=json.dumps(cost_result["materials"], ensure_ascii=False),
        spec_json=json.dumps(spec, ensure_ascii=False),
        cost_json=json.dumps(cost_result, ensure_ascii=False),
        status="generated",
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Artifacts are regenerated on demand, so Render's ephemeral service disk is safe.
    project.plan_svg_path = f"/api/projects/{project.id}/artifacts/plan.svg"
    project.model_3d_path = f"/api/projects/{project.id}/artifacts/model.glb"
    project.schedule_json_path = f"/api/projects/{project.id}/artifacts/schedule.json"
    db.commit()
    db.refresh(project)

    result = _project_summary(project)
    result.update({
        "project_id": project.id,
        "db_id": project.id,
        "description": project.description,
        "spec": spec,
        "compliance": compliance_result,
        "cost": cost_result,
        "market_directions": market_direction_result,
    })
    return result


@app.post("/api/contractors/match")
def match_contractors(req: ContractorQuery):
    results = contractors.match(req.location, req.budget, req.building_type)
    return {
        "contractors": results,
        "count": len(results),
        "directory_note": "Only entries added to data/contractors_gh.json are shown. Verify licensing, references and contact details independently.",
    }


@app.get("/api/projects")
def list_projects(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return {"projects": [_project_summary(project) for project in projects]}


@app.get("/api/projects/{project_id}")
def get_project(project_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    project = _get_owned_project(project_id, current_user, db)
    try:
        cost = json.loads(project.cost_json or "{}")
    except json.JSONDecodeError:
        cost = {}
    spec = _load_project_spec(project)
    result = _project_summary(project)
    result.update({
        "description": project.description,
        "spec": spec,
        "cost": cost,
        "compliance": compliance.check(spec),
        "market_directions": market_directions.build(spec, str(spec.get("market_focus") or "balanced")),
    })
    return result


@app.get("/api/projects/{project_id}/workbench")
def get_project_workbench(project_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    """Return transparent original planning, QTO and delivery cards for one project."""
    project = _get_owned_project(project_id, current_user, db)
    return workbench.build(_load_project_spec(project))


@app.put("/api/projects/{project_id}/design-studio")
def save_design_studio(
    project_id: int,
    req: DesignStudioRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Save bounded room-block geometry and regenerate only on the next artifact request."""
    project = _get_owned_project(project_id, current_user, db)
    if req.active_floor > project.floors:
        raise HTTPException(status_code=422, detail="The selected Design Studio floor is outside this project's floor count")
    room_ids = [room.id for room in req.rooms]
    if len(room_ids) != len(set(room_ids)):
        raise HTTPException(status_code=422, detail="Each Design Studio room needs a unique ID")
    if any(room.floor > project.floors for room in req.rooms):
        raise HTTPException(status_code=422, detail="A room references a floor outside this project's floor count")

    spec = _load_project_spec(project)
    spec["design_studio"] = {
        "schema_version": 1,
        "variant_name": req.variant_name,
        "active_floor": req.active_floor,
        "rooms": [room.model_dump() for room in req.rooms],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Editable concept geometry only; it is not a dimensioned architectural, structural, permit or construction drawing.",
    }
    project.spec_json = json.dumps(spec, ensure_ascii=False)
    db.commit()
    db.refresh(project)
    return {"message": "Design Studio concept saved", "spec": spec, "workbench": workbench.build(spec)}


@app.put("/api/projects/{project_id}/delivery/progress")
def update_delivery_progress(
    project_id: int,
    req: DeliveryProgressRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Store project-owner progress statements with an explicit non-certification boundary."""
    project = _get_owned_project(project_id, current_user, db)
    spec = _load_project_spec(project)
    delivery = spec.get("delivery_tracking") if isinstance(spec.get("delivery_tracking"), dict) else {}
    progress = delivery.get("progress") if isinstance(delivery.get("progress"), dict) else {}
    progress[req.phase_key] = {
        "percent": req.progress_percent,
        "status": req.status,
        "note": req.note.strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    delivery["progress"] = progress
    spec["delivery_tracking"] = delivery
    project.spec_json = json.dumps(spec, ensure_ascii=False)
    db.commit()
    return {"message": "Progress saved", "workbench": workbench.build(spec)}


@app.put("/api/projects/{project_id}/site-review/seismic-trace")
def save_seismic_trace(
    project_id: int,
    req: SeismicTraceRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Store a limited visual waveform summary, never an engineering conclusion."""
    project = _get_owned_project(project_id, current_user, db)
    try:
        summary = review_tools.seismic_trace_summary(req.sample_rate_hz, req.acceleration_g, req.source_note)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    spec = _load_project_spec(project)
    reviews = spec.get("review_inputs") if isinstance(spec.get("review_inputs"), dict) else {}
    reviews["seismic_trace"] = summary
    spec["review_inputs"] = reviews
    project.spec_json = json.dumps(spec, ensure_ascii=False)
    db.commit()
    return {"message": "Seismic trace visual summary saved", "review": summary, "workbench": workbench.build(spec)}


@app.put("/api/projects/{project_id}/site-review/capture-manifest")
def save_capture_manifest(
    project_id: int,
    req: CaptureManifestRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Store privacy-safe capture metadata without accepting photos or reconstructions."""
    project = _get_owned_project(project_id, current_user, db)
    try:
        summary = review_tools.capture_manifest_summary(
            req.image_count, req.ground_control_points, req.overlap_percent, req.coverage_area_sqm, req.capture_note
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    spec = _load_project_spec(project)
    reviews = spec.get("review_inputs") if isinstance(spec.get("review_inputs"), dict) else {}
    reviews["capture_manifest"] = summary
    spec["review_inputs"] = reviews
    project.spec_json = json.dumps(spec, ensure_ascii=False)
    db.commit()
    return {"message": "Capture manifest saved", "review": summary, "workbench": workbench.build(spec)}


@app.put("/api/projects/{project_id}/bim/ifc-manifest")
def save_ifc_manifest(
    project_id: int,
    req: IfcManifestRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Record project-owned IFC inventory metadata without importing a model file."""
    project = _get_owned_project(project_id, current_user, db)
    try:
        summary = review_tools.ifc_manifest_summary(req.ifc_schema, req.filename, req.element_counts, req.author_note)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    spec = _load_project_spec(project)
    reviews = spec.get("review_inputs") if isinstance(spec.get("review_inputs"), dict) else {}
    reviews["ifc_manifest"] = summary
    spec["review_inputs"] = reviews
    project.spec_json = json.dumps(spec, ensure_ascii=False)
    db.commit()
    return {"message": "IFC manifest saved", "review": summary, "workbench": workbench.build(spec)}


@app.put("/api/projects/{project_id}/drawing-review/vector-inventory")
def save_vector_inventory(
    project_id: int,
    req: VectorInventoryRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """Record human-confirmed vector counts and areas without altering drawings."""
    project = _get_owned_project(project_id, current_user, db)
    try:
        summary = review_tools.vector_inventory_summary(
            req.filename, req.unit, req.layer_counts, req.closed_area_sqm, req.source_note
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    spec = _load_project_spec(project)
    reviews = spec.get("review_inputs") if isinstance(spec.get("review_inputs"), dict) else {}
    reviews["vector_inventory"] = summary
    spec["review_inputs"] = reviews
    project.spec_json = json.dumps(spec, ensure_ascii=False)
    db.commit()
    return {"message": "Vector inventory saved", "review": summary, "workbench": workbench.build(spec)}


@app.post("/api/public/project/generate")
def generate_public_project(req: ProjectRequest, request: Request):
    """Generate a time-limited, non-persistent anonymous concept workspace.

    Public mode never writes a ``Project`` row and never exposes an existing
    user's project.  It is intended for a no-login first experience; links
    expire after one hour or earlier on a service restart.
    """
    _prune_public_artifacts()
    _check_public_generation_limit(request)
    spec, market_direction_result = _prepare_concept_spec(
        req.description, req.location, req.budget, req.apply_bathroom_template, req.market_focus
    )
    if req.handoff is not None:
        handoff = req.handoff.model_dump()
        if any(value not in (None, "") for value in handoff.values()):
            spec["professional_handoff"] = handoff

    compliance_result = compliance.check(spec)
    cost_result = _estimate_cost(spec)
    project_name = req.name.strip() if req.name and req.name.strip() else f"{str(spec['building_type']).title()} concept · {spec['location']}"
    token = secrets.token_urlsafe(24)
    artifact_id = f"public-{token}"
    try:
        paths = {
            "plan.svg": Path(plan_gen.generate_plan(spec, artifact_id)).resolve(),
            "model.glb": Path(model_3d.generate_model(spec, artifact_id)).resolve(),
            "schedule.json": Path(schedule_4d.generate_schedule(spec, artifact_id)).resolve(),
        }
    except (OSError, TypeError, ValueError, ArithmeticError) as error:
        raise HTTPException(status_code=500, detail="Could not generate the public concept artifacts") from error
    if not all(path.is_file() and path.parent == OUTPUT_DIR for path in paths.values()):
        raise HTTPException(status_code=500, detail="Public concept artifacts were not created")
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + _PUBLIC_ARTIFACT_TTL
    _public_artifacts[token] = {"paths": paths, "expires_at": expires_at}
    prefix = f"/api/public/artifacts/{token}"
    return {
        "id": token,
        "is_public": True,
        "expires_at": expires_at.isoformat(),
        "name": project_name[:200],
        "description": req.description.strip(),
        "location": spec["location"],
        "building_type": spec["building_type"],
        "floors": int(spec["floors"]),
        "rooms": int(spec["rooms_total"]),
        "area_sqm": float(spec["area_sqm"]),
        "estimated_cost_ghs": cost_result["total_ghs"],
        "compliance_status": compliance_result["status"],
        "status": "temporary-public-concept",
        "created_at": created_at.isoformat(),
        "plan_url": f"{prefix}/plan.svg",
        "model_3d_url": f"{prefix}/model.glb",
        "schedule_url": f"{prefix}/schedule.json",
        "spec": spec,
        "cost": cost_result,
        "compliance": compliance_result,
        "market_directions": market_direction_result,
        "workbench": workbench.build(spec),
        "public_note": "This anonymous concept is not saved to an account and its artifact links expire in one hour.",
    }


@app.post("/api/v2/generate/market-variants")
def generate_market_variants(req: MarketVariantRequest, request: Request):
    """Return clean-room client-briefing directions without generating an approval or a saved project."""
    _check_public_generation_limit(request)
    spec, directions = _prepare_concept_spec(
        req.description, req.location, req.budget, req.apply_bathroom_template, req.market_focus
    )
    return {
        "status": "concept-directions-ready",
        "spec": spec,
        "market_directions": directions,
        "note": "No plan, permit conclusion, construction specification, cost quote, client score or project record was created by this comparison.",
    }


@app.get("/api/public/artifacts/{token}/{artifact_name}")
def get_public_artifact(token: str, artifact_name: str):
    """Serve one temporary public concept artifact through an unguessable link."""
    _prune_public_artifacts()
    record = _public_artifacts.get(token)
    if record is None:
        raise HTTPException(status_code=404, detail="Public concept artifact not found or expired")
    allowed_types = {
        "plan.svg": "image/svg+xml",
        "model.glb": "model/gltf-binary",
        "schedule.json": "application/json",
    }
    path = record.get("paths", {}).get(artifact_name)
    if artifact_name not in allowed_types or not isinstance(path, Path) or not path.is_file():
        raise HTTPException(status_code=404, detail="Public concept artifact not found or expired")
    return FileResponse(
        path,
        media_type=allowed_types[artifact_name],
        filename=f"buildwise-public-{artifact_name}",
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


@app.post("/api/debug/generate-test")
def generate_test_artifacts(current_user: User = Depends(get_current_user)):
    """Generate bounded, authenticated smoke-test artifacts without touching project data.

    This endpoint is intentionally authenticated: publicly writing artifacts on a
    live service would create an unnecessary abuse surface.  It always uses one
    fixed identifier, so repeated diagnostic calls do not create unbounded files.
    """
    del current_user  # Authentication is the access control; no identity is stored.
    sample_spec = {
        "building_type": "residential",
        "location": "Kumasi",
        "floors": 2,
        "bedrooms": 3,
        "bathrooms": 2,
        "rooms_total": 8,
        "area_sqm": 180,
        "special_features": ["solar_power"],
    }
    try:
        paths = {
            "plan": Path(plan_gen.generate_plan(sample_spec, "debug-test")),
            "model": Path(model_3d.generate_model(sample_spec, "debug-test")),
            "schedule": Path(schedule_4d.generate_schedule(sample_spec, "debug-test")),
        }
    except (OSError, TypeError, ValueError, ArithmeticError) as error:
        raise HTTPException(status_code=500, detail="Could not generate diagnostic artifacts") from error
    urls = {
        "plan": "/api/debug/artifacts/plan.svg",
        "model": "/api/debug/artifacts/model.glb",
        "schedule": "/api/debug/artifacts/schedule.json",
    }
    files = {
        key: {"exists": path.is_file(), "bytes": path.stat().st_size if path.is_file() else 0, "path": path.name}
        for key, path in paths.items()
    }
    return {
        "status": "ok" if all(item["exists"] for item in files.values()) else "artifact-generation-failed",
        "sample_spec": sample_spec,
        "artifact_urls": urls,
        "files": files,
        "note": "Diagnostic concept artifacts only; no project was created or changed.",
    }


@app.get("/api/debug/artifacts/{artifact_name}")
def get_debug_artifact(artifact_name: str, current_user: User = Depends(get_current_user)):
    """Serve one fixed diagnostic artifact to an authenticated workspace user."""
    del current_user
    allowed = {
        "plan.svg": (OUTPUT_DIR / "plan_debug-test.svg", "image/svg+xml"),
        "model.glb": (OUTPUT_DIR / "model_debug-test.glb", "model/gltf-binary"),
        "schedule.json": (OUTPUT_DIR / "schedule_debug-test.json", "application/json"),
    }
    artifact = allowed.get(artifact_name)
    if artifact is None or not artifact[0].is_file():
        raise HTTPException(status_code=404, detail="Diagnostic artifact not found; run POST /api/debug/generate-test first")
    return FileResponse(artifact[0], media_type=artifact[1], filename=f"buildwise-debug-{artifact_name}")


@app.get("/api/projects/{project_id}/artifacts/plan.svg")
def get_project_plan(project_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    project = _get_owned_project(project_id, current_user, db)
    spec = _load_project_spec(project)
    path = plan_gen.generate_plan(spec, project.id)
    return FileResponse(path, media_type="image/svg+xml", filename=f"concept-plan-{project.id}.svg")


@app.get("/api/projects/{project_id}/artifacts/model.glb")
def get_project_model(project_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    project = _get_owned_project(project_id, current_user, db)
    spec = _load_project_spec(project)
    path = model_3d.generate_model(spec, project.id)
    return FileResponse(path, media_type="model/gltf-binary", filename=f"concept-model-{project.id}.glb")


@app.get("/api/projects/{project_id}/artifacts/schedule.json")
def get_project_schedule(project_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    project = _get_owned_project(project_id, current_user, db)
    spec = _load_project_spec(project)
    path = schedule_4d.generate_schedule(spec, project.id)
    return FileResponse(path, media_type="application/json", filename=f"concept-schedule-{project.id}.json")


@app.get("/api/projects/{project_id}/artifacts/handoff.json")
def get_professional_handoff_json(project_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    project = _get_owned_project(project_id, current_user, db)
    payload = _professional_handoff_payload(project)
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="buildwise-handoff-{project.id}.json"'},
    )


@app.get("/api/projects/{project_id}/artifacts/handoff.html")
def get_professional_handoff_html(project_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    project = _get_owned_project(project_id, current_user, db)
    return Response(
        content=_professional_handoff_html(_professional_handoff_payload(project)),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="buildwise-handoff-{project.id}.html"'},
    )


@app.get("/api/projects/{project_id}/artifacts/cost.csv")
def get_project_cost_csv(project_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    project = _get_owned_project(project_id, current_user, db)
    try:
        cost = json.loads(project.cost_json or "{}")
    except json.JSONDecodeError:
        cost = {}
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["Buildwise GH — indicative project estimate"])
    writer.writerow(["Project", project.name])
    writer.writerow(["Location", project.location])
    writer.writerow(["Area (m²)", project.area_sqm])
    writer.writerow(["Currency", "GHS"])
    writer.writerow([])
    writer.writerow(["Line item", "Estimated amount (GHS)", "Basis"])
    writer.writerow(["Materials allocation", cost.get("total_materials_ghs", 0), "Indicative percentage allocation"])
    writer.writerow(["Labour allowance", cost.get("labour_cost_ghs", 0), "Indicative percentage allocation"])
    writer.writerow(["Professional fees allowance", cost.get("professional_fees_ghs", 0), "Indicative percentage allocation"])
    writer.writerow(["Contingency allowance", cost.get("contingency_ghs", 0), "Indicative percentage allocation"])
    for material in cost.get("materials", []):
        writer.writerow([material.get("name", "Materials"), material.get("estimated_amount_ghs", 0), "Materials budget allocation; not a measured quantity"])
    writer.writerow(["Indicative total", cost.get("total_ghs", project.estimated_cost_ghs), "Starter rate; not a quote"])
    writer.writerow(["Planning range — low", cost.get("indicative_range_low_ghs", 0), "Approx. -15%"])
    writer.writerow(["Planning range — high", cost.get("indicative_range_high_ghs", 0), "Approx. +15%"])
    writer.writerow([])
    writer.writerow(["Disclaimer", cost.get("disclaimer", "Illustrative estimate only; confirm current local prices and scope.")])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="buildwise-estimate-{project.id}.csv"'},
    )


@app.delete("/api/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    project = _get_owned_project(project_id, current_user, db)
    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/health")
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": "Construction AI Ghana",
        "version": app.version,
        "time": datetime.now(timezone.utc).isoformat(),
    }


# Keep the same-origin frontend mounted last so API routes take precedence.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
