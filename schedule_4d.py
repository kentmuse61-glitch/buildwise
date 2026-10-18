"""Generate a preliminary, sequential construction schedule."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any


class Schedule4D:
    def __init__(self, output_dir: str = "output", data_dir: str = "data") -> None:
        self.output_dir = output_dir
        self.data_dir = data_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_schedule(self, spec: dict[str, Any], project_id: str | int) -> str:
        schedule = self.build_schedule(spec)
        safe_id = "".join(char for char in str(project_id) if char.isalnum() or char in "_-")[:48] or "project"
        filepath = os.path.join(self.output_dir, f"schedule_{safe_id}.json")
        with open(filepath, "w", encoding="utf-8") as output:
            json.dump(schedule, output, indent=2, ensure_ascii=False)
        return filepath

    def build_schedule(self, spec: dict[str, Any], today: date | None = None) -> dict[str, Any]:
        floors = min(max(int(spec.get("floors", 1)), 1), 50)
        area = float(spec.get("area_sqm", 100.0))
        location = str(spec.get("location", "Accra"))
        phases: list[dict[str, Any]] = [
            {"phase": "Site preparation", "duration_days": 14, "critical": True,
             "activities": ["Confirm boundaries and access", "Site clearing", "Setting out", "Geotechnical investigation"]},
            {"phase": "Substructure & foundation", "duration_days": 21, "critical": True,
             "activities": ["Excavation", "Foundation works", "Damp-proof course", "Concrete curing"]},
        ]
        for floor in range(1, floors + 1):
            phases.append({
                "phase": f"Floor {floor} structure",
                "duration_days": 28,
                "critical": True,
                "activities": [f"Columns and walls — level {floor}", f"Beams and slab — level {floor}", "Concrete curing and inspection"],
            })
        phases.extend([
            {"phase": "Masonry & blockwork", "duration_days": 28, "critical": True,
             "activities": ["Walling", "Lintels", "Door and window openings"]},
            {"phase": "Roofing & weatherproofing", "duration_days": 14, "critical": True,
             "activities": ["Roof structure", f"Install {spec.get('roof_type', 'iron_sheet')} covering", "Rainwater goods"]},
            {"phase": "Plumbing & electrical", "duration_days": 21, "critical": False,
             "activities": ["First-fix plumbing", "Electrical conduits and wiring", "Testing before closing walls"]},
            {"phase": "Finishes & fittings", "duration_days": 35, "critical": False,
             "activities": ["Plastering and rendering", "Tiling", "Painting", "Doors, windows and fixtures"]},
            {"phase": "External works", "duration_days": 14, "critical": False,
             "activities": ["Drainage", "Access and hardscape", "Boundary works and landscaping"]},
            {"phase": "Inspection & handover", "duration_days": 7, "critical": True,
             "activities": ["Professional inspections", "Snagging", "Testing and commissioning", "Handover documentation"]},
        ])

        weather = self._weather_config()
        start = (today or date.today()) + timedelta(days=7)
        rainy_months = set(weather.get("rainy_season_months", [5, 6, 7, 10, 11]))
        rainy_factor = float(weather.get("rainy_season_duration_factor", 1.15))
        duration_factor = rainy_factor if start.month in rainy_months else 1.0

        items: list[dict[str, Any]] = []
        current = start
        for phase in phases:
            duration = max(1, round(int(phase["duration_days"]) * duration_factor))
            end = current + timedelta(days=duration)
            items.append({
                "phase": phase["phase"],
                "start": current.isoformat(),
                "end": end.isoformat(),
                "duration_days": duration,
                "critical": phase["critical"],
                "activities": phase["activities"],
                "weather_adjusted": duration_factor > 1,
            })
            current = end

        total_days = (current - start).days
        return {
            "project": spec.get("raw_text", "Construction concept"),
            "location": location,
            "floors": floors,
            "area_sqm": area,
            "start_date": start.isoformat(),
            "estimated_completion": current.isoformat(),
            "total_duration_days": total_days,
            "buffer_included_days": round(total_days * 1.15),
            "weather_adjustment": f"{round((duration_factor - 1) * 100)}% planning allowance for rainy-season conditions" if duration_factor > 1 else "No seasonal allowance applied",
            "planning_note": "Indicative sequential schedule; site conditions, procurement, permits, contractor capacity and parallel work can change dates.",
            "phases": items,
            "gantt_data": self._make_gantt_data(items),
            "milestones": [
                {"name": "Site works start", "date": start.isoformat()},
                {"name": "Structure midpoint (approx.)", "date": (start + timedelta(days=round(total_days * 0.5))).isoformat()},
                {"name": "Roof weather-tight (approx.)", "date": (start + timedelta(days=round(total_days * 0.7))).isoformat()},
                {"name": "Practical completion (estimate)", "date": current.isoformat()},
            ],
        }

    def _weather_config(self) -> dict[str, Any]:
        path = os.path.join(self.data_dir, "weather_zones.json")
        try:
            with open(path, encoding="utf-8") as source:
                return json.load(source)
        except (OSError, json.JSONDecodeError):
            return {"rainy_season_months": [5, 6, 7, 10, 11], "rainy_season_duration_factor": 1.15}

    @staticmethod
    def _make_gantt_data(phases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not phases:
            return []
        start = date.fromisoformat(phases[0]["start"])
        end = date.fromisoformat(phases[-1]["end"])
        total = max((end - start).days, 1)
        result = []
        for phase in phases:
            phase_start = date.fromisoformat(phase["start"])
            phase_end = date.fromisoformat(phase["end"])
            left = (phase_start - start).days / total * 100
            width = (phase_end - phase_start).days / total * 100
            result.append({
                "name": phase["phase"],
                "left": round(left, 2),
                "width": round(width, 2),
                "critical": phase["critical"],
                "start": phase["start"],
                "end": phase["end"],
            })
        return result
