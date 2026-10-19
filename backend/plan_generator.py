"""Generate a clean schematic SVG floor plan (not a construction drawing)."""

from __future__ import annotations

import html
import math
import os
import re
from typing import Any


class PlanGenerator:
    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_plan(self, spec: dict[str, Any], project_id: str | int) -> str:
        filepath = os.path.join(self.output_dir, f"plan_{self._safe_id(project_id)}.svg")
        with open(filepath, "w", encoding="utf-8") as output:
            output.write(self.build_svg(spec))
        return filepath

    @staticmethod
    def _safe_id(value: str | int) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "", str(value))[:48] or "project"

    def build_svg(self, spec: dict[str, Any]) -> str:
        rooms = self._layout_rooms(spec)
        floor_count = max(1, int(spec.get("floors", 1)))
        total_area = max(20.0, float(spec.get("area_sqm", 100.0)))
        footprint_area = total_area / floor_count

        columns = 2 if len(rooms) <= 4 else (3 if len(rooms) <= 9 else 4)
        while len(rooms) % columns:
            rooms.append({"label": "Circulation", "kind": "circulation"})
        rows = math.ceil(len(rooms) / columns)
        # Keep the schematic footprint rectangular while preserving the entered
        # approximate per-floor area.
        footprint_width = math.sqrt(footprint_area * 1.25)
        footprint_depth = footprint_area / footprint_width
        cell_width = footprint_width / columns
        cell_depth = footprint_depth / rows

        canvas_width, canvas_height = 980, 660
        plot_x, plot_y = 135, 112
        plot_width, plot_height = 710, 440
        scale = min(plot_width / footprint_width, plot_height / footprint_depth)
        drawn_width = footprint_width * scale
        drawn_height = footprint_depth * scale
        x0 = plot_x + (plot_width - drawn_width) / 2
        y0 = plot_y + (plot_height - drawn_height) / 2
        safe_type = html.escape(str(spec.get("building_type", "residential")).title())
        safe_location = html.escape(str(spec.get("location", "Ghana")))
        title = f"{safe_type} concept · {safe_location}"

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-label="Schematic concept floor plan">',
            "<defs><style>",
            "text{font-family:Arial,Helvetica,sans-serif;fill:#23312e}",
            ".room{stroke:#52635e;stroke-width:2;vector-effect:non-scaling-stroke}",
            ".room-label{font-size:13px;font-weight:700;text-anchor:middle}",
            ".room-dim{font-size:10px;fill:#66736f;text-anchor:middle}",
            ".measure{font-size:11px;fill:#687873;text-anchor:middle}",
            ".note{font-size:11px;fill:#788680}",
            "</style></defs>",
            f'<rect x="0" y="0" width="{canvas_width}" height="{canvas_height}" fill="#fbfcfa"/>',
            f'<text x="{canvas_width / 2:.1f}" y="38" text-anchor="middle" font-size="21" font-weight="700">{title}</text>',
            f'<text x="{canvas_width / 2:.1f}" y="61" text-anchor="middle" font-size="12" fill="#71807a">Schematic only · Ground-floor layout · {footprint_area:.0f} m² approximate footprint</text>',
        ]

        palette = {
            "living": "#dff0e7",
            "dining": "#e7f2e9",
            "kitchen": "#fff0d2",
            "bedroom": "#e1ecfb",
            "bathroom": "#fbe4e5",
            "circulation": "#eef0ee",
            "other": "#edf1ef",
        }
        for index, room in enumerate(rooms):
            row, col = divmod(index, columns)
            x = x0 + col * cell_width * scale
            y = y0 + row * cell_depth * scale
            w = cell_width * scale
            h = cell_depth * scale
            kind = room["kind"]
            color = palette.get(kind, palette["other"])
            label = html.escape(room["label"])
            parts.append(
                f'<rect class="room" x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="1" fill="{color}"/>'
            )
            if h >= 48 and w >= 85:
                parts.append(f'<text class="room-label" x="{x + w / 2:.2f}" y="{y + h / 2 - 3:.2f}">{label}</text>')
                parts.append(f'<text class="room-dim" x="{x + w / 2:.2f}" y="{y + h / 2 + 15:.2f}">{cell_width:.1f} m × {cell_depth:.1f} m</text>')
            else:
                parts.append(f'<text class="room-label" x="{x + w / 2:.2f}" y="{y + h / 2 + 4:.2f}" font-size="10">{label}</text>')

        # Bold outer perimeter and simple dimension leaders.
        parts.extend([
            f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{drawn_width:.2f}" height="{drawn_height:.2f}" fill="none" stroke="#263b35" stroke-width="4"/>',
            f'<line x1="{x0:.2f}" y1="{y0 - 22:.2f}" x2="{x0 + drawn_width:.2f}" y2="{y0 - 22:.2f}" stroke="#94a19c" stroke-width="1"/>',
            f'<text class="measure" x="{x0 + drawn_width / 2:.2f}" y="{y0 - 29:.2f}">{footprint_width:.1f} m approx.</text>',
            f'<text class="measure" x="{x0 + drawn_width / 2:.2f}" y="{y0 + drawn_height + 24:.2f}">{footprint_depth:.1f} m depth approx.</text>',
            '<rect x="22" y="603" width="936" height="36" rx="9" fill="#f0f4f1"/>',
            '<text class="note" x="38" y="625">Concept layout only — not for permits, construction, structural design, or setting out. Confirm dimensions and code requirements with licensed local professionals.</text>',
            "</svg>",
        ])
        return "\n".join(parts)

    @staticmethod
    def _layout_rooms(spec: dict[str, Any]) -> list[dict[str, str]]:
        bedrooms = min(max(int(spec.get("bedrooms", 2)), 0), 40)
        bathrooms = min(max(int(spec.get("bathrooms", 1)), 0), 40)
        total = min(max(int(spec.get("rooms_total", bedrooms + bathrooms + 2)), 1), 60)

        rooms: list[dict[str, str]] = [
            {"label": "Living", "kind": "living"},
            {"label": "Kitchen", "kind": "kitchen"},
        ]
        rooms.extend({"label": f"Bedroom {i + 1}", "kind": "bedroom"} for i in range(bedrooms))
        rooms.extend({"label": f"Bathroom {i + 1}", "kind": "bathroom"} for i in range(bathrooms))
        extras = [
            {"label": "Dining", "kind": "dining"},
            {"label": "Store", "kind": "other"},
            {"label": "Utility", "kind": "other"},
            {"label": "Study", "kind": "other"},
        ]
        extra_index = 0
        while len(rooms) < max(total, 2):
            rooms.append(extras[extra_index % len(extras)])
            extra_index += 1

        # Required rooms take precedence if the brief's total is smaller than its
        # stated bedroom/bathroom count; otherwise extras fill the remaining slots.
        return rooms
