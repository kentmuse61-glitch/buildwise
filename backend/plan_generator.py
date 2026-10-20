"""Generate resilient, schematic SVG floor plans (not construction drawings)."""

from __future__ import annotations

import html
import logging
import math
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


class PlanGenerator:
    """Generate a concept-level SVG plan from a parsed building brief.

    The generator deliberately uses a simple rectangular room layout. It is an
    illustrative planning aid only, not an architectural, structural, or permit
    drawing.
    """

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_plan(self, spec: dict[str, Any], project_id: str | int) -> str:
        """Generate a plan file, falling back to a valid SVG if needed."""
        safe_id = self._safe_id(project_id)
        filepath = os.path.join(self.output_dir, f"plan_{safe_id}.svg")
        try:
            svg_content = self.build_svg(spec)
            with open(filepath, "w", encoding="utf-8") as output:
                output.write(svg_content)
            return filepath
        except (OSError, TypeError, ValueError, ArithmeticError) as error:
            logger.exception("Plan generation failed for project %s: %s", safe_id, error)
            return self._generate_fallback_plan(safe_id)

    def _generate_fallback_plan(self, project_id: str | int) -> str:
        """Write a simple valid SVG instead of propagating an artifact failure."""
        filepath = os.path.join(self.output_dir, f"plan_{self._safe_id(project_id)}_fallback.svg")
        with open(filepath, "w", encoding="utf-8") as output:
            output.write(self._fallback_svg())
        return filepath

    @staticmethod
    def _safe_id(value: str | int) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "", str(value))[:48] or "project"

    def prepare_residential_guidance(
        self,
        spec: dict[str, Any],
        apply_bathroom_template: bool = False,
    ) -> dict[str, Any]:
        """Attach transparent Ghana-focused residential planning guidance.

        This is a user-selectable concept template, not a Ghana Building Code
        check and never a permit, architectural, or professional design result.
        """
        prepared = dict(spec)
        building_type = str(prepared.get("building_type") or "residential").strip().lower()
        if building_type != "residential":
            return prepared

        bedrooms = self._positive_int(prepared.get("bedrooms"), default=2, minimum=0, maximum=40)
        entered_bathrooms = self._positive_int(prepared.get("bathrooms"), default=1, minimum=0, maximum=40)
        suggested_bathrooms = self._suggested_sanitary_spaces(bedrooms)
        applied_bathrooms = max(entered_bathrooms, suggested_bathrooms) if apply_bathroom_template else entered_bathrooms
        if apply_bathroom_template:
            prepared["bathrooms"] = applied_bathrooms
            minimum_room_count = bedrooms + applied_bathrooms + 5
            prepared["rooms_total"] = max(
                self._positive_int(prepared.get("rooms_total"), default=minimum_room_count, minimum=2, maximum=60),
                minimum_room_count,
            )

        notes = [
            "Organises public living spaces separately from the bedroom zone.",
            "Includes a front veranda, living, dining, kitchen, store and a circulation zone in the visual concept.",
            "Uses a master-ensuite and shared-sanitary-space layout convention where the selected bathroom count allows.",
        ]
        if entered_bathrooms < suggested_bathrooms:
            notes.insert(0, f"Template suggests {suggested_bathrooms} sanitary space{'s' if suggested_bathrooms != 1 else ''} for {bedrooms} bedroom{'s' if bedrooms != 1 else ''}; your brief requested {entered_bathrooms}.")
        if apply_bathroom_template and applied_bathrooms > entered_bathrooms:
            notes.insert(0, f"Applied your selected planning template: sanitary spaces increased from {entered_bathrooms} to {applied_bathrooms}.")

        prepared["planning_guidance"] = {
            "profile": "Ghana-focused residential planning template",
            "applied_bathroom_template": bool(apply_bathroom_template),
            "entered_bathrooms": entered_bathrooms,
            "suggested_bathrooms": suggested_bathrooms,
            "notes": notes,
            "disclaimer": "Planning suggestions only. They are not a Ghana Building Code determination, professional design, or permit approval.",
        }
        return prepared

    @staticmethod
    def _suggested_sanitary_spaces(bedrooms: int) -> int:
        """Return a configurable design-template suggestion, not a legal requirement."""
        if bedrooms <= 1:
            return 1
        return max(2, math.ceil(bedrooms / 2) + 1)

    def build_svg(self, spec: dict[str, Any]) -> str:
        """Public compatibility method used by the test suite and API."""
        return self._build_svg(spec)

    def _build_svg(self, spec: dict[str, Any]) -> str:
        """Build a clean SVG plan, keeping all user text XML-safe."""
        rooms = self._layout_rooms(spec)
        floors = self._positive_int(spec.get("floors"), default=1, minimum=1, maximum=50)
        building_type = str(spec.get("building_type") or "Building").replace("_", " ").title()
        location = str(spec.get("location") or "Ghana")

        total_width = max((room["x"] + room["w"] for room in rooms), default=10.0)
        total_height = max((room["y"] + room["h"] for room in rooms), default=8.0)
        canvas_width, canvas_height = 980, 700
        margin_x, margin_top, margin_bottom = 100, 130, 100
        available_width = canvas_width - margin_x * 2
        available_height = canvas_height - margin_top - margin_bottom
        scale = min(available_width / total_width, available_height / total_height, 55.0)
        offset_x = (canvas_width - total_width * scale) / 2
        offset_y = margin_top + (available_height - total_height * scale) / 2

        # Build SVG markup directly from a fixed element vocabulary. User-derived
        # content is escaped before insertion; this generator never parses XML.
        # Avoiding XML parser APIs also prevents XML entity-expansion attack paths.
        parts: list[str] = []

        def element(name: str, attrs: dict[str, str] | None = None, text: str | None = None) -> None:
            attributes = "".join(
                f' {key}="{html.escape(str(value), quote=True)}"'
                for key, value in (attrs or {}).items()
            )
            if text is None:
                parts.append(f"<{name}{attributes}/>")
            else:
                parts.append(f"<{name}{attributes}>{html.escape(str(text), quote=False)}</{name}>")

        parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" '
            f'viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-label="Schematic concept floor plan">'
        )
        parts.append("""<style>
            .room { stroke: #53645f; stroke-width: 2; vector-effect: non-scaling-stroke; }
            .wall { stroke: #253c35; stroke-width: 4; fill: none; vector-effect: non-scaling-stroke; }
            .label { font-family: Arial, Helvetica, sans-serif; font-size: 14px; font-weight: 700; fill: #24332e; }
            .dimension { font-family: Arial, Helvetica, sans-serif; font-size: 11px; fill: #60716b; }
            .title { font-family: Arial, Helvetica, sans-serif; font-size: 22px; font-weight: 700; fill: #24332e; }
            .subtitle { font-family: Arial, Helvetica, sans-serif; font-size: 12px; fill: #687974; }
        </style>""")
        element("rect", {"x": "0", "y": "0", "width": str(canvas_width), "height": str(canvas_height), "fill": "#fbfcfa"})
        element("text", {"x": str(canvas_width // 2), "y": "42", "text-anchor": "middle", "class": "title"}, f"{building_type} concept plan")
        element(
            "text",
            {"x": str(canvas_width // 2), "y": "66", "text-anchor": "middle", "class": "subtitle"},
            f"{floors} floor{'s' if floors != 1 else ''} · {location} · schematic only",
        )
        guidance = spec.get("planning_guidance") if isinstance(spec.get("planning_guidance"), dict) else {}
        if guidance.get("profile"):
            element(
                "text",
                {"x": str(canvas_width // 2), "y": "88", "text-anchor": "middle", "class": "subtitle"},
                "Ghana-focused planning template · not a code or permit approval",
            )

        for room in rooms:
            x = room["x"] * scale + offset_x
            y = room["y"] * scale + offset_y
            width = room["w"] * scale
            height = room["h"] * scale
            element(
                "rect",
                {
                    "x": f"{x:.2f}", "y": f"{y:.2f}", "width": f"{width:.2f}", "height": f"{height:.2f}",
                    "rx": "2", "class": "room", "fill": self._room_color(room["type"]),
                },
            )
            text_x = x + width / 2
            text_y = y + height / 2
            element("text", {"x": f"{text_x:.2f}", "y": f"{text_y - 3:.2f}", "text-anchor": "middle", "class": "label"}, room["label"])
            if width >= 90 and height >= 58:
                element(
                    "text",
                    {"x": f"{text_x:.2f}", "y": f"{text_y + 16:.2f}", "text-anchor": "middle", "class": "dimension"},
                    f"{room['w']:.1f} m × {room['h']:.1f} m",
                )

        element(
            "rect",
            {"x": f"{offset_x:.2f}", "y": f"{offset_y:.2f}", "width": f"{total_width * scale:.2f}", "height": f"{total_height * scale:.2f}", "class": "wall"},
        )
        element(
            "text",
            {"x": f"{canvas_width / 2:.2f}", "y": f"{offset_y - 24:.2f}", "text-anchor": "middle", "class": "dimension"},
            f"Approx. overall width: {total_width:.1f} m",
        )
        element(
            "text",
            {"x": f"{canvas_width / 2:.2f}", "y": f"{offset_y + total_height * scale + 24:.2f}", "text-anchor": "middle", "class": "dimension"},
            f"Approx. overall depth: {total_height:.1f} m",
        )
        element("rect", {"x": "22", "y": "645", "width": "936", "height": "34", "rx": "8", "fill": "#f0f4f1"})
        element(
            "text",
            {"x": "38", "y": "667", "class": "dimension"},
            "Concept layout only — not for permits, construction, structural design, or setting out.",
        )
        parts.append("</svg>")
        return "\n".join(parts)

    def _layout_rooms(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Choose the residential planning template or a neutral room grid."""
        building_type = str(spec.get("building_type") or "residential").strip().lower()
        if building_type == "residential":
            return self._layout_ghana_residential_rooms(spec)

        bedrooms = self._positive_int(spec.get("bedrooms"), default=2, minimum=0, maximum=40)
        bathrooms = self._positive_int(spec.get("bathrooms"), default=1, minimum=0, maximum=40)
        minimum_rooms = bedrooms + bathrooms + 2
        total = max(
            minimum_rooms,
            self._positive_int(spec.get("rooms_total"), default=minimum_rooms, minimum=2, maximum=60),
        )
        room_types = ["living", "kitchen"]
        room_types.extend(f"bedroom_{number + 1}" for number in range(bedrooms))
        room_types.extend(f"bathroom_{number + 1}" for number in range(bathrooms))
        extras = ["dining", "storage", "utility", "laundry"]
        while len(room_types) < total:
            room_types.append(extras[(len(room_types) - 2) % len(extras)])
        return self._room_records_to_grid(self._records_for_types(room_types), max_columns=3)

    def _layout_ghana_residential_rooms(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Make a transparent, Ghana-focused residential concept layout.

        The sequence represents common planning conventions rather than drawing
        actual doors, accessibility clearances, services, walls, or approvals.
        """
        bedrooms = self._positive_int(spec.get("bedrooms"), default=2, minimum=0, maximum=40)
        bathrooms = self._positive_int(spec.get("bathrooms"), default=1, minimum=0, maximum=40)
        room_types = ["veranda_front", "living", "dining", "kitchen", "store", "corridor"]
        room_types.extend(f"bedroom_{number + 1}" for number in range(bedrooms))
        if bathrooms > 0 and bedrooms > 0:
            room_types.append("ensuite_1")
        remaining_sanitary_spaces = max(0, bathrooms - (1 if bathrooms > 0 and bedrooms > 0 else 0))
        guidance = spec.get("planning_guidance") if isinstance(spec.get("planning_guidance"), dict) else {}
        has_template_visitor_wc = bool(guidance.get("applied_bathroom_template")) and bathrooms >= 3 and remaining_sanitary_spaces > 0
        common_spaces = remaining_sanitary_spaces - (1 if has_template_visitor_wc else 0)
        room_types.extend(f"bathroom_common_{number + 1}" for number in range(common_spaces))
        if has_template_visitor_wc:
            room_types.append("wc_visitor")
        if bedrooms >= 3:
            room_types.append("veranda_back")
        return self._room_records_to_grid(self._records_for_types(room_types), max_columns=3)

    @staticmethod
    def _records_for_types(room_types: list[str]) -> list[dict[str, Any]]:
        labels = {
            "living": "Living room", "kitchen": "Kitchen", "dining": "Dining area", "store": "Store / pantry",
            "utility": "Utility", "laundry": "Laundry", "corridor": "Private corridor", "veranda_front": "Front veranda",
            "veranda_back": "Back veranda", "wc_visitor": "Visitor WC",
        }
        dimensions = {
            "living": (6.0, 5.0), "kitchen": (3.5, 3.0), "dining": (4.5, 3.5), "store": (2.2, 2.0),
            "utility": (3.5, 3.5), "laundry": (3.0, 3.0), "corridor": (5.5, 1.5), "veranda": (5.5, 2.0),
            "bedroom": (4.0, 3.5), "ensuite": (2.2, 2.0), "bathroom": (2.5, 2.2), "wc": (1.6, 1.5),
        }
        records: list[dict[str, Any]] = []
        for room_type in room_types:
            prefix = room_type.split("_", 1)[0]
            width, height = dimensions.get(prefix, (3.0, 3.0))
            label = labels.get(room_type, labels.get(prefix, prefix.title()))
            if room_type == "bedroom_1":
                label, width, height = "Master bedroom", 4.5, 4.0
            elif room_type.startswith("bedroom_"):
                label = f"Bedroom {room_type.rsplit('_', 1)[1]}"
            elif room_type.startswith("ensuite_"):
                label = "Master ensuite"
            elif room_type.startswith("bathroom_common_"):
                label = f"Shared bathroom {room_type.rsplit('_', 1)[1]}"
            records.append({"type": room_type, "label": label, "w": width, "h": height})
        return records

    @staticmethod
    def _room_records_to_grid(records: list[dict[str, Any]], max_columns: int) -> list[dict[str, Any]]:
        if not records:
            return [{"type": "living", "label": "Living room", "w": 6.0, "h": 5.0, "x": 0.0, "y": 0.0}]
        columns = min(max_columns, max(1, len(records)))
        for index, room in enumerate(records):
            room["row"], room["col"] = divmod(index, columns)
        rows = math.ceil(len(records) / columns)
        column_widths = [max((room["w"] for room in records if room["col"] == column), default=1.0) for column in range(columns)]
        row_heights = [max((room["h"] for room in records if room["row"] == row), default=1.0) for row in range(rows)]
        x_positions = [sum(column_widths[:column]) for column in range(columns)]
        y_positions = [sum(row_heights[:row]) for row in range(rows)]
        for room in records:
            room["x"] = x_positions[room["col"]] + (column_widths[room["col"]] - room["w"]) / 2
            room["y"] = y_positions[room["row"]] + (row_heights[room["row"]] - room["h"]) / 2
            room.pop("row")
            room.pop("col")
        return records

    @staticmethod
    def _positive_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            return min(max(int(value), minimum), maximum)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _room_color(room_type: str) -> str:
        palette = {
            "living": "#d4edda", "dining": "#dff0e7", "kitchen": "#fff3cd", "bedroom": "#cce5ff",
            "bathroom": "#f8d7da", "ensuite": "#f8d7da", "wc": "#f8d7da", "store": "#e2e3e5",
            "storage": "#e2e3e5", "utility": "#e2e3e5", "laundry": "#e2e3e5", "corridor": "#eef0ee",
            "veranda": "#e0f2e5",
        }
        return palette.get(room_type.split("_", 1)[0], "#e2e3e5")

    @staticmethod
    def _fallback_svg() -> str:
        return """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"400\" height=\"300\" viewBox=\"0 0 400 300\" role=\"img\" aria-label=\"Plan unavailable\">\n<rect x=\"0\" y=\"0\" width=\"400\" height=\"300\" fill=\"#fbfcfa\"/>\n<rect x=\"50\" y=\"50\" width=\"300\" height=\"200\" rx=\"4\" fill=\"#fff3cd\" stroke=\"#53645f\" stroke-width=\"2\"/>\n<text x=\"200\" y=\"145\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-size=\"16\" fill=\"#24332e\">Plan temporarily unavailable</text>\n<text x=\"200\" y=\"170\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-size=\"12\" fill=\"#60716b\">Please regenerate the project concept.</text>\n</svg>"""
