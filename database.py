"""Database setup: SQLite locally, Render Postgres in production."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parent.parent
_raw_database_url = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'construction_ai.db'}")
if _raw_database_url.startswith("postgres://"):
    DATABASE_URL = _raw_database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif _raw_database_url.startswith("postgresql://"):
    DATABASE_URL = _raw_database_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL = _raw_database_url

_connect_args: dict[str, object] = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
    if not DATABASE_URL.endswith(":memory:"):
        _sqlite_path = DATABASE_URL.split("sqlite:///")[-1].split("?", 1)[0]
        if _sqlite_path and _sqlite_path != ":memory:":
            Path(_sqlite_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    company_name = Column(String(200), default="")
    phone = Column(String(32), default="")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(100), default="Accra", nullable=False)
    building_type = Column(String(50), default="residential", nullable=False)
    floors = Column(Integer, default=1, nullable=False)
    rooms = Column(Integer, default=1, nullable=False)
    area_sqm = Column(Float, default=100.0, nullable=False)
    estimated_cost_ghs = Column(Float, default=0.0, nullable=False)
    compliance_status = Column(String(200), default="Review required", nullable=False)
    plan_svg_path = Column(String(500), default="")
    model_3d_path = Column(String(500), default="")
    schedule_json_path = Column(String(500), default="")
    materials_json = Column(Text, default="[]")
    spec_json = Column(Text, default="{}", nullable=False)
    cost_json = Column(Text, default="{}", nullable=False)
    status = Column(String(20), default="generated", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
