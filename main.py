"""Construction AI Ghana — FastAPI application and same-origin static frontend."""

from __future__ import annotations

import csv
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load local configuration before importing modules that read environment values.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
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
from .nlp_engine import parse_construction_request
from .plan_generator import PlanGenerator
from .schedule_4d import Schedule4D


DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))).expanduser().resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# For a new MVP deployment this creates the initial tables. Use Postgres on Render;
# SQLite is intended for local development and single-process testing only.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Construction AI Ghana",
    version="1.0.0",
    description="Early-stage construction concept planning tools. Generated outputs are illustrative, not professional approvals.",
)

plan_gen = PlanGenerator(str(OUTPUT_DIR))
model_3d = Model3DGenerator(str(OUTPUT_DIR))
schedule_4d = Schedule4D(str(OUTPUT_DIR), str(DATA_DIR))
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


class ProjectRequest(BaseModel):
    description: str = Field(min_length=10, max_length=4000)
    name: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=100)
    budget: float | None = Field(default=None, gt=0, le=1_000_000_000_000)


class ContractorQuery(BaseModel):
    location: str = Field(min_length=1, max_length=100)
    budget: float = Field(gt=0, le=1_000_000_000_000)
    building_type: str = Field(default="residential", max_length=50)


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
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }


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
    spec = parse_construction_request(req.description)
    if req.location and req.location.strip().lower() not in {"auto", "automatic"}:
        spec["location"] = req.location.strip()
    if req.budget is not None:
        spec["budget_constraint"] = req.budget

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
    })
    return result


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
