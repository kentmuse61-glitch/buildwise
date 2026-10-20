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
        """Build a presentation-quality concept plan with clear visual hierarchy.

        The output is a diagrammatic design-study sheet: it communicates spatial
        organisation, approximate room sizes, demarcations, openings and overall
        dimensions. It deliberately does not claim wall build-ups, structural
        members, accessibility clearances, services coordination or setting-out
        accuracy.
        """
        rooms = self._layout_rooms(spec)
        floors = self._positive_int(spec.get("floors"), default=1, minimum=1, maximum=50)
        building_type = str(spec.get("building_type") or "Building").replace("_", " ").title()
        location = str(spec.get("location") or "Ghana")
        design = spec.get("design_studio") if isinstance(spec.get("design_studio"), dict) else {}
        active_floor = self._positive_int(design.get("active_floor"), default=1, minimum=1, maximum=floors)

        min_x = min((float(room["x"]) for room in rooms), default=0.0)
        min_y = min((float(room["y"]) for room in rooms), default=0.0)
        max_x = max((float(room["x"]) + float(room["w"]) for room in rooms), default=10.0)
        max_y = max((float(room["y"]) + float(room["h"]) for room in rooms), default=8.0)
        total_width = max(1.0, max_x - min_x)
        total_height = max(1.0, max_y - min_y)
        canvas_width, canvas_height = 1120, 820
        margin_left, margin_right, margin_top, margin_bottom = 160, 160, 170, 150
        available_width = canvas_width - margin_left - margin_right
        available_height = canvas_height - margin_top - margin_bottom
        scale = min(available_width / total_width, available_height / total_height, 68.0)
        offset_x = margin_left + (available_width - total_width * scale) / 2
        offset_y = margin_top + (available_height - total_height * scale) / 2

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

        def px_x(value: float) -> float:
            return offset_x + (value - min_x) * scale

        def px_y(value: float) -> float:
            return offset_y + (value - min_y) * scale

        parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" '
            f'viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-label="Modern schematic concept floor plan">'
        )
        parts.append("""<defs>
          <pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse"><path d="M 34 0 L 0 0 0 34" fill="none" stroke="#dde8e1" stroke-width="1"/></pattern>
          <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#61746a"/></marker>
          <filter id="shadow" x="-15%" y="-15%" width="130%" height="130%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#183a2b" flood-opacity=".12"/></filter>
        </defs><style>
          .sheet-title { font-family: Arial,Helvetica,sans-serif; font-size: 27px; font-weight: 800; letter-spacing: .04em; fill: #17362b; }
          .sheet-subtitle { font-family: Arial,Helvetica,sans-serif; font-size: 12px; letter-spacing: .08em; fill: #668076; }
          .room { stroke: #315346; stroke-width: 1.6; vector-effect: non-scaling-stroke; }
          .inner-wall { stroke: #29483b; stroke-width: 3.2; vector-effect: non-scaling-stroke; }
          .outer-wall { stroke: #183c30; stroke-width: 10; fill: none; stroke-linejoin: round; vector-effect: non-scaling-stroke; }
          .room-label { font-family: Arial,Helvetica,sans-serif; font-size: 13px; font-weight: 800; fill: #203b31; }
          .room-area { font-family: Arial,Helvetica,sans-serif; font-size: 10px; fill: #597268; }
          .dimension { font-family: Arial,Helvetica,sans-serif; font-size: 10px; fill: #566e63; letter-spacing: .03em; }
          .note { font-family: Arial,Helvetica,sans-serif; font-size: 10px; fill: #667b71; }
          .window { stroke: #57a7bf; stroke-width: 7; stroke-linecap: square; vector-effect: non-scaling-stroke; }
          .door { stroke: #8a6043; stroke-width: 2; fill: none; vector-effect: non-scaling-stroke; }
          .furniture { stroke: #83988d; stroke-width: 1; fill: #ffffff; fill-opacity: .65; }
        </style>""")
        element("rect", {"x": "0", "y": "0", "width": str(canvas_width), "height": str(canvas_height), "fill": "#f8fbf8"})
        element("rect", {"x": "26", "y": "26", "width": str(canvas_width - 52), "height": str(canvas_height - 52), "rx": "18", "fill": "#ffffff", "stroke": "#dce9e1"})
        element("rect", {"x": "56", "y": "122", "width": str(canvas_width - 112), "height": str(canvas_height - 212), "rx": "12", "fill": "url(#grid)", "stroke": "#e3ede6"})
        element("text", {"x": "58", "y": "70", "class": "sheet-title"}, f"{building_type} · CONCEPT PLAN")
        template_note = " · Ghana-focused planning template · not a code or permit approval" if spec.get("planning_guidance") else ""
        element("text", {"x": "58", "y": "94", "class": "sheet-subtitle"}, f"{location}  /  LEVEL {active_floor} OF {floors}  /  DESIGN STUDY{template_note}")
        element("text", {"x": str(canvas_width - 58), "y": "70", "text-anchor": "end", "class": "sheet-subtitle"}, "BUILDWISE GH · REVISION 01")
        element("text", {"x": str(canvas_width - 58), "y": "94", "text-anchor": "end", "class": "note"}, "DIMENSIONS ARE CONCEPTUAL")

        # 1 m guide grid aligned to the concept envelope.
        for metre in range(0, min(41, math.ceil(total_width) + 1)):
            x = px_x(min_x + metre)
            element("line", {"x1": f"{x:.2f}", "y1": f"{offset_y:.2f}", "x2": f"{x:.2f}", "y2": f"{offset_y + total_height * scale:.2f}", "stroke": "#dce9e1", "stroke-width": "0.55", "stroke-dasharray": "2 5"})
        for metre in range(0, min(41, math.ceil(total_height) + 1)):
            y = px_y(min_y + metre)
            element("line", {"x1": f"{offset_x:.2f}", "y1": f"{y:.2f}", "x2": f"{offset_x + total_width * scale:.2f}", "y2": f"{y:.2f}", "stroke": "#dce9e1", "stroke-width": "0.55", "stroke-dasharray": "2 5"})

        room_pixels: list[dict[str, Any]] = []
        for room_index, room in enumerate(rooms, start=1):
            x = px_x(float(room["x"]))
            y = px_y(float(room["y"]))
            width = float(room["w"]) * scale
            height = float(room["h"]) * scale
            room_pixels.append({"room": room, "x": x, "y": y, "width": width, "height": height})
            element("rect", {"x": f"{x:.2f}", "y": f"{y:.2f}", "width": f"{width:.2f}", "height": f"{height:.2f}", "rx": "2", "class": "room", "fill": self._room_color(room["type"]), "filter": "url(#shadow)"})
            # Interior demarcation line reinforces room boundaries when colours are similar.
            element("rect", {"x": f"{x + 2:.2f}", "y": f"{y + 2:.2f}", "width": f"{max(width - 4, 1):.2f}", "height": f"{max(height - 4, 1):.2f}", "rx": "1", "fill": "none", "class": "inner-wall"})
            label_x, label_y = x + width / 2, y + height / 2
            area = float(room["w"]) * float(room["h"])
            element("text", {"x": f"{label_x:.2f}", "y": f"{label_y - 7:.2f}", "text-anchor": "middle", "class": "room-label"}, room["label"])
            element("text", {"x": f"{label_x:.2f}", "y": f"{label_y + 10:.2f}", "text-anchor": "middle", "class": "room-area"}, f"R{room_index:02d} · {area:.1f} m² · {room['w']:.1f} m × {room['h']:.1f} m")
            self._append_concept_furniture(element, str(room["type"]), x, y, width, height)
            # Symbolic opening only: placement is a visual cue, not a door schedule.
            if width > 90 and height > 65:
                door_x = x + width * 0.18
                door_y = y + height - 3
                radius = min(25.0, width * 0.16, height * 0.24)
                element("path", {"d": f"M {door_x:.2f} {door_y:.2f} L {door_x + radius:.2f} {door_y:.2f} M {door_x:.2f} {door_y:.2f} A {radius:.2f} {radius:.2f} 0 0 1 {door_x + radius:.2f} {door_y - radius:.2f}", "class": "door"})

        # Overall envelope and schematic glazing along exterior-facing zones.
        outer_x, outer_y = offset_x, offset_y
        outer_w, outer_h = total_width * scale, total_height * scale
        element("rect", {"x": f"{outer_x:.2f}", "y": f"{outer_y:.2f}", "width": f"{outer_w:.2f}", "height": f"{outer_h:.2f}", "rx": "3", "class": "outer-wall"})
        for item in room_pixels:
            x, y, width, height = item["x"], item["y"], item["width"], item["height"]
            if abs(y - outer_y) < 2:
                element("line", {"x1": f"{x + width * .24:.2f}", "y1": f"{outer_y:.2f}", "x2": f"{x + width * .76:.2f}", "y2": f"{outer_y:.2f}", "class": "window"})
            if abs((y + height) - (outer_y + outer_h)) < 2:
                element("line", {"x1": f"{x + width * .24:.2f}", "y1": f"{outer_y + outer_h:.2f}", "x2": f"{x + width * .76:.2f}", "y2": f"{outer_y + outer_h:.2f}", "class": "window"})
            if abs(x - outer_x) < 2:
                element("line", {"x1": f"{outer_x:.2f}", "y1": f"{y + height * .25:.2f}", "x2": f"{outer_x:.2f}", "y2": f"{y + height * .75:.2f}", "class": "window"})
            if abs((x + width) - (outer_x + outer_w)) < 2:
                element("line", {"x1": f"{outer_x + outer_w:.2f}", "y1": f"{y + height * .25:.2f}", "x2": f"{outer_x + outer_w:.2f}", "y2": f"{y + height * .75:.2f}", "class": "window"})

        # Overall dimensions with extension lines and arrowheads.
        dim_y = outer_y - 52
        for x in (outer_x, outer_x + outer_w):
            element("line", {"x1": f"{x:.2f}", "y1": f"{outer_y - 8:.2f}", "x2": f"{x:.2f}", "y2": f"{dim_y + 8:.2f}", "stroke": "#80948a", "stroke-width": "1"})
        element("line", {"x1": f"{outer_x:.2f}", "y1": f"{dim_y:.2f}", "x2": f"{outer_x + outer_w:.2f}", "y2": f"{dim_y:.2f}", "stroke": "#61746a", "stroke-width": "1.2", "marker-start": "url(#arrow)", "marker-end": "url(#arrow)"})
        element("text", {"x": f"{outer_x + outer_w / 2:.2f}", "y": f"{dim_y - 9:.2f}", "text-anchor": "middle", "class": "dimension"}, f"OVERALL WIDTH  {total_width:.2f} m")
        dim_x = outer_x - 54
        for y in (outer_y, outer_y + outer_h):
            element("line", {"x1": f"{outer_x - 8:.2f}", "y1": f"{y:.2f}", "x2": f"{dim_x + 8:.2f}", "y2": f"{y:.2f}", "stroke": "#80948a", "stroke-width": "1"})
        element("line", {"x1": f"{dim_x:.2f}", "y1": f"{outer_y:.2f}", "x2": f"{dim_x:.2f}", "y2": f"{outer_y + outer_h:.2f}", "stroke": "#61746a", "stroke-width": "1.2", "marker-start": "url(#arrow)", "marker-end": "url(#arrow)"})
        element("text", {"x": f"{dim_x - 11:.2f}", "y": f"{outer_y + outer_h / 2:.2f}", "text-anchor": "middle", "transform": f"rotate(-90 {dim_x - 11:.2f} {outer_y + outer_h / 2:.2f})", "class": "dimension"}, f"OVERALL DEPTH  {total_height:.2f} m")

        # Sheet furniture: north arrow, graphic scale and legend.
        north_x, north_y = canvas_width - 110, 150
        element("path", {"d": f"M {north_x:.2f} {north_y - 31:.2f} L {north_x - 13:.2f} {north_y + 14:.2f} L {north_x:.2f} {north_y + 7:.2f} L {north_x + 13:.2f} {north_y + 14:.2f} Z", "fill": "#1c4b39"})
        element("text", {"x": f"{north_x:.2f}", "y": f"{north_y + 34:.2f}", "text-anchor": "middle", "class": "dimension"}, "NORTH")
        scale_metres = min(5.0, max(1.0, math.floor(total_width / 2)))
        scale_pixels = scale_metres * scale
        scale_x, scale_y = 70.0, canvas_height - 92.0
        element("rect", {"x": f"{scale_x:.2f}", "y": f"{scale_y:.2f}", "width": f"{scale_pixels / 2:.2f}", "height": "10", "fill": "#1d4033"})
        element("rect", {"x": f"{scale_x + scale_pixels / 2:.2f}", "y": f"{scale_y:.2f}", "width": f"{scale_pixels / 2:.2f}", "height": "10", "fill": "#f5f8f5", "stroke": "#1d4033"})
        element("text", {"x": f"{scale_x:.2f}", "y": f"{scale_y + 26:.2f}", "class": "dimension"}, "0")
        element("text", {"x": f"{scale_x + scale_pixels:.2f}", "y": f"{scale_y + 26:.2f}", "text-anchor": "end", "class": "dimension"}, f"{scale_metres:.0f} m")
        element("text", {"x": "300", "y": str(canvas_height - 87), "class": "note"}, "LEGEND  ·  BLUE = CONCEPT GLAZING   BROWN = SYMBOLIC DOOR   GREY = FURNITURE")
        element("rect", {"x": "56", "y": str(canvas_height - 64), "width": str(canvas_width - 112), "height": "28", "rx": "8", "fill": "#edf4ef"})
        element("text", {"x": "70", "y": str(canvas_height - 46), "class": "note"}, "CONCEPT DESIGN STUDY ONLY — VERIFY ALL DIMENSIONS, WALLS, OPENINGS, SITE CONDITIONS, STRUCTURE AND SERVICES WITH QUALIFIED PROFESSIONALS.")
        parts.append("</svg>")
        return "\n".join(parts)

    @staticmethod
    def _append_concept_furniture(element: Any, room_type: str, x: float, y: float, width: float, height: float) -> None:
        """Draw light schematic furniture cues without presenting a fit-out plan."""
        prefix = room_type.split("_", 1)[0]
        if width < 70 or height < 52:
            return
        if prefix == "living":
            element("rect", {"x": f"{x + width * .30:.2f}", "y": f"{y + height * .68:.2f}", "width": f"{width * .40:.2f}", "height": f"{height * .13:.2f}", "rx": "5", "class": "furniture"})
            element("circle", {"cx": f"{x + width * .50:.2f}", "cy": f"{y + height * .43:.2f}", "r": f"{min(width, height) * .09:.2f}", "class": "furniture"})
        elif prefix == "bedroom":
            element("rect", {"x": f"{x + width * .27:.2f}", "y": f"{y + height * .28:.2f}", "width": f"{width * .46:.2f}", "height": f"{height * .38:.2f}", "rx": "4", "class": "furniture"})
            element("line", {"x1": f"{x + width * .30:.2f}", "y1": f"{y + height * .40:.2f}", "x2": f"{x + width * .70:.2f}", "y2": f"{y + height * .40:.2f}", "class": "furniture"})
        elif prefix in {"kitchen", "dining"}:
            element("rect", {"x": f"{x + width * .22:.2f}", "y": f"{y + height * .30:.2f}", "width": f"{width * .56:.2f}", "height": f"{height * .22:.2f}", "rx": "3", "class": "furniture"})
        elif prefix in {"bathroom", "ensuite", "wc"}:
            element("rect", {"x": f"{x + width * .30:.2f}", "y": f"{y + height * .32:.2f}", "width": f"{width * .36:.2f}", "height": f"{height * .25:.2f}", "rx": "6", "class": "furniture"})

    def layout_rooms(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Return concept room geometry for the active Design Studio floor.

        This public read-only helper lets the workbench and SVG generator share
        the same geometry.  Stored room data is still treated as untrusted and
        normalized again here before it is rendered.
        """
        return self._layout_rooms(spec)

    def _layout_rooms(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        """Choose custom Design Studio geometry or a transparent starter grid."""
        design = spec.get("design_studio") if isinstance(spec.get("design_studio"), dict) else {}
        custom_rooms = design.get("rooms") if isinstance(design.get("rooms"), list) else []
        if custom_rooms:
            active_floor = self._positive_int(
                design.get("active_floor"),
                default=1,
                minimum=1,
                maximum=self._positive_int(spec.get("floors"), default=1, minimum=1, maximum=50),
            )
            normalized = self._normalize_custom_rooms(custom_rooms, active_floor)
            if normalized:
                return normalized

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

    def _normalize_custom_rooms(self, custom_rooms: list[Any], active_floor: int) -> list[dict[str, Any]]:
        """Normalize user-authored room blocks for safe SVG rendering.

        The API validates these fields before persistence.  This extra guard is
        intentional so a malformed legacy record cannot produce unbounded SVG
        dimensions or inject markup through a room label/type.
        """
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(custom_rooms):
            if not isinstance(raw, dict):
                continue
            floor = self._positive_int(raw.get("floor"), default=1, minimum=1, maximum=50)
            if floor != active_floor:
                continue
            try:
                x = min(max(float(raw.get("x")), 0.0), 1_000.0)
                y = min(max(float(raw.get("y")), 0.0), 1_000.0)
                width = min(max(float(raw.get("width")), 0.5), 200.0)
                depth = min(max(float(raw.get("depth")), 0.5), 200.0)
            except (TypeError, ValueError):
                continue
            label = str(raw.get("label") or f"Room {index + 1}").strip()[:60] or f"Room {index + 1}"
            room_type = re.sub(r"[^A-Za-z0-9_-]", "", str(raw.get("room_type") or "room").lower())[:40] or "room"
            normalized.append({
                "id": str(raw.get("id") or f"room-{index + 1}")[:64],
                "type": room_type,
                "label": label,
                "w": width,
                "h": depth,
                "x": x,
                "y": y,
                "floor": floor,
            })
        return normalized

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
