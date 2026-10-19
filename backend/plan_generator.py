"""Generate resilient, schematic SVG floor plans (not construction drawings)."""

from __future__ import annotations

import html
import logging
import math
import os
import re
from typing import Any
from xml.dom import minidom

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

        doc = minidom.Document()
        svg = doc.createElement("svg")
        svg.setAttribute("xmlns", "http://www.w3.org/2000/svg")
        svg.setAttribute("width", str(canvas_width))
        svg.setAttribute("height", str(canvas_height))
        svg.setAttribute("viewBox", f"0 0 {canvas_width} {canvas_height}")
        svg.setAttribute("role", "img")
        svg.setAttribute("aria-label", "Schematic concept floor plan")
        doc.appendChild(svg)

        def element(name: str, attrs: dict[str, str] | None = None, text: str | None = None):
            node = doc.createElement(name)
            for key, value in (attrs or {}).items():
                node.setAttribute(key, value)
            if text is not None:
                node.appendChild(doc.createTextNode(text))
            svg.appendChild(node)
            return node

        style = doc.createElement("style")
        style.appendChild(doc.createTextNode("""
            .room { stroke: #53645f; stroke-width: 2; vector-effect: non-scaling-stroke; }
            .wall { stroke: #253c35; stroke-width: 4; fill: none; vector-effect: non-scaling-stroke; }
            .label { font-family: Arial, Helvetica, sans-serif; font-size: 14px; font-weight: 700; fill: #24332e; }
            .dimension { font-family: Arial, Helvetica, sans-serif; font-size: 11px; fill: #60716b; }
            .title { font-family: Arial, Helvetica, sans-serif; font-size: 22px; font-weight: 700; fill: #24332e; }
            .subtitle { font-family: Arial, Helvetica, sans-serif; font-size: 12px; fill: #687974; }
        """))
        svg.appendChild(style)
        element("rect", {"x": "0", "y": "0", "width": str(canvas_width), "height": str(canvas_height), "fill": "#fbfcfa"})
        element("text", {"x": str(canvas_width // 2), "y": "42", "text-anchor": "middle", "class": "title"}, f"{building_type} concept plan")
        element(
            "text",
            {"x": str(canvas_width // 2), "y": "66", "text-anchor": "middle", "class": "subtitle"},
            f"{floors} floor{'s' if floors != 1 else ''} · {location} · schematic only",
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
        # Element serialization avoids an XML declaration, preserving the API's
        # existing SVG response contract.
        return svg.toprettyxml(indent="  ")

    def _layout_rooms(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Lay out rooms on a non-overlapping grid with reasonable defaults."""
        bedrooms = self._positive_int(spec.get("bedrooms"), default=2, minimum=0, maximum=40)
        bathrooms = self._positive_int(spec.get("bathrooms"), default=1, minimum=0, maximum=40)
        minimum_rooms = bedrooms + bathrooms + 2
        requested_total = self._positive_int(spec.get("rooms_total"), default=minimum_rooms, minimum=2, maximum=60)
        total = max(minimum_rooms, requested_total)

        room_types = ["living", "kitchen"]
        room_types.extend(f"bedroom_{number + 1}" for number in range(bedrooms))
        room_types.extend(f"bathroom_{number + 1}" for number in range(bathrooms))
        extras = ["dining", "storage", "utility", "laundry"]
        while len(room_types) < total:
            room_types.append(extras[(len(room_types) - 2) % len(extras)])

        labels = {
            "living": "Living", "kitchen": "Kitchen", "dining": "Dining", "storage": "Storage",
            "utility": "Utility", "laundry": "Laundry",
        }
        preferred_sizes = {
            "living": (8.0, 6.0), "kitchen": (5.0, 4.0), "dining": (6.0, 5.0),
            "storage": (3.0, 3.0), "utility": (3.5, 3.5), "laundry": (3.0, 3.0),
        }
        records: list[dict[str, Any]] = []
        columns = min(3, max(1, len(room_types)))
        rows = math.ceil(len(room_types) / columns)
        for index, room_type in enumerate(room_types):
            prefix = room_type.split("_", 1)[0]
            width, height = preferred_sizes.get(prefix, (5.0 if prefix == "bedroom" else 3.2, 4.5 if prefix == "bedroom" else 3.0))
            label = labels.get(prefix, prefix.title())
            if "_" in room_type and prefix in {"bedroom", "bathroom"}:
                label = f"{label} {room_type.rsplit('_', 1)[1]}"
            records.append({"type": room_type, "label": label, "w": width, "h": height, "row": index // columns, "col": index % columns})

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
            "bathroom": "#f8d7da", "storage": "#e2e3e5", "utility": "#e2e3e5", "laundry": "#e2e3e5",
        }
        return palette.get(room_type.split("_", 1)[0], "#e2e3e5")

    @staticmethod
    def _fallback_svg() -> str:
        return """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"400\" height=\"300\" viewBox=\"0 0 400 300\" role=\"img\" aria-label=\"Plan unavailable\">\n<rect x=\"0\" y=\"0\" width=\"400\" height=\"300\" fill=\"#fbfcfa\"/>\n<rect x=\"50\" y=\"50\" width=\"300\" height=\"200\" rx=\"4\" fill=\"#fff3cd\" stroke=\"#53645f\" stroke-width=\"2\"/>\n<text x=\"200\" y=\"145\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-size=\"16\" fill=\"#24332e\">Plan temporarily unavailable</text>\n<text x=\"200\" y=\"170\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-size=\"12\" fill=\"#60716b\">Please regenerate the project concept.</text>\n</svg>"""
