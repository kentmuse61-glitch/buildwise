"""Original, review-first design-to-delivery calculations for Buildwise.

This module is deliberately dependency-light and keeps every calculation
traceable.  It is inspired by public AEC product categories (planning, QTO,
progress, energy and site review) but does not import, copy, or process third
party drawings, plans, source assets, or no-license source code.

All figures are early-planning allowances.  They are not a bill of quantities,
structural design, electrical design, programme commitment, or professional
site/seismic assessment.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .plan_generator import PlanGenerator
from .schedule_4d import Schedule4D


class ProjectWorkbench:
    """Build transparent, project-scoped planning and delivery summaries."""

    def __init__(self, plan_generator: PlanGenerator, schedule_generator: Schedule4D) -> None:
        self.plan_generator = plan_generator
        self.schedule_generator = schedule_generator

    def build(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Return all original concept-workbench cards for one project spec."""
        schedule = self.schedule_generator.build_schedule(spec)
        rooms = self.plan_generator.layout_rooms(spec)
        quantities = self._quantities(spec, rooms)
        delivery = self._delivery(schedule, spec)
        return {
            "status": "concept-review-required",
            "design_studio": self._design_studio(spec, rooms),
            "quantity_takeoff": quantities,
            "block_modules": self._block_modules(quantities),
            "energy_planning": self._energy_plan(spec, quantities),
            "delivery_tracking": delivery,
            "drawing_review": self._drawing_review(spec),
            "site_and_engineering": self._site_and_engineering(spec),
            "bim_interoperability": self._bim_interoperability(spec),
            "method_note": (
                "Buildwise uses original, deterministic concept calculations. Review and replace every allowance "
                "with measured, professionally verified project information before procurement or construction."
            ),
        }

    def _design_studio(self, spec: dict[str, Any], rooms: list[dict[str, Any]]) -> dict[str, Any]:
        design = spec.get("design_studio") if isinstance(spec.get("design_studio"), dict) else {}
        active_floor = self._int(design.get("active_floor"), 1, 1, self._int(spec.get("floors"), 1, 1, 50))
        all_rooms = design.get("rooms") if isinstance(design.get("rooms"), list) else []
        uses_custom_layout = bool(all_rooms)
        floor_area = sum(float(room["w"]) * float(room["h"]) for room in rooms)
        return {
            "schema_version": 1,
            "uses_custom_layout": uses_custom_layout,
            "active_floor": active_floor,
            "floors": self._int(spec.get("floors"), 1, 1, 50),
            "rooms": rooms,
            "visible_floor_area_sqm": round(floor_area, 2),
            "note": (
                "Room blocks are editable concept geometry. They do not establish wall thicknesses, access, "
                "setbacks, fire escape, structural spans, services, or construction dimensions."
            ),
        }

    def _quantities(self, spec: dict[str, Any], rooms: list[dict[str, Any]]) -> dict[str, Any]:
        floors = self._int(spec.get("floors"), 1, 1, 50)
        gross_area = self._number(spec.get("area_sqm"), 100.0, 20.0, 1_000_000.0)
        rooms_area = sum(float(room["w"]) * float(room["h"]) for room in rooms)
        # A custom layout on the selected floor gives a clearer concept footprint;
        # otherwise retain the user's parsed all-floor area as the source of truth.
        footprint = rooms_area if rooms and isinstance(spec.get("design_studio"), dict) and spec["design_studio"].get("rooms") else gross_area / floors
        footprint = max(10.0, footprint)
        side = math.sqrt(footprint)
        outer_perimeter = 4.0 * side
        external_wall_area = outer_perimeter * 3.0 * floors
        internal_partition_allowance = sum(2.0 * (float(room["w"]) + float(room["h"])) for room in rooms) * 0.35 * 3.0
        gross_wall_area = external_wall_area + internal_partition_allowance
        openings_allowance = gross_wall_area * 0.12
        net_wall_area = max(0.0, gross_wall_area - openings_allowance)
        roof_area = footprint * 1.12
        floor_slab_area = footprint * floors
        concrete_allowance_m3 = floor_slab_area * 0.10 + footprint * 0.25
        return {
            "basis": {
                "gross_floor_area_sqm": round(gross_area, 2),
                "floors": floors,
                "concept_footprint_sqm": round(footprint, 2),
                "visible_room_area_sqm": round(rooms_area, 2),
                "wall_height_allowance_m": 3.0,
                "openings_allowance_percent": 12,
            },
            "items": [
                {"item": "Floor slab allowance", "quantity": round(floor_slab_area, 2), "unit": "m²", "basis": "Concept footprint × floors"},
                {"item": "Roof coverage allowance", "quantity": round(roof_area, 2), "unit": "m²", "basis": "Concept footprint × 1.12 pitch allowance"},
                {"item": "Net wall face allowance", "quantity": round(net_wall_area, 2), "unit": "m²", "basis": "Perimeter/partition allowance less 12% openings"},
                {"item": "Concrete allowance", "quantity": round(concrete_allowance_m3, 2), "unit": "m³", "basis": "0.10 m slabs + 0.25 m³/m² conceptual foundation allowance"},
            ],
            "disclaimer": (
                "Transparent early-planning quantities only. A quantity surveyor must measure drawings, specifications, "
                "site conditions, openings, reinforcement, waste, labour and current supplier rates."
            ),
        }

    @staticmethod
    def _block_modules(quantities: dict[str, Any]) -> dict[str, Any]:
        wall_item = next((item for item in quantities["items"] if item["item"] == "Net wall face allowance"), {})
        wall_area = float(wall_item.get("quantity", 0))
        nominal_block_face_sqm = 0.40 * 0.20
        wastage = 0.08
        blocks = math.ceil((wall_area / nominal_block_face_sqm) * (1.0 + wastage))
        return {
            "assumption": "400 × 200 mm nominal block face, 8% concept wastage allowance",
            "estimated_blocks": blocks,
            "pallets_at_120_blocks": math.ceil(blocks / 120) if blocks else 0,
            "mortar_joint_and_strength_note": "Block type, thickness, mortar mix, reinforcement and strength are not selected by this tool.",
            "disclaimer": "Confirm module dimensions, material quality, structural design and supplier pack sizes with qualified professionals and suppliers.",
        }

    def _energy_plan(self, spec: dict[str, Any], quantities: dict[str, Any]) -> dict[str, Any]:
        area = float(quantities["basis"]["gross_floor_area_sqm"])
        features = {str(item).lower() for item in spec.get("special_features", []) if isinstance(item, str)}
        solar_requested = "solar_power" in features or "solar" in features
        low_kw = max(1.5, round(area * 0.0125, 1))
        high_kw = max(low_kw, round(area * 0.025, 1))
        return {
            "solar_requested_in_brief": solar_requested,
            "concept_pv_capacity_range_kwp": [low_kw, high_kw],
            "planning_prompts": [
                "Record actual appliance loads, operating hours and critical circuits.",
                "Confirm roof orientation, shading, structure, metering, battery requirements and utility arrangements on site.",
                "Sequence energy-intensive work only after contractor, safety and supply constraints are confirmed.",
            ],
            "disclaimer": "This is not an electrical load calculation, solar design, tariff analysis, equipment schedule, or energy compliance assessment.",
        }

    def _delivery(self, schedule: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        delivery = spec.get("delivery_tracking") if isinstance(spec.get("delivery_tracking"), dict) else {}
        raw_progress = delivery.get("progress") if isinstance(delivery.get("progress"), dict) else {}
        phases = []
        total_weight = 0.0
        weighted_progress = 0.0
        for phase in schedule.get("phases", []):
            name = str(phase.get("phase", "Project activity"))
            key = self._phase_key(name)
            entry = raw_progress.get(key) if isinstance(raw_progress.get(key), dict) else {}
            percent = self._int(entry.get("percent"), 0, 0, 100)
            duration = max(1, self._int(phase.get("duration_days"), 1, 1, 10_000))
            total_weight += duration
            weighted_progress += percent * duration
            phases.append({
                "key": key,
                "phase": name,
                "planned_start": phase.get("start"),
                "planned_end": phase.get("end"),
                "planned_duration_days": duration,
                "progress_percent": percent,
                "status": str(entry.get("status") or ("Not started" if percent == 0 else "In progress" if percent < 100 else "Complete")),
                "note": str(entry.get("note") or ""),
                "updated_at": entry.get("updated_at"),
            })
        return {
            "overall_progress_percent": round(weighted_progress / total_weight, 1) if total_weight else 0.0,
            "phases": phases,
            "planning_note": schedule.get("planning_note"),
            "disclaimer": "Progress is user-entered and does not certify work quality, payment entitlement, safety, completion, or contractor performance.",
        }

    @staticmethod
    def _drawing_review(spec: dict[str, Any]) -> dict[str, Any]:
        design = spec.get("design_studio") if isinstance(spec.get("design_studio"), dict) else {}
        reviews = spec.get("review_inputs") if isinstance(spec.get("review_inputs"), dict) else {}
        vector_inventory = reviews.get("vector_inventory") if isinstance(reviews.get("vector_inventory"), dict) else None
        return {
            "status": vector_inventory.get("status") if vector_inventory else "No source drawing uploaded",
            "available_design_data": "Editable room blocks" if design.get("rooms") else "Generated room blocks",
            "vector_inventory": vector_inventory,
            "review_workflow": [
                "Preserve each source file as an immutable original.",
                "Record format, source, revision, author and checksum before automated extraction.",
                "Present detected geometry and quantities with confidence values for human confirmation.",
                "Never silently alter a source drawing or represent a derived result as professionally approved.",
            ],
            "note": "Secure drawing upload/quarantine and DXF/vector-PDF extraction require a separately reviewed storage and malware-scanning deployment path.",
        }

    @staticmethod
    def _site_and_engineering(spec: dict[str, Any]) -> dict[str, Any]:
        handoff = spec.get("professional_handoff") if isinstance(spec.get("professional_handoff"), dict) else {}
        reviews = spec.get("review_inputs") if isinstance(spec.get("review_inputs"), dict) else {}
        seismic = reviews.get("seismic_trace") if isinstance(reviews.get("seismic_trace"), dict) else None
        capture = reviews.get("capture_manifest") if isinstance(reviews.get("capture_manifest"), dict) else None
        site_inputs = sum(1 for key in ("site_width_m", "site_depth_m", "building_footprint_sqm") if handoff.get(key))
        return {
            "site_input_completeness": f"{site_inputs}/3 optional handoff dimensions supplied",
            "seismic_visualization_status": seismic.get("status") if seismic else "No professionally interpreted geotechnical or seismic dataset supplied",
            "seismic_trace": seismic,
            "site_capture_manifest": capture,
            "engineering_review_prompts": [
                "Obtain a boundary/site survey and verify drainage, utilities and road reserve.",
                "Appoint qualified professionals for structural, geotechnical, drainage, electrical and plumbing design as applicable.",
                "Use professionally interpreted site/subsurface information only; do not infer ground conditions from a concept model.",
            ],
            "disclaimer": "No structural, seismic, geotechnical, fire, environmental, or services engineering verification is performed.",
        }

    @staticmethod
    def _bim_interoperability(spec: dict[str, Any]) -> dict[str, Any]:
        reviews = spec.get("review_inputs") if isinstance(spec.get("review_inputs"), dict) else {}
        ifc_manifest = reviews.get("ifc_manifest") if isinstance(reviews.get("ifc_manifest"), dict) else None
        return {
            "ifc_import_status": ifc_manifest.get("status") if ifc_manifest else "Not enabled",
            "ifc_manifest": ifc_manifest,
            "glb_concept_status": "Available for generated Buildwise concept massing",
            "next_safe_step": "Review a maintained IFC viewer, its licence, browser security model and sample-model handling before accepting user IFC files.",
            "note": "Do not upload third-party BIM models unless you have the right to share them and a private storage/review workflow is in place.",
        }

    @staticmethod
    def _number(value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            return min(max(float(value), minimum), maximum)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            return min(max(int(value), minimum), maximum)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _phase_key(value: str) -> str:
        key = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
        return key[:80] or "project-activity"
